"""Identity/classification regressions evaluated from the shipped CEL settings."""

import itertools
import json
import unittest

import promql_parser as promql
import re2
from test_contract import (
    BY_ID,
    component,
    evaluate,
    mapped,
    record,
    render_topological_monitor,
    walk,
)


class IdentityTests(unittest.TestCase):
    def test_probe_observation_marker_composes_on_native_service_and_instance(self):
        for signal, marker, metric in itertools.product(
            ("TRACES", "METRICS"), (None, "", "http-probe"), ("httpcheck.status", "ollama_api_up")
        ):
            data = record(signal, attributes={"gen_ai.provider.name": "ollama"}, metric=metric)
            data["resource"]["attributes"]["suse.ai.product"] = "ollama"
            if marker is not None:
                data["resource"]["attributes"]["suse.ai.observation.kind"] = marker
            for kind in ("otel service", "otel service instance"):
                results = [r for r in mapped(data) if r["typeName"] == kind]
                eligible = signal == "METRICS" and marker == "http-probe" and metric == "httpcheck.status"
                self.assertEqual(len(results), 2 if eligible else 1)
                self.assertEqual(len({r["identifier"] for r in results}), 1)
                probes = [r for r in results if r["tags"].get("suse.ai.observation.kind") == "http-probe"]
                self.assertEqual(len(probes), int(eligible))
                for probe in probes:
                    self.assertEqual(probe["tags"], {"suse.ai.observation.kind": "http-probe"})

    def test_logical_cluster_labels_preserve_identity_and_signal_parity(self):
        identities = {}
        for cluster in (None, "", "local", "suse-ai"):
            attributes = {
                "gen_ai.agent.name": "planner",
                "gen_ai.request.model": "model",
                "gen_ai.provider.name": "ollama",
            }
            for signal in ("TRACES", "METRICS"):
                data = record(signal, attributes=attributes)
                if cluster is not None:
                    data["resource"]["attributes"]["k8s.cluster.name"] = cluster
                kinds = ("genai model usage", "genai agent") if signal == "TRACES" else ("genai model usage",)
                for kind in kinds:
                    result = component(data, kind)
                    identities.setdefault(kind, set()).add(result["identifier"])
                    if cluster:
                        self.assertEqual(result["tags"]["cluster-name"], cluster)
                    else:
                        self.assertNotIn("cluster-name", result["tags"])
        # Cluster membership is informational, as on the native hosting service.
        self.assertTrue(all(len(values) == 1 for values in identities.values()))

    def test_monitor_endpoint_patterns_match_only_the_literal_endpoint(self):
        query = BY_ID["urn:stackpack:suse-ai:monitor:model-usage-latency"]["arguments"][
            "queries"
        ]["promqlQuery"]
        for address in (None, "", "vllm.ai.svc", "model.+[1].example", 'a"$\\E.b'):
            for port in (None, "", "8000"):
                endpoint = {
                    k: v
                    for k, v in {
                        "server.address": address,
                        "server.port": port,
                    }.items()
                    if v is not None
                }
                data = record(
                    attributes={
                        "gen_ai.provider.name": "openai",
                        "gen_ai.request.model": "llama3",
                        **endpoint,
                    }
                )
                traces = component(data, "genai model usage")
                data["signal"] = "METRICS"
                metrics = component(data, "genai model usage")
                self.assertEqual(traces["identifier"], metrics["identifier"])
                self.assertEqual(traces["tags"], metrics["tags"])
                tree = promql.parse(render_topological_monitor(query, endpoint))
                for node in walk(tree):
                    if not isinstance(node, promql.VectorSelector):
                        continue
                    for matcher in node.matchers.matchers:
                        if matcher.name not in ("server_address", "server_port"):
                            continue
                        # promql-parser preserves string-literal escapes here.
                        pattern = json.loads('"' + matcher.value + '"')
                        value = endpoint.get(matcher.name.replace("_", "."), "")
                        self.assertIsNotNone(re2.fullmatch(pattern, value))
                        for other in (
                            value + "x",
                            "",
                            "vllmXaiXsvc",
                            "modelXX1xexample",
                        ):
                            if other != value:
                                self.assertIsNone(re2.fullmatch(pattern, other))

    def test_legacy_monitor_binding_does_not_fill_an_empty_tag(self):
        with self.assertRaisesRegex(AssertionError, "Unresolved monitor binding"):
            render_topological_monitor(
                'metric{server_address="${tags.server.address}"}', {}
            )

    def test_unclassified_signals_do_not_contribute_default_categories_or_products(
        self,
    ):
        for signal, product in itertools.product(("TRACES", "METRICS"), (None, "")):
            data = record(signal, attributes={"gen_ai.provider.name": "vllm"})
            if product is not None:
                data["resource"]["attributes"]["suse.ai.product"] = product
            for kind in ("otel service", "otel service instance"):
                with self.subTest(signal=signal, product=product, kind=kind):
                    result = component(data, kind)
                    self.assertEqual(result["tags"]["stackpack"], "suse-ai")
                    self.assertNotIn("suse.ai.category", result["tags"])
                    self.assertNotIn("suse.ai.product", result["tags"])

    def test_cross_signal_contributions_are_compatible_in_both_orders(self):
        # The live suite also checks composition in the backend; this test
        # checks the exact contributions without simulating merge precedence.
        traces = record(attributes={"gen_ai.provider.name": "vllm"})
        metrics = record(
            "METRICS",
            resource={**traces["resource"]["attributes"], "suse.ai.product": "vllm"},
            metric="vllm:num_requests_running",
        )
        for signals in ((traces, metrics), (metrics, traces)):
            for kind in ("otel service", "otel service instance"):
                results = [component(data, kind) for data in signals]
                self.assertEqual(results[0]["identifier"], results[1]["identifier"])
                self.assertEqual(
                    {
                        r["tags"]["suse.ai.category"]
                        for r in results
                        if "suse.ai.category" in r["tags"]
                    },
                    {"inference-engine"},
                )
                self.assertEqual(
                    {
                        r["tags"]["suse.ai.product"]
                        for r in results
                        if "suse.ai.product" in r["tags"]
                    },
                    {"vllm"},
                )

    def test_agent_name_matrix_and_hosting_identity(self):
        for canonical, legacy, kind in itertools.product(
            (None, "", "canonical"), (None, "", "legacy"), (None, "agent", "task")
        ):
            attrs = {
                k: v
                for k, v in {
                    "gen_ai.agent.name": canonical,
                    "traceloop.entity.name": legacy,
                    "traceloop.span.kind": kind,
                }.items()
                if v is not None
            }
            data = record(attributes=attrs)
            expected = canonical or (legacy if kind == "agent" else None)
            agents = [c for c in mapped(data) if c["typeName"] == "genai agent"]
            relations = [
                r
                for r in mapped(data, "OtelRelationMapping")
                if r["typeName"] == "is-hosted-on"
            ]
            with self.subTest(canonical=canonical, legacy=legacy, kind=kind):
                self.assertEqual(len(agents), int(bool(expected)))
                self.assertEqual(len(relations), len(agents))
                if expected:
                    self.assertEqual(agents[0]["name"], expected)
                    self.assertEqual(agents[0]["tags"]["gen_ai.agent.name"], expected)
                    self.assertEqual(relations[0]["sourceId"], agents[0]["identifier"])
                    self.assertEqual(
                        relations[0]["targetId"],
                        component(data, "otel service")["identifier"],
                    )

    def test_namespace_and_instance_separation(self):
        for kind in (
            "otel service",
            "otel service instance",
            "genai agent",
            "genai model usage",
        ):
            identifiers = set()
            for namespace, service, instance in itertools.product(
                ("a", "b"), ("one", "two"), ("replica-1", "replica-2")
            ):
                data = record(
                    resource={
                        "service.namespace": namespace,
                        "service.name": service,
                        "service.instance.id": instance,
                    },
                    attributes={
                        "gen_ai.agent.name": "planner",
                        "gen_ai.request.model": "model",
                        "gen_ai.provider.name": "vllm",
                    },
                )
                identifiers.add(component(data, kind)["identifier"])
            self.assertEqual(
                len(identifiers), 8 if kind == "otel service instance" else 4
            )
            for namespace in (None, "", "default"):
                data = record(
                    attributes={
                        "gen_ai.agent.name": "planner",
                        "gen_ai.request.model": "model",
                        "gen_ai.provider.name": "vllm",
                    }
                )
                data["resource"]["attributes"].pop("service.namespace")
                if namespace is not None:
                    data["resource"]["attributes"]["service.namespace"] = namespace
                self.assertEqual(
                    component(data, kind)["tags"]["service.namespace"], "default"
                )

    def test_readable_identifiers_keep_fields_and_hosting_relations_distinct(self):
        # Ordinary colons and slashes remain usable. Complete field separators
        # embedded in values are intentionally outside the naming convention.
        for kind, attribute in (
            ("genai agent", "gen_ai.agent.name"),
            ("genai model usage", "gen_ai.request.model"),
            ("genai served model", "model_name"),
        ):
            identifiers = []
            for namespace, service, name in (
                ("a:b", "c", "d"),
                ("a", "b:c", "d"),
                ("a", "b", "c:d"),
                ("a/b", "c", "d"),
                ("a", "b/c", "d"),
                ("a", "b", "c/d"),
            ):
                data = record(
                    "METRICS" if kind == "genai served model" else "TRACES",
                    resource={
                        "service.namespace": namespace,
                        "service.name": service,
                        **({"suse.ai.product": "vllm"}
                           if kind == "genai served model" else {}),
                    },
                    attributes={attribute: name, "gen_ai.provider.name": "vllm"},
                    metric="vllm:num_requests_running"
                    if kind == "genai served model"
                    else "gen_ai.client.operation.duration",
                )
                identifier = component(data, kind)["identifier"]
                field = {
                    "genai agent": "agent",
                    "genai model usage": "provider/vllm:address/:port/:model",
                    "genai served model": "served-model",
                }[kind]
                self.assertEqual(
                    identifier,
                    f"urn:suse-ai:namespace/{namespace}:service/{service}:{field}/{name}",
                )
                identifiers.append(identifier)
                if kind in ("genai agent", "genai served model"):
                    relations = mapped(data, "OtelRelationMapping")
                    self.assertEqual(len(relations), 1)
                    self.assertEqual(relations[0]["sourceId"], identifier)
                    self.assertEqual(
                        relations[0]["targetId"],
                        component(data, "otel service")["identifier"],
                    )
            self.assertEqual(len(set(identifiers)), len(identifiers))

        # Model mappings read different fields; both must preserve the same
        # fields, including the provider and endpoint dimensions.
        identifiers = set()
        for provider, address, port, model in (
            ("provider:a", "b", "80", "model"),
            ("provider", "a:b", "80", "model"),
            ("provider", "a", "b:80", "model"),
            ("provider", "a", "b", "80:model"),
        ):
            values = {
                "gen_ai.provider.name": provider,
                "server.address": address,
                "server.port": port,
                "gen_ai.request.model": model,
            }
            across_signals = {
                component(record(signal, attributes=values), "genai model usage")[
                    "identifier"
                ]
                for signal in ("TRACES", "METRICS")
            }
            self.assertEqual(len(across_signals), 1)
            self.assertEqual(
                across_signals,
                {"urn:suse-ai:namespace/prod-eu:service/assistant"
                 f":provider/{provider}:address/{address}:port/{port}:model/{model}"},
            )
            identifiers.update(across_signals)
        self.assertEqual(len(identifiers), 4)

    def test_overview_labels_accept_multiple_unknown_and_missing_values(
        self,
    ):
        columns = BY_ID["urn:stackpack:suse-ai:component-presentation:common"][
            "presentation"
        ]["overview"]["columns"]
        expressions = {c["columnId"]: c["projection"]["value"] for c in columns if "value" in c["projection"]}
        category = expressions["suse_ai_category"]
        product = expressions["suse_ai_product"]
        tags = {
            "suse.ai.category": ["application", "inference-engine", "future-role"],
            "suse.ai.product": ["vllm", "ollama"],
        }
        self.assertEqual(
            evaluate(category, {"tags": tags}), "Application, Inference, future-role"
        )
        self.assertEqual(evaluate(product, {"tags": tags}), "vllm, ollama")
        self.assertEqual(evaluate(category, {"tags": {}}), "Application")
        self.assertEqual(evaluate(product, {"tags": {}}), "")
        self.assertEqual(
            evaluate(category, {"tags": {"suse.ai.category": []}}), "Application"
        )
        for clusters, expected in (
            (None, ""), ([], ""), ([""], ""), (["local"], "local"),
            (["local", "", "suse-ai"], "local, suse-ai"),
        ):
            with self.subTest(clusters=clusters):
                tags = {} if clusters is None else {"cluster-name": clusters}
                self.assertEqual(
                    evaluate(expressions["suse_ai_otel_k8s_cluster"], {"tags": tags}),
                    expected,
                )

    def test_ordinary_non_ai_control_stays_outside_ai_topology(self):
        for signal in ("TRACES", "METRICS"):
            for resource in ({}, {"suse.ai.product": "", "suse.ai.component.type": ""}):
                data = record(signal, metric="http.server.request.duration")
                data["resource"]["attributes"].update(resource)
                self.assertEqual(mapped(data), [])

"""Monitor query states and operator remediation contracts."""

import os
import unittest

import promql_parser as promql

from monitor_cases import IDENTITY, MODEL, PREFIX, labels, matrix_cases, point, recipes
from test_contract import BY_ID, NODES, PACK, component, mapped, record, walk
from test_promql import run_promql_cases


class MonitorContractTest(unittest.TestCase):
    def test_agents_inherit_health_while_engines_serve_directly_monitored_models(self):
        monitor = BY_ID[PREFIX + "hosted-component-health"]
        self.assertTrue(monitor["function"].endswith(":derived-state-monitor"))
        self.assertEqual(monitor["arguments"], {"componentTypes": "genai agent"})
        for namespace in ("team-one", "team-two"):
            resource = {"service.name": "runtime", "service.namespace": namespace}
            observations = [
                ("genai agent", record(resource=resource, attributes={"gen_ai.agent.name": "agent"})),
                ("genai served model", record("METRICS", resource={**resource, "suse.ai.product": "vllm"}, metric="vllm:num_requests_running",
                                               attributes={"model_name": "model"})),
                ("genai served model", record("METRICS", resource={**resource, "suse.ai.product": "ollama"}, metric="ollama_model_info",
                                               attributes={"model": "model"})),
            ]
            for kind, data in observations:
                logical = component(data, kind)["identifier"]
                host = component(data, "otel service")["identifier"]
                relations = mapped(data, "OtelRelationMapping")
                source, target, relation = ((logical, host, "is-hosted-on") if kind == "genai agent"
                                             else (host, logical, "serves-model"))
                self.assertEqual([(r["sourceId"], r["targetId"], r["typeName"], r["dependencyType"]) for r in relations],
                                 [(source, target, relation, "HIERARCHICAL")])

    def test_every_monitor_has_three_state_fixtures_and_operator_guidance(self):
        nodes = {n["identifier"].removeprefix(PREFIX): n for n in NODES
                 if n["_type"] == "Monitor" and "threshold" in n["arguments"]}
        self.assertEqual(nodes.keys(), recipes().keys())
        for key, node in nodes.items():
            arguments = node["arguments"]
            self.assertIn("${", arguments["titleTemplate"], key)
            text = (PACK / "includes" / node["remediationHint"]).read_text()
            self.assertEqual([line for line in text.splitlines() if line.startswith("### ")],
                             ["### Check first", "### Likely causes", "### Fix", "### Verify"])
            self.assertIn("{{componentUrnForUrl}}", text)
            self.assertIn("absent", text)
            fail, clear = recipes()[key]["values"]
            threshold = arguments["threshold"]
            comparator = {"GT": lambda value: value > threshold,
                          "GTE": lambda value: value >= threshold,
                          "LT": lambda value: value < threshold}[arguments["comparator"]]
            self.assertTrue(comparator(fail), key)
            self.assertFalse(comparator(clear), key)

    @unittest.skipUnless(os.environ.get("AI_PROMETHEUS_IMAGE"), "Set AI_PROMETHEUS_IMAGE for query evaluation")
    def test_all_monitor_queries_in_failing_recovering_and_no_data_states(self):
        result = run_promql_cases(matrix_cases())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_freshness_observation_and_service_mapping_contract(self):
        monitor = BY_ID[PREFIX + "genai-metric-stream-active"]
        args = monitor["arguments"]
        self.assertEqual((monitor["intervalSeconds"], args["comparator"], args["threshold"],
                          args["failureState"]), (60, "GT", 300, "DEVIATING"))
        mapping = BY_ID["urn:stackpack:suse-ai:otel-component-mapping:services-metrics"]
        self.assertEqual(mapping["expireAfter"], 900_000)
        urn = args["urnTemplate"].replace("${service_namespace}", "ai").replace("${service_name}", "ui")
        for cluster in ("east", "west"):
            resource = {"service.namespace": "ai", "service.name": "ui", "k8s.cluster.name": cluster}
            for metric in ("gen_ai.client.operation.duration", "gen_ai.client.token.usage"):
                with self.subTest(metric=metric, cluster=cluster):
                    service = component(record("METRICS", resource=resource, metric=metric), "otel service")
                    self.assertEqual(service["identifier"], urn)
        # More than one source can maintain this service. Only duration enrolls its freshness check.
        query = promql.parse(args["metric"]["query"])
        self.assertEqual({s.name for s in walk(query) if isinstance(s, promql.VectorSelector)},
                         {"gen_ai_client_operation_duration_seconds_count"})

    @unittest.skipUnless(os.environ.get("AI_PROMETHEUS_IMAGE"), "Set AI_PROMETHEUS_IMAGE for query evaluation")
    def test_observed_duration_lifecycle(self):
        duration = "gen_ai_client_operation_duration_seconds_count"
        tokens = "gen_ai_client_token_usage_tokens_count"
        producer = {**MODEL, "gen_ai_provider_name": "ollama",
                    "otel_scope_name": "suse.ai.open_webui.ollama",
                    "service_instance_id": "pod-1", "k8s_cluster_name": "cluster-a"}

        def row(metric, values="1+0x30", **tags):
            series = point(metric, 1, **{**producer, **tags})
            series["values"] = values
            return series

        def age(when, seconds=None, identity=IDENTITY):
            return {"monitor": "genai-metric-stream-active", "eval_time": when,
                    "samples": [] if seconds is None else [{"labels": labels(identity), "value": seconds}]}

        def errors(value, when="20m"):
            return {"monitor": "model-usage-errors", "monitor_tags": {"gen_ai.provider.name": "ollama"},
                    "eval_time": when, "samples": [] if value is None else [
                        {"labels": labels({**IDENTITY, "gen_ai_request_model": MODEL["gen_ai_request_model"]}),
                         "value": value}]}

        cases = [
            {"name": "Token-only, trace, reachability, excluded and unidentified callers",
             "series": [row(tokens), row("gen_ai_client_token_usage_count", gen_ai_token_type="output"),
                        point("up", 1),
                        point("otel_span_calls_total", 1), row(duration, suse_ai_managed="false"),
                        row(duration, service_namespace=""), row(duration, service_name="")],
             "checks": [age("0m"), age("10m"), age("25m")]},
            {"name": "Both streams stop after an off-grid duration sample; lookback cannot renew it",
             "interval": "1s",
             "series": [row(duration, "_x7 0"), row(tokens, "_x7 3 stale")],
             "checks": [age("6s"), age("7s", 0), age("306s999ms", 299.999),
                        age("307s", 300), age("307s1ms", 300.001), age("906s999ms", 899.999),
                        age("907s"), age("907s1ms")]},
            {"name": "Sample and stale marker between timestamp steps still enroll and expire",
             "interval": "1s", "series": [row(duration, "_x7 0 stale")],
             "checks": [age("6s"), age("7s", 0), age("8s", 15),
                        age("307s", 300), age("307s1ms", 307.001), age("906s999ms", 900), age("907s")]},
            {"name": "Both streams marked stale; counter restarts before and after expiry",
             "series": [row(duration, "7 stale _x5 0 stale _x14 0"), row(tokens, "3 stale")],
             "checks": [age("6m", 360), age("7m", 0), age("21m59s", 899),
                        age("22m"), age("23m", 0)]},
            {"name": "Continuous tokens cannot extend a previously observed duration",
             "series": [row(tokens), row(duration, "9+0x2 stale _x20 9")],
             "checks": [age("7m", 300), age("8m", 360), age("16m59s", 899),
                        age("17m"), age("23m"), age("24m", 0)]},
            {"name": "Tokens continue for the silent target while its sibling still exports duration",
             "series": [row(tokens), row(duration, "1 stale"), row(duration, server_address="other")],
             "checks": [age("6m", 360), age("14m59s", 899), age("15m", 0)]},
            {"name": "Fresh idle zero has no model error ratio",
             "series": [row(duration, "0+0x30")], "checks": [age("20m", 0), errors(None)]},
            {"name": "Fresh duration across failed calls and subsequent successful calls",
             "series": [row(duration, "0+60x20 1200+0x10", error_type="TimeoutError"),
                        row(duration, "0+0x20 60+60x9")],
             "checks": [age("20m", 0), errors(1), age("26m", 0), errors(0, "26m")]},
            {"name": "Fresh same-target duration recovers across outcome and scrape labels",
             "series": [row(duration, "1 stale", error_type="TimeoutError"),
                        row(duration, "_x7 0", job="replacement")],
             "checks": [age("6m", 360), age("7m", 0)]},
            {"name": "A missing port is distinct from a known port even without token evidence",
             "series": [row(duration, "1 stale", server_port=""), row(duration)],
             "checks": [age("6m", 360), age("15m", 0)]},
        ]
        for dimension in ("server_address", "server_port", "gen_ai_request_model", "k8s_cluster_name",
                          "service_instance_id", "otel_scope_name", "gen_ai_provider_name"):
            cases.append({"name": "Active sibling differs in " + dimension,
                          "series": [row(duration, "1 stale"), row(duration, **{dimension: "other"})],
                          "checks": [age("6m", 360), age("14m59s", 899), age("15m", 0)]})
        for dimension in ("service_namespace", "service_name"):
            other = {**IDENTITY, dimension: "other"}
            check = age("6m", 360)
            check["samples"] += age("6m", 0, other)["samples"]
            cases.append({"name": "Distinct service attachment by " + dimension,
                          "series": [row(duration, "1 stale"), row(duration, **other)],
                          "checks": [check, age("15m", 0, other)]})
        result = run_promql_cases(cases)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(os.environ.get("AI_PROMETHEUS_IMAGE"), "Set AI_PROMETHEUS_IMAGE for query evaluation")
    def test_application_reliability_covers_background_work_without_inventing_idle_health(self):
        def check(value):
            return {"monitor": "application-span-error-ratio", "samples": [] if value is None else [
                {"labels": labels(IDENTITY), "value": value}]}

        cases = []
        for kind in ("SPAN_KIND_CLIENT", "SPAN_KIND_INTERNAL", "SPAN_KIND_SERVER"):
            cases.append({"name": "Observed " + kind + " failures",
                          "series": [point("otel_span_calls_total", 6, counter=True, span_kind=kind, status_code="STATUS_CODE_ERROR"),
                                     point("otel_span_calls_total", 54, counter=True, span_kind=kind, status_code="STATUS_CODE_OK")],
                          "checks": [check(0.1)]})
        cases.extend([
            {"name": "Observed successful operations without an error series", "series": [
                point("otel_span_calls_total", 60, counter=True, status_code="STATUS_CODE_OK")], "checks": [check(0)]},
            {"name": "Idle counters supply no health assertion", "series": [
                point("otel_span_calls_total", 5, status_code="STATUS_CODE_OK")], "checks": [check(None)]},
            {"name": "Unrelated services and namespaces cannot supply health", "series": [
                point("otel_span_calls_total", 60, counter=True, identity={**IDENTITY, "service_name": "other"}),
                point("otel_span_calls_total", 60, counter=True, identity={**IDENTITY, "service_namespace": "other"})],
             "checks": [check(None)]},
        ])
        result = run_promql_cases(cases)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(os.environ.get("AI_PROMETHEUS_IMAGE"), "Set AI_PROMETHEUS_IMAGE for query evaluation")
    def test_ollama_health_requires_fresh_model_evidence_and_preserves_idle_availability(self):
        identity = {**IDENTITY, "k8s_cluster_name": "cluster-a", "service_instance_id": "pod-a"}

        def row(metric, values="1+0x20", **dimensions):
            result = point(metric, 1, identity={**identity, **dimensions})
            result["values"] = values
            return result

        def check(value, when="5m"):
            return {"monitor": "ollama-model-unavailable", "eval_time": when,
                    "samples": [] if value is None else [{"labels": labels({
                        **IDENTITY, "k8s_cluster_name": "cluster-a", "model": "llama3"}), "value": value}]}

        cases = [
            {"name": "Loaded and unloaded models remain available; API failure, deletion and recovery are distinct",
             "series": [row("ollama_api_up", "1 1 0 1 1"),
                        row("ollama_model_loaded", "1 0 _ _ 0", model="llama3")],
             "checks": [check(value, f"{minute}m") for minute, value in enumerate([1, 1, 0, 0, 1])]},
            {"name": "Stale model samples cannot override a newer successful inventory without that model",
             "series": [row("ollama_api_up"), row("ollama_model_loaded", "1 _x20", model="llama3")],
             "checks": [check(0)]},
            {"name": "Model telemetry without an API observation cannot assert health",
             "series": [row("ollama_model_loaded", model="llama3")], "checks": [check(None)]},
            {"name": "No telemetry is not healthy or unhealthy", "series": [], "checks": [check(None)]},
            {"name": "Both health and failure observations expire after two minutes",
             "series": [row("ollama_api_up", "1 0"), row("ollama_model_loaded", "0", model="llama3")],
             "checks": [check(1, "0m"), check(0, "1m"), check(None, "3m")]},
            {"name": "Newest failed scraper cannot be masked by an older success for the same replica",
             "series": [row("ollama_api_up", "1 1 1 1 _ _", job="old"),
                        row("ollama_model_loaded", "1 1 1 1 _ _", job="old", model="llama3"),
                        row("ollama_api_up", "_ _ _ _ 0 0", job="new")],
             "checks": [check(0)]},
            {"name": "One observed available replica serves the model even if another fails",
             "series": [row("ollama_api_up", "0+0x20"), row("ollama_api_up", service_instance_id="pod-b"),
                        row("ollama_model_loaded", "0+0x20", model="llama3", service_instance_id="pod-b")],
             "checks": [check(1)]},
            {"name": "Another replica reporting another model does not rescue this unavailable model",
             "series": [row("ollama_api_up", "0+0x20"), row("ollama_api_up", service_instance_id="pod-b"),
                        row("ollama_model_loaded", model="other", service_instance_id="pod-b")],
             "checks": [check(0)]},
        ]
        for dimension in ("k8s_cluster_name", "service_namespace", "service_name"):
            cases.append({"name": "Unrelated " + dimension + " cannot supply model health",
                          "series": [row("ollama_api_up", **{dimension: "other"}),
                                     row("ollama_model_loaded", model="llama3", **{dimension: "other"})],
                          "checks": [check(None)]})
        # Clusterless inventory is supported without selecting another cluster.
        data = record("METRICS", resource={"service.name": IDENTITY["service_name"],
                      "service.namespace": IDENTITY["service_namespace"]},
                      metric="ollama_model_info", attributes={"model": "llama3"})
        model_tags = component(data, "genai served model")["tags"]
        cases.append({"name": "A model without a cluster label only observes clusterless telemetry",
                      "series": [row("ollama_api_up", k8s_cluster_name=""),
                                 row("ollama_model_loaded", "0+0x20", model="llama3", k8s_cluster_name=""),
                                 row("ollama_api_up", "0+0x20", k8s_cluster_name="other")],
                      "checks": [{"monitor": "ollama-model-unavailable", "monitor_tags": model_tags,
                                  "samples": [{"labels": labels({**IDENTITY, "model": "llama3"}), "value": 1}]}]})
        result = run_promql_cases(cases)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

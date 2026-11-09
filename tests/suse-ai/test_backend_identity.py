"""Opt-in real backend composition checks; never substitutes local CEL results.

Set AI_LIVE_TESTS=1, AI_LIVE_KUBECONFIG, AI_LIVE_CLUSTER_NAME and
AI_LIVE_EVIDENCE_DIR after installing a fresh test StackPack. Uses the existing
sts context and the identity-fixture Collector/emitter pod in suse-ai-v2-demo.
Leaves telemetry and the deployment available for review.
"""

import json
import os
import subprocess
import time
import unittest
import uuid
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import yaml
from identity_fixture import attrs
from test_contract import BY_ID

STS = ["sts"]
if os.environ.get("STS_CONTEXT"):
    STS += ["--context", os.environ["STS_CONTEXT"]]


@unittest.skipUnless(
    os.environ.get("AI_LIVE_TESTS") == "1", "Opt-in backend composition test"
)
class BackendTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = Path(os.environ["AI_LIVE_EVIDENCE_DIR"])
        cls.evidence.mkdir(parents=True, exist_ok=True)
        cls.kube = [
            "kubectl",
            "--kubeconfig",
            os.environ["AI_LIVE_KUBECONFIG"],
            "-n",
            "suse-ai-v2-demo",
        ]
        pods = json.loads(
            subprocess.check_output(
                cls.kube + ["get", "pods", "-l", "app=identity-fixture", "-o", "json"]
            )
        )
        pod = pods["items"][0]
        cls.pod = pod["metadata"]["name"]
        cls.k8s = {
            "k8s.cluster.name": os.environ["AI_LIVE_CLUSTER_NAME"],
            "k8s.namespace.name": pod["metadata"]["namespace"],
            "k8s.pod.name": cls.pod,
            "k8s.pod.uid": pod["metadata"]["uid"],
            "k8s.node.name": pod["spec"]["nodeName"],
        }
        config_path = (
            Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
            / "stackstate-cli/config.yaml"
        )
        config = yaml.safe_load(config_path.read_text())
        cls.context = next(
            c["context"]
            for c in config["contexts"]
            if c["name"] == (os.environ.get("STS_CONTEXT") or config["current-context"])
        )
        cls.prefix = "identity-" + uuid.uuid4().hex[:8]
        for kind in ("component", "relation"):
            result = subprocess.check_output(
                [*STS, f"otel-{kind}-mapping", "list", "-o", "json"]
            )
            (cls.evidence / f"{kind}-mappings.json").write_bytes(result)
        (cls.evidence / "stackpacks.json").write_bytes(
            subprocess.check_output([*STS, "stackpack", "list", "-o", "json"])
        )

    @classmethod
    def api(cls, path, body=None):
        # Use the same explicitly selected or active CLI context for API requests.
        headers = {"Content-Type": "application/json"}
        if cls.context.get("service-token"):
            headers["X-API-Key"] = cls.context["service-token"]
        else:
            headers["X-API-Token"] = cls.context["api-token"]
        request = Request(
            cls.context["url"].rstrip("/") + path,
            None if body is None else json.dumps(body).encode(),
            headers,
        )
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    @classmethod
    def snapshot(cls, query):
        return cls.api(
            "/api/snapshot",
            {
                "query": query,
                "queryVersion": "0.0.1",
                "metadata": {
                    "groupingEnabled": False,
                    "showIndirectRelations": False,
                    "minGroupSize": 0,
                    "groupedByLayer": False,
                    "groupedByDomain": False,
                    "groupedByRelation": False,
                    "autoGrouping": False,
                    "connectedComponents": False,
                    "neighboringComponents": False,
                    "showFullComponent": True,
                },
            },
        )["viewSnapshotResponse"]

    def capture(self, name, data):
        (self.evidence / (self.prefix + "-" + name + ".json")).write_text(
            json.dumps(data, indent=2)
        )
        return data

    def wait_for(self, predicate, description):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(2)
        self.fail("Timed out waiting for " + description)

    def send(self, signal, resource, attributes=None, value=7):
        now = time.time_ns()
        if signal == "traces":
            cases = (
                attributes
                if isinstance(attributes, list)
                else [attributes or {"gen_ai.provider.name": "vllm"}]
            )
            spans = [
                {
                    "traceId": uuid.uuid4().hex,
                    "spanId": uuid.uuid4().hex[:16],
                    "name": "identity-fixture",
                    "kind": 3,
                    "startTimeUnixNano": str(now - 100000000),
                    "endTimeUnixNano": str(now),
                    "attributes": attrs(values),
                }
                for values in cases
            ]
            payload = {
                "resourceSpans": [
                    {
                        "resource": {"attributes": attrs(resource)},
                        "scopeSpans": [{"spans": spans}],
                    }
                ]
            }
        else:
            record = {
                "name": "vllm:num_requests_waiting",
                "gauge": {
                    "dataPoints": [
                        {
                            "timeUnixNano": str(now),
                            "asInt": str(value),
                            "attributes": attrs({"model_name": "identity-model"}),
                        }
                    ]
                },
            }
            payload = {
                "resourceMetrics": [
                    {
                        "resource": {"attributes": attrs(resource)},
                        "scopeMetrics": [{"metrics": [record]}],
                    }
                ]
            }
        self.send_payload(signal, payload)

    def send_payload(self, signal, payload):
        script = (
            "import urllib.request\nr=urllib.request.Request('http://localhost:4318/v1/"
            + signal
            + "',data="
            + repr(json.dumps(payload).encode())
            + ",headers={'Content-Type':'application/json'})\nprint(urllib.request.urlopen(r,timeout=10).status)"
        )
        result = subprocess.check_output(
            self.kube + ["exec", "-i", self.pod, "-c", "emitter", "--", "python", "-"],
            input=script,
            text=True,
        )
        self.assertEqual(result.strip(), "200")

    @staticmethod
    def tag_values(component, key):
        return {t[len(key) + 1 :] for t in component["tags"] if t.startswith(key + ":")}

    def services(self, name):
        return self.snapshot(f'name = "{name}" and type = "otel service"')["components"]

    def inventory_ids(self, name):
        query = BY_ID[f"urn:stackpack:suse-ai:component-presentation:{name}"][
            "binding"
        ]["query"]
        return {c["id"] for c in self.snapshot(query)["components"]}

    def trace_results(self, service):
        now = int(time.time()) * 1000
        return self.api(
            f"/api/traces/query?start={now - 600000}&end={now}&page=0&pageSize=100",
            {
                "primarySpanFilter": {"attributes": {"service.name": [service]}},
                "secondarySpanFilter": {"attributes": {}},
                "sortBy": [],
            },
        )["traces"]


class BackendIdentityTest(BackendTestCase):
    def test_product_metrics_and_unclassified_traces_in_both_arrival_orders(self):
        for first, second in (("metrics", "traces"), ("traces", "metrics")):
            name = self.prefix + "-" + first
            resource = {
                **self.k8s,
                "service.name": name,
                "service.namespace": "suse-ai-v2-demo",
                "service.instance.id": name + "-replica",
            }
            for index, signal in enumerate((first, second)):
                self.send(
                    signal,
                    {
                        **resource,
                        **({"suse.ai.product": "vllm"} if signal == "metrics" else {}),
                    },
                )

                def composed(name=name, index=index, first=first):
                    values = self.services(name)
                    if len(values) != 1:
                        return False
                    tags = self.tag_values(values[0], "suse.ai.category")
                    want_product = index == 1 or first == "metrics"
                    return (
                        values[0]
                        if tags == ({"inference-engine"} if want_product else set())
                        else False
                    )

                service = self.wait_for(composed, name + " " + signal)
                if index == 0 and first == "traces":
                    self.assertIn(service["id"], self.inventory_ids("applications"))
            # Confirm the second signal actually processed, even when its tag set is empty.
            self.wait_for(
                lambda name=name: any(t["resources"] for t in self.trace_results(name)),
                "ingested trace",
            )
            service = self.capture(name, self.services(name)[0])
            self.assertEqual(service["name"], name)
            self.assertEqual(
                service["identifiers"],
                [f"urn:opentelemetry:namespace/suse-ai-v2-demo:service/{name}"],
            )
            self.assertEqual(
                self.tag_values(service, "suse.ai.category"), {"inference-engine"}
            )
            self.assertEqual(self.tag_values(service, "suse.ai.product"), {"vllm"})
            self.assertIn(service["id"], self.inventory_ids("inference"))
            self.assertNotIn(service["id"], self.inventory_ids("applications"))
            instance = self.wait_for(
                lambda name=name: self.snapshot(
                    f'label = "service.name:{name}" and type = "otel service instance"'
                )["components"],
                "service instance",
            )
            self.assertEqual(len(instance), 1)
            self.assertEqual(
                self.tag_values(instance[0], "suse.ai.category"), {"inference-engine"}
            )
            detail = self.capture(
                name + "-detail", self.api(f"/api/components/{service['id']}")
            )
            self.assertEqual(
                detail["boundTraces"]["filter"]["attributes"]["service.namespace"],
                ["suse-ai-v2-demo"],
            )
            self.assertEqual(
                detail["boundTraces"]["filter"]["attributes"]["service.name"], [name]
            )
            def hosted_model():
                snapshot = self.snapshot(f'label = "service.name:{name}"')
                models = [
                    c for c in snapshot["components"]
                    if c["typeIdentifier"].endswith(":genai served model")
                ]
                if len(models) != 1:
                    return False
                return snapshot if any(
                    r["source"] == service["id"] and r["target"] == models[0]["id"]
                    and r["typeIdentifier"].endswith(":serves-model")
                    for r in snapshot["relations"]
                ) else False

            snapshot = self.capture(
                name + "-served-model",
                self.wait_for(hosted_model, "served model and hosting relation"),
            )
            model = next(
                c for c in snapshot["components"]
                if c["typeIdentifier"].endswith(":genai served model")
            )
            self.assertEqual(model["name"], "identity-model")
            self.assertEqual(
                model["identifiers"],
                [f"urn:suse-ai:namespace/suse-ai-v2-demo:service/{name}"
                 ":served-model/identity-model"],
            )
            self.check_chart_and_monitor(service)

    def check_chart_and_monitor(self, service):
        end = int(time.time() * 1000)
        perspective = self.capture(
            service["name"] + "-charts",
            self.api(
                f"/api/components/{service['id']}/metricPerspectiveData"
                f"?startTime={end - 600000}&endTime={end}"
            ),
        )
        queue = next(
            metric
            for tab in perspective["tabs"]
            for section in tab["sections"]
            for metric in section["metrics"]
            if metric["boundMetricId"].get("metricId") == "suse_ai_vllm_req_waiting"
        )
        expression = queue["boundQueries"][0]["expression"]
        self.assertIn('service_namespace="suse-ai-v2-demo"', expression)
        self.assertIn(f'service_name="{service["name"]}"', expression)

        def chart_values():
            result = self.api(
                "/api/metrics/query_batch",
                {
                    "queries": [
                        {
                            "id": "queue",
                            "query": expression,
                            "_type": "instant",
                            "time": str(int(time.time())),
                        }
                    ]
                },
            )
            return result["results"][0]["data"]["data"]["result"]

        values = self.capture(
            service["name"] + "-chart-values",
            self.wait_for(chart_values, "queue chart value"),
        )
        self.assertEqual(len(values), 1)
        self.assertEqual(float(values[0]["value"][1]), 7)
        monitor = json.loads(
            subprocess.check_output(
                [
                    *STS,
                    "monitor",
                    "status",
                    "--identifier",
                    "urn:stackpack:suse-ai:monitor:vllm-request-queue-buildup",
                    "-o",
                    "json",
                ]
            )
        )["monitor-status"]
        monitor_id = monitor["monitor"]["id"]

        def attached():
            now = int(time.time() * 1000)
            states = self.api(
                f"/api/components/{service['id']}/checkStates"
                f"?startTime={now - 600000}&endTime={now}"
            )["checkStates"]
            return [
                s for s in states if s["identifier"].startswith(f"mn_{monitor_id}_")
            ]

        self.capture(
            service["name"] + "-queue-monitor",
            self.wait_for(attached, "queue monitor attached to the canonical service"),
        )

    def test_explicit_multiple_roles_and_non_ai_control(self):
        name = self.prefix + "-multi"
        resource = {
            **self.k8s,
            "service.name": name,
            "service.namespace": "suse-ai-v2-demo",
        }
        # The stock instance mapping preserves explicit resource labels while
        # the AI mapping contributes its product role: two independent sources.
        self.send(
            "metrics",
            {
                **resource,
                "service.instance.id": name + "-replica",
                "suse.ai.product": "vllm",
                "suse.ai.category": "application",
            },
        )

        def composed():
            values = self.snapshot(
                f'label = "service.name:{name}" and type = "otel service instance"'
            )["components"]
            return (
                values[0]
                if len(values) == 1
                and self.tag_values(values[0], "suse.ai.category")
                == {"application", "inference-engine"}
                else False
            )

        instance = self.capture(
            "multi", self.wait_for(composed, "multiple explicit roles")
        )
        self.capture("multi-detail", self.api(f"/api/components/{instance['id']}"))
        overview = self.capture(
            "multi-overview",
            self.api(
                "/api/overview/"
                + quote(
                    "urn:stackpack:suse-ai:component-presentation:instances", safe=""
                ),
                {},
            ),
        )
        row = next(
            row
            for row in overview["data"]
            if row["componentIdentifier"] in instance["identifiers"]
        )
        category = row["cells"]["suse_ai_category"]
        self.assertEqual(category["_type"], "TextCell")
        self.assertEqual(
            set(category["value"].split(", ")), {"Inference", "Application"}
        )
        name = self.prefix + "-control"
        self.send(
            "traces", {**resource, "service.name": name}, {"http.request.method": "GET"}
        )
        control = self.wait_for(lambda: self.services(name), "ordinary non-AI control")[
            0
        ]
        self.assertNotIn("suse-ai", self.tag_values(control, "stackpack"))
        self.assertNotIn(control["id"], self.inventory_ids("applications"))
        self.capture("control", control)

    def test_namespaces_agent_names_and_hosting_relations(self):
        name = self.prefix + "-agents"
        namespaces = (None, "", self.prefix + "-a", self.prefix + "-b")
        cases = []
        for canonical in (None, "", "canonical"):
            for legacy in (
                None,
                "",
                "legacy-" + ("absent" if canonical is None else "empty"),
            ):
                cases.append(
                    {
                        key: value
                        for key, value in {
                            "gen_ai.agent.name": canonical,
                            "traceloop.entity.name": legacy,
                            "traceloop.span.kind": "agent",
                        }.items()
                        if value is not None
                    }
                )
        # The resource really comes from this Kubernetes pod, but deliberately
        # omits k8s.namespace.name to exercise the generic namespace fallback.
        resource = {
            key: value for key, value in self.k8s.items() if key != "k8s.namespace.name"
        }
        for index, namespace in enumerate(namespaces):
            values = {
                **resource,
                "service.name": name,
                "service.instance.id": f"{name}-{index}",
            }
            if namespace is not None:
                values["service.namespace"] = namespace
            self.send("traces", values, cases)
        query = f'label = "service.name:{name}"'

        def complete():
            snapshot = self.snapshot(query)
            agents = [
                c
                for c in snapshot["components"]
                if c["typeIdentifier"].endswith(":genai agent")
            ]
            relations = [
                r
                for r in snapshot["relations"]
                if r["typeIdentifier"].endswith(":is-hosted-on")
            ]
            return snapshot if len(agents) == 9 and len(relations) == 9 else False

        snapshot = self.capture(
            "agents", self.wait_for(complete, "agent components and hosting relations")
        )
        components = {c["id"]: c for c in snapshot["components"]}
        services = [
            c
            for c in components.values()
            if c["typeIdentifier"].endswith(":otel service")
        ]
        instances = [
            c
            for c in components.values()
            if c["typeIdentifier"].endswith(":otel service instance")
        ]
        self.assertEqual(len(services), 3)
        self.assertEqual(len(instances), 4)
        self.assertEqual(
            {next(iter(self.tag_values(c, "service.namespace"))) for c in services},
            {"default", self.prefix + "-a", self.prefix + "-b"},
        )
        for service in services:
            detail = self.capture(
                f"application-{service['id']}",
                self.api(f"/api/components/{service['id']}"),
            )
            self.assertIn(service["id"], self.inventory_ids("applications"))
            self.assertIn(
                "suse_ai_requests",
                {
                    metric["boundMetricId"].get("metricId")
                    for section in detail["highlightMetrics"]
                    for metric in section["metrics"]
                },
            )
        for relation in snapshot["relations"]:
            if not relation["typeIdentifier"].endswith(":is-hosted-on"):
                continue
            service, agent = (
                components[relation["target"]],
                components[relation["source"]],
            )
            self.assertIn(agent["name"], {"canonical", "legacy-absent", "legacy-empty"})
            namespace = next(iter(self.tag_values(service, "service.namespace")))
            self.assertEqual(self.tag_values(agent, "service.namespace"), {namespace})
            self.assertEqual(self.tag_values(agent, "service.name"), {name})
            self.assertEqual(
                agent["identifiers"],
                [
                    f"urn:suse-ai:namespace/{namespace}:service/{name}"
                    f":agent/{agent['name']}"
                ],
            )
            detail = self.capture(
                f"agent-{agent['id']}", self.api(f"/api/components/{agent['id']}")
            )
            filters = detail["boundTraces"]["filter"]["attributes"]
            self.assertEqual(filters["service.namespace"], [namespace])
            self.assertEqual(filters["gen_ai.agent.name"], [agent["name"]])

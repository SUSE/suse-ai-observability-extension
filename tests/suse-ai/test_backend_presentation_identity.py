"""Opt-in presentation binding regressions against the actual installed backend.

Uses the existing isolated OTLP fixture and sts context, like test_backend_identity.
No local rendering substitutes for the trace filter returned by the platform.
"""

import itertools
import json
import subprocess
import time
import uuid

from identity_fixture import attrs
from test_backend_identity import BackendTestCase


class BackendPresentationIdentityTest(BackendTestCase):
    def test_probe_binding_and_native_monitor_failure_recovery(self):
        name = self.prefix + "-probe"
        resource = {
            **self.k8s, "service.name": name, "service.namespace": self.prefix,
            "service.instance.id": self.k8s["k8s.pod.uid"],
            "suse.ai.component.type": "mcp-server",
            "suse.ai.observation.kind": "http-probe",
        }
        identity = f"urn:opentelemetry:namespace/{self.prefix}:service/{name}"
        for code, value, health in (("200", 1, "CLEAR"), ("", 0, "DEVIATING"), ("201", 1, "CLEAR")):
            self.send_payload("metrics", {"resourceMetrics": [{
                "resource": {"attributes": attrs(resource)},
                "scopeMetrics": [{"metrics": [{"name": "httpcheck.status", "gauge": {"dataPoints": [{
                    "timeUnixNano": str(time.time_ns()), "asInt": str(value),
                    "attributes": attrs({"http.status_class": "2xx", "http.status_code": code,
                                         "http.url": "http://fixture/health"}),
                }]}}]}],
            }]})
            service = self.wait_for(lambda: self.services(name), "probe service")[0]
            self.assertEqual(self.tag_values(service, "suse.ai.observation.kind"), {"http-probe"})
            # A later resource without the marker updates the generic mappings.
            # Probe eligibility must survive in its separate contribution.
            runtime_resource = {k: v for k, v in resource.items() if k != "suse.ai.observation.kind"}
            runtime_resource["service.version"] = "after-probe-" + (code or "failure")
            self.send_payload("metrics", {"resourceMetrics": [{
                "resource": {"attributes": attrs(runtime_resource)},
                "scopeMetrics": [{"metrics": [{"name": "ollama_api_up", "gauge": {"dataPoints": [{
                    "timeUnixNano": str(time.time_ns()), "asInt": "1",
                }]}}]}],
            }]})

            def composed_probe():
                components = self.snapshot(f'label = "service.name:{name}" and type in ("otel service", "otel service instance")')["components"]
                ready = len(components) == 2 and all(
                    runtime_resource["service.version"] in self.tag_values(c, "service.version")
                    and self.tag_values(c, "suse.ai.observation.kind") == {"http-probe"}
                    for c in components
                )
                return components if ready else False

            self.capture("probe-composition-" + health + code, self.wait_for(composed_probe, "probe/runtime composition"))
            end = int(time.time() * 1000)
            charts = self.api(f'/api/components/{service["id"]}/metricPerspectiveData?startTime={end-600000}&endTime={end}')
            metric = next(m for t in charts["tabs"] for s in t["sections"] for m in s["metrics"]
                          if m["boundMetricId"].get("metricId") == "suse-ai-http-probe-success")
            query = metric["boundQueries"][0]["expression"]

            def observed_value():
                response = self.api("/api/metrics/query_batch", {"queries": [{
                    "id": "probe", "query": query, "_type": "instant", "time": str(int(time.time())),
                }]})
                samples = response["results"][0]["data"]["data"]["result"]
                return response if len(samples) == 1 and float(samples[0]["value"][1]) == value else False

            self.capture("probe-chart-" + health + code, self.wait_for(observed_value, "latest probe status"))
            result = json.loads(subprocess.check_output([
                "sts", "monitor", "run", "--identifier", "urn:stackpack:suse-ai:monitor:http-probe-unavailable", "-o", "json",
            ]))
            self.capture("probe-monitor-" + health + code, result)
            state = next(s for s in result["run-result"]["checkStates"]["CheckStates"]["checkStates"]
                         if s["topologyElementIdentifier"] == identity)
            self.assertEqual(state["health"], health)

    def test_model_trace_links_isolate_missing_and_known_endpoints(self):
        endpoints = [
            {},
            {"server.address": "", "server.port": ""},
            {"server.address": "backend.example"},
            {"server.port": 11434},
            {"server.address": "backend.example", "server.port": 11434},
            {"server.address": "other.example", "server.port": 11434},
        ]
        expected = {}
        rows = []
        now = time.time_ns()
        for ns, name in itertools.product(("one", "two"), ("caller", "other")):
            namespace, service = self.prefix + "-" + ns, self.prefix + "-" + name
            spans = []
            for endpoint in endpoints:
                address, port = str(endpoint.get("server.address", "")), str(endpoint.get("server.port", ""))
                identifier = (f"urn:suse-ai:namespace/{namespace}:service/{service}"
                              f":provider/ollama:address/{address}:port/{port}:model/test-model")
                trace_id = uuid.uuid4().hex
                expected.setdefault(identifier, {"traces": set(), "address": address, "port": port})["traces"].add(trace_id)
                spans.append({
                    "traceId": trace_id, "spanId": uuid.uuid4().hex[:16],
                    "name": "presentation-endpoint-test", "kind": 3,
                    "startTimeUnixNano": str(now - 100000000), "endTimeUnixNano": str(now),
                    "attributes": attrs({"gen_ai.provider.name": "ollama", "gen_ai.request.model": "test-model", **endpoint}),
                })
            rows.append({"resource": {"attributes": attrs({
                **self.k8s, "service.namespace": namespace, "service.name": service,
                "service.instance.id": self.k8s["k8s.pod.uid"],
            })}, "scopeSpans": [{"spans": spans}]})
        self.send_payload("traces", {"resourceSpans": rows})

        def components_ready():
            components = self.snapshot(f'type = "genai model usage" and (label = "service.name:{self.prefix}-caller" or '
                                       f'label = "service.name:{self.prefix}-other")')["components"]
            return components if len(components) == len(expected) else False

        components = self.wait_for(components_ready, "isolated endpoint model components")
        for component in components:
            identity = component["identifiers"][0]
            case = expected[identity]
            detail = self.capture(str(component["id"]) + "-detail", self.api(f'/api/components/{component["id"]}'))
            bound = detail["boundTraces"]["filter"]
            self.assertEqual(bound["attributes"]["server.address"], [case["address"]])
            self.assertEqual(bound["attributes"]["server.port"], [case["port"]])
            self.assertEqual(self.tag_values(component, "cluster-name"), {self.k8s["k8s.cluster.name"]})

            def matching_traces():
                end = int(time.time() * 1000)
                result = self.api(f'/api/traces/query?start={end - 600000}&end={end}&page=0&pageSize=100', {
                    "primarySpanFilter": bound, "secondarySpanFilter": {"attributes": {}}, "sortBy": [],
                })
                return result if {r["traceId"] for r in result["traces"]} == case["traces"] else False

            self.capture(str(component["id"]) + "-traces", self.wait_for(matching_traces, "exact endpoint trace matches"))

    def test_ordinary_agent_does_not_bind_demo_only_highlights(self):
        name = self.prefix + "-ordinary-agent"
        self.send("traces", {
            **self.k8s, "service.name": name, "service.namespace": self.prefix,
            "suse.ai.component.type": "agent", "service.instance.id": self.k8s["k8s.pod.uid"],
        }, {"gen_ai.agent.name": "ordinary", "gen_ai.request.model": "test-model", "gen_ai.provider.name": "ollama"})
        service = self.wait_for(lambda: self.services(name), "ordinary agent service")[0]
        self.assertEqual(self.tag_values(service, "suse.ai.category"), {"agent"})
        # Use the actual contribution query and actual composed Highlights.
        from test_contract import BY_ID
        query = BY_ID["urn:stackpack:suse-ai:component-presentation:agent-highlights"]["binding"]["query"]
        self.assertNotIn(service["id"], {c["id"] for c in self.snapshot(query)["components"]})
        detail = self.capture("ordinary-agent-detail", self.api(f'/api/components/{service["id"]}'))
        self.assertNotIn("suse-ai-demo-agent-", str(detail))
        agents = self.wait_for(lambda: self.snapshot(f'type = "genai agent" and label = "service.name:{name}"')["components"], "logical ordinary agent")
        self.assertEqual(self.tag_values(agents[0], "cluster-name"), {self.k8s["k8s.cluster.name"]})

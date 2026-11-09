"""Monitor query states and operator remediation contracts."""

import os
import unittest

from monitor_cases import IDENTITY, PREFIX, labels, matrix_cases, point, recipes
from test_contract import BY_ID, NODES, PACK, component, mapped, record
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

"""Monitor query states and operator remediation contracts."""

import os
import unittest

from monitor_cases import PREFIX, matrix_cases, recipes
from test_contract import BY_ID, NODES, PACK, component, mapped, record
from test_promql import run_promql_cases


class MonitorContractTest(unittest.TestCase):
    def test_hosted_components_depend_on_their_own_service_for_derived_health(self):
        monitor = BY_ID[PREFIX + "hosted-component-health"]
        self.assertTrue(monitor["function"].endswith(":derived-state-monitor"))
        self.assertEqual(monitor["arguments"], {"componentTypes": "genai served model, genai agent"})
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
                self.assertEqual([(r["sourceId"], r["targetId"], r["dependencyType"]) for r in relations],
                                 [(logical, host, "HIERARCHICAL")])

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

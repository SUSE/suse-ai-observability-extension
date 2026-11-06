"""Monitor query states and operator remediation contracts."""

import os
import unittest

from monitor_cases import PREFIX, matrix_cases, recipes
from test_contract import NODES, PACK
from test_promql import run_promql_cases


class MonitorContractTest(unittest.TestCase):
    def test_every_monitor_has_three_state_fixtures_and_operator_guidance(self):
        nodes = {n["identifier"].removeprefix(PREFIX): n for n in NODES if n["_type"] == "Monitor"}
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

"""Evaluate critical migrated queries against actual Prometheus time series."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from test_contract import BY_ID, render, render_topological_monitor


def run_promql_cases(cases):
    """Evaluate shipped queries with the CI-pinned Prometheus engine."""
    tests = []
    for case in cases:
        checks = []
        for check in case["checks"]:
            if "monitor" in check:
                arguments = BY_ID[
                    "urn:stackpack:suse-ai:monitor:" + check["monitor"]
                ]["arguments"]
                expression = (
                    render_topological_monitor(
                        arguments["queries"]["promqlQuery"], check.get("endpoint"), check.get("monitor_tags")
                    )
                    if "queries" in arguments
                    else arguments["metric"]["query"]
                )
            elif "column" in check:
                presentation = BY_ID[
                    "urn:stackpack:suse-ai:component-presentation:" + check["presentation"]
                ]
                column = next(c for c in presentation["presentation"]["overview"]["columns"]
                              if c["columnId"] == check["column"])
                expression = render(column["projection"]["query"], instance=check.get("instance", False))
            elif "summary" in check:
                presentation = BY_ID[
                    "urn:stackpack:suse-ai:component-presentation:" + check["presentation"]
                ]
                summary = next(m for m in presentation["presentation"]["summary"]["metrics"]
                               if m["summaryMetricId"] == check["summary"])
                expression = render(summary["query"], instance=check.get("instance", False))
            else:
                presentation = BY_ID[
                    "urn:stackpack:suse-ai:component-presentation:"
                    + check["presentation"]
                ]
                metric = next(
                    m
                    for m in presentation["metrics"]
                    if m["metricId"] == check["metric"]
                )
                query = next(
                    (q for q in metric["metricQueries"] if q.get("alias") == check.get("query_alias")),
                    metric["metricQueries"][0],
                )
                expression = render(query["expression"], instance=check.get("instance", False))
            checks.append(
                {
                    "expr": expression,
                    "eval_time": check.get("eval_time", "5m"),
                    "exp_samples": check["samples"],
                }
            )
        tests.append(
            {
                "name": case["name"],
                "interval": "1m",
                "input_series": case["series"],
                "promql_expr_test": checks,
            }
        )
    with tempfile.TemporaryDirectory(prefix="suse-ai-promql-") as directory:
        directory = Path(directory)
        directory.chmod(0o755)
        (directory / "tests.yaml").write_text(
            yaml.safe_dump(
                {"evaluation_interval": "1m", "fuzzy_compare": True, "tests": tests}
            )
        )
        result = subprocess.run(
            [
                os.environ.get("AI_CONTAINER_RUNTIME", "docker"),
                "run",
                "--rm",
                "--network",
                "none",
                "--entrypoint",
                "/bin/promtool",
                "--volume",
                str(directory) + ":/test:ro,z",
                os.environ["AI_PROMETHEUS_IMAGE"],
                "test",
                "rules",
                "/test/tests.yaml",
            ],
            capture_output=True,
            text=True,
        )
        return result


@unittest.skipUnless(
    os.environ.get("AI_PROMETHEUS_IMAGE"),
    "Set AI_PROMETHEUS_IMAGE to run query evaluation",
)
class PromQLTest(unittest.TestCase):
    def test_migrated_queries_on_scoped_and_sparse_series(self):
        cases = yaml.safe_load(
            Path(__file__).with_name("promql-cases.yaml").read_text()
        )["cases"]
        result = run_promql_cases(cases)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

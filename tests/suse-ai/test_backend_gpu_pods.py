"""Read-only checks against real GPU and CPU workloads in the installed backend.

Set AI_LIVE_TESTS=1, AI_LIVE_EVIDENCE_DIR and AI_GPU_POD_CASES (a JSON file).
Each case has kubeconfig, cluster, namespace, pod, gpu and gpu_node fields,
plus an optional component_id recorded before the upgrade. Include a GPU pod,
a CPU pod on a GPU node, and a CPU pod on a non-GPU node. GPU cases need DCGM's
default metrics and workload attribution. Uses the existing sts configuration.
"""

import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from urllib.parse import quote

import promql_parser as promql
import yaml

from test_backend_identity import BackendTestCase
from test_contract import BY_ID, walk


@unittest.skipUnless(os.environ.get("AI_GPU_POD_CASES"), "Opt-in real GPU pod fixtures")
class BackendGpuPodsTest(BackendTestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads(Path(os.environ["AI_GPU_POD_CASES"]).read_text())
        cls.evidence = Path(os.environ["AI_LIVE_EVIDENCE_DIR"])
        cls.evidence.mkdir(parents=True, exist_ok=True)
        cls.prefix = "gpu-pods"
        config = yaml.safe_load(
            (Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
             / "stackstate-cli/config.yaml").read_text()
        )
        cls.context = next(
            c["context"] for c in config["contexts"] if c["name"] == (os.environ.get("STS_CONTEXT") or config["current-context"])
        )

    def test_real_workload_eligibility_and_bound_queries(self):
        self.assertTrue({(True, True), (False, True), (False, False)} <= {
            (c["gpu"], c["gpu_node"]) for c in self.cases
        }, "Supply both CPU controls and a real GPU workload")
        presentation = BY_ID["urn:stackpack:suse-ai:component-presentation:gpu-pods"]
        matched = {
            c["id"] for c in self.snapshot(presentation["binding"]["query"])["components"]
        }
        for case in self.cases:
            with self.subTest(cluster=case["cluster"], namespace=case["namespace"], pod=case["pod"]):
                kube = ["kubectl", "--kubeconfig", case["kubeconfig"]]
                pod = json.loads(subprocess.check_output(
                    kube + ["-n", case["namespace"], "get", "pod", case["pod"], "-o", "json"]
                ))
                node_name = pod["spec"]["nodeName"]
                node = json.loads(subprocess.check_output(kube + ["get", "node", node_name, "-o", "json"]))
                gpu_limits = [
                    amount for container in pod["spec"]["containers"]
                    for key, amount in container.get("resources", {}).get("limits", {}).items()
                    if key.startswith("nvidia.com/") and float(amount) > 0
                ]
                self.assertEqual(bool(gpu_limits), case["gpu"])
                self.assertEqual(node["metadata"].get("labels", {}).get("nvidia.com/gpu.present") == "true", case["gpu_node"])
                identity = f"urn:kubernetes:/{case['cluster']}:{case['namespace']}:pod/{case['pod']}"
                full = self.capture(case["cluster"] + "-" + case["pod"] + "-component", self.api(
                    "/api/components/" + quote(identity, safe="")
                ))
                data = full["data"]
                if "component_id" in case:
                    self.assertEqual(data["id"], case["component_id"])
                self.assertIn("stackpack:kubernetes", data["tags"])
                self.assertEqual(data["id"] in matched, case["gpu"])
                self.assertEqual("suse.ai.gpu.telemetry:dcgm" in data["tags"], case["gpu"])
                now = int(time.time() * 1000)
                charts = self.capture(case["cluster"] + "-" + case["pod"] + "-charts", self.api(
                    f"/api/components/{data['id']}/metricPerspectiveData?startTime={now - 600000}&endTime={now}"
                ))
                tabs = [t for t in charts["tabs"] if t["tabId"] == "suse_ai_gpu"]
                summary = [m for m in full["summary"]["metrics"]
                           if m["boundMetricId"].get("metricId", "").startswith("suse-ai-common-pod-")]
                self.assertEqual(bool(tabs), case["gpu"])
                self.assertEqual(len(summary), 4 if case["gpu"] else 0)
                # The GPU extension must retain the native Kubernetes presentation.
                self.assertTrue(any(t["tabId"] == "kubernetes-pod" for t in charts["tabs"]))
                expressions = [m["query"] for m in summary] + [
                    q["expression"] for t in tabs for s in t["sections"]
                    for m in s["metrics"] for q in m["boundQueries"]
                ]
                for expression in expressions:
                    for selector in walk(promql.parse(expression.replace("${__rate_interval}", "5m"))):
                        if isinstance(selector, promql.VectorSelector):
                            labels = {m.name: m.value for m in selector.matchers.matchers}
                            self.assertEqual(labels["k8s_cluster_name"], case["cluster"])
                            self.assertEqual(labels["k8s_node_name"], node_name)
                            self.assertEqual(labels["pod_namespace"], case["namespace"])
                            self.assertEqual(labels["pod_name"], case["pod"])
                if expressions:
                    values = self.capture(case["cluster"] + "-" + case["pod"] + "-values", self.api(
                        "/api/metrics/query_batch", {"queries": [
                            {"id": str(i), "query": e.replace("${__rate_interval}", "5m"), "_type": "instant", "time": str(now // 1000)}
                            for i, e in enumerate(expressions)
                        ]}
                    ))
                    self.assertEqual(len(values["results"]), len(expressions))
                    for value in values["results"]:
                        self.assertTrue(value["data"]["data"]["result"], value)


if __name__ == "__main__":
    unittest.main()

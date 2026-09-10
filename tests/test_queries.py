import json
from pathlib import Path
import tempfile
import time
import unittest
import urllib.parse
import urllib.request

from support import binary, free_port, nodes, process


class QueryRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.directory = Path(directory.name)
        port = free_port()
        cls.base = f"http://127.0.0.1:{port}"
        runtime = process([binary("METRICS_BIN"), f"-storageDataPath={cls.directory / 'data'}",
                           f"-httpListenAddr=127.0.0.1:{port}", "-search.latencyOffset=0s",
                           "-memory.allowedBytes=128MB"], cls.directory, port)
        runtime.__enter__()
        cls.addClassCleanup(runtime.__exit__, None, None, None)

    def setUp(self):
        self.now = int(time.time())
        self.case = self.id().rsplit(".", 1)[1]

    def import_samples(self, samples):
        lines = []
        for metric, labels, value, timestamp in samples:
            labels = dict(labels, test_case=self.case)
            selector = ",".join(f"{key}={json.dumps(value)}" for key, value in labels.items())
            lines.append(f"{metric}{{{selector}}} {value} {timestamp * 1000}")
        request = urllib.request.Request(self.base + "/api/v1/import/prometheus",
                                         data=("\n".join(lines) + "\n").encode())
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 204)
        with urllib.request.urlopen(self.base + "/internal/force_flush", timeout=5) as response:
            response.read()

    def query(self, expression, timestamp=None, component_name="worker-0"):
        substitutions = {"name": component_name, "tags.node-name": "worker-1", "tags.namespace": "tenant-a",
                         "tags.cluster-name": "alpha", "__rate_interval": "5m"}
        for key, value in substitutions.items():
            expression = expression.replace("${" + key + "}", value)
        expression = expression.replace("{", '{test_case="' + self.case + '",')
        url = self.base + "/api/v1/query?" + urllib.parse.urlencode({
            "query": expression, "time": timestamp or self.now, "nocache": "1"})
        with urllib.request.urlopen(url, timeout=5) as response:
            result = json.load(response)
        self.assertEqual(result["status"], "success", result)
        return result["data"]["result"]

    def scalar(self, expression, timestamp=None):
        result = self.query(expression, timestamp)
        self.assertEqual(len(result), 1, result)
        return float(result[0]["value"][1])

    @staticmethod
    def monitor(product, node_id):
        return next(n["arguments"]["metric"]["query"] for n in nodes(f"monitors/{product}/monitor.sty")
                    if n["id"] == node_id)

    def registry_expressions(self):
        bindings = nodes("metric-bindings/kubeflow-model-registry-metrics.sty")
        queries = next(n["queries"] for n in bindings if n["id"] == -652)
        return {"monitor": self.monitor("kubeflow-model-registry", -3025),
                **{q["alias"]: q["expression"] for q in queries}}

    def test_registry_missing_checks_remain_unknown(self):
        for expression in self.registry_expressions().values():
            self.assertEqual(self.query(expression), [])
        self.assertEqual(self.query(self.monitor("kubeflow-model-registry", -3023)), [])

    def test_registry_failure_recovery_and_relapse(self):
        labels = {"suse_ai_component_name": "kubeflow-model-registry", "validation_type": "contains",
                  "http_url": "http://registry/api", "service_instance_id": "registry", "k8s_cluster_name": "alpha"}
        # Opposite outcomes are deliberately absent, as in the real receiver.
        self.import_samples([(f"httpcheck_validation_{outcome}", labels, 1, self.now - 120 + i * 30)
                             for i, outcome in enumerate(("failed", "passed", "failed", "passed"))])
        for i, expected in enumerate((1, 0, 1, 0)):
            for name, expression in self.registry_expressions().items():
                with self.subTest(outcome=i, expression=name):
                    self.assertEqual(self.scalar(expression, self.now - 120 + i * 30),
                                     1 - expected if name == "passed" else expected)

    def test_registry_any_failing_endpoint_alerts(self):
        common = {"suse_ai_component_name": "kubeflow-model-registry", "validation_type": "contains"}
        self.import_samples([
            ("httpcheck_validation_failed", dict(common, http_url="http://down/api"), 1, self.now - 30),
            ("httpcheck_validation_passed", dict(common, http_url="http://healthy/api"), 1, self.now),
        ])
        self.assertEqual(self.scalar(self.registry_expressions()["monitor"]), 1)

    def test_registry_availability_uses_latest_status_label_shape(self):
        common = {"suse_ai_component_name": "kubeflow-model-registry", "http_url": "http://registry/api",
                  "service_instance_id": "registry", "k8s_cluster_name": "alpha"}
        samples = []
        for i, code in enumerate((200, 503, 200, 401, 200)):
            for status_class in ("2xx", "4xx", "5xx"):
                active = status_class[0] == str(code)[0]
                labels = dict(common, http_status_class=status_class)
                if active:
                    labels["http_status_code"] = str(code)
                samples.append(("httpcheck_status", labels, int(active), self.now - 150 + i * 30))
        self.import_samples(samples)
        queries = next(n["queries"] for n in nodes("metric-bindings/kubeflow-model-registry-metrics.sty")
                       if n["id"] == -650)
        for i, code in enumerate((200, 503, 200, 401, 200)):
            timestamp = self.now - 150 + i * 30
            self.assertEqual(self.scalar(self.monitor("kubeflow-model-registry", -3023), timestamp), int(code == 200))
            for query in queries:
                self.assertEqual(self.scalar(query["expression"], timestamp), int(query["alias"][0] == str(code)[0]))

    def test_kserve_ignores_unrelated_controllers_and_preserves_queues(self):
        samples = []
        for i in range(6):
            timestamp = self.now - 300 + i * 60
            for product, result, rate in (("kserve", "success", 1), ("kserve", "error", 0),
                                          ("unrelated-operator", "error", 10)):
                samples.append(("controller_runtime_reconcile_total",
                                {"suse_ai_component_name": product, "result": result}, i * 60 * rate, timestamp))
        for product, value in (("kserve", 0), ("unrelated-operator", 120)):
            samples.append(("workqueue_longest_running_processor_seconds", {"suse_ai_component_name": product}, value, self.now))
        # Summed processing time is NOT the longest active item.
        samples.append(("workqueue_unfinished_work_seconds", {"suse_ai_component_name": "kserve"}, 120, self.now))
        for queue, value in (("inferenceservice", 2), ("servingruntime", 3)):
            samples.append(("workqueue_depth", {"suse_ai_component_name": "kserve", "name": queue}, value, self.now))
        self.import_samples(samples)
        self.assertEqual(self.scalar(self.monitor("kserve", -3016)), 0)
        self.assertEqual(self.scalar(self.monitor("kserve", -3018)), 0)
        depth = next(n["queries"][0]["expression"] for n in nodes("metric-bindings/kserve-metrics.sty") if n["id"] == -635)
        self.assertEqual({r["metric"]["name"]: float(r["value"][1]) for r in self.query(depth)},
                         {"inferenceservice": 2, "servingruntime": 3})

    def test_kserve_real_failures_still_alert(self):
        samples = []
        for i in range(6):
            for result, rate in (("error", 1), ("success", 1)):
                samples.append(("controller_runtime_reconcile_total",
                                {"suse_ai_component_name": "kserve", "result": result}, i * 60 * rate, self.now - 300 + i * 60))
        samples.append(("workqueue_longest_running_processor_seconds", {"suse_ai_component_name": "kserve"}, 90, self.now))
        self.import_samples(samples)
        self.assertAlmostEqual(self.scalar(self.monitor("kserve", -3016)), 0.5)
        self.assertEqual(self.scalar(self.monitor("kserve", -3018)), 90)

    def test_kserve_missing_controller_does_not_report_healthy(self):
        self.assertEqual(self.query(self.monitor("kserve", -3016)), [])
        binding = next(n for n in nodes("metric-bindings/kserve-metrics.sty") if n["id"] == -634)
        self.assertEqual(self.query(binding["queries"][0]["expression"]), [])

    def test_kserve_idle_controller_without_error_series_is_healthy(self):
        self.import_samples([
            ("controller_runtime_reconcile_total", {"suse_ai_component_name": "kserve", "result": "success"},
             100, self.now - 300 + i * 60) for i in range(6)
        ])
        self.assertEqual(self.scalar(self.monitor("kserve", -3016)), 0)
        binding = next(n for n in nodes("metric-bindings/kserve-metrics.sty") if n["id"] == -634)
        self.assertEqual(self.scalar(binding["queries"][0]["expression"]), 0)

    def test_gpu_identity_excludes_other_namespaces_and_clusters(self):
        samples = []
        for cluster, namespace, value in (("alpha", "tenant-a", 10), ("alpha", "tenant-b", 90), ("beta", "tenant-a", 99)):
            labels = {"k8s_cluster_name": cluster, "k8s_node_name": "worker-1", "pod_name": "worker-0",
                      "pod_namespace": namespace, "container_name": "app", "gpu": "0", "vgpu": "0"}
            for metric in ("DCGM_FI_DEV_GPU_UTIL", "DCGM_FI_DEV_FB_USED", "DCGM_FI_DEV_GPU_TEMP"):
                samples.append((metric, labels, value, self.now))
        self.import_samples(samples)
        for binding in nodes("metric-bindings/common-metrics.sty"):
            if binding["id"] in (-584, -615, -616, -617):
                with self.subTest(binding=binding["id"]):
                    self.assertEqual(self.scalar(binding["queries"][0]["expression"]),
                                     10 * 1048576 if binding["id"] == -617 else 10)
        for binding in nodes("metric-bindings/gpu-metrics.sty"):
            if binding["id"] in (-606, -607, -608):
                result = self.query(binding["queries"][0]["expression"], component_name="worker-1")
                scale = 1048576 if binding["id"] == -608 else 1
                self.assertEqual(sorted(float(r["value"][1]) for r in result), [10 * scale, 90 * scale])

    def test_changed_queries_parse(self):
        for relative in ("metric-bindings/common-metrics.sty", "metric-bindings/gpu-metrics.sty",
                         "metric-bindings/kserve-metrics.sty", "metric-bindings/kubeflow-model-registry-metrics.sty"):
            for binding in nodes(relative):
                for query in binding["queries"]:
                    with self.subTest(binding=binding["id"], expression=query["expression"]):
                        self.query(query["expression"])

import copy
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

import yaml

from support import (ENV, ROOT, attr_map, attrs, binary, collector, examples, free_port,
                     http_server, isolate, metrics, send, spans)


class CollectorRegressions(unittest.TestCase):
    def test_examples_validate_with_pinned_collector(self):
        rendered = subprocess.check_output([
            "helm", "template", "regression", "open-telemetry/opentelemetry-collector",
            "--version", "0.165.0", "--namespace", "suse-private-ai", "-f",
            str(ROOT / "integrations/otel-collector/otel-values.yaml"),
        ], text=True)
        configs = examples()
        configs["helm"] = yaml.safe_load(next(doc["data"]["relay"] for doc in yaml.safe_load_all(rendered)
                                             if doc and doc.get("kind") == "ConfigMap" and "relay" in doc.get("data", {})))
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            token = directory / "token"
            token.write_text("test-placeholder")
            for name, config in configs.items():
                with self.subTest(example=name):
                    path = directory / (name + ".yaml")
                    # Validation opens this credential file; no cluster token is needed.
                    path.write_text(yaml.safe_dump(config).replace(
                        "/var/run/secrets/kubernetes.io/serviceaccount/token", str(token)))
                    result = subprocess.run([binary("COLLECTOR_BIN"), "validate", "--config", str(path)],
                                            env=ENV, text=True, capture_output=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sampling_preserves_kubeflow_hints_and_topology(self):
        for name, source in examples().items():
            with self.subTest(example=name), tempfile.TemporaryDirectory() as tmp, http_server() as sink:
                directory, port = Path(tmp), free_port()
                names = [p for p in source["service"]["pipelines"]
                         if p.startswith("traces") and p != "traces/spanmetrics"]
                config = isolate(source, names, directory, port)
                # Exercise the actual topology exporter against a local intake.
                config["exporters"]["topology"] = copy.deepcopy(source["exporters"]["topology"])
                config["exporters"]["topology"].update(
                    endpoint=f"http://127.0.0.1:{sink.server_port}", flush_interval="10s")
                config["service"]["pipelines"]["traces/topology"]["exporters"].append("topology")
                now = time.time_ns()

                def resource(service, trace, count, span_attrs=None):
                    return {"resource": {"attributes": attrs({
                        "service.name": service, "k8s.namespace.name": "ml-platform",
                        "k8s.pod.name": service + "-pod", "k8s.pod.uid": service + "-uid",
                        "k8s.node.name": "worker-1",
                    })}, "scopeSpans": [{"spans": [{
                        "traceId": f"{trace:032x}", "spanId": f"{trace * 10000 + i:016x}",
                        "name": service, "kind": 3, "startTimeUnixNano": str(now),
                        "endTimeUnixNano": str(now + 1_000_000), "status": {"code": 1},
                        "attributes": attrs(span_attrs or {}),
                    } for i in range(1, count + 1)]}]}

                payload = {"resourceSpans": [
                    resource("ordinary-http", 1, 600),  # Exceeds the shipped sampler's rate cap.
                    resource("ml-pipeline", 2, 1, {"kserve.inference.service": "iris"}),
                    resource("ml-pipeline", 3, 1, {"http.url": "http://model-registry-service/api"}),
                    resource("iris-predictor-default", 4, 1),
                ]}
                with collector(config, directory, port):
                    send(port, "traces", payload)
                    time.sleep(14)  # Shipped decision_wait=10s, plus batch/file flush.
                backend = [item for pipeline in names if pipeline not in ("traces", "traces/topology")
                           for item in spans(directory / (pipeline.replace("/", "-") + ".jsonl"))]
                self.assertEqual(len(backend), 3, "A new backend branch bypassed sampling or duplicated spans")
                by_trace = {int(span["traceId"], 16): (res, span) for res, span in backend}
                self.assertEqual(set(by_trace), {2, 3, 4})
                self.assertEqual(attr_map(by_trace[2][1]["attributes"])["peer.service"], "kserve")
                self.assertEqual(attr_map(by_trace[3][1]["attributes"])["peer.service"], "kubeflow-model-registry")
                self.assertEqual(attr_map(by_trace[2][0]["attributes"])["suse.ai.component.type"], "workflow-engine")
                self.assertEqual(attr_map(by_trace[4][0]["attributes"])["suse.ai.component.name"], "kserve")
                for _, span in backend:
                    self.assertNotIn("gen_ai.provider.name", attr_map(span.get("attributes", [])))
                self.assertTrue(sink.payloads, "No topology snapshot was emitted")
                topology = sink.payloads[-1]["topologies"][0]
                edges = {(r["sourceId"], r["targetId"]) for r in topology["relations"]}
                source_id = "urn:suse-ai:product:workflow-engine:kubeflow-pipelines"
                for target in ("kserve", "kubeflow-model-registry"):
                    self.assertIn((source_id, "urn:suse-ai:product:inference-engine:" + target), edges)
                for component in topology["components"]:
                    self.assertFalse(any(label.startswith("k8s.namespace.name:")
                                         for label in component["data"]["labels"]),
                                     "Cross-namespace products must not inherit a static namespace")

    def test_application_namespace_preservation_and_fallbacks(self):
        cases = [({"k8s.namespace.name": "tenant-a"}, "tenant-a"),
                 ({"k8s.namespace.name": "tenant-a", "service.namespace": "logical-service"}, "tenant-a"),
                 ({"service.namespace": "tenant-b"}, "tenant-b"), ({}, "suse-private-ai")]
        for name, source in examples().items():
            with self.subTest(example=name), tempfile.TemporaryDirectory() as tmp:
                directory, port = Path(tmp), free_port()
                config = isolate(source, ["metrics/infer-applications"], directory, port)
                now = str(time.time_ns())
                payload = {"resourceMetrics": [{
                    "resource": {"attributes": attrs(dict({"service.name": f"app-{i}",
                        "k8s.pod.name": f"pod-{i}", "k8s.pod.uid": f"uid-{i}"}, **values))},
                    "scopeMetrics": [{"metrics": [{"name": "gen_ai.client.operation.duration", "unit": "s",
                        "histogram": {"aggregationTemporality": 2, "dataPoints": [{
                            "startTimeUnixNano": now, "timeUnixNano": now, "count": "1", "sum": 0.01,
                            "bucketCounts": ["1", "0"], "explicitBounds": [1.0]}]}}]}],
                } for i, (values, _) in enumerate(cases)]}
                with collector(config, directory, port):
                    send(port, "metrics", payload)
                    time.sleep(3)
                actual = {attr_map(r["attributes"])["service.name"]: attr_map(r["attributes"])
                          for r, _ in metrics(directory / "metrics-infer-applications.jsonl")}
                self.assertEqual(set(actual), {f"app-{i}" for i in range(len(cases))})
                for i, (_, expected) in enumerate(cases):
                    self.assertEqual(actual[f"app-{i}"]["k8s.namespace.name"], expected)
                    self.assertEqual(actual[f"app-{i}"]["suse.ai.component.type"], "application")

    def test_httpcheck_emits_sparse_validation_and_real_namespace(self):
        for name, source in examples().items():
            with self.subTest(example=name), tempfile.TemporaryDirectory() as tmp, http_server() as server:
                server.responses = {"/valid": (200, {"items": []}), "/invalid": (200, {"error": "wrong body"})}
                directory, port = Path(tmp), free_port()
                pipeline = "metrics/kubeflow-model-registry"
                config = isolate(source, [pipeline], directory, port)
                config["service"]["pipelines"][pipeline]["receivers"].append("otlp")
                receiver = config["receivers"]["http_check/model-registry"]
                target = receiver["targets"][0]
                receiver["collection_interval"] = "1s"
                receiver["targets"] = [dict(copy.deepcopy(target), endpoint=f"http://127.0.0.1:{server.server_port}/{result}")
                                       for result in ("valid", "invalid")]
                with collector(config, directory, port):
                    time.sleep(4)
                checks = {}
                for resource, metric in metrics(directory / "metrics-kubeflow-model-registry.jsonl"):
                    values = attr_map(resource["attributes"])
                    self.assertEqual(values["k8s.namespace.name"], "ml-platform")
                    self.assertEqual(values["suse.ai.component.type"], "ml-registry")
                    if metric["name"].startswith("httpcheck.validation"):
                        for point in metric["sum"]["dataPoints"]:
                            endpoint = attr_map(point["attributes"])["http.url"].rsplit("/", 1)[1]
                            checks.setdefault(endpoint, {})[metric["name"]] = int(point["asInt"])
                self.assertEqual(checks, {"valid": {"httpcheck.validation.passed": 1},
                                          "invalid": {"httpcheck.validation.failed": 1}})

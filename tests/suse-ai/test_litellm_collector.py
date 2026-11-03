"""Scrape real HTTP endpoints through the optional LiteLLM Collector pipeline."""

import copy
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
import uuid

import yaml

from test_contract import ROOT, component, record


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.paths.append(self.path)
        if self.path != "/metrics/":
            self.send_error(404)
            return
        # Native LiteLLM 1.98 metric names, types and dimensions.
        body = b'''# TYPE litellm_guardrail_requests_total counter
litellm_guardrail_requests_total{guardrail_name="prompt-policy",status="error",hook_type="pre_call"} 2
# TYPE litellm_deployment_state gauge
litellm_deployment_state{litellm_model_name="guarded-route",model_id="backend-1",api_base="http://inference:8000",api_provider="openai"} 0
# TYPE litellm_request_total_latency_metric histogram
litellm_request_total_latency_metric_bucket{requested_model="guarded-route",model="qwen",le="1"} 4
litellm_request_total_latency_metric_bucket{requested_model="guarded-route",model="qwen",le="+Inf"} 5
litellm_request_total_latency_metric_sum{requested_model="guarded-route",model="qwen"} 4
litellm_request_total_latency_metric_count{requested_model="guarded-route",model="qwen"} 5
'''
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@unittest.skipUnless(os.environ.get("AI_COLLECTOR_IMAGE"), "Set AI_COLLECTOR_IMAGE")
class LiteLLMCollectorTest(unittest.TestCase):
    def test_replica_identity_and_guardrail_dimensions_survive_scraping(self):
        servers = []
        for _ in range(2):
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), MetricsHandler)
            server.paths = []
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            servers.append(server)

        example = ROOT / "examples/suse-ai"
        base = yaml.safe_load((example / "collector.yaml").read_text())
        overlay = yaml.safe_load((example / "litellm-receiver.yaml").read_text())
        pipeline = copy.deepcopy(overlay["service"]["pipelines"]["metrics/litellm"])
        processors = base["processors"] | overlay["processors"]
        with tempfile.TemporaryDirectory(prefix="suse-ai-litellm-") as directory:
            directory = Path(directory)
            directory.chmod(0o777)
            receiver = copy.deepcopy(overlay["receivers"]["prometheus/litellm"])
            job = receiver["config"]["scrape_configs"][0]
            # Replace Kubernetes transport only; execute the shipped relabel rules.
            job.pop("kubernetes_sd_configs")
            job["file_sd_configs"] = [{"files": ["/test/targets.json"]}]
            job["scrape_interval"] = "1s"
            targets = []
            for index, server in enumerate(servers):
                targets.append({"targets": [f"127.0.0.1:{server.server_port}"], "labels": {
                    "__meta_kubernetes_service_name": "litellm-router",
                    "__meta_kubernetes_pod_uid": f"pod-{index}",
                    "__meta_kubernetes_pod_name": f"litellm-{index}",
                    "__meta_kubernetes_pod_node_name": f"node-{index}",
                }})
            excluded = copy.deepcopy(targets[0])
            excluded["labels"]["__meta_kubernetes_service_name"] = "unrelated"
            targets.append(excluded)
            excluded = copy.deepcopy(targets[0])
            excluded["labels"].pop("__meta_kubernetes_pod_uid")
            targets.append(excluded)
            (directory / "targets.json").write_text(json.dumps(targets))
            pipeline["exporters"] = ["file"]
            config = {
                "receivers": {"prometheus/litellm": receiver},
                "processors": {name: processors[name] for name in pipeline["processors"]},
                "exporters": {"file": {"path": "/test/metrics.jsonl", "flush_interval": "100ms"}},
                "service": {"pipelines": {"metrics/litellm": pipeline},
                            "telemetry": {"metrics": {"level": "none"}}},
            }
            (directory / "collector.yaml").write_text(yaml.safe_dump(config))
            container = "suse-ai-litellm-" + uuid.uuid4().hex[:10]
            subprocess.run([
                os.environ.get("AI_CONTAINER_RUNTIME", "docker"), "run", "--detach", "--name", container, "--network", "host",
                "-v", f"{directory}:/test:rw,z", "-e", "OBSERVED_NAMESPACE=ai-test",
                "-e", "K8S_CLUSTER_NAME=test-cluster", "-e", "LITELLM_SERVICE_NAME=team-proxy",
                "-e", "LITELLM_METRICS_PORT=(" + "|".join(str(s.server_port) for s in servers) + ")",
                os.environ["AI_COLLECTOR_IMAGE"], "--config=/test/collector.yaml",
            ], check=True, capture_output=True, text=True)
            try:
                seen = {}
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline and len(seen) < 2:
                    output = directory / "metrics.jsonl"
                    if output.exists():
                        for line in output.read_text().splitlines():
                            try:
                                batches = json.loads(line).get("resourceMetrics", [])
                            except json.JSONDecodeError:
                                continue
                            for batch in batches:
                                attrs = {a["key"]: next(iter(a["value"].values()))
                                         for a in batch["resource"]["attributes"]}
                                for scope in batch.get("scopeMetrics", []):
                                    for metric in scope.get("metrics", []):
                                        if metric["name"].startswith("litellm_guardrail_requests"):
                                            seen[attrs["service.instance.id"]] = (attrs, metric)
                    time.sleep(0.1)
                self.assertEqual(set(seen), {"pod-0", "pod-1"})
                for instance, (attrs, metric) in seen.items():
                    self.assertEqual(attrs["service.name"], "team-proxy")
                    self.assertEqual(attrs["service.namespace"], "ai-test")
                    self.assertEqual(attrs["k8s.pod.uid"], instance)
                    self.assertEqual(attrs["k8s.cluster.name"], "test-cluster")
                    self.assertEqual(attrs["suse.ai.product"], "litellm")
                    self.assertEqual(metric["sum"]["aggregationTemporality"], 2)
                    point = metric["sum"]["dataPoints"][0]
                    labels = {a["key"]: next(iter(a["value"].values())) for a in point["attributes"]}
                    self.assertEqual(labels["guardrail_name"], "prompt-policy")
                    self.assertEqual(labels["status"], "error")
                    self.assertEqual(labels["hook_type"], "pre_call")
                    mapped = component(record("METRICS", resource=attrs, metric=metric["name"]), "otel service")
                    self.assertEqual(mapped["identifier"], "urn:opentelemetry:namespace/ai-test:service/team-proxy")
                    self.assertEqual(mapped["tags"]["suse.ai.category"], "model-proxy")
                self.assertTrue(all(s.paths and set(s.paths) == {"/metrics/"} for s in servers))
                log = subprocess.check_output([os.environ.get("AI_CONTAINER_RUNTIME", "docker"), "logs", container], stderr=subprocess.STDOUT, text=True)
                self.assertNotIn('"level":"error"', log.lower())
            finally:
                subprocess.run([os.environ.get("AI_CONTAINER_RUNTIME", "docker"), "rm", "--force", container], check=True, capture_output=True)

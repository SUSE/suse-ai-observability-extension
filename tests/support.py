"""Local process fixtures; no cluster, credentials, or backend writes are used."""

from contextlib import contextmanager
import copy
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "stackpack/suse-ai/provisioning/templates"
ENV = dict(os.environ, API_KEY="test-placeholder", K8S_CLUSTER_NAME="alpha",
           SUSE_AI_NAMESPACE="suse-private-ai", KUBEFLOW_NAMESPACE="ml-platform",
           MODEL_REGISTRY_BEARER_TOKEN="test-placeholder", MY_POD_IP="127.0.0.1")


def binary(variable):
    executable = shutil.which(os.environ.get(variable, ""))
    if not executable:
        raise RuntimeError(f"Set {variable} to an executable; see knowledge/REGRESSION_TESTS.md")
    return executable


def examples():
    directory = ROOT / "integrations/otel-collector"
    helm = yaml.safe_load((directory / "otel-values.yaml").read_text())["config"]
    operator = next(doc["spec"]["config"] for doc in yaml.safe_load_all(
        (directory / "otel-collector-operator.yaml").read_text()
    ) if doc and doc.get("kind") == "OpenTelemetryCollector")
    return {"helm": helm, "operator": operator}


def nodes(relative):
    # These fixtures exercise STY data, not the backend's Handlebars runtime.
    return yaml.safe_load(re.sub(r"\{\{.*?\}\}", "TEMPLATE", (TEMPLATES / relative).read_text()))


def attrs(values):
    return [{"key": key, "value": {"stringValue": value}} for key, value in values.items()]


def attr_map(values):
    return {item["key"]: next(iter(item["value"].values())) for item in values}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for local test process")


@contextmanager
def process(command, directory, port):
    log_path = directory / "process.log"
    with log_path.open("w") as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=ENV)
        try:
            def ready():
                if child.poll() is not None:
                    raise RuntimeError(log_path.read_text())
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        return True
                except OSError:
                    return False
            wait_until(ready)
            yield child
        finally:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                raise RuntimeError(f"Test process failed to stop: {log_path.read_text()}")
        if child.returncode != 0:
            raise RuntimeError(log_path.read_text())


@contextmanager
def http_server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = self.server.responses[self.path]
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_POST(self):
            self.server.payloads.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.responses = {}
    server.payloads = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def isolate(source, names, directory, port):
    """Keep shipped processors/wiring, replacing Kubernetes enrichment and I/O."""
    config = {"receivers": {"otlp": {"protocols": {"http": {"endpoint": f"127.0.0.1:{port}"}}}},
              "processors": {}, "exporters": {}, "connectors": {},
              "service": {"telemetry": {"logs": {"level": "error"}, "metrics": {"level": "none"}},
                          "pipelines": {}}}
    for name in names:
        pipeline = copy.deepcopy(source["service"]["pipelines"][name])
        if name == "traces":
            pipeline["receivers"] = ["otlp"]
        pipeline["processors"] = [p for p in pipeline["processors"] if p != "k8s_attributes"]
        for processor in pipeline["processors"]:
            config["processors"][processor] = copy.deepcopy(source["processors"].get(processor) or {})
        for receiver in pipeline["receivers"]:
            if receiver in source.get("connectors", {}):
                config["connectors"][receiver] = copy.deepcopy(source["connectors"][receiver])
            elif receiver != "otlp":
                config["receivers"][receiver] = copy.deepcopy(source["receivers"][receiver])
        if name != "traces":
            exporter = "file/" + name.replace("/", "-")
            config["exporters"][exporter] = {"path": str(directory / (name.replace("/", "-") + ".jsonl")),
                                             "flush_interval": "100ms"}
            pipeline["exporters"] = [exporter]
        config["service"]["pipelines"][name] = pipeline
    if "memory_limiter" in config["processors"]:
        config["processors"]["memory_limiter"] = {"check_interval": "1s", "limit_mib": 512, "spike_limit_mib": 128}
    return config


@contextmanager
def collector(config, directory, port):
    path = directory / "config.yaml"
    path.write_text(yaml.safe_dump(config))
    with process([binary("COLLECTOR_BIN"), "--config", str(path)], directory, port):
        yield


def send(port, signal, payload):
    request = urllib.request.Request(f"http://127.0.0.1:{port}/v1/{signal}",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise AssertionError(response.read())


def records(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def spans(path):
    return [(rs.get("resource", {}), span) for record in records(path)
            for rs in record.get("resourceSpans", []) for scope in rs.get("scopeSpans", [])
            for span in scope.get("spans", [])]


def metrics(path):
    return [(rm.get("resource", {}), metric) for record in records(path)
            for rm in record.get("resourceMetrics", []) for scope in rm.get("scopeMetrics", [])
            for metric in scope.get("metrics", [])]

import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import unittest
from urllib.request import urlopen


spec = importlib.util.spec_from_file_location("ollama_metrics", Path(__file__).resolve().parents[1] / "ollama_metrics.py")
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


class Api(BaseHTTPRequestHandler):
    status = 200
    body = b'{"models": []}'
    delay = 0
    paths = []

    def do_GET(self):
        self.paths.append(self.path)
        time.sleep(self.delay)
        self.send_response(self.status)
        self.end_headers()
        try:
            self.wfile.write(self.body)
        except BrokenPipeError:
            pass

    def log_message(self, *_args):
        pass


class MetricsTest(unittest.TestCase):
    def setUp(self):
        Api.status, Api.body, Api.delay, Api.paths = 200, b'{"models": []}', 0, []
        self.api = self.server(Api)
        self.endpoint = f"http://127.0.0.1:{self.api.server_port}/api/ps"

    def server(self, handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_empty_process_is_healthy_with_zero_loaded_models(self):
        text = metrics.collect(self.endpoint).decode()
        self.assertIn("ollama_api_up 1\n", text)
        self.assertIn("ollama_loaded_models 0\n", text)
        self.assertNotIn('model="', text)
        self.assertEqual(Api.paths, ["/api/ps"])

    def test_reported_allocations_and_model_label_escaping(self):
        Api.body = json.dumps({"models": [{"name": 'model"\\\n', "size": 100, "size_vram": 0, "context_length": 4096}]}).encode()
        text = metrics.collect(self.endpoint).decode()
        self.assertIn('ollama_model_size_bytes{model="model\\"\\\\\\n"} 100\n', text)
        self.assertIn('ollama_model_vram_bytes{model="model\\"\\\\\\n"} 0\n', text)
        self.assertIn('ollama_model_context_length{model="model\\"\\\\\\n"} 4096\n', text)
        for forbidden in ("gen_ai", "tokens", "request_duration", "service_instance", "pod_uid"):
            self.assertNotIn(forbidden, text)

    def test_missing_optional_allocations_are_omitted(self):
        Api.body = b'{"models": [{"model": "small-model"}]}'
        text = metrics.collect(self.endpoint).decode()
        self.assertIn("ollama_loaded_models 1\n", text)
        self.assertNotIn('model="small-model"', text)

    def test_invalid_snapshots_do_not_turn_into_empty_successes(self):
        for payload in (None, {}, {"models": None}, {"models": [None]}, {"models": [{"name": ""}]},
                        {"models": [{"name": "same"}, {"name": "same"}]},
                        *({"models": [{"name": "bad", "size": value}]} for value in (-1, True, "42", float("nan")))):
            with self.subTest(payload=payload):
                Api.body = json.dumps(payload).encode()
                text = metrics.collect(self.endpoint).decode()
                self.assertIn("ollama_api_up 0\n", text)
                self.assertNotIn("ollama_loaded_models", text)
                self.assertNotIn("ollama_model_", text)

    def test_failure_after_success_does_not_reuse_snapshot(self):
        Api.body = b'{"models": [{"name": "old", "size": 42}]}'
        self.assertIn(b'ollama_model_size_bytes{model="old"} 42', metrics.collect(self.endpoint))
        for status, body in ((500, Api.body), (200, b"invalid-json"), (200, b" " * (metrics.MAX_RESPONSE_BYTES + 1))):
            with self.subTest(status=status):
                Api.status, Api.body = status, body
                result = metrics.collect(self.endpoint)
                self.assertIn(b"ollama_api_up 0\n", result)
                self.assertNotIn(b"ollama_model_", result)
                self.assertNotIn(b"ollama_loaded_models", result)

    def test_timeout_is_unavailable(self):
        Api.delay = 0.2
        self.assertIn(b"ollama_api_up 0\n", metrics.collect(self.endpoint, timeout=0.01))

    def test_instances_are_isolated(self):
        class Unavailable(Api):
            status = 503
        other = self.server(Unavailable)
        self.assertIn(b"ollama_api_up 1", metrics.collect(self.endpoint))
        self.assertIn(b"ollama_api_up 0", metrics.collect(f"http://127.0.0.1:{other.server_port}/api/ps"))

    def test_http_exporter_and_health_route(self):
        server = self.server(metrics.handler(self.endpoint, 1))
        origin = f"http://127.0.0.1:{server.server_port}"
        with urlopen(origin + "/metrics") as response:
            self.assertIn("text/plain", response.headers["Content-Type"])
            self.assertIn(b"ollama_loaded_models 0", response.read())
        Api.status = 503
        with urlopen(origin + "/healthz") as response:
            self.assertEqual(response.read(), b"ok\n")


if __name__ == "__main__":
    unittest.main()

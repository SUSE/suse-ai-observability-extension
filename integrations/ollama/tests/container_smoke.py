"""Run the packaged exporter with the Kubernetes sidecar's restrictions."""

import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid


RUNTIME = os.environ.get("CONTAINER_RUNTIME", "podman")
IMAGE = os.environ.get("OLLAMA_IMAGE", "registry.suse.com/ai/containers/suse-ai-ollama-exporter:0.1.0")
PLATFORM = os.environ.get("OLLAMA_PLATFORM", "linux/amd64")
API = """
from http.server import BaseHTTPRequestHandler, HTTPServer
class API(BaseHTTPRequestHandler):
    state = 'loaded'
    def do_POST(self):
        API.state = self.path[1:]
        self.send_response(204)
        self.end_headers()
    def do_GET(self):
        if self.path != '/api/ps':
            self.send_error(404)
            return
        self.send_response(503 if API.state == 'down' else 200)
        self.end_headers()
        self.wfile.write(b'{"models": []}' if API.state == 'empty' else
            b'{"models": [{"name": "smoke-model", "size": 1048576, "size_vram": 524288, "context_length": 4096}]}')
    def log_message(self, *args):
        pass
HTTPServer(('0.0.0.0', 11434), API).serve_forever()
"""
SECURITY = """
import hashlib, json, os
from pathlib import Path
status = dict(line.split(':', 1) for line in Path('/proc/1/status').read_text().splitlines())
try:
    Path('/tmp/ollama-write-probe').write_text('must fail')
except OSError as error:
    write_errno = error.errno
else:
    write_errno = 0
print(json.dumps({
    'uid': os.getuid(), 'gid': os.getgid(),
    'pid1_uid': [int(value) for value in status['Uid'].split()],
    'pid1_gid': [int(value) for value in status['Gid'].split()],
    'capabilities': {key: int(status[key], 16) for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')},
    'no_new_privileges': int(status['NoNewPrivs']),
    'seccomp': int(status['Seccomp']),
    'machine': os.uname().machine,
    'readonly_root': bool(os.statvfs('/').f_flag & os.ST_RDONLY),
    'write_errno': write_errno,
    'script_sha256': hashlib.sha256(Path('/opt/ollama-metrics/ollama_metrics.py').read_bytes()).hexdigest(),
}))
"""


def run(*args):
    result = subprocess.run([RUNTIME, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if result.returncode:
        raise RuntimeError(f"{RUNTIME} {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


class ContainerTest(unittest.TestCase):
    def start(self, *args):
        name = f"ollama-smoke-{uuid.uuid4().hex[:12]}"
        removal = [RUNTIME, "rm", "-f"]
        if Path(RUNTIME).name == "podman":
            removal.append("--time=0")
        self.addCleanup(subprocess.run, [*removal, name],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        restrictions = ["--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges"]
        if Path(RUNTIME).name == "podman":
            # Podman otherwise adds writable /tmp and /run tmpfs mounts.
            restrictions.append("--read-only-tmpfs=false")
        run("run", "-d", "--pull=never", "--platform", PLATFORM, "--name", name, *restrictions, *args)
        return name

    def setUp(self):
        self.api = self.start("-p", "127.0.0.1::11434", "-p", "127.0.0.1::11435",
                              "-p", "127.0.0.1::11436", "--entrypoint", "python3", IMAGE, "-B", "-c", API)
        self.api_origin = self.origin(11434)
        self.fetch(self.api_origin + "/api/ps")

    def origin(self, port):
        return "http://" + run("port", self.api, f"{port}/tcp")

    def fetch(self, url):
        deadline = time.monotonic() + 30
        while True:
            try:
                with urlopen(url, timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    return response.read().decode()
            except (URLError, TimeoutError, ConnectionError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)

    def state(self, state):
        with urlopen(Request(self.api_origin + "/" + state, method="POST"), timeout=2) as response:
            self.assertEqual(response.status, 204)

    def test_default_entrypoint_with_restricted_filesystem_and_capabilities(self):
        exporter = self.start("--network", f"container:{self.api}", IMAGE)
        origin = self.origin(11435)
        self.assertEqual(self.fetch(origin + "/healthz"), "ok\n")
        metrics = self.fetch(origin + "/metrics")
        for sample in ("ollama_api_up 1\n", "ollama_loaded_models 1\n",
                       'ollama_model_size_bytes{model="smoke-model"} 1048576\n',
                       'ollama_model_vram_bytes{model="smoke-model"} 524288\n',
                       'ollama_model_context_length{model="smoke-model"} 4096\n'):
            self.assertIn(sample, metrics)
        security = json.loads(run("exec", exporter, "python3", "-B", "-c", SECURITY))
        self.assertEqual(security["uid"], 65532)
        self.assertEqual(security["gid"], 65532)
        self.assertEqual(security["pid1_uid"], [65532] * 4)
        self.assertEqual(security["pid1_gid"], [65532] * 4)
        self.assertEqual(set(security["capabilities"].values()), {0})
        self.assertEqual(security["no_new_privileges"], 1)
        self.assertEqual(security["seccomp"], 2)
        self.assertEqual(security["machine"], {"linux/amd64": "x86_64", "linux/arm64": "aarch64"}[PLATFORM])
        self.assertTrue(security["readonly_root"])
        self.assertEqual(security["write_errno"], errno.EROFS)
        script = Path(__file__).resolve().parents[1] / "ollama_metrics.py"
        self.assertEqual(security["script_sha256"], hashlib.sha256(script.read_bytes()).hexdigest())
        print(f"\n{PLATFORM}: /healthz=200, /metrics=200; security={json.dumps(security, sort_keys=True)}", flush=True)
        self.state("empty")
        self.assertIn("ollama_loaded_models 0\n", self.fetch(origin + "/metrics"))
        self.state("down")
        metrics = self.fetch(origin + "/metrics")
        self.assertIn("ollama_api_up 0\n", metrics)
        self.assertNotIn("ollama_model_", metrics)
        self.assertNotIn("ollama_loaded_models", metrics)
        self.assertEqual(self.fetch(origin + "/healthz"), "ok\n")

    def test_command_line_overrides(self):
        self.start("--network", f"container:{self.api}", IMAGE,
                   "--ollama-url", "http://localhost:11434", "--port", "11436", "--timeout", "1")
        origin = self.origin(11436)
        self.assertEqual(self.fetch(origin + "/healthz"), "ok\n")
        self.assertIn("ollama_api_up 1\n", self.fetch(origin + "/metrics"))


if __name__ == "__main__":
    unittest.main()

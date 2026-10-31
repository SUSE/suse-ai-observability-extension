"""Run the real CLI against a local HTTP fixture; no backend provisioning occurs."""
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlparse
import zipfile

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("sts"), "Requires the installed sts CLI")
class RealCliTest(unittest.TestCase):
    def test_init_fresh_rerun_and_upgrade_without_experimental_flags(self):
        versions = []
        instances = {name: [] for name in ("suse-ai", "open-telemetry", "kubernetes-v2")}
        writes = []

        def pack(name):
            current = instances[name][0]["stackPackVersion"] if instances[name] else "3.0.0"
            result = {"name": name, "displayName": name, "version": current,
                      "isMultiConfig": name == "kubernetes-v2", "canUninstall": True,
                      "categories": [], "configurationUrls": [], "steps": [],
                      "releaseStatus": "ENABLED", "configurations": instances[name]}
            if name == "suse-ai" and current != "3.0.0" and "3.0.0" in versions:
                result["nextVersion"] = dict(result, version="3.0.0", configurations=[])
            return result

        class Handler(http.server.BaseHTTPRequestHandler):
            def send_json(self, value, code=200):
                body = json.dumps(value).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/api/server/info":
                    self.send_json({"version": {"major": 7, "minor": 0, "patch": 0,
                                               "diff": "", "commit": "fixture", "isDev": False},
                                    "deploymentMode": "SelfHosted", "platformVersion": "2.11.1"})
                elif path == "/api/stackpack":
                    self.send_json([pack(name) for name in instances if name != "suse-ai" or versions])
                elif path == "/api/stackpack/suse-ai/versions":
                    self.send_json([{"version": version, "isDev": False, "isInUse": False}
                                    for version in versions])
                else:
                    self.send_json({"unexpected": self.path}, 404)

            def do_POST(self):
                parsed = urlparse(self.path)
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                writes.append((parsed.path, parse_qs(parsed.query), body))
                if parsed.path == "/api/stackpack":
                    versions.append("3.0.0")
                    self.send_json(pack("suse-ai"))
                elif parsed.path.endswith("/provision"):
                    name = parsed.path.split("/")[-2]
                    item = {"id": 100 + sum(map(len, instances.values())), "status": "INSTALLED",
                            "stackPackVersion": "3.0.0", "lastUpdateTimestamp": 0,
                            "config": json.loads(body)}
                    instances[name].append(item)
                    self.send_json(item)
                elif parsed.path == "/api/stackpack/suse-ai/upgrade":
                    instances["suse-ai"][0]["stackPackVersion"] = "3.0.0"
                    self.send_json("ok")
                else:
                    self.send_json({"unexpected": self.path}, 404)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "suse-ai.sts"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("stackpack.yaml", "name: suse-ai\nversion: 3.0.0\nschemaVersion: '2.0'\n")
            env = dict(os.environ, STACKSTATE_API_URL=f"http://127.0.0.1:{server.server_port}",
                       STACKSTATE_TOKEN="local-fixture", STACKSTATE_TOKEN_TYPE="api",
                       KUBERNETES_CLUSTERS="alpha", SUSE_AI_ARCHIVE=str(archive), STS_WAIT_SECONDS="5")
            for key in ("STS_BIN", "STS_CONTEXT", "CLEANUP_LEGACY", "UNINSTALL",
                        "STS_EXPERIMENTAL_STACKPACKS", "STS_EXPERIMENTAL_STACKPACK"):
                env.pop(key, None)

            def setup():
                result = subprocess.run(["bash", str(ROOT / "init.sh")], env=env,
                                        text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            setup()
            first = len(writes)
            setup()
            self.assertEqual(first, len(writes), "Re-run made an HTTP mutation")
            instances["suse-ai"][0]["stackPackVersion"] = "2.2.0"
            identity = instances["suse-ai"][0]["id"]
            setup()
            self.assertEqual(instances["suse-ai"][0]["id"], identity)
            upgrades = [request for request in writes if request[0].endswith("/upgrade")]
            self.assertEqual(len(upgrades), 1)
            self.assertEqual(upgrades[0][1]["unlocked"], ["overwrite"])
            uploads = [request for request in writes if request[0] == "/api/stackpack"]
            self.assertEqual(len(uploads), 1)
            self.assertIn(archive.read_bytes(), uploads[0][2])
            ai_install = next(request for request in writes if request[0] == "/api/stackpack/suse-ai/provision")
            self.assertTrue(any("3.0.0" in values for values in ai_install[1].values()), ai_install[1])

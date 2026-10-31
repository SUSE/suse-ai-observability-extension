"""Run the identity fixtures through the example Collector's real pipelines."""

import json
import os
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

import yaml
from identity_fixture import IdentityCases
from test_contract import ROOT


@unittest.skipUnless(
    os.environ.get("AI_COLLECTOR_IMAGE"),
    "Set AI_COLLECTOR_IMAGE for Collector integration",
)
class IdentityCollectorTest(IdentityCases, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="identity-collector-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        cls.directory.chmod(0o777)
        config = yaml.safe_load((ROOT / "examples/suse-ai/collector.yaml").read_text())
        for key in ("transform/suse_ai_resource", "transform/genai_compat", "transform/suse_ai_database"):
            config["processors"][key]["error_mode"] = "propagate"
        config["exporters"] = {
            "file/" + signal: {
                "path": "/test/" + signal + ".json",
                "flush_interval": "100ms",
            }
            for signal in ("metrics", "traces", "logs")
        }
        for name, pipeline in config["service"]["pipelines"].items():
            pipeline["exporters"] = [
                "file/" + name.split("/")[0] if e == "otlp_grpc/suse" else e
                for e in pipeline["exporters"]
            ]
        for connector in config["connectors"].values():
            connector["metrics_flush_interval"] = "1s"
        (cls.directory / "collector.yaml").write_text(
            yaml.safe_dump(config, sort_keys=False)
        )
        cls.container = "suse-ai-identity-" + uuid.uuid4().hex[:10]
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                cls.container,
                "-p",
                "127.0.0.1::4318",
                "-v",
                f"{cls.directory}:/test:rw,z",
                os.environ["AI_COLLECTOR_IMAGE"],
                "--config=/test/collector.yaml",
            ],
            check=True,
            capture_output=True,
        )
        cls.addClassCleanup(
            lambda: subprocess.run(
                ["docker", "rm", "-f", cls.container], check=False, capture_output=True
            )
        )
        cls.endpoint = (
            "http://"
            + subprocess.check_output(
                ["docker", "port", cls.container, "4318/tcp"], text=True
            ).strip()
        )
        cls.wait_for(cls.ready, "OTLP listener")

    @classmethod
    def ready(cls):
        try:
            with urlopen(
                Request(
                    cls.endpoint + "/v1/traces",
                    b"{}",
                    {"Content-Type": "application/json"},
                ),
                timeout=1,
            ):
                return True
        except OSError:
            return False

    @classmethod
    def wait_for(cls, predicate, description):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.1)
        logs = subprocess.check_output(
            ["docker", "logs", cls.container], stderr=subprocess.STDOUT, text=True
        )
        raise AssertionError(f"Timed out waiting for {description}\n{logs[-4000:]}")

    def send(self, signal, payload):
        request = Request(
            self.endpoint + "/v1/" + signal,
            json.dumps(payload).encode(),
            {"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertFalse(json.load(response).get("partialSuccess"))

    def signal_resources(self, signal, key):
        path = self.directory / (signal + ".json")
        rows = []
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    rows.extend(json.loads(line).get(key, []))
                except json.JSONDecodeError:
                    pass  # File exporter flush in progress.
        return rows

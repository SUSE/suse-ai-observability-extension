"""Exercise the actual strategic merge with kubectl, without a cluster."""

import copy
import json
from pathlib import Path
import subprocess
import unittest


PATCH = Path(__file__).resolve().parents[1] / "sidecar-patch.yaml"


class PatchTest(unittest.TestCase):
    def check_patch(self, legacy):
        ollama = {"name": "ollama", "image": "ollama:test",
                  "resources": {"limits": {"nvidia.com/gpu": 1}},
                  "volumeMounts": [{"name": "models", "mountPath": "/models"}]}
        volumes = [{"name": "models", "persistentVolumeClaim": {"claimName": "ollama-models"}}]
        pod = {"containers": [copy.deepcopy(ollama)], "volumes": copy.deepcopy(volumes)}
        if legacy:
            pod["containers"].append({"name": "ollama-runtime-metrics", "image": "python:3.13-alpine",
                                      "command": ["python3", "-B", "/opt/ollama-metrics/ollama_metrics.py"],
                                      "args": ["--port", "9999"],
                                      "volumeMounts": [{"name": "ollama-runtime-metrics",
                                                        "mountPath": "/opt/ollama-metrics"}]})
            pod["volumes"].append({"name": "ollama-runtime-metrics", "configMap": {"name": "old-source"}})
        deployment = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "ollama"},
                      "spec": {"strategy": {"type": "Recreate"}, "template": {"spec": pod}}}
        # Applying twice must remain safe for both new and previously installed sidecars.
        for _ in range(2):
            result = subprocess.run(["kubectl", "patch", "--local", "-f", "-", "--type", "strategic",
                                     "--patch-file", str(PATCH), "-o", "json"], input=json.dumps(deployment),
                                    text=True, capture_output=True, check=True, timeout=30)
            deployment = json.loads(result.stdout)
            self.assertEqual(deployment["spec"]["strategy"], {"type": "Recreate"})
            pod = deployment["spec"]["template"]["spec"]
            self.assertEqual(pod["volumes"], volumes)
            self.assertEqual(next(c for c in pod["containers"] if c["name"] == "ollama"), ollama)
            sidecar = next(c for c in pod["containers"] if c["name"] == "ollama-runtime-metrics")
            self.assertEqual(sidecar["image"], "registry.suse.com/ai/containers/suse-ai-ollama-exporter:0.1.0")
            for field in ("command", "args", "volumeMounts"):
                self.assertFalse(sidecar.get(field))
            security = sidecar["securityContext"]
            self.assertEqual(security["runAsUser"], 65532)
            self.assertEqual(security["runAsGroup"], 65532)
            self.assertTrue(security["runAsNonRoot"])
            self.assertTrue(security["readOnlyRootFilesystem"])
            self.assertFalse(security["allowPrivilegeEscalation"])
            self.assertEqual(security["capabilities"]["drop"], ["ALL"])

    def test_new_sidecar(self):
        self.check_patch(legacy=False)

    def test_upgrade_from_configmap_sidecar(self):
        self.check_patch(legacy=True)


if __name__ == "__main__":
    unittest.main()

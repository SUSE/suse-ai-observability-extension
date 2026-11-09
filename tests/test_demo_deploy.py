"""Version reservation and forward-only demo lifecycle, without a live backend."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("demo_deploy", ROOT / "scripts/demo-deploy.py")
DEMO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEMO)


class FakeClient:
    def __init__(self):
        self.versions = ["2.0.0"]
        self.instances = []
        self.calls = []
        self.run_calls = []
        self.fail_upload = False
        self.offered = None

    def run(self, command, **kwargs):
        self.run_calls.append(command)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return "source-commit\n"
        if command[:2] == ["task", "stackpack-validate"]:
            source = Path(kwargs["env"]["STACKPACK_SOURCE"])
            self.validated_manifest = (source / "stackpack.yaml").read_bytes()
        if command[:3] == ["sts", "stackpack", "package"]:
            source = Path(command[command.index("-d") + 1])
            target = Path(command[command.index("-f") + 1])
            manifest = (source / "stackpack.yaml").read_bytes()
            assert manifest == self.validated_manifest
            with zipfile.ZipFile(target, "w") as archive:
                archive.writestr("stackpack.yaml", manifest)
        return ""

    def cli(self, *args):
        self.calls.append(args)
        if args[:2] == ("stackpack", "list-versions"):
            return {"versions": [{"version": v} for v in self.versions]}
        if args[:2] == ("stackpack", "list-instances"):
            name = args[args.index("--name") + 1]
            if name == "suse-ai":
                return {"instances": json.loads(json.dumps(self.instances))}
            return {"instances": [{"status": "INSTALLED", "config": {"kubernetes_cluster_name": "suse-ai"}}]}
        if args[:2] == ("stackpack", "upload"):
            with zipfile.ZipFile(args[-1]) as archive:
                manifest = archive.read("stackpack.yaml").decode()
            self.uploaded = next(line[9:] for line in manifest.splitlines() if line.startswith("version: "))
            if self.fail_upload:
                raise RuntimeError("Upload connection lost; server outcome unknown")
            self.versions.append(self.uploaded)
        if args[:2] == ("stackpack", "list"):
            return {"stackpacks": [{"name": "suse-ai", "nextVersion": {"version": self.offered or max(self.versions)}}]}
        if args[:2] in (("stackpack", "install"), ("stackpack", "upgrade")):
            self.instances = [{"id": 123, "status": "INSTALLED", "stackPackVersion": self.uploaded}]


class DemoDeploymentTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name)
        self.client = FakeClient()

    def deploy(self, version="", token_type="service"):
        args = ["demo-deploy.py", "--url", "http://127.0.0.1:18081", "--token-file", "/unused-token",
                "--state-dir", str(self.state), "--version", version, "--token-type", token_type]
        with patch("sys.argv", args), patch.object(DEMO, "Client", return_value=self.client):
            DEMO.main()

    def test_fresh_install_then_upgrade_validates_the_exact_manifest_and_uses_overwrite(self):
        self.deploy()
        self.deploy()
        self.assertEqual(self.client.instances[0]["stackPackVersion"], "3.0.0-dev.2")
        mutations = [c for c in self.client.calls if c[1] in ("install", "upgrade")]
        self.assertEqual([c[1] for c in mutations], ["install", "upgrade"])
        for command in mutations:
            self.assertEqual(command[command.index("--unlocked-strategy") + 1], "overwrite")
        self.assertIn("--stackpack-version", mutations[0])
        self.assertEqual(json.loads((self.state / "versions/3.0.0-dev.2/record.json").read_text())["status"], "installed")

    def test_unknown_upload_outcome_consumes_version_even_when_absent_from_catalog(self):
        self.client.fail_upload = True
        with self.assertRaisesRegex(RuntimeError, "outcome unknown"):
            self.deploy()
        self.client.fail_upload = False
        with self.assertRaises(ValueError):
            self.deploy("3.0.0-dev.1")
        self.deploy()
        self.assertEqual(self.client.instances[0]["stackPackVersion"], "3.0.0-dev.2")
        uploads = [c for c in self.client.calls if c[1] == "upload"]
        self.assertEqual(len(uploads), 2)
        self.assertNotEqual(uploads[0][-1], uploads[1][-1])

    def test_api_authentication_is_carried_into_post_deploy_verification(self):
        self.deploy(token_type="api")
        inspection = next(c for c in self.client.run_calls if c[:2] == ["task", "demo-inspect"])
        self.assertIn("SPIKE_TOKEN_TYPE=api", inspection)
        record = json.loads((self.state / "versions/3.0.0-dev.1/record.json").read_text())
        self.assertEqual(record["tokenType"], "api")

    def test_api_and_service_credentials_use_the_matching_cli_authentication(self):
        token_file = self.state / "test-token"
        token_file.write_text("fixture-token\n")
        for mode, expected in (("service", "--service-token"), ("api", "--api-token")):
            with self.subTest(mode=mode):
                client = DEMO.Client("http://127.0.0.1:18081", token_file, mode)
                with patch.object(client, "run", return_value='{"instances": []}') as run:
                    self.assertEqual(client.cli("stackpack", "list-instances"), {"instances": []})
                command = run.call_args.args[0]
                self.assertIn(expected, command)
                self.assertEqual(command[command.index(expected) + 1], "fixture-token")
                other = "--api-token" if mode == "service" else "--service-token"
                self.assertNotIn(other, command)

    def test_existing_stable_instance_is_rejected_before_any_mutation(self):
        self.client.instances = [{"id": 123, "status": "INSTALLED", "stackPackVersion": "3.0.1"}]
        with self.assertRaisesRegex(ValueError, "no automatic removal"):
            self.deploy()
        self.assertFalse(any(c[1] in ("upload", "install", "upgrade", "uninstall") for c in self.client.calls))

    def test_legacy_instance_upgrades_in_place_without_removal(self):
        self.client.instances = [{"id": 123, "status": "INSTALLED", "stackPackVersion": "2.0.0"}]
        self.deploy()
        self.assertEqual(self.client.instances[0]["id"], 123)
        self.assertEqual(self.client.instances[0]["stackPackVersion"], "3.0.0-dev.1")
        mutations = [c for c in self.client.calls if c[1] in ("install", "upgrade", "uninstall", "downgrade")]
        self.assertEqual([c[1] for c in mutations], ["upgrade"])
        self.assertIn("overwrite", mutations[0])

    def test_unexpected_server_upgrade_target_is_rejected_without_downgrade_or_restore(self):
        self.deploy()
        self.client.offered = "3.0.1"
        with self.assertRaisesRegex(ValueError, "unpinned upgrade"):
            self.deploy()
        self.assertEqual(self.client.instances[0]["stackPackVersion"], "3.0.0-dev.1")
        self.assertFalse(any(c[1] in ("upgrade", "downgrade", "uninstall") for c in self.client.calls))

    def test_version_sequence_obeys_numeric_and_demo_catalog_order(self):
        used = {"3.0.0-dev.2", "3.0.0-dev.10", "2.0.0"}
        self.assertEqual(DEMO.choose_version(used), "3.0.0-dev.20")
        self.assertEqual(DEMO.choose_version({"3.0.0-dev.8"}), "3.0.0-dev.9")
        self.assertEqual(DEMO.choose_version({"3.0.0-dev.90"}), "3.0.0-dev.91")
        self.assertEqual(DEMO.choose_version({"3.0.0-dev.99", "3.0.0-dev.100"}), "3.0.0-dev.990")
        self.assertEqual(DEMO.choose_version({"3.0.0-dev.9", "3.0.0-dev.10000"}), "3.0.0-dev.90000")
        for version in ("3.0.0-dev.0", "3.0.0-dev.01", "3.0.0-dev.9", "3.0.0-dev.10", "3.0.0-dev.11", "3.0.0", "3.0.1-dev.1"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                DEMO.choose_version(used, version)

    def test_digit_boundary_upgrades_without_deleting_or_reusing_versions(self):
        self.client.versions += ["3.0.0-dev.9", "3.0.0-dev.10"]
        self.client.instances = [{"id": 123, "status": "INSTALLED", "stackPackVersion": "3.0.0-dev.9"}]
        self.deploy()
        self.assertEqual(self.client.instances[0]["stackPackVersion"], "3.0.0-dev.90")
        self.assertEqual(self.client.instances[0]["id"], 123)
        mutations = [c for c in self.client.calls if c[1] in ("upload", "upgrade", "downgrade", "uninstall", "delete")]
        self.assertEqual([c[1] for c in mutations], ["upload", "upgrade"])
        self.assertIn("overwrite", mutations[-1])

    def test_demo_connection_rejects_nonlocal_targets_and_embedded_credentials(self):
        for url in ("https://example.org", "http://127.0.0.1.example.org", "http://user:secret@localhost",
                    "http://localhost/api", "http://localhost/?target=other"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                DEMO.demo_url(url)


if __name__ == "__main__":
    unittest.main()

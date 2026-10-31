import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class InstallerTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.state = self.directory / "state.json"
        self.state.write_text('{}')
        fixture = self.directory / "sts"
        shutil.copyfile(ROOT / "tests/fixtures/fake_sts.py", fixture)
        fixture.chmod(0o755)
        archive = self.directory / "suse-ai.sts"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("stackpack.yaml", "name: suse-ai\nversion: 3.0.0\nschemaVersion: '2.0'\n")
        self.env = dict(os.environ, STS_BIN=str(fixture), STS_CONTEXT="fixture",
                        KUBERNETES_CLUSTERS=" alpha, beta ", SUSE_AI_ARCHIVE=str(archive),
                        FAKE_STS_STATE=str(self.state), STS_WAIT_SECONDS="1")
        for key in ("UNINSTALL", "CLEANUP_LEGACY"):
            self.env.pop(key, None)

    def run_init(self, success=True, **env):
        result = subprocess.run(["bash", str(ROOT / "init.sh")], env=dict(self.env, **env),
                                text=True, capture_output=True, timeout=20)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(self.state.read_text())

    def seed(self, version, **extra):
        self.state.write_text(json.dumps({"versions": [version], "instances": {"suse-ai": [
            {"id": 99, "status": "INSTALLED", "config": {}, "stackPackVersion": version}]}, **extra}))

    def test_fresh_install_and_rerun_have_no_second_mutation(self):
        first = self.run_init()
        self.assertEqual(len(first["instances"]["kubernetes-v2"]), 2)
        self.assertEqual(len(first["instances"]["open-telemetry"]), 1)
        self.assertEqual(first["instances"]["suse-ai"][0]["stackPackVersion"], "3.0.0")
        self.assertEqual(sum(c[1] == "upload" for c in first["calls"]), 1)
        second = self.run_init()
        self.assertTrue(all(c[1].startswith("list") for c in second["calls"][len(first["calls"]):]))

    def test_old_schema_instance_uses_upgrade_and_preserves_instance_id(self):
        self.seed("2.2.0")
        result = self.run_init()
        self.assertEqual(result["instances"]["suse-ai"][0]["id"], 99)
        self.assertEqual(result["instances"]["suse-ai"][0]["stackPackVersion"], "3.0.0")
        self.assertEqual(sum(c[1] == "upgrade" for c in result["calls"]), 1)
        self.assertFalse(any(c[1] == "uninstall" for c in result["calls"]))

    def test_existing_catalog_version_is_never_reuploaded(self):
        self.state.write_text(json.dumps({"versions": ["3.0.0"]}))
        result = self.run_init()
        self.assertFalse(any(c[1] == "upload" for c in result["calls"]))

    def test_cli_read_and_upload_failures_do_not_install_ai(self):
        for command in ("list-instances", "list", "list-versions", "upload"):
            with self.subTest(command=command):
                self.state.write_text(json.dumps({"fail": command, "versions": ["2.2.0"]}))
                result = self.run_init(success=False)
                self.assertFalse(result.get("instances", {}).get("suse-ai"))

    def test_failed_upgrade_never_uninstalls(self):
        self.seed("2.2.0", fail="upgrade")
        result = self.run_init(success=False)
        self.assertEqual(result["instances"]["suse-ai"][0]["stackPackVersion"], "2.2.0")
        self.assertFalse(any(c[1] == "uninstall" for c in result["calls"]))

    def test_rejects_newer_install_unexpected_upgrade_target_and_bad_readback(self):
        for version, extra in (("3.0.1", {}), ("2.2.0", {"next": "3.0.1"}),
                               ("2.2.0", {"wrong_result": True})):
            with self.subTest(version=version, extra=extra):
                self.seed(version, **extra)
                self.run_init(success=False)

    def test_same_version_error_is_not_success(self):
        self.seed("3.0.0")
        state = json.loads(self.state.read_text())
        state["instances"]["suse-ai"][0]["status"] = "ERROR"
        self.state.write_text(json.dumps(state))
        self.run_init(success=False)

    def test_uninstall_is_idempotent(self):
        self.seed("3.0.0")
        first = self.run_init(UNINSTALL="true")
        second = self.run_init(UNINSTALL="true")
        self.assertEqual(second["instances"]["suse-ai"], [])
        self.assertTrue(all(c[1].startswith("list") for c in second["calls"][len(first["calls"]):]))

    def test_empty_cluster_names_fail_before_mutation(self):
        for clusters in ("", "alpha,", "alpha,,beta", "alpha, ,beta"):
            self.run_init(success=False, KUBERNETES_CLUSTERS=clusters)
            self.assertEqual(json.loads(self.state.read_text()), {})

    def test_explicit_legacy_cleanup_preserves_unrelated_autosync_and_menus(self):
        self.state.write_text(json.dumps({
            "menus": [{"id": 1, "name": "GenAI Observability"}, {"id": 2, "name": "SUSE AI"}],
            "instances": {"autosync": [
                {"id": 10, "config": {"sts_instance_type": "suse-ai", "sts_instance_url": "alpha"}},
                {"id": 11, "config": {"sts_instance_type": "other", "sts_instance_url": "alpha"}},
                {"id": 12, "config": {"sts_instance_type": "suse-ai", "sts_instance_url": "elsewhere"}},
            ]}}))
        result = self.run_init(CLEANUP_LEGACY="true")
        self.assertEqual([menu["id"] for menu in result["menus"]], [2])
        self.assertEqual([item["id"] for item in result["instances"]["autosync"]], [11, 12])

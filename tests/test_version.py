import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VersionRegressions(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        (self.directory / "scripts").mkdir()
        (self.directory / "stackpack/suse-ai").mkdir(parents=True)
        self.script = self.directory / "scripts/bump-version.py"
        shutil.copyfile(ROOT / "scripts/bump-version.py", self.script)
        self.conf = self.directory / "stackpack/suse-ai/stackpack.yaml"
        self.original = 'name: suse-ai\nversion: 3.0.0\n'
        self.conf.write_text(self.original)
        self.git("init", "--quiet")
        self.git("add", ".")
        self.git("-c", "user.name=Regression Test", "-c", "user.email=test@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Fixture")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.directory, check=True, capture_output=True)

    def bump(self, target=""):
        return subprocess.run(["python3", str(self.script)], capture_output=True, text=True,
                              env=dict(os.environ, TARGET_VERSION=target), timeout=10)

    def test_increments_and_explicit_higher_version(self):
        self.assertEqual(self.bump().returncode, 0)
        self.assertIn('version: 3.0.1', self.conf.read_text())
        self.assertEqual(self.bump("3.0.10").returncode, 0)
        self.assertEqual(self.conf.read_text(), self.original.replace("3.0.0", "3.0.10"))

    def test_rejects_reuse_downgrades_and_invalid_versions(self):
        self.git("tag", "v3.0.3-rc0")
        self.git("tag", "v3.0.4")
        for target in ("3.0.0", "2.9.9", "03.0.10", "3.0.10;false", "3.0.3", "3.0.4"):
            with self.subTest(target=target):
                self.assertNotEqual(self.bump(target).returncode, 0)
                self.assertEqual(self.conf.read_text(), self.original)

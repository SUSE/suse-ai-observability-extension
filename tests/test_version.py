import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from support import ROOT


class VersionRegressions(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        (self.directory / "scripts").mkdir()
        (self.directory / "stackpack/suse-ai").mkdir(parents=True)
        self.script = self.directory / "scripts/bump-version.py"
        shutil.copyfile(ROOT / "scripts/bump-version.py", self.script)
        self.conf = self.directory / "stackpack/suse-ai/stackpack.conf"
        self.original = 'name = "suse-ai"\nversion = "2.2.0"\n'
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
        self.assertIn('version = "2.2.1"', self.conf.read_text())
        self.assertEqual(self.bump("2.2.10").returncode, 0)
        self.assertEqual(self.conf.read_text(), self.original.replace("2.2.0", "2.2.10"))

    def test_rejects_reuse_downgrades_and_invalid_versions(self):
        self.git("tag", "v2.2.3-rc0")
        self.git("tag", "v2.2.4")
        for target in ("2.2.0", "2.1.9", "02.2.10", "2.2.10;false", "2.2.3", "2.2.4"):
            with self.subTest(target=target):
                self.assertNotEqual(self.bump(target).returncode, 0)
                self.assertEqual(self.conf.read_text(), self.original)

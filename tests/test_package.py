import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class PackageTest(unittest.TestCase):
    def test_rebuild_after_modes_timestamps_timezone_and_zip_options_change(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / "source"
            shutil.copytree(ROOT / "stackpack/suse-ai", source)
            output = directory / "dist"
            command = ["bash", str(ROOT / "scripts/package-stackpack.sh"), str(source), str(output)]
            subprocess.run(command, check=True, capture_output=True)
            archive = next(output.glob("*.sts"))
            original = archive.read_bytes()
            for path in source.rglob("*"):
                if path.is_file():
                    path.chmod(0o755)
                    os.utime(path, (1800000000, 1800000000))
            (source / "stale.sts").write_text("must not be packaged")
            subprocess.run(command, check=True, capture_output=True,
                           env=dict(os.environ, TZ="Pacific/Auckland", ZIPOPT="-9"))
            self.assertEqual(original, archive.read_bytes())
            self.assertIn(hashlib.sha256(original).hexdigest(), (output / "SHA256SUMS").read_text())
            with zipfile.ZipFile(archive) as package:
                self.assertEqual(package.namelist(), sorted(package.namelist()))
                self.assertNotIn("stale.sts", package.namelist())
                for entry in package.infolist():
                    self.assertEqual(entry.date_time, (1980, 1, 1, 0, 0, 0))
                    self.assertEqual(entry.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(entry.extra, b"")
                    self.assertEqual(package.read(entry), (source / entry.filename).read_bytes())

    @unittest.skipUnless(shutil.which("sts"), "CLI comparison requires sts")
    def test_file_contents_equal_sts_package(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            subprocess.run(["bash", str(ROOT / "scripts/package-stackpack.sh"),
                            str(ROOT / "stackpack/suse-ai"), str(directory / "dist")],
                           check=True, capture_output=True)
            subprocess.run(["sts", "stackpack", "package", "-d", str(ROOT / "stackpack/suse-ai"),
                            "-f", str(directory / "cli.sts")], check=True, capture_output=True,
                           env=dict(os.environ, STS_EXPERIMENTAL_STACKPACKS="1"))
            with zipfile.ZipFile(next((directory / "dist").glob("*.sts"))) as ours, \
                    zipfile.ZipFile(directory / "cli.sts") as cli:
                contents = lambda archive: {e.filename: archive.read(e) for e in archive.infolist() if not e.is_dir()}
                self.assertEqual(contents(ours), contents(cli))

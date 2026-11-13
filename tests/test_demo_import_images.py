"""Check that an exec stream cannot keep the image importer waiting for EOF."""

import importlib.util
from pathlib import Path
import subprocess
import unittest


SPEC = importlib.util.spec_from_file_location(
    "demo_import_images", Path(__file__).resolve().parents[1] / "scripts/demo-import-images.py"
)
IMPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORT)


class BoundedImageStreamTest(unittest.TestCase):
    def test_reader_finishes_while_exec_stdin_is_still_open(self):
        with subprocess.Popen(IMPORT.bounded_stdin(["cat"], 7),
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as process:
            process.stdin.write(b"archive")
            process.stdin.flush()
            self.assertEqual(process.wait(timeout=5), 0)
            self.assertFalse(process.stdin.closed)
            self.assertEqual(process.stdout.read(), b"archive")

    def test_importer_failure_is_returned(self):
        result = subprocess.run(IMPORT.bounded_stdin(["sh", "-c", "cat >/dev/null; exit 9"], 3),
                                input=b"zip", capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 9)

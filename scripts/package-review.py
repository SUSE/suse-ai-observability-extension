"""Build an unpublished review version without editing the release checkout."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


root = Path(__file__).resolve().parents[1]
version = os.environ["REVIEW_VERSION"]
if not re.fullmatch(r"\d+\.\d+\.\d+-dev(?:[.-][0-9A-Za-z.-]+)?", version):
    raise SystemExit("REVIEW_VERSION must be a dev version, for example 3.0.2-dev.20261105.1")
output = Path(os.environ["REVIEW_OUTPUT"]).resolve()
output.mkdir(parents=True, exist_ok=True)
archive = output / ("suse-ai-" + version + ".sts")
if archive.exists():
    raise SystemExit("Review archive already exists; choose a fresh REVIEW_VERSION")
with tempfile.TemporaryDirectory(prefix="suse-ai-review-") as directory:
    pack = Path(directory) / "suse-ai"
    shutil.copytree(root / "stackpack/suse-ai", pack)
    manifest = pack / "stackpack.yaml"
    source = manifest.read_text()
    source, count = re.subn(r"^version:.*$", "version: " + version, source, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit("Expected exactly one top-level StackPack version")
    manifest.write_text(source)
    # The stable release packager intentionally rejects prerelease versions.
    subprocess.run(["sts", "stackpack", "package", "-d", str(pack), "-f", str(archive)], check=True)
    print(hashlib.sha256(archive.read_bytes()).hexdigest(), archive)

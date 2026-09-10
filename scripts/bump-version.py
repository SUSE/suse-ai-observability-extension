#!/usr/bin/env python3
"""Increment a stable StackPack version without reusing an existing release tag."""

import os
from pathlib import Path
import re
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / "stackpack/suse-ai/stackpack.conf"
    content = path.read_text()
    match = re.search(r'^version = "(\d+\.\d+\.\d+)"$', content, re.MULTILINE)
    if not match:
        raise SystemExit("Expected one stable major.minor.patch version in stackpack.conf")
    current = tuple(map(int, match[1].split(".")))
    target = os.environ.get("TARGET_VERSION") or ".".join(
        map(str, (*current[:2], current[2] + 1))
    )
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", target):
        raise SystemExit("TARGET_VERSION must be a stable major.minor.patch version")
    if tuple(map(int, target.split("."))) <= current:
        raise SystemExit("TARGET_VERSION must be greater than the current version")
    tags = subprocess.check_output(
        ["git", "tag", "--list", target, f"v{target}", f"v{target}-*"], cwd=root, text=True
    ).strip()
    if tags:
        raise SystemExit(f"Version {target} has already been used by a release tag: {tags}")
    path.write_text(content[:match.start(1)] + target + content[match.end(1):])
    print(f"StackPack version updated to {target}")


if __name__ == "__main__":
    main()

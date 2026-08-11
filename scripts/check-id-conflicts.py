#!/usr/bin/env python3
"""Verify that numeric `id:` declarations across StackPack .sty templates are unique.

StackState template IDs (ComponentTypes, MetricBindings, ViewTypes, Monitors,
Syncs, etc.) are partitioned into per-type ranges and must be globally unique
across every .sty file. A duplicate almost always means two nodes were assigned
the same ID by mistake -- a common hazard after merging two branches that each
added new nodes. Exits non-zero (1) when a conflict is found.

Usage: check-id-conflicts.py [ROOT]   (ROOT defaults to ./stackpack)
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

# Matches both mapping fields ("    id: -5001") and list-item fields
# ("  - id: -640"). Anchoring after the optional list marker prevents keys such
# as "identifier:" from matching.
ID_RE = re.compile(r"^\s*(?:-\s+)?id\s*:\s*(-?\d+)\b")


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("stackpack")
    if not root.exists():
        print(f"error: path '{root}' does not exist", file=sys.stderr)
        return 2

    locations: dict[str, list[str]] = defaultdict(list)
    for sty in sorted(root.rglob("*.sty")):
        text = sty.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            m = ID_RE.match(line)
            if m:
                locations[m.group(1)].append(f"{sty}:{lineno}")

    if not locations:
        print(f"No id: declarations found under '{root}' -- nothing to check.")
        return 0

    total = sum(len(locs) for locs in locations.values())
    conflicts = {i: locs for i, locs in locations.items() if len(locs) > 1}

    if conflicts:
        print(f"Found {len(conflicts)} duplicate id(s) across {total} declarations:\n")
        for i in sorted(conflicts, key=int):
            print(f"  id {i} is declared {len(conflicts[i])} times:")
            for loc in conflicts[i]:
                print(f"    - {loc}")
            print()
        print("Each StackPack id must be globally unique. Reassign the "
              "colliding ids to free values in their type's range.")
        return 1

    print(f"OK: {total} id declarations, all {len(locations)} unique.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Render an offline review gallery from the actual SVG sources."""

import argparse
import base64
import html
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cards = []
    for path in sorted((ROOT / "stackpack/suse-ai/icons/outline").glob("*.svg")):
        title = ET.fromstring(path.read_bytes()).find("{http://www.w3.org/2000/svg}title").text
        src = "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode()
        cards.append('<article><div class="sizes">'
                     + ''.join(f'<img src="{src}" width="{size}" height="{size}" alt="{html.escape(title)}">'
                               for size in (80, 40, 20))
                     + f'</div><h2>{html.escape(title)}</h2><code>{path.name}</code></article>')
    content = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>SUSE AI icon family</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f7f5;color:#173d32;font:16px/1.6 system-ui,sans-serif}
main{max-width:1280px;margin:auto;padding:48px}h1{font-size:36px;margin:0 0 8px;font-weight:650}
p{max-width:900px;color:#3b554b;margin:8px 0 30px}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
article{background:white;border:1px solid #d7e4dc;border-radius:12px;padding:24px;min-width:0}
.sizes{display:flex;align-items:center;gap:18px;height:100px}h2{font-size:16px;margin:16px 0 4px}
code{font-size:12px;color:#496057}footer{margin-top:28px;color:#496057}
@media(max-width:1000px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:700px){main{padding:24px}.grid{grid-template-columns:repeat(2,1fr)}}
</style><main><h1>SUSE AI · outline family</h1>
<p>Original SVG sources at 80, 40 and 20 pixels. A 40 × 40 grid, one 2-unit round stroke,
SUSE green #30BA78 and pale green #E4F5EB. Each symbol has a text label for identification.</p>
<div class="grid">''' + "\n".join(cards) + '''</div>
<footer>17 original vector assets · Apache-2.0 · Source and role mapping in icons/outline/LICENSES.md</footer>
</main></html>'''
    with args.output.open("x") as handle:
        handle.write(content)
    print(args.output)


if __name__ == "__main__":
    main()

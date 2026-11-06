#!/usr/bin/env python3
"""Check native dashboard assets before validation or lane-B integration."""

import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import promql_parser as promql
import yaml

from build_dashboards import build

ROOT = Path(__file__).resolve().parents[2]


def selectors(expression):
    if isinstance(expression, promql.VectorSelector):
        yield expression
    elif isinstance(expression, promql.MatrixSelector):
        yield expression.vector_selector
    else:
        for field in ("expr", "lhs", "rhs", "param"):
            child = getattr(expression, field, None)
            if child is not None:
                yield from selectors(child)
        for child in getattr(expression, "args", []):
            yield from selectors(child)


def main():
    allowlist = json.loads((ROOT / "knowledge/DASHBOARD_METRIC_INVENTORY_20261105.json").read_text())["metrics"]
    expected = build()
    used = set()
    query_count = 0
    for path in sorted((ROOT / "stackpack/suse-ai/settings/dashboards").glob("*.sty")):
        data = yaml.safe_load(path.read_text())
        assert data == expected.pop(path.stem), f"Generated asset drift: {path}"
        node, = data["nodes"]
        assert node["_type"] == "Dashboard" and node["identifier"].endswith(":" + path.stem)
        spec = node["dashboard"]["spec"]
        panels = spec["panels"]
        assert panels["about"]["spec"]["display"]["name"] == "About / How to read"
        assert len(panels) <= 12, f"Too many panels: {path}"
        refs = []
        occupied = set()
        for item in spec["layouts"][0]["spec"]["items"]:
            key = item["content"]["$ref"].removeprefix("#/spec/panels/")
            assert key in panels and key not in refs, f"Bad layout reference: {path}:{key}"
            refs.append(key)
            assert 0 <= item["x"] < item["x"] + item["width"] <= 24
            for x in range(item["x"], item["x"] + item["width"]):
                for y in range(item["y"], item["y"] + item["height"]):
                    assert (x, y) not in occupied, f"Overlapping panels: {path}:{key}"
                    occupied.add((x, y))
        assert set(refs) == set(panels)
        kinds = [value["spec"]["plugin"]["kind"] for value in panels.values()]
        assert kinds.count("StatChart") == 4 and kinds.count("TimeSeriesChart") >= 4
        for key, value in panels.items():
            panel = value["spec"]
            queries = [q["spec"]["plugin"]["spec"]["query"] for q in panel["queries"]]
            if panel["plugin"]["kind"] == "TimeSeriesChart":
                assert len(queries) == 2 and "offset 1h" in queries[1], f"No comparison: {path}:{key}"
                assert queries[1].replace(" offset 1h", "") == queries[0], f"Mismatched comparison: {path}:{key}"
                assert panel["plugin"]["spec"]["visual"]["connectNulls"] is False
            for query in queries:
                query_count += 1
                assert "or vector(0)" not in query, f"Unconditional missing-data zero: {path}:{key}"
                for vector in selectors(promql.parse(query.replace("${cluster}", "fixture"))):
                    assert vector.name in allowlist, f"Unverified metric: {vector.name}"
                    assert any(m.name == "k8s_cluster_name" and m.value == "fixture" for m in vector.matchers.matchers)
                    used.add(vector.name)
        for variable in spec["variables"]:
            assert set(variable["spec"]["plugin"]["spec"]["matchers"]) <= set(allowlist)
        text = panels["about"]["spec"]["plugin"]["spec"]["text"]
        assert "ai-factory:" not in text
        assert len(re.findall(r"/#/dashboards/urn:stackpack:suse-ai:shared:dashboard:", text)) == 3
    assert not expected, "Missing generated dashboards"

    icon_dir = ROOT / "stackpack/suse-ai/icons/outline"
    files = sorted(icon_dir.glob("*.svg"))
    assert len(files) == 17
    licenses = (icon_dir / "LICENSES.md").read_text()
    ns = {"s": "http://www.w3.org/2000/svg"}
    for path in files:
        root = ET.fromstring(path.read_bytes())
        assert root.attrib["viewBox"] == "0 0 40 40"
        assert root.attrib["width"] == root.attrib["height"] == "16"
        assert root.find("s:title", ns).text and root.find("s:desc", ns).text
        assert root.find("s:rect", ns).attrib["fill"] == "#E4F5EB"
        group = root.find("s:g", ns)
        assert group.attrib["stroke"] == "#30BA78" and group.attrib["stroke-width"] == "2"
        assert group.attrib["fill"] == "none"
        for element in root.iter():
            assert element.tag.split("}")[-1] in {"svg", "title", "desc", "rect", "g", "path", "circle", "ellipse"}
            assert not any("href" in name or name.startswith("on") for name in element.attrib)
            if "stroke-width" in element.attrib:
                assert element.attrib["stroke-width"] == "2"
        assert "SPDX-License-Identifier: Apache-2.0" in path.read_text()
        assert "[" + path.name + "](" + path.name + ")" in licenses
    print(f"4 native dashboards; {query_count} parsed, scoped queries; {len(used)} verified metric names; 17 SVGs: passed")


if __name__ == "__main__":
    main()

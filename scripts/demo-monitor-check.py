"""Exercise installed monitor functions using preview-only controlled query inputs.

Does not upload settings, ingest telemetry or persist test health states. Pair this
with test_monitors.py, which evaluates each original query against metric fixtures.
"""

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import yaml


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo_deploy", ROOT / "scripts/demo-deploy.py")
deployment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deployment)


class Loader(yaml.SafeLoader):
    pass


for tag in ("!include", "!icon", "!resource"):
    Loader.add_constructor(tag, lambda loader, node: loader.construct_scalar(node))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", type=deployment.demo_url, required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--token-type", choices=("service", "api"), default="service")
    parser.add_argument("--monitors", default="", help="Comma-separated monitor identifier suffixes; default is all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True)
    client = deployment.Client(args.url, args.token_file, args.token_type)
    token_header = "X-API-Key" if args.token_type == "service" else "X-API-Token"

    def save(name, data):
        (args.output / (name + ".json")).write_text(json.dumps(data, indent=2) + "\n")
        return data

    def api(path, body=None):
        request = Request(args.url + path, None if body is None else json.dumps(body).encode(),
                          {token_header: client.token, "Content-Type": "application/json"})
        with urlopen(request, timeout=90) as response:
            return json.load(response)

    def snapshot(query):
        return api("/api/snapshot", {"query": query, "queryVersion": "0.0.1", "metadata": {
            "groupingEnabled": False, "showIndirectRelations": False, "minGroupSize": 0,
            "groupedByLayer": False, "groupedByDomain": False, "groupedByRelation": False,
            "autoGrouping": False, "connectedComponents": False, "neighboringComponents": False,
            "showFullComponent": True}})["viewSnapshotResponse"]["components"]

    def tags(component):
        return dict(value.split(":", 1) for value in component["tags"] if ":" in value)

    source = {}
    for path in (ROOT / "stackpack/suse-ai/settings").rglob("*.sty"):
        for node in yaml.load(path.read_text(), Loader=Loader)["nodes"]:
            if node["_type"] == "Monitor":
                source[node["identifier"]] = node
    installed = save("monitors-before", client.cli("monitor", "list"))["monitors"]
    baseline = json.loads(args.baseline.read_text())["monitors"]
    ids = lambda nodes: {n["identifier"]: n["id"] for n in nodes}
    assert ids(baseline).items() <= ids(installed).items(), "Monitor identity changed from the supplied baseline"
    monitors = [m for m in installed if m["identifier"] in source]
    assert len(monitors) == len(source)
    if args.monitors:
        requested = set(args.monitors.split(","))
        monitors = [m for m in monitors if m["identifier"].rsplit(":", 1)[-1] in requested]
        assert {m["identifier"].rsplit(":", 1)[-1] for m in monitors} == requested, "Unknown requested monitor"
    components = snapshot('label = "stackpack:suse-ai" or type = "node"')
    service = next(c for c in components if c["identifiers"][0] ==
                   "urn:opentelemetry:namespace/suse-private-ai:service/ollama")
    node = next(c for c in components if c["typeIdentifier"].endswith(":node")
                and tags(c).get("cluster-name") == "suse-ai")
    topological = {}
    for monitor in monitors:
        item = source[monitor["identifier"]]
        if "queries" in item["arguments"]:
            query = item["arguments"]["queries"]["topologyQuery"]
            if query not in topological:
                matches = snapshot(query)
                assert matches, "Preview requires an existing component for " + query
                topological[query] = matches[0]

    def check(monitor):
        key = monitor["identifier"].rsplit(":", 1)[-1]
        definition = source[monitor["identifier"]]
        settings = definition["arguments"]
        if definition["function"].endswith(":derived-state-monitor"):
            save(key + "-live-run", client.cli("monitor", "run", "--identifier", monitor["identifier"]))
            print(key + ": live derived-health dry run captured", flush=True)
            return {"identifier": monitor["identifier"], "id": monitor["id"],
                    "previews": [], "verification": "live-derived-health-dry-run"}
        threshold = settings["threshold"]
        margin = max(1, abs(threshold) * 0.1)
        failing, recovering = {
            "GT": (threshold + margin, threshold),
            "GTE": (threshold, threshold - margin),
            "LT": (threshold - margin, threshold),
        }[settings["comparator"]]
        is_topological = "queries" in settings
        component = (topological[settings["queries"]["topologyQuery"]] if is_topological
                     else node if key == "nvidia-xid-errors" else service)
        component_tags = tags(component)
        dimensions = {"service_namespace": component_tags.get("service.namespace", "suse-private-ai"),
                      "service_name": component_tags.get("service.name", "ollama"),
                      "model_name": component_tags.get("vllm.model.name", "preview-model"),
                      "model": component_tags.get("ollama.model.name", "preview-model"),
                      "gen_ai_request_model": component_tags.get("gen_ai.request.model", "preview-model"),
                      "k8s_cluster_name": "suse-ai", "k8s_node_name": component["name"]}
        results = []
        for state, value in (("failing", failing), ("recovering", recovering), ("no-data", None)):
            query = "vector(1) unless vector(1)" if value is None else "vector(" + str(value) + ")"
            for label, label_value in dimensions.items():
                query = "label_replace(" + query + "," + json.dumps(label) + "," + json.dumps(label_value) + ',"","")'
            arguments = copy.deepcopy(monitor["arguments"])
            metric = next(a for a in arguments if a["_type"] in
                          ("ArgumentPromQLMetricVal", "ArgumentTopologyPromQLMetricVal"))
            if is_topological:
                metric["value"]["topologyQuery"] = 'identifier = "' + component["identifiers"][0] + '"'
                metric["value"]["promQLQuery"] = query
            else:
                metric["value"]["query"] = query
            body = {"arguments": arguments}
            save(key + "-" + state + "-input", {"component": component["identifiers"][0], "query": query})
            route = "/api/monitors/" + quote(monitor["identifier"], safe="") + "/preview"
            summary = save(key + "-" + state, api(route, body))
            checks = save(key + "-" + state + "-checks", api(route + "/checkStates", body))
            assert not summary["errors"], (key, state, summary)
            expected = None if value is None else settings["failureState"] if state == "failing" else "CLEAR"
            assert summary["healthStatesCount"] == (0 if expected is None else 1), (key, state, summary)
            assert [c["healthState"] for c in checks["states"]] == ([] if expected is None else [expected]), (key, state, checks)
            results.append({"state": state, "health": expected, "checkCount": len(checks["states"])})
        # Original installed query, still dry-run: capture real production inputs separately.
        save(key + "-live-run", client.cli("monitor", "run", "--identifier", monitor["identifier"]))
        print(key + ": failing / recovering / no-data previews passed", flush=True)
        return {"identifier": monitor["identifier"], "id": monitor["id"], "previews": results}

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, monitors))
    after = save("monitors-after", client.cli("monitor", "list"))["monitors"]
    assert ids(after) == ids(installed)
    save("summary", {"monitors": results, "preservedMonitorIds": len(baseline),
                     "persistedTestHealthStates": False, "ingestedTestTelemetry": False})
    previewed = sum(bool(item["previews"]) for item in results)
    print(f"Verified {previewed} threshold monitors with 3 preview states each; "
          f"captured {len(results) - previewed} derived-health runs; no test states persisted")


if __name__ == "__main__":
    main()

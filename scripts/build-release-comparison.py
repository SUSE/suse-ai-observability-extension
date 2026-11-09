"""Stage an isolated release comparison; never upload or alter the source tag.

The released settings and their native OTel companion are namespaced together.
Telemetry attributes and metric queries are preserved. Kubernetes node metadata
is captured from actual nodes; live DCGM observations keep their comparison
identities alive. A dependency links each comparison node to its observed node.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
NAME = "suse-ai-v300"
LABEL = "SUSE AI 3.0 release"
PREFIX = "urn:stackpack:" + NAME + ":"
TYPE_PREFIX = "v3.0 release "
TYPES = ("otel service instance", "otel service", "otel namespace", "service namespace (otel)", "genai served model",
         "genai model usage", "genai agent", "genai database dependency", "pod", "node",
         "host", "function", "task")


class Asset(str):
    def __new__(cls, value, tag):
        instance = str.__new__(cls, value)
        instance.tag = tag
        return instance


class Loader(yaml.SafeLoader):
    pass


class Dumper(yaml.SafeDumper):
    pass


for asset_tag in ("!icon", "!include", "!resource"):
    Loader.add_constructor(asset_tag, lambda loader, node: Asset(loader.construct_scalar(node), node.tag))
Dumper.add_representer(Asset, lambda dumper, value: dumper.represent_scalar(value.tag, str(value)))


def read(path):
    return yaml.load(path.read_text(), Loader=Loader)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(value, Dumper=Dumper, sort_keys=False, width=110))


def rewrite_text(value):
    value = re.sub(r"urn:stackpack:open-telemetry:([^:]+):", PREFIX + r"\1:companion-", value)
    value = value.replace("urn:stackpack:suse-ai:", PREFIX)
    value = value.replace("urn:opentelemetry:", "urn:" + NAME + ":otel:")
    value = value.replace("urn:suse-ai:", "urn:" + NAME + ":")
    # Kubernetes namespace/cluster links are shared read-only resources. Only
    # node/pod identities are duplicated, including additionalIdentifiers.
    if ":pod/" in value or ":node/" in value:
        value = value.replace("urn:kubernetes:/", "urn:" + NAME + ":kubernetes:/")
    value = value.replace("stackpack:open-telemetry", "stackpack:" + NAME + "-otel")
    value = re.sub(r"stackpack:suse-ai(?![A-Za-z0-9-])", "stackpack:" + NAME, value)
    if value == "'open-telemetry'":
        value = "'" + NAME + "-otel'"
    if value == "'suse-ai'":
        value = "'" + NAME + "'"
    # Native mapping output has tags but cannot set arbitrary legacy properties.
    # Read the same captured host identity through a tag, preserving the exact
    # resulting GPU host PromQL rather than leaving the comparison unbound.
    value = re.sub(r"'sts_host'\s+in\s+properties\s*\?\s*properties\.sts_host\s*:\s*''",
                   "tags.singleValue('suse.ai.comparison.sts_host')", value)
    for original in TYPES:
        for quote in ('"', "'"):
            value = value.replace(quote + original + quote, quote + TYPE_PREFIX + original + quote)
        if value == original:
            value = TYPE_PREFIX + original
    return value


def rewrite(value, companion=False):
    if isinstance(value, Asset):
        return Asset(("companion/" if companion else "") + str(value), value.tag)
    if isinstance(value, str):
        return rewrite_text(value)
    if isinstance(value, list):
        return [rewrite(item, companion) for item in value]
    if isinstance(value, dict):
        return {key: rewrite(item, companion) for key, item in value.items()}
    return value


def isolate_node(node, companion=False):
    node = rewrite(node, companion)
    if companion and node["_type"] == "OtelComponentMapping":
        # The comparison adapter also sees resource records without Kubernetes
        # or service namespace metadata. Preserve ordinary companion defaults
        # instead of evaluating a missing key. Released SUSE settings are not
        # changed by these companion-only guards.
        for variable in node.get("vars", []):
            if variable["name"] == "namespace":
                variable["value"] = ("'service.namespace' in resource.attributes && "
                                     "resource.attributes['service.namespace'] != '' ? "
                                     "resource.attributes['service.namespace'] : 'default'")
            elif variable["name"] == "clusterName":
                variable["value"] = ("'k8s.cluster.name' in resource.attributes ? "
                                     "resource.attributes['k8s.cluster.name'] : ''")
    if node["_type"] == "MainMenuGroup":
        node["name"] = LABEL
    if node["_type"] == "Monitor":
        node["name"] = "3.0 release: " + node["name"]
    if node["_type"] == "ComponentPresentation":
        menu = node.get("presentation", {}).get("overview", {}).get("mainMenu")
        if menu and companion:
            del node["presentation"]["overview"]["mainMenu"]
        elif menu:
            menu["group"] = LABEL
    return node


def export_source(ref, output):
    revision = subprocess.check_output(["git", "rev-parse", ref + "^{commit}"], cwd=ROOT, text=True).strip()
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", revision,
                                     "stackpack/suse-ai"], cwd=ROOT, text=True).splitlines()
    if "stackpack/suse-ai/stackpack.yaml" not in paths:
        raise ValueError("The selected release is not a native StackPack")
    for name in paths:
        path = output / Path(name).relative_to("stackpack/suse-ai")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(subprocess.check_output(["git", "show", revision + ":" + name], cwd=ROOT))
    return revision


def node_bridge(snapshot, output):
    nodes = []
    observed = []
    pod_icon = next((component.get("iconbase64", "")
                     for component in snapshot["viewSnapshotResponse"]["components"]
                     if component["typeIdentifier"].endswith("component-type:pod")), "")
    if not pod_icon.startswith("data:image/png;base64,"):
        raise ValueError("Capture a native Kubernetes pod icon with the topology snapshot")
    (output / "icons/companion/observed-pod.png").write_bytes(base64.b64decode(pod_icon.split(",", 1)[1]))
    for component in snapshot["viewSnapshotResponse"]["components"]:
        if not component["typeIdentifier"].endswith("component-type:node"):
            continue
        tags = dict(tag.split(":", 1) for tag in component.get("tags", []) if ":" in tag)
        if tags.get("nvidia.com/gpu.present") != "true":
            continue
        name, cluster = component["name"], tags["cluster-name"]
        # Retain only metadata needed by the released node presentation, not
        # health samples, credentials, mutable pod data or arbitrary config.
        tags = {k: v for k, v in tags.items() if k.startswith(("nvidia.com/", "feature.node.kubernetes.io/system-os_release.", "kubernetes.io/"))
                or k in ("cluster-name", "source-name", "os", "os-version")}
        tags["stackpack"] = NAME
        host = component.get("properties", {}).get("sts_host")
        if not isinstance(host, str) or not host:
            raise ValueError("Capture the actual sts_host identity for GPU node " + name)
        tags["suse.ai.comparison.sts_host"] = host
        original = "urn:kubernetes:/" + cluster + ":node/" + name
        identifier = original.replace("urn:kubernetes:/", "urn:" + NAME + ":kubernetes:/")
        condition = ("'k8s.cluster.name' in resource.attributes && 'k8s.node.name' in resource.attributes && "
                     "resource.attributes['k8s.cluster.name'] == " + json.dumps(cluster) +
                     " && resource.attributes['k8s.node.name'] == " + json.dumps(name))
        inputs = {"signal": ["METRICS"], "resource": {"condition": condition,
                  "scope": {"metric": {"condition": "metric.name.startsWith('DCGM_')", "action": "'CREATE'"}}}}
        slug = hashlib.sha256(original.encode()).hexdigest()[:16]
        nodes.append({"_type": "OtelComponentMapping", "identifier": PREFIX + "otel-component-mapping:comparison-node-" + slug,
                      "name": "Release comparison node " + name, "input": inputs,
                      "output": {"identifier": json.dumps(identifier), "name": json.dumps(name),
                                 "typeName": json.dumps(TYPE_PREFIX + "node"),
                                 "required": {"tags": [{"source": json.dumps(tags), "pattern": "^(.*)$", "target": "${1}"}]}},
                      "rank": {"specificity": 150}, "expireAfter": 900000})
        nodes.append({"_type": "OtelRelationMapping", "identifier": PREFIX + "otel-relation-mapping:comparison-node-observed-" + slug,
                      "name": "Release comparison uses observed node " + name, "input": inputs,
                      "output": {"sourceId": json.dumps(identifier), "targetId": json.dumps(original),
                                 "typeName": "'comparison-of'", "dependencyType": "'HIERARCHICAL'"},
                      "expireAfter": 900000})
        observed.append({"name": name, "cluster": cluster, "sourceId": component["id"], "metadata": tags})
        if not (output / "icons/companion/observed-node.png").exists():
            icon = component.get("iconbase64", "")
            if icon.startswith("data:image/png;base64,"):
                (output / "icons/companion/observed-node.png").write_bytes(base64.b64decode(icon.split(",", 1)[1]))
    if not observed:
        raise ValueError("Capture the actual GPU nodes before building this comparison")
    nodes.append({"_type": "Monitor", "name": "3.0 comparison: observed node health",
                  "identifier": PREFIX + "monitor:comparison-observed-node-health", "intervalSeconds": 30,
                  "status": "ENABLED", "function": "urn:stackpack:common:monitor-function:derived-state-monitor",
                  "arguments": {"componentTypes": TYPE_PREFIX + "node"}})
    nodes.append({"_type": "ComponentPresentation", "name": "Release comparison node source",
                  "identifier": PREFIX + "component-presentation:comparison-node-source",
                  "binding": {"_type": "ComponentPresentationQueryBinding", "query": 'type = "' + TYPE_PREFIX + 'node"'},
                  "rank": {"specificity": 1}, "presentation": {"icon": Asset("companion/observed-node.png", "!icon")}})
    nodes.append({"_type": "ComponentPresentation", "name": "Release comparison observed Kubernetes pod",
                  "identifier": PREFIX + "component-presentation:comparison-pod-source",
                  "binding": {"_type": "ComponentPresentationQueryBinding", "query": 'type = "' + TYPE_PREFIX + 'pod"'},
                  "rank": {"specificity": 1}, "presentation": {
                      "icon": Asset("companion/observed-pod.png", "!icon"), "highlight": {"fields": [{
                      "fieldId": "suse_ai_comparison_observed_pod", "title": "Observed pod", "order": 85,
                      "projection": {"_type": "ComponentLinkProjection", "name": "name",
                                     "identifier": "'urn:kubernetes:/' + tags.singleValue('cluster-name') + ':' + tags.singleValue('namespace') + ':pod/' + name"}}]}}})
    write(output / "settings/comparison-node-bridge.sty", {"nodes": nodes})
    return observed


def build(ref, otel_source, topology, output):
    output.mkdir(parents=True, exist_ok=False)
    revision = export_source(ref, output)
    original_hashes = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in output.rglob("*") if p.is_file()}
    manifest = read(output / "stackpack.yaml")
    if manifest["name"] != "suse-ai" or manifest["version"] != "3.0.0":
        raise ValueError("This adapter is specifically for the published 3.0.0 comparison")
    manifest.update(name=NAME, displayName=LABEL + " comparison")
    write(output / "stackpack.yaml", manifest)
    for path in sorted((output / "settings").rglob("*.sty")):
        write(path, {"nodes": [isolate_node(n) for n in read(path)["nodes"]]})
    # Readable remediation links are namespaced; no telemetry expression is
    # rewritten to make an absent release signal appear populated.
    for path in (output / "includes").rglob("*"):
        if path.is_file():
            path.write_text(rewrite_text(path.read_text()))
    for directory in ("icons", "includes", "resources"):
        if (otel_source / directory).exists():
            shutil.copytree(otel_source / directory, output / directory / "companion")
    for path in sorted((otel_source / "settings").rglob("*.sty")):
        nodes = [isolate_node(n, True) for n in read(path)["nodes"] if n["_type"] != "MainMenuGroup"]
        if nodes:
            write(output / "settings/companion" / path.relative_to(otel_source / "settings"), {"nodes": nodes})
    observed = node_bridge(json.loads(topology.read_text()), output)
    nodes = [n for p in (output / "settings").rglob("*.sty") for n in read(p)["nodes"]]
    for node in nodes:
        if not node["identifier"].startswith(PREFIX):
            raise ValueError("Unisolated settings identifier: " + node["identifier"])
        if node["_type"] == "OtelComponentMapping":
            expressions = [node["output"]["identifier"], *node["output"].get("required", {}).get("additionalIdentifiers", [])]
            if any(re.search(r"urn:(?:opentelemetry|kubernetes|suse-ai):", expression) for expression in expressions):
                raise ValueError("Unisolated component identity: " + node["identifier"])
    provenance = {"releaseRef": ref, "sourceCommit": revision, "name": NAME,
                  "companionVersion": read(otel_source / "stackpack.yaml")["version"],
                  "originalFileSha256": original_hashes, "observedNodes": observed,
                  "settingsCount": len(nodes)}
    (output.parent / "comparison-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print("Staged", len(nodes), "settings from", revision, "in", output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-ref", default="v3.0.0")
    parser.add_argument("--otel-source", required=True, type=Path)
    parser.add_argument("--topology", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(args.release_ref, args.otel_source, args.topology, args.output)


if __name__ == "__main__":
    main()

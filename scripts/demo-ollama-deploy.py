"""Import a locally built exporter into RKE2 demo nodes and retain its deployment."""

import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runtime", choices=("docker", "podman"), default="docker")
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    if not args.image.startswith("local.invalid/suse-ai-ollama-exporter:"):
        parser.error("Use a unique local.invalid/suse-ai-ollama-exporter:<tag> image")
    if not args.kubeconfig.is_file():
        parser.error("An explicit downstream demo kubeconfig is required")
    os.umask(0o077)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    kube = ["kubectl", "--kubeconfig", str(args.kubeconfig.resolve())]

    def run(command, *, data=None, stdin=None, timeout=360, read_retries=0):
        for attempt in range(read_retries + 1):
            result = subprocess.run(command, input=data, stdin=stdin, capture_output=True, timeout=timeout)
            if not result.returncode:
                return result.stdout
            error = result.stderr.decode(errors="replace")
            transient = any(message in error for message in ("connection reset", "EOF", "i/o timeout"))
            if not transient or attempt == read_retries:
                raise RuntimeError(error)
            with (output / "transport-retries.log").open("a") as log:
                log.write(error + "\n")
            print("Retrying a read-only image verification after a transport failure", flush=True)
            time.sleep(attempt + 1)

    def save(name, value):
        (output / name).write_text(json.dumps(value, indent=2) + "\n")

    before = json.loads(run(kube + ["-n", "suse-private-ai", "get", "deployment", "ollama", "-o", "json"]))
    save("ollama-before.json", before)
    nodes = json.loads(run(kube + ["get", "nodes", "-o", "json"]))
    save("nodes.json", nodes)
    image = json.loads(run([args.runtime, "image", "inspect", args.image]))[0]
    save("image.json", image)
    for node in nodes["items"]:
        info = node["status"]["nodeInfo"]
        if not info["containerRuntimeVersion"].startswith("containerd:") or info["architecture"] != image["Architecture"]:
            raise RuntimeError("Every demo node must use containerd and match the local image architecture")
    if not nodes["items"]:
        raise RuntimeError("The downstream demo has no nodes")
    archive = output / "exporter.tar"
    run([args.runtime, "save", "-o", str(archive), args.image])
    suffix = uuid.uuid4().hex[:8]
    for index, node in enumerate(nodes["items"]):
        name = f"suse-ai-exporter-import-{suffix}-{index}"
        pod = {
            "apiVersion": "v1", "kind": "Pod",
            "metadata": {"name": name, "namespace": "observability", "labels": {"suse-ai-demo-import": suffix}},
            "spec": {
                "nodeName": node["metadata"]["name"], "restartPolicy": "Never",
                "activeDeadlineSeconds": 600, "automountServiceAccountToken": False,
                "containers": [{"name": "import", "image": "registry.suse.com/bci/bci-base:15.7",
                                "command": ["/bin/sleep", "600"], "securityContext": {"runAsUser": 0},
                                "volumeMounts": [{"name": "bin", "mountPath": "/host-bin", "readOnly": True},
                                                 {"name": "containerd", "mountPath": "/run/k3s/containerd"}]}],
                "volumes": [{"name": "bin", "hostPath": {"path": "/var/lib/rancher/rke2/bin", "type": "Directory"}},
                            {"name": "containerd", "hostPath": {"path": "/run/k3s/containerd", "type": "Directory"}}],
            },
        }
        save(f"import-{index}.json", pod)
        command = kube + ["-n", "observability"]
        run(command + ["create", "-f", "-"], data=json.dumps(pod).encode())
        print("Importing exporter into " + node["metadata"]["name"], flush=True)
        try:
            run(command + ["wait", "--for=condition=Ready", "pod/" + name, "--timeout=90s"])
            ctr = command + ["exec", "-i", name, "--", "/host-bin/ctr", "--address",
                             "/run/k3s/containerd/containerd.sock", "--namespace", "k8s.io", "images"]
            with archive.open("rb") as source:
                (output / f"import-{index}.log").write_bytes(run(ctr + ["import", "-"], stdin=source))
            verify = command + ["exec", name, "--", "/host-bin/ctr", "--address",
                                "/run/k3s/containerd/containerd.sock", "--namespace", "k8s.io",
                                "images", "list", "-q"]
            imported = run(verify, read_retries=2).decode().splitlines()
            if args.image not in imported:
                raise RuntimeError("Imported image reference is absent from the node")
        finally:
            run(command + ["delete", "pod", name, "--ignore-not-found", "--wait=false"])

    command = kube + ["-n", "suse-private-ai"]
    current = json.loads(run(command + ["get", "deployment", "ollama", "-o", "json"]))
    if current["spec"] != before["spec"]:
        raise RuntimeError("Ollama spec changed during imports; inspect it before patching")
    containers = current["spec"]["template"]["spec"]["containers"]
    index = next(i for i, c in enumerate(containers) if c["name"] == "ollama-runtime-metrics")
    path = f"/spec/template/spec/containers/{index}"
    patch = [{"op": "test", "path": path + "/name", "value": "ollama-runtime-metrics"},
             {"op": "test", "path": path + "/image", "value": containers[index]["image"]},
             {"op": "replace", "path": path + "/image", "value": args.image},
             {"op": "add", "path": path + "/imagePullPolicy", "value": "Never"}]
    save("deployment-patch.json", patch)
    run(command + ["patch", "deployment", "ollama", "--type=json", "--patch-file", str(output / "deployment-patch.json")])
    print("Waiting for the Ollama rollout", flush=True)
    (output / "rollout.log").write_bytes(run(command + ["rollout", "status", "deployment/ollama", "--timeout=300s"]))
    after = json.loads(run(command + ["get", "deployment", "ollama", "-o", "json"]))
    save("ollama-after.json", after)
    expected = copy.deepcopy(before["spec"])
    expected["template"]["spec"]["containers"][index].update(image=args.image, imagePullPolicy="Never")
    if after["spec"] != expected:
        raise RuntimeError("Unexpected Ollama spec change; inspect the captured before/after manifests")
    print(f"Exporter retained on {len(nodes['items'])} nodes: {args.image}", flush=True)


if __name__ == "__main__":
    main()

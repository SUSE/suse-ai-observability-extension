"""Import local development images into an explicitly selected RKE2 demo cluster."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid


def validate_images(images):
    if not isinstance(images, list) or not images:
        raise ValueError("The image file must contain a nonempty JSON array")
    if any(not isinstance(image, str) or not image.startswith("local.invalid/")
           or ":" not in image or any(c.isspace() for c in image) for image in images):
        raise ValueError("Every image must have an explicit local.invalid/ repository and tag")
    if len(set(images)) != len(images):
        raise ValueError("Image references must be unique")
    return images


def bounded_stdin(command, size):
    """Close the remote reader after the archive bytes, without awaiting exec EOF."""
    if size <= 0:
        raise ValueError("The image archive must not be empty")
    return ["sh", "-c", 'size=$1; shift; head -c "$size" | "$@"',
            "bounded-stdin", str(size), *command]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", required=True, type=Path)
    parser.add_argument("--images-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runtime", choices=("docker", "podman"), default="docker")
    parser.add_argument("--node", help="Import into one named node when resuming an interrupted import")
    args = parser.parse_args()
    if not args.kubeconfig.is_file():
        parser.error("An explicit downstream demo kubeconfig is required")
    images = validate_images(json.loads(args.images_file.read_text()))
    os.umask(0o077)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    kube = ["kubectl", "--kubeconfig", str(args.kubeconfig.resolve())]

    def run(command, *, data=None, stdin=None, timeout=1800):
        result = subprocess.run(command, input=data, stdin=stdin, capture_output=True, timeout=timeout)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result.stdout

    nodes = json.loads(run(kube + ["get", "nodes", "-o", "json"]))
    if args.node:
        nodes["items"] = [node for node in nodes["items"] if node["metadata"]["name"] == args.node]
        if not nodes["items"]:
            raise ValueError("The requested node does not exist in the selected cluster")
    local = json.loads(run([args.runtime, "image", "inspect", *images]))
    (output / "nodes.json").write_text(json.dumps(nodes, indent=2))
    (output / "images.json").write_text(json.dumps(local, indent=2))
    architectures = {image["Architecture"] for image in local}
    if not nodes["items"] or len(architectures) != 1:
        raise RuntimeError("Images and demo nodes must have one matching architecture")
    for node in nodes["items"]:
        info = node["status"]["nodeInfo"]
        if (not info["containerRuntimeVersion"].startswith("containerd:")
                or info["architecture"] not in architectures):
            raise RuntimeError("Every demo node must use containerd and match the images")

    archive = output / "images.tar.gz"
    with (output / "save.log").open("wb") as log:
        process = subprocess.Popen([args.runtime, "save", *images], stdout=subprocess.PIPE, stderr=log)
        try:
            with gzip.open(archive, "wb", compresslevel=1) as target:
                shutil.copyfileobj(process.stdout, target)
        finally:
            process.stdout.close()
        if process.wait(timeout=120):
            raise RuntimeError("Image export failed; inspect save.log")
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    (output / "archive.sha256").write_text(digest + "  images.tar.gz\n")
    suffix = uuid.uuid4().hex[:8]

    def import_node(item):
        index, node = item
        name = f"suse-ai-demo-import-{suffix}-{index}"
        pod = {
            "apiVersion": "v1", "kind": "Pod",
            "metadata": {"name": name, "namespace": "observability",
                         "labels": {"suse-ai-demo-import": suffix}},
            "spec": {
                "nodeName": node["metadata"]["name"], "restartPolicy": "Never",
                "activeDeadlineSeconds": 3600, "automountServiceAccountToken": False,
                "containers": [{"name": "import", "image": "registry.suse.com/bci/bci-base:15.7",
                                "command": ["/bin/sleep", "3600"], "securityContext": {"runAsUser": 0},
                                "volumeMounts": [{"name": "bin", "mountPath": "/host-bin", "readOnly": True},
                                                 {"name": "containerd", "mountPath": "/run/k3s/containerd"}]}],
                "volumes": [{"name": "bin", "hostPath": {"path": "/var/lib/rancher/rke2/bin", "type": "Directory"}},
                            {"name": "containerd", "hostPath": {"path": "/run/k3s/containerd", "type": "Directory"}}],
            },
        }
        command = kube + ["-n", "observability"]
        run(command + ["create", "-f", "-"], data=json.dumps(pod).encode())
        try:
            run(command + ["wait", "--for=condition=Ready", "pod/" + name, "--timeout=180s"])
            print("Importing images into " + node["metadata"]["name"], flush=True)
            ctr = ["/host-bin/ctr", "--address", "/run/k3s/containerd/containerd.sock",
                   "--namespace", "k8s.io", "images"]
            with archive.open("rb") as source:
                result = run(command + ["exec", "-i", name, "--",
                                       *bounded_stdin([*ctr, "import", "-"], archive.stat().st_size)], stdin=source)
            (output / f"import-{index}.log").write_bytes(result)
            imported = run(command + ["exec", name, "--", *ctr, "list", "-q"]).decode().splitlines()
            if not set(images).issubset(imported):
                raise RuntimeError("Imported references are missing on " + node["metadata"]["name"])
            print("Verified images on " + node["metadata"]["name"], flush=True)
            return node["metadata"]["name"]
        finally:
            run(command + ["delete", "pod", name, "--ignore-not-found", "--wait=false"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        imported_nodes = list(pool.map(import_node, enumerate(nodes["items"])))
    (output / "verified.json").write_text(json.dumps({"images": images, "nodes": imported_nodes}, indent=2))
    print(f"Imported {len(images)} images into {len(imported_nodes)} nodes; no registry push", flush=True)


if __name__ == "__main__":
    main()

"""Build, test and export a local dual-architecture release handoff; never publish."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from ollama_metrics import VERSION


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "integrations/ollama"
IMAGE = f"registry.suse.com/ai/containers/suse-ai-ollama-exporter:{VERSION}"


def main():
    resources = ROOT / ".resources"
    resources.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(tempfile.mkdtemp(prefix=f"ollama-release-{stamp}-", dir=resources))
    print(f"Local release artifacts: {output}", flush=True)
    image_revisions = {}
    with (output / "test-output.txt").open("w") as log:
        def run(*args):
            print("+ " + " ".join(args), file=log, flush=True)
            process = subprocess.Popen(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            for line in process.stdout:
                print(line, end="", flush=True)
                print(line, end="", file=log, flush=True)
            if process.wait():
                raise subprocess.CalledProcessError(process.returncode, args)

        run("task", "ollama-test")
        run("task", "ollama-patch-test")
        local = f"localhost/suse-ai-ollama-exporter:{output.name}"
        for arch in ("amd64", "arm64"):
            variables = ("RUNTIME=podman", f"OLLAMA_PLATFORM=linux/{arch}", f"OLLAMA_IMAGE={local}-{arch}")
            run("task", "ollama-image-build", *variables)
            run("task", "ollama-image-test", *variables)
            image_revisions[arch] = subprocess.check_output(
                ["podman", "image", "inspect", f"{local}-{arch}", "--format",
                 '{{index .Labels "org.opencontainers.image.revision"}}'], text=True).strip()
        assert len(set(image_revisions.values())) == 1, "Architecture builds must use the same source revision"
        run("podman", "manifest", "create", local, f"{local}-amd64", f"{local}-arm64")
        try:
            # The destination is a filesystem OCI layout, never a registry transport.
            run("podman", "manifest", "push", "--all", "--format", "oci", "--digestfile", str(output / "digest.txt"),
                local, f"oci:{output / 'image'}")
        finally:
            subprocess.run(["podman", "manifest", "rm", local], check=True, stdout=subprocess.DEVNULL)

    source = output / "source"
    source.mkdir()
    for src, dest in ((SOURCE / "Containerfile", "Dockerfile"), (SOURCE / "ollama_metrics.py", "ollama_metrics.py"),
                      (SOURCE / "LICENSE", "LICENSE"), (SOURCE / "README.md", "README.md"),
                      (SOURCE / "sidecar-patch.yaml", "sidecar-patch.yaml"),
                      (SOURCE / "release/_service", "_service")):
        shutil.copyfile(src, source / dest)
    shutil.copytree(SOURCE / "tests", source / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    (source / "REVISION").write_text(image_revisions["amd64"] + "\n")
    digest = (output / "digest.txt").read_text().strip()
    index_path = output / "image/blobs/sha256" / digest.removeprefix("sha256:")
    index_bytes = index_path.read_bytes()
    assert digest == "sha256:" + hashlib.sha256(index_bytes).hexdigest()
    index = json.loads(index_bytes)
    assert {(m["platform"]["os"], m["platform"]["architecture"]) for m in index["manifests"]} == {
        ("linux", "amd64"), ("linux", "arm64")}
    report = {
        "proposed_image": IMAGE,
        "published": False,
        "local_oci_index_digest": digest,
        "platforms": [{"platform": m["platform"], "digest": m["digest"]} for m in index["manifests"]],
        "image_revisions": image_revisions,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_status": subprocess.check_output(["git", "status", "--short", "--", "integrations/ollama"],
                                                 cwd=ROOT, text=True).splitlines(),
        "source_sha256": {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(source.rglob("*")) if p.is_file()},
        "release_status": "Local candidate only. SUSE build-service submission and registry promotion require approval."
    }
    (output / "release.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

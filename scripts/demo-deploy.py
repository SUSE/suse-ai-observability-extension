"""Forward-only demo deployments with immutable, locally recorded dev versions."""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEV = re.compile(r"3\.0\.0-dev\.([1-9][0-9]*)")


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def demo_url(value):
    parsed = urlparse(value)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment):
        raise ValueError("Use an explicit HTTP localhost demo port-forward, never a default context")
    return value.rstrip("/")


def choose_version(used, requested=""):
    numbers = [int(m[1]) for v in used if (m := DEV.fullmatch(v))]
    next_number = max(numbers, default=0) + 1
    greatest_suffix = max((str(n) for n in numbers), default="")
    # The demo catalog orders prerelease strings lexicographically: dev.10 is
    # below dev.9. Stay above both that order and numeric SemVer order without
    # deleting catalog entries or reusing an upload (9 -> 90, 99 -> 990).
    if str(next_number) <= greatest_suffix:
        next_number = int(greatest_suffix + "0")
        while next_number <= max(numbers):
            next_number *= 10
    version = requested or f"3.0.0-dev.{next_number}"
    match = DEV.fullmatch(version)
    if not match:
        raise ValueError("DEMO_VERSION must be 3.0.0-dev.N with a positive integer N")
    if version in used or int(match[1]) <= max(numbers, default=0):
        raise ValueError(f"Version {version} was used or is below the recorded development sequence")
    if match[1] <= greatest_suffix:
        raise ValueError(f"Version {version} sorts below an existing demo prerelease; use 3.0.0-dev.{next_number}")
    return version


def check_installed(instances, version):
    if len(instances) > 1:
        raise ValueError("Expected at most one SUSE AI instance")
    if not instances:
        return None
    current = instances[0]
    match = DEV.fullmatch(current["stackPackVersion"])
    legacy = re.fullmatch(r"2\.[0-9]+\.[0-9]+", current["stackPackVersion"])
    if current["status"] != "INSTALLED" or not (match or legacy):
        raise ValueError("Expected a ready 2.x/dev instance or a confirmed clean install; no automatic removal")
    if match and int(match[1]) >= int(DEV.fullmatch(version)[1]):
        raise ValueError("Refusing a downgrade or reuse of the installed version")
    return current


class Client:
    def __init__(self, url, token_file, token_type="service"):
        self.url = demo_url(url)
        if token_type not in ("service", "api"):
            raise ValueError("Token type must be service or api")
        self.token_flag = "--service-token" if token_type == "service" else "--api-token"
        self.token = token_file.read_text().strip()
        if not self.token:
            raise ValueError("Demo token file is empty")

    def run(self, command, *, env=None, timeout=600):
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                    text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Command timed out; inspect the demo before continuing") from None
        if result.returncode:
            message = (result.stdout + result.stderr).replace(self.token, "<redacted>")
            raise RuntimeError(message or "Command failed")
        return result.stdout

    def cli(self, *args):
        raw = self.run([os.environ.get("STS_BIN", "sts"), "--url", self.url,
                        self.token_flag, self.token, *args, "-o", "json"])
        return json.loads(raw) if raw.strip() else None


def install(client, version, current):
    if current is None:
        client.cli("stackpack", "install", "--name", "suse-ai", "--stackpack-version", version,
                   "--unlocked-strategy", "overwrite", "--wait", "--timeout", "300s")
    else:
        packs = client.cli("stackpack", "list")["stackpacks"]
        pack = next(p for p in packs if p["name"] == "suse-ai")
        offered = (pack.get("nextVersion") or {}).get("version")
        if offered != version:
            raise ValueError(f"Server offers {offered}, not {version}; refusing an unpinned upgrade")
        client.cli("stackpack", "upgrade", "--name", "suse-ai", "--unlocked-strategy", "overwrite",
                   "--wait", "--timeout", "300s")
    result = client.cli("stackpack", "list-instances", "--name", "suse-ai")
    instances = result["instances"]
    if (len(instances) != 1 or instances[0]["status"] != "INSTALLED"
            or instances[0]["stackPackVersion"] != version):
        raise RuntimeError("Installed state does not match the uploaded version")
    if current is not None and instances[0]["id"] != current["id"]:
        raise RuntimeError("Upgrade changed the instance ID")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, type=demo_url)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--token-type", choices=("service", "api"), default="service")
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--cluster", default="suse-ai")
    parser.add_argument("--version", default="")
    parser.add_argument("--source", type=Path, default=ROOT / "stackpack/suse-ai")
    args = parser.parse_args()
    os.umask(0o077)
    state = args.state_dir.resolve()
    state.mkdir(parents=True, exist_ok=True)
    with (state / "deploy.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        client = Client(args.url, args.token_file, args.token_type)
        catalog = client.cli("stackpack", "list-versions", "--name", "suse-ai")
        before = client.cli("stackpack", "list-instances", "--name", "suse-ai")
        versions = state / "versions"
        versions.mkdir(exist_ok=True)
        used = {v["version"] for v in catalog["versions"]} | {p.name for p in versions.iterdir()}
        tags = client.run(["git", "tag", "--list", "3.0.0-dev.*", "v3.0.0-dev.*"])
        used.update(t.removeprefix("v") for t in tags.splitlines())
        version = choose_version(used, args.version)
        current = check_installed(before["instances"], version)
        # A stable 3.0.x entry would divert the server's normal upgrade selection.
        if any(re.fullmatch(r"3\.0\.[0-9]+", v["version"]) for v in catalog["versions"]):
            raise ValueError("Stable 3.0.x catalog entries remain; clean them only after explicit confirmation")
        for name in ("open-telemetry", "kubernetes-v2"):
            companions = client.cli("stackpack", "list-instances", "--name", name)["instances"]
            if name == "kubernetes-v2":
                companions = [i for i in companions if i["config"].get("kubernetes_cluster_name") == args.cluster]
            if not companions or any(i["status"] not in ("INSTALLED", "WAITING_FOR_DATA") for i in companions):
                raise ValueError(f"The demo requires an existing ready {name} companion")

        attempt = versions / version
        attempt.mkdir()  # This reservation is never removed, even when validation/upload fails.
        record = {"version": version, "url": args.url, "status": "reserved", "tokenType": args.token_type,
                  "createdUTC": datetime.now(timezone.utc).isoformat(),
                  "sourceCommit": client.run(["git", "rev-parse", "HEAD"]).strip()}
        save(attempt / "record.json", record)
        save(attempt / "instances-before.json", before)
        save(attempt / "catalog-before.json", catalog)
        pack = attempt / "source" / "stackpack" / "suse-ai"
        shutil.copytree(args.source.resolve(), pack)
        manifest = pack / "stackpack.yaml"
        text, count = re.subn(r"^version:.*$", "version: " + version, manifest.read_text(), flags=re.MULTILINE)
        if count != 1:
            raise ValueError("Expected exactly one manifest version")
        manifest.write_text(text)
        print(f"Validating {version}; evidence: {attempt}", flush=True)
        output = client.run(["task", "stackpack-validate"],
                            env=dict(os.environ, STACKPACK_SOURCE=str(pack)))
        (attempt / "validation.log").write_text(output)
        archive = attempt / f"suse-ai-{version}.sts"
        client.run(["sts", "stackpack", "package", "-d", str(pack), "-f", str(archive)])
        record.update(status="upload-attempted", sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
        save(attempt / "record.json", record)  # Consume the version before a potentially ambiguous upload.
        print(f"Uploading {version} once", flush=True)
        client.cli("stackpack", "upload", "--file", str(archive))
        record["status"] = "uploaded"
        save(attempt / "record.json", record)
        save(attempt / "instances-after.json", install(client, version, current))
        record["status"] = "installed"
        save(attempt / "record.json", record)
        client.run(["task", "demo-inspect", "SPIKE_URL=" + args.url,
                    "SPIKE_TOKEN_FILE=" + str(args.token_file.resolve()),
                    "SPIKE_TOKEN_TYPE=" + args.token_type,
                    "SPIKE_EVIDENCE=" + str(attempt / "verification"), "SPIKE_STAGE=deployed"])
        print(f"Installed {version}; synchronization and mapping snapshots: {attempt / 'verification'}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(str(error)) from None

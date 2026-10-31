#!/usr/bin/env python3
"""Stateful CLI boundary fixture. It does not simulate server provisioning."""
import json
import os
from pathlib import Path
import sys

path = Path(os.environ["FAKE_STS_STATE"])
state = json.loads(path.read_text())
domain = "stackpack" if "stackpack" in sys.argv else "settings"
args = sys.argv[sys.argv.index(domain):]
command = args[1]
name = args[args.index("--name") + 1] if "--name" in args else None
state.setdefault("calls", []).append(args)
path.write_text(json.dumps(state))
if command == state.get("fail"):
    print("Injected CLI failure", file=sys.stderr)
    sys.exit(1)
if domain == "settings":
    if command == "list":
        response = {"settings": state.get("menus", [])}
    elif command == "delete":
        identity = int(args[args.index("--ids") + 1])
        state["menus"] = [menu for menu in state["menus"] if menu["id"] != identity]
        response = {}
    else:
        raise AssertionError(args)
    path.write_text(json.dumps(state))
    print(json.dumps(response))
    sys.exit(0)
instances = state.setdefault("instances", {})
versions = state.setdefault("versions", [])
target = "3.0.0"
response = {}
if command == "list-instances":
    if name == "suse-ai" and not versions:
        print("StackPack not found", file=sys.stderr)
        sys.exit(1)
    response = {"instances": instances.get(name, [])}
elif command == "list-versions":
    response = {"versions": [{"version": v} for v in versions]}
elif command == "list":
    response = {"stackpacks": [{"name": "suse-ai", "nextVersion": {"version": state.get("next", target)}}]
                if versions else []}
elif command == "upload":
    assert target not in versions, "Installer tried to reuse an uploaded version"
    versions.append(target)
elif command == "install":
    assert not instances.get(name) or name == "kubernetes-v2", "Duplicate installation"
    item = {"id": sum(map(len, instances.values())) + 1, "status": "INSTALLED", "config": {},
            "stackPackVersion": target if name == "suse-ai" else "1.0.0"}
    if name == "kubernetes-v2":
        item["config"] = {"kubernetes_cluster_name": args[args.index("-p") + 1].split("=", 1)[1]}
    if name == "suse-ai":
        assert args[args.index("--stackpack-version") + 1] == target
        assert target in versions
    instances.setdefault(name, []).append(item)
elif command == "upgrade":
    assert args[args.index("--unlocked-strategy") + 1] == "overwrite"
    assert "--wait" in args
    assert instances[name] and target in versions
    for item in instances[name]:
        item["stackPackVersion"] = "9.0.0" if state.get("wrong_result") else target
elif command == "uninstall":
    identity = int(args[args.index("--id") + 1])
    instances[name] = [i for i in instances.get(name, []) if i["id"] != identity]
else:
    raise AssertionError(args)
path.write_text(json.dumps(state))
print(json.dumps(response))

# Ollama runtime observations

`ollama_metrics.py` exposes a read-only snapshot from the local Ollama
[`GET /api/ps`](https://docs.ollama.com/api/ps) endpoint. Run one exporter beside
each Ollama process. It never generates inference requests or substitutes
client measurements for server telemetry.

| Gauge | Meaning |
| --- | --- |
| `ollama_api_up` | 1 for a valid local API snapshot; 0 for HTTP, timeout, JSON or schema failures |
| `ollama_loaded_models` | Number of models loaded by this process, including a real zero for an empty process |
| `ollama_model_size_bytes{model}` | Model allocation/residency reported as `size` by Ollama |
| `ollama_model_vram_bytes{model}` | GPU allocation/residency reported as `size_vram` by Ollama |
| `ollama_model_context_length{model}` | Reported context window of the loaded model |

Memory gauges are allocations reported by Ollama, not utilization, per-request
memory, token counts, cost, or inference latency. Optional missing API fields
produce no corresponding gauge. An unsuccessful snapshot emits only
`ollama_api_up 0`; no model data is cached. Gate residency charts on the current
`ollama_api_up == 1` per instance so a backend's lookback cannot display a previous
snapshot as current. `/healthz` tests the exporter process only.

## Existing Kubernetes deployment

The reference patch adds the packaged SUSE exporter to an existing Deployment.
It reads `127.0.0.1:11434/api/ps` within that pod and exposes `/metrics` on 11435.
The proposed release image is
`registry.suse.com/ai/containers/suse-ai-ollama-exporter:0.1.0`; publication is
pending the SUSE registry release process. Use the patch only after that image
is available, and pin its published multi-architecture digest for deployment.
The image bakes in the script and defaults to UID/GID 65532. The patch enforces
a read-only root filesystem, drops all capabilities, disables privilege
escalation and uses the runtime's default seccomp profile. No writable directory
or source ConfigMap is needed.
The existing Ollama container, GPU allocation, volumes and deployment strategy
stay owned by the original deployment configuration. Applying the patch rolls
the pod; account for the workload's availability and GPU/PVC constraints first.

From this directory, substitute the actual namespace and deployment name:

```bash
kubectl -n YOUR_NAMESPACE patch deployment YOUR_OLLAMA_DEPLOYMENT \
  --type strategic --patch-file sidecar-patch.yaml
```

The patch's `null` fields and `$patch: delete` directive remove the previous
sidecar command, arguments, source mount and `ollama-runtime-metrics` volume
when upgrading. Omitting these fields from a strategic merge would retain the
old configuration. Other containers and volumes are preserved. The old
ConfigMap object can be removed separately once no pod references it.

The Collector repository's `examples/ollama-runtime.yaml` discovers pods with
`app.kubernetes.io/name=ollama` and the `ollama-metrics` port. It uses the actual
pod UID as `service.instance.id`, together with actual pod namespace/name/node
metadata. Use the same logical service name/namespace as any existing Ollama
telemetry. Scrape each pod directly through one Collector owner; a load-balanced
Service address cannot provide reliable process identity.

Configure the scrape interval above the exporter's five-second API timeout.
Restrict metrics access with your normal cluster network policy. The exporter
does not require API credentials for the local Ollama process. For a different
local origin or port, use `--ollama-url`, `--port` or `--timeout`; keep one exporter
per process rather than pointing all replicas at a shared Service.

## Validation

```bash
task ollama-test
task ollama-patch-test
task ollama-image-build
task ollama-image-test
```

The standard-library tests exercise the actual HTTP exporter and API failures,
empty/malformed snapshots, missing optional values, label escaping, replica
isolation and stale-data prevention. The collection contract is tested against
Ollama 0.21.2's `/api/ps` response. Models are metric labels only; this integration
does not create served-model topology or request/token charts.

The patch checks require `kubectl` and run locally, without contacting a cluster.
The image tasks use Podman by default. Pass `RUNTIME=docker` to both
`task ollama-image-build` and `task ollama-image-test` to use Docker, including
when the local `.env` selects another runtime. Use `OLLAMA_PLATFORM=linux/arm64` on an ARM host,
or with an existing binfmt/QEMU installation. `OLLAMA_IMAGE` overrides the local
image reference. The image tests exercise the baked-in entrypoint and default
arguments, argument overrides, populated/empty/failed API snapshots and
`/healthz`. They check the actual process UID/GID, zero capability sets,
`no_new_privs`, seccomp, read-only root mount and a rejected write to `/tmp`, without
overriding the image's user or mounting the source. CI runs on native amd64 and
arm64 runners and only builds and tests locally.

## SUSE registry release handoff

Keep the image version independent of the StackPack version. This exporter
supplies ordinary Prometheus metrics to the Collector for either StackPack
generation; building it does not require a StackPack upload or topology change.

The Containerfile uses the multi-architecture SUSE BCI Python 3.13 index pinned
by digest. Python's HTTP, JSON, networking and TLS modules come from that image;
there are no pip dependencies or downloads during the build beyond the base
image. Keeping the complete SUSE Python runtime avoids maintaining a hand-copied
interpreter/stdlib/shared-library subset. Update the base digest and rebuild
both architectures when taking base-image fixes. The bundled Apache-2.0
`LICENSE` is a copy of the repository license.

Prepare a local handoff from the repository root:

```bash
task ollama-release-prepare
```

This requires Task, Python, kubectl, Podman and either native execution or
working binfmt/QEMU support for both architectures. It runs the existing tests,
checks both patch scenarios, builds and smoke-tests linux/amd64 and linux/arm64,
then writes a new `.resources/ollama-release-*/` directory containing:

- `image/`: an OCI image layout with both architecture manifests and their layers.
- `digest.txt` and `release.json`: the local OCI index digest, per-platform
  digests, source commit/status and source-file checksums.
- `test-output.txt`: complete build and test output.
- `source/`: the build-service `Dockerfile` (copied from the Containerfile),
  script, license, README, sidecar patch, tests, `REVISION` and `_service` metadata helper.

The `podman manifest push` command in this task writes to the local `oci:`
filesystem transport. It does not contact a destination registry, create Git
tags, push a branch or open a PR. A local digest is not evidence of publication;
the SUSE build service may produce a different digest.

After explicit approval, hand the reviewed source to the SUSE AI container
release owner. An existing related setup image records `Devel:AI`, repository
`containers`, as its SUSE build-service origin; confirm that project and the
proposed package `suse-ai-ollama-exporter-container` with the owner before
submission. Configure the approved project's base-image dependency and enable
`x86_64` and `aarch64`. The recipe includes the standard
[OBS build tags and architecture directives](https://openbuildservice.org/help/manuals/obs-user-guide/cha-obs-supported-formats).
The maintainer must confirm the build-tag mapping and promotion route to the
proposed `registry.suse.com/ai/containers/suse-ai-ollama-exporter` repository.
The `%DISTURL%` label is a build-service placeholder until that build occurs;
set `org.opencontainers.image.revision` from the bundled `REVISION` file.

The staged source can be tested independently of this repository's Taskfile:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B tests/sidecar_patch.py -v
CONTAINER_RUNTIME=podman OLLAMA_PLATFORM=linux/amd64 \
  OLLAMA_IMAGE=YOUR_BUILT_IMAGE python3 -B tests/container_smoke.py -v
```

Run the tests against both resulting SUSE builds and complete the product's
normal registry review and promotion process. Record the published index
digest, verify that it contains linux/amd64 and linux/arm64, and use that digest
in the sidecar patch. Do not substitute a local image ID or the BCI base digest.
Registry publication, source/tag pushes and PR creation require confirmation.

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
The release image is
`registry.suse.com/ai/containers/suse/suse-ai-ollama-exporter:<version>`, where
`<version>` is the extension release version without the leading `v`. The first
release is `3.0.0`. Publication and image-mirror promotion are still pending.
Before applying `sidecar-patch.yaml`, replace
`<PUBLISHED_MULTI_ARCH_INDEX_DIGEST>` with the published SUSE registry index's
64-character SHA-256 value. The placeholder is intentionally not a usable
digest; do not substitute a local image ID, a platform digest or the BCI base
digest.
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
task workflows-lint
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
overriding the image's user or mounting the source. They also check the OCI
version and reference labels. `OLLAMA_VERSION` defaults to `3.0.0`; set it to
the intended extension release version for both build and test tasks. The
`ollama-runtime.yml` CI workflow runs on native amd64 and arm64 runners and
only builds and tests locally. `task workflows-lint` requires `actionlint`.

## Release publication and promotion

The exporter uses the extension's release version, starting with `3.0.0`:

```text
extension release vX.Y.Z
  -> ghcr.io/suse/suse-ai-ollama-exporter:X.Y.Z (linux/amd64 + linux/arm64)
  -> image-mirror
  -> registry.suse.com/ai/containers/suse/suse-ai-ollama-exporter:X.Y.Z
```

The [publication workflow](../../.github/workflows/publish-ollama-exporter.yml)
runs when a GitHub release is published, or through `workflow_dispatch` against
an existing `vX.Y.Z` tag. Branch dispatches and prerelease tag suffixes are
rejected before publishing. It builds each architecture on a native
runner, pushes each image by digest, and joins them into one manifest list.
`docker/metadata-action` creates `X.Y.Z`, `X.Y` and `sha-<short-commit>` tags;
`latest` is disabled. Both OCI version and reference labels use `X.Y.Z`.
Exporter, sidecar patch and container tests run in `ollama-runtime.yml` for
relevant pull requests and pushes to `main`. The publication workflow does
not repeat those tests.
Pull requests never publish images. The setup image is built in IBS; its old
GitHub publication workflow targeting the nonexistent `trunk` branch was removed.

Publication requires these manual steps:

1. Merge the workflow before creating the extension's `v3.0.0` release tag and
   publishing the GitHub release. Creating a tag alone does not trigger this
   workflow. To retry an existing release, use
   `gh workflow run publish-ollama-exporter.yml --repo SUSE/suse-ai-observability-extension --ref v3.0.0`.
2. After the first publication, a **SUSE organization admin must make the
   `suse-ai-ollama-exporter` GHCR package public**, as for the Collector package.
   [New GHCR packages are private by default](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#pushing-container-images),
   even when the source repository is public. This workflow does not change
   package visibility.
3. Configure the image-mirror mapping from
   `ghcr.io/suse/suse-ai-ollama-exporter:3.0.0` to
   `registry.suse.com/ai/containers/suse/suse-ai-ollama-exporter:3.0.0` in the
   separate mirror configuration and complete its promotion process.
4. Inspect both registries and verify that the promoted index contains
   `linux/amd64` and `linux/arm64`:

   ```bash
   docker buildx imagetools inspect ghcr.io/suse/suse-ai-ollama-exporter:3.0.0
   docker buildx imagetools inspect registry.suse.com/ai/containers/suse/suse-ai-ollama-exporter:3.0.0
   ```

   Record the SUSE registry's top-level index digest and replace the digest
   placeholder in `sidecar-patch.yaml` before deployment. Use the destination
   registry's digest, which must be checked after mirroring.

## Local release validation

Building this exporter does not require a StackPack upload or topology change.

The Containerfile uses the multi-architecture SUSE BCI Python 3.13 index pinned
by digest. Python's HTTP, JSON, networking and TLS modules come from that image;
there are no pip dependencies or downloads during the build beyond the base
image. Keeping the complete SUSE Python runtime avoids maintaining a hand-copied
interpreter/stdlib/shared-library subset. Update the base digest and rebuild
both architectures when taking base-image fixes. The bundled Apache-2.0
`LICENSE` is a copy of the repository license.

Prepare a local handoff from the repository root:

```bash
task ollama-release-prepare OLLAMA_VERSION=3.0.0
```

This requires Task, Python, kubectl, Podman and either native execution or
working binfmt/QEMU support for both architectures. It runs the existing tests,
checks both patch scenarios, builds and smoke-tests linux/amd64 and linux/arm64,
then writes a new `.resources/ollama-release-*/` directory containing:

- `image/`: an OCI image layout with both architecture manifests and their layers.
- `digest.txt` and `release.json`: the local OCI index digest, per-platform
  digests, source commit/status and source-file checksums.
- `test-output.txt`: complete build and test output.
- `source/`: a snapshot of the upstream `Containerfile`, `.dockerignore`, script,
  license, README, sidecar patch and tests, plus `REVISION`.

The `podman manifest push` command in this task writes to the local `oci:`
filesystem transport. It does not contact a destination registry, create Git
tags, push a branch or open a PR. A local digest is not evidence of publication;
the GHCR build and the promoted SUSE registry index must be inspected separately.
The local bundle remains useful for offline review; release publication is
owned by the GitHub workflow and SUSE promotion by image-mirror.

The source snapshot can be tested independently of this repository's Taskfile:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B tests/sidecar_patch.py -v
CONTAINER_RUNTIME=podman OLLAMA_PLATFORM=linux/amd64 OLLAMA_VERSION=3.0.0 \
  OLLAMA_IMAGE=YOUR_BUILT_IMAGE python3 -B tests/container_smoke.py -v
```

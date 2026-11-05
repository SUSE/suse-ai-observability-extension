# SUSE AI Observability Extension

The native schema v2 StackPack (release 3.0.1) for [SUSE Observability](https://www.suse.com/products/observability/) that transforms OpenTelemetry telemetry from GenAI workloads into high-level topology views, metric dashboards, and health monitors.

## What It Does

The extension auto-discovers GenAI components running on Kubernetes and organizes them into a layered topology:

| Layer | Components |
|-------|------------|
| **Applications** | GenAI apps, agents, UIs |
| **Services** | Inference engines, vector databases, search engines, model proxies, MCP servers, workflow engines, ML registries |
| **Models** | LLM models (vLLM, Ollama) |
| **GPU Nodes** | Kubernetes nodes with NVIDIA GPUs |

It provides out-of-the-box metric bindings and health monitors for vLLM,
Ollama, Milvus, OpenSearch, Elasticsearch, GPU infrastructure, KServe, Kubeflow
Pipelines, and Kubeflow Model Registry. The companion demo bindings cover agent
tool execution, RAG retrieval quality, and generated scenarios.

## Prerequisites

- [SUSE Observability](https://www.suse.com/products/observability/) instance
- [StackState CLI (`sts`)](https://dl.stackstate.com/stackstate-cli/install.sh) 3.9.2 for installation
- [Task](https://taskfile.dev/) runner installed
- Bash, GNU coreutils/findutils and Info-ZIP for offline packaging
- `docker` or `podman` and Python test dependencies for validation
- Bash, `jq`, `unzip`, `sed`, `grep` and GNU `sort` in the setup container

## Project Structure

```
.
├── stackpack/suse-ai/          # The StackPack
│   ├── stackpack.yaml          # Native schema v2 manifest and release version
│   ├── settings/               # OTel mappings, presentations and monitors
│   ├── includes/               # Monitor remediation hints
│   ├── icons/                  # Native UI icons
│   └── resources/              # Documentation shown in the SUSE Observability UI
├── examples/suse-ai/           # Native Collector examples used by the tests
├── tests/suse-ai/              # Native mapping, query, Collector and live tests
├── integrations/
│   ├── otel-collector/         # OTel Collector Helm values (test environment)
│   └── oi-filter/              # OTel Collector Python filters
├── knowledge/                  # Architecture docs, guides, conventions
├── init.sh                     # Install/uninstall script (runs inside the container)
└── Taskfile.yaml               # Development task automation
```

## Getting Started

### 1. Configure your environment

Copy the example env file and adjust as needed:

```bash
cp .env.example .env
```

Set `CONTAINER_RUNTIME` to `podman` (default) or `docker`.

### 2. Build and validate the release artifact

```bash
python3 -m venv .resources/native-tests
.resources/native-tests/bin/pip install -r tests/requirements.txt
CONTAINER_RUNTIME=docker task stackpack-test PYTHON=.resources/native-tests/bin/python
CONTAINER_RUNTIME=docker task stackpack-validate
task stackpack-package
(cd dist && sha256sum --check SHA256SUMS)
```

The offline packaging task produces `dist/suse-ai-3.0.1.sts` and `SHA256SUMS`.
A rebuild has the same SHA-256, independent of checkout timestamps and modes.
See [the release record](knowledge/NATIVE_STACKPACK_RELEASE.md) for the exact
ZIP command, import provenance, version policy and validation limits.

This repository provides the StackPack archive and `init.sh`. Setup images
are built separately and must include the archive at `/mnt/suse-ai.sts`,
the installer, CLI 3.9.2 and the runtime tools above.

### 3. Run the setup container

Set `SETUP_IMAGE` to the fully qualified setup image reference for your
deployment, including its version tag or digest.

The container expects the following environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `STACKSTATE_API_URL` | Yes | SUSE Observability API URL |
| `STACKSTATE_TOKEN` | Yes | API or service token |
| `STACKSTATE_TOKEN_TYPE` | Yes | `api` or `service` |
| `KUBERNETES_CLUSTERS` | Install only | Comma-separated list of cluster names |
| `STS_SKIP_SSL` | No | Set to `true` to skip TLS verification |
| `STS_CA_CERT_PATH` | No | Path to a custom CA certificate |
| `UNINSTALL` | No | Set to `true` to uninstall the suse-ai StackPack and wait for removal |
| `CLEANUP_LEGACY` | No | Explicit pre-2.x menu/autosync cleanup; separate from install |
| `STS_CONTEXT` | No | Use a configured CLI context instead of the three authentication variables |
| `SUSE_AI_ARCHIVE` | No | Override `/mnt/suse-ai.sts` for local testing |
| `STS_WAIT_SECONDS` | No | Operation timeout, default 300 seconds |

**Install:**

```bash
podman run --rm \
  -e STACKSTATE_API_URL=https://your-instance.example.com \
  -e STACKSTATE_TOKEN=your-token \
  -e STACKSTATE_TOKEN_TYPE=api \
  -e KUBERNETES_CLUSTERS=cluster-a,cluster-b \
  "${SETUP_IMAGE:?Set SETUP_IMAGE to the setup image reference}"
```

The init script will:
1. Install a `kubernetes-v2` StackPack instance for each cluster
2. Install the `open-telemetry` StackPack
3. Upload the bundled `suse-ai` version only if it is absent from the catalog
4. Install that exact version, or upgrade with `--unlocked-strategy overwrite`
5. Verify the final installed status and version

Re-running an already successful setup performs reads only. Authentication,
upload and provisioning errors stop setup. Newer installed versions are not
downgraded. Companion provisioning accepts `WAITING_FOR_DATA`; SUSE AI must
reach `INSTALLED`. The 2.2.0 → 3.0.0 upgrade was verified with CLI 3.9.2 on
Observability 2.11.1 and preserves the instance ID without a reinstall. See the
[migration evidence and recovery procedure](knowledge/NATIVE_STACKPACK_RELEASE.md)
before upgrading installations with local customizations.

**Uninstall:**

```bash
podman run --rm \
  -e STACKSTATE_API_URL=https://your-instance.example.com \
  -e STACKSTATE_TOKEN=your-token \
  -e STACKSTATE_TOKEN_TYPE=api \
  -e UNINSTALL=true \
  "${SETUP_IMAGE:?Set SETUP_IMAGE to the setup image reference}"
```

## Development

### StackPack development workflow

The fastest iteration loop during development is to upload the StackPack directly without building a container:

```bash
# Increment the patch version
task version-up

# Validate, package, and invoke the same installer as the setup container
KUBERNETES_CLUSTERS=cluster-a task stackpack-upload STS_CONTEXT=my-context
```

Every new uploaded payload requires an unused version in `stackpack.yaml`.
`stackpack-upload` validates and packages first; the installer skips an existing
catalog version and never overwrites it. Use `task version-up` for a patch bump
or `task version-up TARGET_VERSION=<higher-major.minor.patch>`.

`stackpack-test` runs the native mapping, PromQL, Collector and release tests.
The [regression test guide](knowledge/REGRESSION_TESTS.md) documents the retained
legacy Collector checks; the [native release record](knowledge/NATIVE_STACKPACK_RELEASE.md)
describes native test dependencies and live checks.

To uninstall all instances (useful for a clean re-install):

```bash
task stackpack-uninstall
```

### Running Groovy scripts

```bash
task sts-script FILE=path/to/script.groovy
```

### Useful CLI commands

```bash
# List installed StackPack instances
sts stackpack list-instances --name suse-ai -o json

# Query the topology
sts script run --script "Topology.query('label = \"suse.ai.managed\"')"

# Inspect a topology sync
sts topology-sync list
sts topology-sync describe --id <id>
```

### Architecture reference

The `knowledge/` directory contains detailed documentation on the project architecture, component types, metric bindings, monitor creation, and design decisions. The earlier guides describe the 2.x architecture; start with
[the native release record](knowledge/NATIVE_STACKPACK_RELEASE.md) and
[the native StackPack README](stackpack/suse-ai/README.md) for v3.

The [Open WebUI Ollama integration](integrations/open-webui/README.md) describes
the in-process provider adapter, native trace correlation and explicitly resolved
client dependencies for Open WebUI 0.6.41.

## License

[Apache 2.0](LICENSE)

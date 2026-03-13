# SUSE AI Observability Extension

A StackPack for [SUSE Observability](https://www.suse.com/products/observability/) that transforms OpenTelemetry telemetry from GenAI workloads into high-level topology views, metric dashboards, and health monitors.

## What It Does

The extension auto-discovers GenAI components running on Kubernetes and organizes them into a layered topology:

| Layer | Components |
|-------|------------|
| **Applications** | GenAI apps, agents, UIs |
| **Services** | Inference engines, vector databases, search engines, model proxies, MCP servers, workflow engines, ML registries |
| **Models** | LLM models (vLLM, Ollama) |
| **GPU Nodes** | Kubernetes nodes with NVIDIA GPUs |

It provides out-of-the-box metric bindings and health monitors for vLLM, Ollama, Milvus, OpenSearch, Elasticsearch, and GPU infrastructure.

## Prerequisites

- [SUSE Observability](https://www.suse.com/products/observability/) instance
- [StackState CLI (`sts`)](https://dl.stackstate.com/stackstate-cli/install.sh) installed
- [Task](https://taskfile.dev/) runner installed
- `podman` or `docker` for building the container image

## Project Structure

```
.
├── stackpack/suse-ai/          # The StackPack
│   ├── stackpack.conf          # StackPack metadata and versioning
│   ├── provisioning/           # Groovy scripts, STY templates, icons
│   │   ├── SuseAiProvision.groovy
│   │   └── templates/          # Component types, metrics, monitors, views, sync
│   └── resources/              # Documentation shown in the SUSE Observability UI
├── integrations/
│   ├── otel-collector/         # OTel Collector Helm values (test environment)
│   └── oi-filter/              # OTel Collector Python filters
├── knowledge/                  # Architecture docs, guides, conventions
├── Dockerfile                  # Multi-stage build for the setup container
├── init.sh                     # Install/uninstall script (runs inside the container)
└── Taskfile.yaml               # Development task automation
```

## Getting Started

### 1. Configure your environment

Copy the example env file and adjust as needed:

```bash
cp .env.example .env
```

Available settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_NAME` | `suse-ai-observability` | Container image name |
| `IMAGE_VERSION` | `latest` | Container image tag |
| `CONTAINER_RUNTIME` | `podman` | `podman` or `docker` |

### 2. Build and push the container image

```bash
task build
task push
```

The container image packages the StackPack archive, the `sts` CLI, and the `init.sh` script.

### 3. Run the setup container

The container expects the following environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `STACKSTATE_API_URL` | Yes | SUSE Observability API URL |
| `STACKSTATE_TOKEN` | Yes | API or service token |
| `STACKSTATE_TOKEN_TYPE` | Yes | `api` or `service` |
| `KUBERNETES_CLUSTERS` | Install only | Comma-separated list of cluster names |
| `STS_SKIP_SSL` | No | Set to `true` to skip TLS verification |
| `STS_CA_CERT_PATH` | No | Path to a custom CA certificate |
| `UNINSTALL` | No | Set to `true` to uninstall the suse-ai StackPack |

**Install:**

```bash
podman run --rm \
  -e STACKSTATE_API_URL=https://your-instance.example.com \
  -e STACKSTATE_TOKEN=your-token \
  -e STACKSTATE_TOKEN_TYPE=api \
  -e KUBERNETES_CLUSTERS=cluster-a,cluster-b \
  suse-ai-observability:latest
```

The init script will:
1. Install a `kubernetes-v2` StackPack instance for each cluster
2. Install the `open-telemetry` StackPack
3. Upload and install (or upgrade) the `suse-ai` StackPack

**Uninstall:**

```bash
podman run --rm \
  -e STACKSTATE_API_URL=https://your-instance.example.com \
  -e STACKSTATE_TOKEN=your-token \
  -e STACKSTATE_TOKEN_TYPE=api \
  -e UNINSTALL=true \
  suse-ai-observability:latest
```

## Development

### StackPack development workflow

The fastest iteration loop during development is to upload the StackPack directly without building a container:

```bash
# Increment the patch version
task version-up

# Zip, upload, and upgrade in one step
task stackpack-upload
```

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

The `knowledge/` directory contains detailed documentation on the project architecture, component types, metric bindings, monitor creation, and design decisions. Start with `knowledge/ARCH.md` for an overview.

## License

[Apache 2.0](LICENSE)

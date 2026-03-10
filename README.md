# SUSE AI Observability Extension

GenAI observability StackPack for SUSE Observability. Transforms OTel telemetry into high-level topology views.

## Quick Start

```bash
# Build and upload stackpack
task version-up
task stackpack-upload

# Verify sync
sts topology-sync list
sts topology-sync describe --id <id>
```

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `knowledge/` | Architecture, guides, best practices |
| `stackpack/` | StackPack provisioning (Groovy, STY templates) |
| `integrations/` | OTel collector configs, filters |
| `setup/` | Installation assets |
| `scripts/` | Debug/verification scripts |

## Key Commands

```bash
# StackPack
task stackpack-upload                    # Build & upload
sts stackpack install -n suse-ai         # Install instance
sts stackpack upgrade -n suse-ai --unlocked-strategy overwrite

# Topology
sts topology-sync list
sts topology-sync describe --id <id>
sts script run --script "Topology.query('label = \"suse.ai.managed\"')"

# Debug
./scripts/debug-model-discovery.sh
./scripts/verify-model-components.sh
```

## Development

- See `knowledge/` for architecture, component types, monitor creation
- Groovy scripts in `stackpack/suse-ai/provisioning/`
- Use `npm-groovy-lint` before committing Groovy changes
- Always increment version in `stackpack.conf` before upload

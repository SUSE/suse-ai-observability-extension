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

The reference patch adds a non-root Python sidecar to an existing Deployment.
It reads `127.0.0.1:11434/api/ps` within that pod and exposes `/metrics` on 11435.
The existing Ollama container, GPU allocation, volumes and deployment strategy
stay owned by the original deployment configuration. Applying the patch rolls
the pod; account for the workload's availability and GPU/PVC constraints first.

From this directory, substitute the actual namespace and deployment name:

```bash
kubectl -n YOUR_NAMESPACE create configmap ollama-runtime-metrics \
  --from-file=ollama_metrics.py --dry-run=client -o yaml | kubectl apply -f -
kubectl -n YOUR_NAMESPACE patch deployment YOUR_OLLAMA_DEPLOYMENT \
  --type strategic --patch-file sidecar-patch.yaml
```

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
```

The standard-library tests exercise the actual HTTP exporter and API failures,
empty/malformed snapshots, missing optional values, label escaping, replica
isolation and stale-data prevention. The collection contract is tested against
Ollama 0.21.2's `/api/ps` response. Models are metric labels only; this integration
does not create served-model topology or request/token charts.

# Kubeflow Integration

**Current Status**: v1 — KServe and Pipelines fully integrated with metrics + traces; Model Registry topology-only.

## Overview

Kubeflow is monitored via three product components:

- `inference-engine.kserve` — aggregates all KServe InferenceServices in the cluster.
- `workflow-engine.kubeflow-pipelines` — aggregates the KFP control plane (api-server, scheduledworkflow controller, persistence agent, MLMD).
- `ml-registry.kubeflow` — Kubeflow Model Registry (topology only in v1).

## Architecture

### Discovery

Signals are collected via the SUSE AI custom OTel collector. Three new Prometheus scrape jobs in `integrations/otel-collector/otel-values.yaml`:

- `kubeflow-pipelines` — Kubernetes service discovery in `${KUBEFLOW_NAMESPACE}` (default `kubeflow`).
- `kserve-controller` — pods labeled `control-plane=kserve-controller-manager` in the `kserve` namespace.
- `kserve-inferenceservices` — pods carrying `serving.kserve.io/inferenceservice` label, port `http-usermetric` (the qpext aggregated endpoint).

### Required customer configuration

KServe InferenceServices must enable metric aggregation:

```yaml
metadata:
  annotations:
    serving.kserve.io/enable-metric-aggregation: "true"
    serving.kserve.io/enable-prometheus-scraping: "true"
```

Without these, the queue-proxy emits its own metrics on a port we don't scrape.

### Resource attribute tagging

`transform/kserve`, `transform/kubeflow-pipelines`, and `transform/kubeflow-model-registry` add:

| Key | Value |
|---|---|
| `suse.ai.managed` | `true` |
| `suse.ai.component.name` | `kserve` / `kubeflow-pipelines` / `kubeflow-model-registry` |
| `suse.ai.component.type` | `inference-engine` / `workflow-engine` / `ml-registry` |

### Topology relations

| Edge | Mechanism |
|---|---|
| `kserve → llm-model.<x>` | Existing `traces/model-relations` (auto-discovers from `gen_ai.*` spans when KServe runs vLLM/Ollama) |
| `application → kserve` | Existing `traces/provider-relations` (when app sets `gen_ai.provider.name=kserve`) |
| `kubeflow-pipelines → kserve` | New `transform/kubeflow-relations`: spans with `kserve.inference.service` attribute → `peer.service=kserve` |
| `kubeflow-pipelines → kubeflow-model-registry` | New `transform/kubeflow-relations`: spans hitting registry API → `peer.service=kubeflow-model-registry` |

## Metric bindings

Documented in `stackpack/suse-ai/provisioning/templates/metric-bindings/kserve-metrics.sty` and `kubeflow-pipelines-metrics.sty`. Highlights:

- KServe: request rate, P50/P95/P99 latency, per-step latency, queue depth, model load duration, error ratio.
- Pipelines: API request rate, API latency P95, run success ratio, run failure rate, reconcile lag, MLMD operation rate.

## Monitors

`templates/monitors/kserve/monitor.sty` and `templates/monitors/kubeflow-pipelines/monitor.sty`. The cross-cutting `-3001 GenAI Application Metric Stream Active` monitor will fire for KServe whenever an instrumented application sends `gen_ai.*` traffic to it; KFP and Model Registry do not emit GenAI client metrics themselves, so they rely on their own per-product monitors (`-3019..-3022` for KFP; none in v1 for Model Registry).

Each monitor links to a per-symptom remediation hint (e.g. `remediation-error-rate.md.hbs`, `remediation-reconcile-lag.md.hbs`) — see those files for the actual kubectl commands.

## Future work

- Custom OTel receiver in the SUSE AI collector image to poll the Kubeflow Model Registry REST API and synthesize metrics (registered_models, model_versions, registrations_total). IDs -650..-659 reserved for the resulting bindings; -3023 reserved for the registration-error-rate monitor.
- Kubeflow Notebooks, Central Dashboard, Training Operator, Katib coverage.

## Troubleshooting

### KServe InferenceService doesn't appear under "Inference Engines"

- Confirm the `serving.kserve.io/enable-metric-aggregation: "true"` annotation is set on the InferenceService.
- Confirm the qpext port name is `http-usermetric` (default for KServe ≥ v0.10).
- Check the OTel collector logs for `kserve-inferenceservices` scrape errors.

### Pipelines control plane shows no data

- Verify `KUBEFLOW_NAMESPACE` matches your install (some distributions use `kubeflow-system`).
- Confirm the four control-plane services exist: `kubectl get svc -n <namespace> | grep -E 'ml-pipeline|metadata-grpc'`.
- Some KFP versions don't expose all controller-runtime metrics — empty charts are expected then.

### Model Registry shows no metrics

This is expected in v1 — Model Registry is topology-only. K8s pod-level health comes through the K8s StackPack.

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

- `kubeflow-pipelines` — Kubernetes service discovery in `${KUBEFLOW_NAMESPACE}` (default `kubeflow`), keeping only the `http` metrics port. The KFP api-server serves Prometheus on `ml-pipeline`'s `http` port (8888); its `grpc` port (8887) and the gRPC-only `metadata-grpc-service` (8080) return 415/503 on `/metrics`, so a `__meta_kubernetes_service_port_name` filter (`http|metrics|http-metrics`) drops them.
- `kserve-controller` — pods labeled `control-plane=kserve-controller-manager`, discovered cluster-wide (no namespace filter). The official SUSE Kubeflow chart co-locates the KServe controller in the `kubeflow` namespace; a standalone KServe install uses `kserve`. The label is specific enough to find it either way. The SUSE chart fronts the controller metrics with **kube-rbac-proxy** (HTTPS on port `8443`, bearer-token auth), so the job uses `scheme: https`, `insecure_skip_verify`, and the collector ServiceAccount token (`credentials_file`), and keeps only port `8443`. This requires the collector clusterRole to grant `nonResourceURLs: ["/metrics"]` (kube-rbac-proxy authorizes via SubjectAccessReview).
- `kserve-inferenceservices` — pods carrying `serving.kserve.io/inferenceservice` label, scraped on the **model container's own Prometheus endpoint** (`prometheus.kserve.io/{port,path}`, normally `8080`/`/metrics`). This is the primary source of KServe *serving* metrics (`request_predict_seconds`, pre/post-process latency); the controller job above only adds controller-runtime reconcile metrics. It does **not** use the metric-aggregation port (`http-usermetric`/`aggr-metric:9088`): that endpoint only binds when KServe's qpext queue-proxy image is configured, and the SUSE Kubeflow chart ships the **stock Knative queue-proxy** (`config-deployment` `queueSidecarImage`), so nothing ever listens there even with `enable-metric-aggregation: "true"`. The job anchors on the `user-port` container port to avoid duplicate targets, then rewrites the address/path from the KServe annotations.

> **Collector image requirement:** these configs need a collector image whose OTTL supports the resource-context transforms and whose topology exporter accepts `cluster_name`. Validated against `ghcr.io/suse/suse-ai-opentelemetry-collector:latest`; the productized `registry.suse.com/ai/containers/suse-ai-opentelemetry-collector:0.149.0` is too old (rejects `cluster_name`). OTTL statements must **not** use the `??` operator — the shipping collector lexers reject it; guard nil with `attributes[...] != nil and IsMatch(...)` instead.

### Required customer configuration

KServe InferenceServices should enable Prometheus scraping so KServe advertises the
model container's metrics endpoint via the `prometheus.kserve.io/{port,path}` annotations:

```yaml
metadata:
  annotations:
    serving.kserve.io/enable-prometheus-scraping: "true"
    # Harmless but non-functional on the SUSE chart (no qpext queue-proxy image);
    # the job scrapes the model container directly, not the aggregate port.
    serving.kserve.io/enable-metric-aggregation: "true"
```

**Note on metric aggregation:** KServe's `enable-metric-aggregation` is meant to merge
the model-server metrics with queue-proxy request metrics onto a single `aggr-metric:9088`
(`http-usermetric`) endpoint. That only works when Knative's `queueSidecarImage`
(`config-deployment` in `knative-serving`) points at KServe's **qpext** queue-proxy image.
The SUSE Kubeflow chart ships the stock Knative queue-proxy, so the aggregate port is never
bound — the mutator sets the `AGGREGATE_PROMETHEUS_METRICS_PORT=9088` env and the
`prometheus.io/port: 9088` annotation, but nothing listens there. We therefore scrape the
model container's own `/metrics` (which already exposes `request_predict_seconds` etc.)
and skip the aggregate endpoint entirely. Queue-proxy request-latency metrics are not
collected under this chart as a result.

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

- Confirm the `serving.kserve.io/enable-prometheus-scraping: "true"` annotation is set on the InferenceService (this makes KServe advertise `prometheus.kserve.io/{port,path}`).
- Confirm the model container serves `/metrics` on its user port (8080): `kubectl exec <predictor-pod> -c kserve-container -- wget -qO- localhost:8080/metrics`.
- Do **not** expect data on the `http-usermetric`/`aggr-metric:9088` port on the SUSE chart — it is not bound (stock Knative queue-proxy, no qpext). See "Required customer configuration".
- Check the OTel collector logs for `kserve-inferenceservices` scrape errors.

### Pipelines control plane shows no data

- Verify `KUBEFLOW_NAMESPACE` matches your install (some distributions use `kubeflow-system`).
- Confirm the four control-plane services exist: `kubectl get svc -n <namespace> | grep -E 'ml-pipeline|metadata-grpc'`.
- Some KFP versions don't expose all controller-runtime metrics — empty charts are expected then.

### Model Registry shows no metrics

This is expected in v1 — Model Registry is topology-only. K8s pod-level health comes through the K8s StackPack.

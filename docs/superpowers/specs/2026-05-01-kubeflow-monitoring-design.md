# Kubeflow Monitoring Integration — Design

**Status:** Draft, awaiting user review
**Date:** 2026-05-01
**Scope:** Integrate Kubeflow Pipelines, KServe, and Kubeflow Model Registry into the SUSE AI Observability StackPack.

---

## 1. Goal

Add Kubeflow as a first-class monitored product in the StackPack so operators can:

- See KServe inference services, Kubeflow Pipelines control plane, and Model Registry as topology components in SUSE Observability.
- Get out-of-the-box metric charts (request rate, latency, error rate, run success/failure) bound to those components.
- Receive proactive alerts via monitors when key health signals deviate.
- Trace requests through KServe and Pipelines workflows from the product page.

Re-enable the previously commented `workflow-engine` and `ml-registry` menu entries in the SUSE AI sidebar as a side effect of these additions.

---

## 2. Scope

**In scope (v1):**

- `inference-engine.kserve` — single product aggregating all KServe InferenceServices.
- `workflow-engine.kubeflow-pipelines` — single product aggregating the KFP control plane (api-server, scheduledworkflow controller, persistence agent, MLMD).
- `ml-registry.kubeflow` — topology-only shell (no metric bindings in v1; placeholder for a future custom OTel receiver).
- New OTel collector scrape jobs, transform processors, and trace pipelines.
- New ComponentTypes, MetricBindings, Monitors, TraceBindings, and SpanToComponentBindings.
- Re-enable `workflow-engine` and `ml-registry` menu entries.

**Out of scope (v1):**

- Kubeflow Notebooks, Central Dashboard, Training Operator, Katib (deferred).
- Per-InferenceService product components (chosen against in design Q2 — kept as related-resources instances).
- Per-pipeline-run topology nodes (chosen against in design Q3 — too noisy).
- Re-enabling the `model-proxy` and `mcp-server` menu entries (out of scope for this work; no Kubeflow tie).
- Kubeflow Model Registry metrics (deferred until custom receiver work).

---

## 3. Architecture

### 3.1 Component model

| ComponentType | Category | Aggregation | Specialization rule |
|---|---|---|---|
| `inference-engine.kserve` | inference-engine | One product per cluster; InferenceServices appear under "Instances" tab | Product extractor switch case on `productName == "kserve"` |
| `workflow-engine.kubeflow-pipelines` | workflow-engine | One product per cluster; control-plane pods appear under "Instances" tab | Product extractor switch case on `productName == "kubeflow-pipelines"` |
| `ml-registry.kubeflow` | ml-registry | One product per cluster | Product extractor switch case on `productName == "kubeflow-model-registry"` |

KServe → LLM-model relations are auto-discovered by the existing `traces/model-relations` pipeline whenever an InferenceService runs vLLM/Ollama and emits `gen_ai.provider.name` + `gen_ai.request.model` spans. No new code required for that edge.

### 3.2 Data flow

```
KServe InferenceService pods --(prom scrape, qpext)--> OTel collector
KFP control-plane pods       --(prom scrape)----------> OTel collector
Kubeflow MR pods             --(K8s health only, v1)---> SUSE Obs (via K8s agent)

OTel collector pipelines:
  metrics:
    + transform/kserve, transform/kubeflow-pipelines, transform/kubeflow-model-registry
      (tag suse.ai.managed, suse.ai.component.{name,type})
  traces:
    + transform/kserve-traces, transform/kfp-traces
      (tag suse.ai.component.name on incoming spans)
    + transform/kubeflow-relations
      (set peer.service for kfp -> kserve and kfp -> model-registry edges)
  routing/traces fans out to existing topology, model-relations, provider-relations
                 + new traces/kubeflow-relations
```

### 3.3 Topology relations

| Relation | Mechanism | New code? |
|---|---|---|
| `kserve → llm-model.<x>` | Existing `traces/model-relations` (via `gen_ai.*`) | No |
| `application → kserve` | Existing `traces/provider-relations` if app emits `gen_ai.provider.name=kserve` | No |
| `kubeflow-pipelines → kserve` | New OTTL transform: spans with `kserve.inference.service` attribute → `peer.service=kserve` | Yes |
| `kubeflow-pipelines → kubeflow-model-registry` | New OTTL transform: spans hitting registry API → `peer.service=kubeflow-model-registry` | Yes |

Product-to-product edges materialize via the existing topology exporter (no exporter-side changes).

---

## 4. Signal collection — OTel collector changes

All in `integrations/otel-collector/otel-values.yaml` (test config; production users override via Helm values).

### 4.1 New environment variable

```yaml
extraEnvs:
  - name: KUBEFLOW_NAMESPACE
    value: "kubeflow"   # default; users override per cluster
```

### 4.2 New Prometheus scrape jobs

Under `receivers.prometheus.config.scrape_configs`:

```yaml
- job_name: 'kubeflow-pipelines'
  scrape_interval: 15s
  kubernetes_sd_configs:
    - role: service
      namespaces:
        names: ['${env:KUBEFLOW_NAMESPACE}']
  relabel_configs:
    - source_labels: [__meta_kubernetes_service_name]
      action: keep
      regex: '(ml-pipeline|ml-pipeline-scheduledworkflow|ml-pipeline-persistenceagent|metadata-grpc-service)'
- job_name: 'kserve-controller'
  scrape_interval: 15s
  kubernetes_sd_configs:
    - role: pod
      namespaces:
        names: ['kserve']
  relabel_configs:
    - source_labels: [__meta_kubernetes_pod_label_control_plane]
      action: keep
      regex: 'kserve-controller-manager'
- job_name: 'kserve-inferenceservices'
  scrape_interval: 15s
  kubernetes_sd_configs:
    - role: pod
  relabel_configs:
    - source_labels: [__meta_kubernetes_pod_label_serving_kserve_io_inferenceservice]
      action: keep
      regex: '.+'
    - source_labels: [__meta_kubernetes_pod_container_port_name]
      action: keep
      regex: 'http-usermetric'   # qpext aggregated port
```

### 4.3 New transform processors

Mirror the existing `transform/vllm` pattern:

- `transform/kserve` — set `suse.ai.managed=true`, `suse.ai.component.name=kserve`, `suse.ai.component.type=inference-engine` where `service.name` matches the kserve runtime pattern.
- `transform/kubeflow-pipelines` — same with name `kubeflow-pipelines`, type `workflow-engine`.
- `transform/kubeflow-model-registry` — same with name `kubeflow-model-registry`, type `ml-registry`.

Wired into the existing `metrics` pipeline alongside the current vllm/qdrant/milvus transforms.

### 4.4 New trace transforms

- `transform/kserve-traces` — set `suse.ai.component.name=kserve` and `suse.ai.component.type=inference-engine` on spans where the resource carries `serving.kserve.io/inferenceservice` attribute (KServe queue-proxy spans), OR where `service.name` matches the regex `.*-predictor-default|.*-transformer-default|.*-explainer-default` (the Knative-revision naming convention).
- `transform/kfp-traces` — set `suse.ai.component.name=kubeflow-pipelines` and `suse.ai.component.type=workflow-engine` where `service.name` is one of `ml-pipeline`, `ml-pipeline-scheduledworkflow`, `ml-pipeline-persistenceagent`, `metadata-grpc-service`.
- `transform/kubeflow-relations` — OTTL statements (executed in `traces/kubeflow-relations` after the resource transforms above so source attribution is correct):
  - `set(attributes["peer.service"], "kserve") where attributes["kserve.inference.service"] != nil`
  - `set(attributes["peer.service"], "kubeflow-model-registry") where IsMatch(attributes["http.url"], ".*model-registry.*")`

New pipeline `traces/kubeflow-relations` consumes from `routing/traces` and exports to `otlp` after the transforms. Added to the routing connector's `pipelines:` table.

### 4.5 Customer requirement

Document in `enabled.md` and `configuration.md`:

> KServe InferenceServices must set `serving.kserve.io/enable-metric-aggregation: "true"` (or use the qpext extension globally) for per-runtime metrics to be scraped.

---

## 5. Stackpack artifacts

All paths relative to `stackpack/suse-ai/provisioning/templates/`.

### 5.1 ID allocation (verified against MEMORY.md, no collisions)

| Artifact | IDs |
|---|---|
| ComponentTypes | -5015 (kserve), -5016 (kfp), -5017 (model-registry) |
| MetricBindings — kserve | -630 to -639 |
| MetricBindings — kfp | -640 to -649 |
| MetricBindings — model-registry | (none in v1) |
| Monitors — kserve | -3016 to -3018 |
| Monitors — kfp | -3019 to -3022 |

### 5.2 New files

```
component-types/products.sty
  + ComponentType inference-engine.kserve              (id -5015)
  + ComponentType workflow-engine.kubeflow-pipelines   (id -5016)
  + ComponentType ml-registry.kubeflow                 (id -5017)
  + TraceBinding + SpanToComponentBinding for each (kserve, kfp; not model-registry)

metric-bindings/kserve-metrics.sty                     (NEW)
metric-bindings/kubeflow-pipelines-metrics.sty         (NEW)

monitors/kserve/monitor.sty                            (NEW)
monitors/kserve/remediation-deviating.md.hbs           (NEW)
monitors/kserve/remediation-critical.md.hbs            (NEW)
monitors/kubeflow-pipelines/monitor.sty                (NEW)
monitors/kubeflow-pipelines/remediation-*.md.hbs       (NEW)

provisioning/icons/kserve.svg                          (NEW)
provisioning/icons/kubeflow-pipelines.svg              (NEW)
provisioning/icons/kubeflow-model-registry.svg         (NEW)
```

### 5.3 Modified files

| File | Change |
|---|---|
| `suse-ai.sty` | `{{ include }}` the 2 new metric-binding files and 2 new monitor files |
| `shared.sty` | Uncomment `query-view:workflow-engine` and `query-view:ml-registry` (lines 28, 30) |
| `sync/component-mapping-function.groovy` | Add 3 cases (`kserve`, `kubeflow-pipelines`, `kubeflow-model-registry`) to the `productName` switch (lines 89-113) |
| `sync/suse-ai-product-id-extractor.groovy` | Add the same 3 cases to its switch (lines 58-81) |
| `view-types/inference-engines.sty` | Confirm `Latency P95` column already resolves for the kserve binding (the column references a metric-binding URN — kserve gets the same one). If the existing column hardcodes a vllm-only URN, switch it to a per-type fallback. |
| `view-types/workflow-engines.sty` | Add `Run Success Rate` column → `urn:stackpack:suse-ai:shared:metric-binding:kubeflow-pipelines:run-success-rate` |
| `view-types/ml-registries.sty` | No change in v1 |
| `integrations/otel-collector/otel-values.yaml` | All collector changes from §4 |
| `stackpack.conf` | Bump version to v201 |
| `resources/configuration.md` | Add Kubeflow setup section (namespace, kserve annotation) |
| `resources/enabled.md` | Add 3 new product types to the list |
| `resources/detailed-overview.md` | Add Kubeflow to supported-products list |
| `resources/RELEASE.md` | New v201 entry |
| `knowledge/KUBEFLOW.md` (NEW) | Architecture & troubleshooting (mirrors `OPENWEBUI.md`) |

---

## 6. Metric bindings (detail)

Bindings follow `METRIC_BINDINGS_GUIDE.md` patterns: multi-query for percentiles, `or 0` on ratios, `${name}` substitution for component-scoped queries.

### 6.1 KServe (`kserve-metrics.sty`, scope `type = "inference-engine.kserve"`)

| ID | Name | Primary expression |
|---|---|---|
| -630 | Request Rate | `sum by (service_name) (rate(revision_request_count{namespace=~".+"}[${__rate_interval}]))` |
| -631 | Request Latency | `histogram_quantile(0.95, sum by (service_name, le) (rate(revision_app_request_latencies_bucket[5m])))` (multi-query P50/P95/P99) |
| -632 | Predict Step Latency | multi-query over `request_preprocess_seconds_bucket`, `request_predict_seconds_bucket`, `request_postprocess_seconds_bucket` |
| -633 | Queue Depth | `max by (service_name) (queue_depth)` |
| -634 | Model Load Duration | `max by (service_name) (model_load_seconds)` |
| -635 | Error Ratio | `(sum by (service_name) (rate(revision_request_count{response_code_class="5xx"}[5m])) or 0) / sum by (service_name) (rate(revision_request_count[5m]))` |

### 6.2 Kubeflow Pipelines (`kubeflow-pipelines-metrics.sty`, scope `type = "workflow-engine.kubeflow-pipelines"`)

| ID | Name | Primary expression |
|---|---|---|
| -640 | API Request Rate | controller-runtime `workqueue_adds_total` rate, plus ml-pipeline HTTP server request rate |
| -641 | API Latency P95 | `histogram_quantile(0.95, sum by (verb, le) (rate(rest_client_request_duration_seconds_bucket[5m])))` |
| -642 | Run Success Rate | `(sum(rate(run_server_run_count{status="Succeeded"}[15m])) or 0) / sum(rate(run_server_run_count[15m]))` |
| -643 | Run Failure Rate | `sum(rate(run_server_run_count{status="Failed"}[15m]))` |
| -644 | Reconcile Lag | `max(workqueue_unfinished_work_seconds)` |
| -645 | MLMD Operation Rate | `sum by (grpc_method) (rate(grpc_server_handled_total{job=~".*metadata-grpc.*"}[5m]))` |

### 6.3 Common bindings (no new file)

`common-metrics.sty` (CPU/memory) and `genai-metrics.sty` (gen_ai_client_*) attach to all three new product types via their existing scope predicates.

---

## 7. Monitors (detail)

All use `urn:stackpack:common:monitor-function:threshold`. Each has a remediation hint sibling file.

### 7.1 KServe (`monitors/kserve/monitor.sty`)

| ID | Name | Query (sketch) | Threshold | State |
|---|---|---|---|---|
| -3016 | KServe High Error Rate | `(sum by (service_name) (rate(revision_request_count{response_code_class="5xx"}[5m])) or 0) / sum by (service_name) (rate(revision_request_count[5m]))` | > 0.05 | CRITICAL |
| -3017 | KServe Latency P95 High | `histogram_quantile(0.95, sum by (service_name, le) (rate(revision_app_request_latencies_bucket[5m])))` | > 2 (s) | DEVIATING |
| -3018 | KServe Model Load Failures | `sum by (service_name) (increase(model_load_seconds_count{success="false"}[5m]))` | > 0 | DEVIATING |

`urnTemplate`: `urn:suse-ai:product:inference-engine:kserve` (single product). The `service_name` label is informational only — used in `titleTemplate` so operators see which InferenceService is degraded.

### 7.2 Kubeflow Pipelines (`monitors/kubeflow-pipelines/monitor.sty`)

| ID | Name | Query (sketch) | Threshold | State |
|---|---|---|---|---|
| -3019 | KFP Run Failure Rate High | failure rate / total run rate | > 0.10 | DEVIATING |
| -3020 | KFP Reconcile Lag | `max(workqueue_unfinished_work_seconds)` | > 60 (s) | DEVIATING |
| -3021 | KFP API Server Down | `up{job="kubeflow-pipelines",service=~".*ml-pipeline.*"}` | == 0 for 5m | CRITICAL |
| -3022 | KFP MLMD gRPC Errors | `sum(rate(grpc_server_handled_total{grpc_code!="OK",job=~".*metadata-grpc.*"}[5m]))` | > 1 | DEVIATING |

`urnTemplate`: `urn:suse-ai:product:workflow-engine:kubeflow-pipelines`.

### 7.3 Cross-cutting

The existing `-3001 GenAI Application Metric Stream Active` monitor automatically covers all three new products because they carry `suse.ai.component.name` tags.

---

## 8. Future extension — Model Registry custom receiver

Deferred for v1, captured here for posterity:

A custom OTel receiver in the SUSE AI collector image (separate repo, https://github.com/SUSE/suse-ai-opentelemetry-collector) could poll the Kubeflow Model Registry REST API on a fixed interval and synthesize metrics:

| Synthesized metric | Type | Source |
|---|---|---|
| `kfmr.registered_models` | Gauge | `GET /api/model_registry/v1alpha3/registered_models` count |
| `kfmr.model_versions` | Gauge by `model_name` | `GET .../model_versions` per model |
| `kfmr.registrations_total` | Counter | derived from `created_at` deltas |
| `kfmr.api_request_duration_seconds` | Histogram | from polling itself (proxy for registry latency) |

Once landed, fill `kubeflow-model-registry-metrics.sty` with bindings (IDs -650 to -659 reserved) and add a registration-error-rate monitor (id -3023).

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Customer KServe install doesn't enable metric aggregation | Document the annotation requirement prominently in `configuration.md`; collector falls back gracefully (no metrics, but topology still works via traces) |
| `kubeflow` namespace name varies (some installs use `kubeflow-system`) | `KUBEFLOW_NAMESPACE` env var is overridable per Helm install |
| KFP metric names drift between v1 and v2 of the API | Both metric names checked into bindings; queries use `or` between alternatives where divergent |
| Per-step kserve metrics depend on the runtime (sklearn vs vLLM) | Bindings degrade gracefully — empty series render as "no data" rather than breaking the chart |
| ID collision with concurrent work | Final implementation step does a `grep -rn "id: -" stackpack/` sweep before commit |

---

## 10. Verification plan

After implementation:

1. `task stackpack-upload` succeeds without provisioning errors.
2. `sts topology-sync describe` shows no errors for either sync.
3. With a test KServe InferenceService running:
   - The `inference-engine.kserve` product appears under the **Inference Engines** menu.
   - Per-InferenceService rows appear in the related-resources tab.
   - Request rate and latency charts render with data.
4. With a test pipeline run:
   - `workflow-engine.kubeflow-pipelines` product appears under the (newly re-enabled) **Workflow Engines** menu.
   - Run success/failure metrics tick when runs complete.
5. `ml-registry.kubeflow` appears under the (newly re-enabled) **ML Registries** menu, with K8s pod-level health.
6. A simulated 5xx burst from a kserve InferenceService triggers monitor `-3016` to CRITICAL.

---

## 11. References

- KServe Prometheus metrics: https://kserve.github.io/archive/0.14/modelserving/observability/prometheus_metrics/
- KServe qpext: https://github.com/kserve/kserve/blob/master/qpext/README.md
- Kubeflow Pipelines architecture: https://deepwiki.com/kubeflow/pipelines/6.5-supporting-controllers-and-services
- Existing patterns followed: `knowledge/COMPONENT_TYPE_GUIDE.md`, `knowledge/METRIC_BINDINGS_GUIDE.md`, `knowledge/MONITOR_CREATION_GUIDE.md`, `knowledge/GENAI_TOPOLOGY_INFERENCE.md`, `knowledge/OPENWEBUI.md`.

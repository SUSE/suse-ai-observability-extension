# SUSE AI Observability StackPack

## Version 2.2.0

- Fixed the Collector examples' Kubeflow trace path bypassing tail sampling.
  Product classification now runs before trace fan-out, dependency hints run
  before sampling, and the separate topology exporter still sees all spans.
- Preserved existing Kubernetes namespaces during application inference and
  Model Registry specialization. Removed the topology exporter's static
  namespace label; resource discovery supplies actual namespace metadata.
- Corrected Model Registry monitor targets to the canonical ML-registry URN.
  Validation and availability queries now follow the latest synthetic check,
  including failure and recovery when the receiver emits different series.
- Scoped KServe alerts and serving charts to KServe metrics. Reconcile lag now
  measures the longest active work item; queue charts retain the queue name.
- Scoped pod GPU/vGPU charts by cluster and namespace, and node charts by
  cluster, to avoid mixing identically named workloads.
- Restored five-minute topology data-source expiry after updates stop and
  repaired the Milvus request-success metric-binding reference.
- Added local Collector, PromQL, Groovy, and template regression checks through
  `task stackpack-test`. Collector example changes require a Collector config
  rollout in addition to upgrading the StackPack.

- Added Kubeflow integration: KServe (`inference-engine.kserve`), Kubeflow Pipelines (`workflow-engine.kubeflow-pipelines`), Kubeflow Model Registry (`ml-registry.kubeflow`).
- Re-enabled the **Workflow Engines** and **ML Registries** sidebar menu entries.
- New OTel collector scrape jobs and transforms for Kubeflow metrics and traces (`KUBEFLOW_NAMESPACE`, product resource tagging, and dependency hints on the sampled trace path).
- New monitors for KServe and Kubeflow Pipelines, each with per-symptom
  remediation hints.
- Expanded Kubeflow Pipelines coverage with KFP gRPC reliability, Argo workflow
  phases, reconciliation latency, queue health, pod outcomes, controller errors,
  and retries.
- Added instrumented demo-lifecycle charts for model accuracy, step duration,
  and the KServe deployment smoke test. One-shot lifecycle charts remain visible
  between runs while selecting only the newest run's series within 24 hours.
- Added synthetic Kubeflow Model Registry availability, duration, response-size,
  response-validation, and error metrics, plus unavailable/slow/invalid-response
  monitors.
- Added agent execution, RAG retrieval quality, and generated demo-scenario
  metric bindings to the application and agent component types.
- Added product specialization and topology relations for Kubeflow products
  and demo applications.
- Added pre-upload duplicate-ID and Groovy validation to the Taskfile workflow.

## Version 2.1.0

- Fixed product-to-product topology not appearing in the UI: the "SUSE AI Topology" sync now consumes the topology exporter's fixed stream topic.
- Added multi-cluster support: product components now carry a `k8s.cluster.name` label (sourced from `K8S_CLUSTER_NAME`) as metadata, so the same product aggregates across clusters.

## Version 0.1.241

- Consolidated vLLM latency charts into multi-query bindings (P99/P95/P90/P50/Avg in a single chart).
- Added per-model component views for vLLM inference engines with dedicated performance metrics.
- Added "Top Models by Usage" metric binding for vLLM.
- Fixed application metric bindings to use correct OTel-to-Prometheus metric names.
- Added Total Tokens and Total Cost columns to the AI Applications view.
- Added Operation Duration (P95) metric binding for application components.
- Bound GenAI health monitor to application components.
- Updated documentation links.

## Version 0.1.110

- Initial release of the SUSE AI Observability StackPack.
- Provides topology mapping for GenAI components based on OpenTelemetry semantic conventions.
- Supports categorization into User Workloads, Platform Components, and GPU Nodes.
- Includes metric bindings and health monitors for AI-specific metrics (token usage, inference latency, GPU memory, etc.).
- Uses `suse-ai:` prefix for component URNs to avoid conflicts with standard OpenTelemetry components.

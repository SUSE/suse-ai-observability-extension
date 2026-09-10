# Kubeflow integration

**Current status:** KServe, Kubeflow Pipelines, and Kubeflow Model Registry have
topology, traces, metrics, and monitors in the official StackPack 2.2.0 source. Model Registry
metrics are synthetic API health signals because the deployed registry does not
publish a Prometheus endpoint.

## Product topology

| Product | Component type | Signal sources |
|---|---|---|
| KServe | `inference-engine.kserve` | predictor metrics, controller metrics, application and pipeline spans |
| Kubeflow Pipelines | `workflow-engine.kubeflow-pipelines` | KFP API metrics, Argo controller metrics, instrumented demo steps |
| Kubeflow Model Registry | `ml-registry.kubeflow` | HTTP synthetic check and client spans |

The SUSE AI synchronization keeps its own `urn:suse-ai:` identifiers so it does
not take ownership of OpenTelemetry components. The Model Registry component
uses the canonical `urn:suse-ai:product:ml-registry:kubeflow-model-registry`
identifier for monitor attachment. Metrics-only discovery creates that ID.
When topology discovery supplies the legacy inference-engine external ID, the
sync preserves it for relation resolution and adds the canonical ID as an alias.

## Collector configuration

The test-environment configuration is
`integrations/otel-collector/otel-values.yaml`. It is validated against the
custom SUSE AI Collector 0.156.0. Its Kubeflow-specific receivers and scrape
jobs are:

- `prometheus/kubeflow-pipelines`: discovers Kubeflow services and keeps only
  HTTP metrics ports. In the deployed chart, `ml-pipeline:8888` is the useful
  KFP API target; the gRPC ports are not Prometheus endpoints.
- `prometheus/kubeflow-workflow-controller`: discovers the Argo
  `workflow-controller` pod and scrapes HTTPS port 9090 with its cluster-local
  self-signed certificate accepted.
- `prometheus/kserve-controller`: scrapes kube-rbac-proxy HTTPS port 8443 using
  the collector ServiceAccount token and `/metrics` non-resource permission.
- `prometheus/kserve-inferenceservices`: discovers predictor pods and rewrites
  the target from `prometheus.kserve.io/{port,path}` annotations to the model
  container's endpoint, normally port 8080 and `/metrics`.
- `http_check/model-registry`: calls
  `/api/model_registry/v1alpha3/registered_models` every 30 seconds with the
  configured bearer token and validates that the response contains `"items"`.

The file intentionally also retains the supported Elasticsearch/OpenSearch,
Qdrant, Milvus, vLLM, GPU, and debug-exporter configuration. An absent service
can produce expected scrape or DNS errors in a particular demo cluster; do not
remove its configuration merely to silence that environment.

`MODEL_REGISTRY_BEARER_TOKEN=demo` is appropriate only for this demo cluster.
Use a Secret-provided token in any non-demo environment.

### KServe metric aggregation

The SUSE Kubeflow chart uses the stock Knative queue-proxy. KServe's optional
qpext aggregation listener therefore does not bind on port 9088 even if
`serving.kserve.io/enable-metric-aggregation` is set. The collector intentionally
scrapes the model container's own metrics endpoint instead.

### Resource tagging

The collector assigns:

| Product | `suse.ai.component.name` | `suse.ai.component.type` |
|---|---|---|
| KServe | `kserve` | `inference-engine` |
| Pipelines API and Argo | `kubeflow-pipelines` | `workflow-engine` |
| Model Registry check | `kubeflow-model-registry` | `ml-registry` |

The Prometheus receiver exposes the scrape job as resource `service.name`.
Transforms must match the job names (`kubeflow-pipelines`,
`kubeflow-workflow-controller`, `kserve-controller`, and
`kserve-inferenceservices`), not guessed workload names. OTTL in the shipping
collector must use explicit nil guards; its lexer does not accept `??`.

Application inference preserves an existing `k8s.namespace.name`, including
when `service.namespace` describes a different logical namespace. Only missing
Kubernetes namespaces fall back to `service.namespace` or `SUSE_AI_NAMESPACE`.
The Model Registry synthetic check supplies `KUBEFLOW_NAMESPACE`, and its
Groovy mapper preserves incoming namespace labels. The topology exporter's
static `namespace` is empty because its product URNs aggregate across namespaces;
namespace metadata comes from resource-based discovery when available.

## Topology relations

KServe and KFP resource classification runs on trace ingress before fan-out.
`transform/kubeflow-relations` adds `peer.service` hints on `traces/sampling`
before tail sampling. There is no separate `traces/kubeflow-relations` backend
export branch. The private `traces/topology` branch runs
`transform/kubeflow-product-topology`, translating dependencies for the topology
exporter without adding synthetic GenAI attributes to normal backend traces.
It still sees spans rejected by tail sampling, preserving product relations:

| Edge | Source evidence |
|---|---|
| application or agent -> KServe | client span with `kserve.inference.service` |
| application or pipeline -> Model Registry | client span URL containing `model-registry` |
| pipeline -> KServe | instrumented deploy/predict client spans |

The August demo verification recorded all three specialized products. `sts topology
inspect` resolved `kubeflow-pipelines`, `kubeflow-model-registry`,
`agent-service`, `rag-service`, and `traffic-gen` to their SUSE AI component
types.

The topology data source expires elements after five minutes without updates.
This is separate from the pinned Collector exporter's 15-minute retention of
sparse relations across periodic complete snapshots.

## Metric bindings

### KServe

- predictor request rate and prediction latency;
- preprocess, predict, and postprocess step latency;
- controller reconciliation rate and error ratio;
- controller workqueue depth.

KServe queries select `suse_ai_component_name="kserve"` before aggregating.
The reconcile ratio reports zero for an idle observed controller or one with
no error series, and remains empty when the controller's metrics are absent.
Workqueue series use the `name` label. The lag monitor checks
`workqueue_longest_running_processor_seconds`, which measures an individual
active item; `workqueue_unfinished_work_seconds` sums time across active items.

The model server uses `request_predict_seconds`-family histograms labeled by
`model_name`. Queue-proxy `revision_*` metrics are not available in this chart.

### Kubeflow Pipelines

- run and pipeline API rates, total runs, pipeline/version/job inventory;
- completed-run success ratio and terminal outcomes;
- gRPC request rate, error ratio, and P95 handling latency;
- Argo workflows by phase and operation-duration P95;
- queue depth, unfinished work, oldest item, and retry rate;
- pending pods, pods by phase, and controller error rate;
- demo model accuracy, step-duration P95, and deployment smoke-test outcomes.

The exact deployed Argo names include
`argo_workflows_pod_pending_count_total`, `argo_workflows_pods_count_total`,
`argo_workflows_error_count_total`, `argo_workflows_queue_retries_total`, and
`argo_workflows_count_total`. The short-lived demo step pods normally export one
cumulative point, so their duration, accuracy, and smoke-test bindings use the
sample timestamp to retain and select only the newest series within 24 hours;
they intentionally do not use `rate()`.

### Kubeflow Model Registry

- 2xx/4xx/5xx availability status;
- request duration;
- response-body validation;
- response size;
- connection or read errors.

The receiver emits passed or failed validation samples, rather than a zero for
the opposite outcome. Validation queries compare their timestamps so a new
failure alerts and a new success clears the failure. Availability queries also
select the latest status series per endpoint before aggregation, since
`http_status_code` is absent on zero-valued status classes. With no eligible
check samples, the queries stay empty rather than reporting success.

### Demo applications

- agent tool call rate, tool-duration P95, iterations, and run outcomes;
- RAG retrieved-document count, no-hit rate, context-size P95, and request P95;
- generated scenario rate/outcome and scenario-duration P95.

## Monitors

The Kubeflow monitor set covers:

- KFP API unavailable;
- Argo workflow controller unavailable;
- recent workflow failures;
- workflow pod image-pull failures;
- KFP gRPC error ratio;
- controller queue lag;
- Model Registry unavailable, slow, or returning an invalid body;
- KServe predict latency, reconcile errors, and reconcile lag.

Each monitor maps directly to a product URN and has a remediation document.

## Demo lifecycle

The companion repo's `demo/kubeflow` pipeline creates a real KFP Dataset,
trains and evaluates a scikit-learn model, writes KFP Model/Metrics artifacts,
registers the exact artifact in Model Registry, deploys it from the same
S3-compatible object store to KServe, and performs a prediction smoke test. The
stable `suse-ai-sklearn-iris` Service selects only the latest-created revision
after it becomes the latest-ready revision, avoiding both Kubeflow OIDC and
stale-revision routing.

## Icon verification

The customized Kubeflow Pipelines SVG is valid XML and decodes to 7,682 bytes.
Its SHA-256 is
`37a17f2e30fa14b7ba98f33d0ce32eb25d337755c3194b3f988d7decad62265c`.
The source and the installed ComponentType have the same hash. The Milvus SVG is
also valid XML. A blank topology icon is therefore not evidence that the stock
Kubeflow icon was deployed; browser cache or UI rendering can be investigated
separately without changing the StackPack icon payload.

## Debugging order

Debug the integration one evidence boundary at a time. This prevents a UI
symptom from being misdiagnosed as a collector or StackPack problem:

1. Confirm the upstream endpoint serves the expected signal and record its
   exact metric names and labels.
2. Confirm the collector discovers that endpoint and has no current scrape or
   export error for it.
3. Query the raw signal in VictoriaMetrics before evaluating a MetricBinding or
   monitor expression.
4. Inspect the installed StackPack node with `sts settings describe`; do not
   assume the working-tree STY is what the backend currently uses.
5. Evaluate the exact installed query and component scope.
6. Only then investigate topology rendering, browser cache, or other UI state.

For short-lived pipeline pods, an instant raw query can be empty after
Prometheus staleness even though the run exported correctly. The lifecycle
bindings retain a 24-hour window and select the newest timestamp. Histogram
selection must preserve `(le, step)` while choosing the newest run, and smoke
selection must preserve `inference_service`; otherwise buckets or outcomes from
different runs can be combined. A single cumulative point is evidence, but it
is not a counter rate.

KServe deployment acceptance is also a handoff check, not merely a Ready
condition. Require `latestCreatedRevision == latestReadyRevision` before
updating the stable Service, then verify that the Service selector and its
endpoint pod both name that exact revision. This catches the window in which an
older revision remains Ready while a new revision is still starting.

## Troubleshooting

- **No KServe serving metrics:** verify the InferenceService advertises
  `prometheus.kserve.io/port` and `prometheus.kserve.io/path`, then send at least
  one prediction. A transient scrape refusal while a revision starts is normal.
- **No Argo metrics:** verify the workflow-controller pod exposes HTTPS 9090 and
  that `KUBEFLOW_NAMESPACE` matches its namespace.
- **Model Registry is 4xx:** verify the bearer token and the v1alpha3
  `registered_models` route from inside the cluster.
- **Pipeline charts are empty:** inspect the exact metric name in VictoriaMetrics
  before assuming an upstream name; this distribution differs from several
  upstream examples. If the raw one-shot metric exists only in a range query,
  inspect timestamp selection rather than adding `rate()`.
- **Raw backend data exists but a chart is empty:** compare the installed
  MetricBinding expression and component scope with the source STY. This is a
  binding or installed-version boundary, not a scrape boundary.
- **The customized icon is blank:** hash the decoded installed `iconbase64`
  payload and compare it with source. Matching valid bytes move the investigation
  to browser cache or the UI renderer; do not replace the payload speculatively.
- **Topology sync count is non-zero but `describe` has no errors:** the list
  counter is cumulative. Use `sts topology-sync describe` to determine whether
  any current error details remain, and scope acceptance to the SUSE AI syncs
  changed by this StackPack.

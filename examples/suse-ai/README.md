# Collector examples

`collector.yaml` is an OTLP gateway for the v2 StackPack, tested with upstream
`otel/opentelemetry-collector-contrib:0.156.0`. Its component set uses no custom
topology exporter. Configure the OTLP endpoint as `host:port` and supply the API
key through environment variables:

```sh
export SUSE_OBSERVABILITY_OTLP_ENDPOINT=receiver.example.com:443
# Set SUSE_OBSERVABILITY_API_KEY through your secret manager.
otelcol-contrib --config=collector.yaml
```

TLS verification is enabled by default. Use your deployment's existing TLS and
authentication configuration when adapting this example.

The example forwards each trace once, generates standard span metrics, preserves
native GenAI metrics, and forwards correlated logs. Disable its `span_metrics`
connector and remove it from both pipelines if your existing telemetry gateway
already generates those metrics. Sending the same telemetry to two spanmetric
generators will double-count calls.

Native mappings retain model usage from original GenAI spans and SDK metrics.
Application details link to that usage by service identity; model usage does
not create an application-to-model communication edge or require a Count
connector. Both trace-only and metric-only clients remain supported.

AI-specific identifiers use readable, labeled fields, for example:

```text
urn:suse-ai:namespace/prod:service/assistant:agent/planner
urn:suse-ai:namespace/prod:service/assistant:provider/ollama:address/ollama.ai.svc:port/11434:model/llama3
urn:suse-ai:namespace/prod:service/inference:served-model/llama3
```

Model usage retains its provider and both endpoint fields, including empty values
for unknown endpoints. Metrics and traces use the same identity. Values are not
escaped: embedded field separators such as `:service/` or `:agent/` can cause
collisions. Avoiding these sequences in names is an instrumentation convention,
not an enforced validation rule. Ordinary colons and slashes remain usable.

This replaces the earlier draft's length-prefixed agent/model identifiers.
Existing draft installations will discover new AI-specific components; the old
contributions expire after 15 minutes without observations, subject to platform
processing delay. Component history and component-specific monitor overrides are
not migrated. Native OpenTelemetry service and instance identifiers are unchanged.

The standard `service_graph/suse_ai` connector pairs CLIENT/SERVER spans and
emits `suse.ai.service.calls` observations for canonical service relationships.
Only positive increments of its request counter are forwarded, so cached idle
series do not keep relationships alive. The original traces still supply the
companion's instance relationships. No separate tenant mapping is required.
Route both sides of each trace through the same gateway; a scaled deployment
needs trace-aware routing. Virtual/uninstrumented peers do not create fabricated
services. Service-call relationships and model-usage components expire 15 minutes
after their last observation, subject to platform processing delay.

Compatibility transforms fill missing provider and token-usage attributes from
known OpenLLMetry/legacy fields. A nonempty `gen_ai.agent.name` wins; when it is
absent or empty, an agent span (`traceloop.span.kind=agent`) can use a nonempty
`traceloop.entity.name`. Neither an empty name nor a legacy name on a non-agent
span creates a named agent. Original fields, service names, instance IDs,
instrumentation scopes, and `telemetry.sdk.*` remain intact.

Namespace normalization runs before export and before span/servicegraph metrics
are generated. A nonempty `service.namespace` wins. Otherwise, the Collector uses
a nonempty, actual `k8s.namespace.name`, then `default` if neither is available.
Existing `service_namespace` metric labels follow the normalized resource.
For example, an empty service namespace in Kubernetes namespace `team-a` becomes
`team-a`; an explicit `team-b` stays `team-b`. Non-Kubernetes resources receive no
invented Kubernetes attributes. Configure explicit namespaces for workloads that
must remain separate outside Kubernetes. Stock OpenTelemetry 0.1.4 still requires
Kubernetes cluster metadata in its base mappings; normalization alone does not
resolve that separate companion limitation.

Set `suse.ai.product` on the resource for each product receiver. The compatibility
processor recognizes the old exact product names and qualified component types;
it cannot classify an arbitrary service name by guessing its product. It adds
no inference-engine identity based on `gen_ai.provider.name`.

`vllm-receiver.yaml` demonstrates adding an existing product scrape without
rewriting pushed application telemetry:

```sh
export VLLM_SERVICE_NAME=llama-runtime
export VLLM_SERVICE_NAMESPACE=production-cluster-a-ai
export VLLM_METRICS_TARGET=vllm.ai.svc.cluster.local:8000
otelcol-contrib --config=collector.yaml --config=vllm-receiver.yaml
```

Apply the same resource classification at the appropriate existing receivers for
other products. Keep their scrape discovery, authentication, Kubernetes resource
enrichment, Elasticsearch receiver, Model Registry HTTP checks, and DCGM scraping.
This gateway example does not replace those deployment-specific inputs.

Ollama services and instances also receive the generic GenAI charts. They query
SDK metrics attributed to that service: operation duration, token usage, and
optional reported cost. They do not synthesize measurements from Ollama's HTTP
responses or move client measurements onto the server. A client that reports
`gen_ai.provider.name=ollama` remains a client; only a resource identified as the
Ollama product receives that product classification. Missing cost telemetry stays
unavailable, rather than implying zero cost.

## SUSE AI Demo metrics

The **SUSE AI Demo** presentation is for the instrumentation in
[`suse-ai-demo-apps`](https://github.com/thbertoldi/suse-ai-demo-apps). Add
`suse.ai.demo=true` to the demo application's resource attributes, for example
through `OTEL_RESOURCE_ATTRIBUTES`, to enable its Agent, RAG, and demo scenario
panels on the native service and its instances. This opt-in is only for these
custom panels; ordinary GenAI discovery and charts do not require it.

The panels consume these custom metric families after OTLP-to-Prometheus naming:

| Family | Panels and dimensions |
| --- | --- |
| `suse_ai_agent_tool_calls_total`, `suse_ai_agent_tool_duration_seconds_bucket` | Tool rate by `tool_name`/`outcome`; tool duration P95 by `tool_name` |
| `suse_ai_agent_iterations_{sum,count}`, `suse_ai_agent_runs_total` | Iterations per run; run rate by `outcome`/`truncated` |
| `suse_ai_rag_retrieval_documents_{sum,count}`, `suse_ai_rag_retrieval_no_hits_total` | Documents per retrieval; no-hit rate |
| `suse_ai_rag_context_size_bytes_bucket`, `suse_ai_rag_request_duration_seconds_bucket` | Context size and RAG request duration P95 |
| `suse_ai_demo_scenario_runs_total`, `suse_ai_demo_scenario_duration_seconds_bucket` | Scenario rate by `scenario`/`outcome`; scenario duration P95 |

Emit only the relevant families for each demo application. Queries always filter
by service namespace/name and additionally by instance ID on instance details.
Agent spans alone do not provide these custom counters or histograms.

## Collection and migration checks

The first migration test should use unsampled traces. If you later add tail
sampling, derive span metrics before sampling and retain independent SDK/product
metrics. Trace-only named agents can disappear after 15 minutes without an
observed span. Validate topology and metric behavior before removing old
synthetic topology pipelines.

The Collector integration test verifies transformations using real OTLP traces,
metrics, and logs. Follow the test commands in the
[StackPack README](../../stackpack/suse-ai/README.md) with `AI_COLLECTOR_IMAGE`
set. It starts an isolated container with local file exporters and sends no
telemetry to SUSE Observability.


## Kubernetes gateway

Create the namespace, an `ai-collector-settings` ConfigMap with `cluster-name`
(the name used by the Kubernetes StackPack) and `otlp-endpoint`, and a
`suse-observability-api-key` Secret with key `API_KEY`. Keep credentials in your
existing secret provisioning process. Then run:

```sh
kubectl -n <application-namespace> apply -k examples/suse-ai
```

The Kustomize example deploys the Collector, namespace-scoped discovery RBAC,
and OTLP Service. It discovers running `app=vllm` pods on port 8000 and uses the
pod UID as `service.instance.id`. Configure application SDKs with the same pod
UID, `service.namespace`, and `k8s.pod.uid`, and send OTLP to `ai-collector:4317`.
Pod metadata is enriched from the API. The explicitly configured cluster name
is added only by this Kubernetes overlay; the general gateway does not invent
Kubernetes metadata for applications elsewhere.

TLS is verified by default. The optional `otlp-insecure` setting is for an
explicitly trusted plaintext OTLP endpoint, such as an internal test gateway.
The ConfigMap content hash triggers a Collector rollout when receiver settings
change. Do not run multiple replicas of this scraping configuration without a
Target Allocator or partitioned discovery: each replica would scrape every pod.

`dcgm-receiver.yaml` is an optional third config file for an existing NVIDIA
DCGM exporter DaemonSet. Set `DCGM_EXPORTER_NAMESPACE` and `K8S_CLUSTER_NAME`,
and grant the Collector ServiceAccount `get/list/watch` on pods in that exporter
namespace. Mount the file and append `--config=/config/dcgm-receiver.yaml` to the
Collector arguments. Pod discovery scrapes each exporter separately and keeps
node identity, avoiding load-balanced scrapes across GPU nodes. It normalizes
DCGM's pod labels for the existing GPU charts.

GPU pod tabs and summaries require both a native Kubernetes pod and recent DCGM
telemetry attributed to that workload. The mapping uses `k8s.cluster.name` and
`k8s.node.name` from the scrape resource, and nonempty `pod_namespace` and
`pod_name` datapoint labels from DCGM. It marks the existing pod identity; it
does not use the exporter pod's resource identity or assume that every pod on
a GPU node uses a GPU. CPU-only pods therefore keep their normal presentation.
The marker expires after five minutes without GPU utilization, framebuffer
usage, temperature or power samples. If the exporter cannot attribute metrics
to workloads, GPU node charts remain available but pod GPU tabs do not appear.
These charts show the device measurements attributed by DCGM; shared-device
temperature and power are not isolated per-process measurements.

For NVIDIA XID monitoring, enable the supported windowed error-count metric in
the DCGM exporter metrics CSV (in addition to the existing metrics):

```csv
DCGM_EXP_XID_ERRORS_COUNT, gauge, Number of XID errors in the configured time window.
```

Set `DCGM_EXPORTER_XID_COUNT_WINDOW_SIZE=300000` for a five-minute exporter
window. This was verified with exporter `4.6.1-4.8.4-distroless`. The exporter
reports zero after a successful collection with no errors; newer DCGM versions
can omit `DCGM_FI_DEV_XID_ERRORS` until an error occurs. The monitor prefers the
windowed count and retains the last-XID metric as a fallback for older exporters.
It also retains observations for five minutes, so an error can remain visible
for up to ten minutes with that exporter window. Missing telemetry remains
missing; the query does not synthesize healthy nodes from unrelated GPU metrics.
An enabled counter can still be unavailable from the driver; do not fabricate
zero values when it is absent.

## LiteLLM

`litellm-receiver.yaml` is an optional Kubernetes scrape pipeline. Load it alongside
`collector.yaml` (and the Kubernetes overlay when also receiving application OTLP).
Set `OBSERVED_NAMESPACE`, `K8S_CLUSTER_NAME`, and optionally `LITELLM_SERVICE_NAME`
(default `litellm`), `LITELLM_K8S_SERVICE_NAME` (default `litellm-router`) and
`LITELLM_METRICS_PORT` (default `4000`). The included Role grants read access to
services, endpoints and pods. Discovery scrapes individual pods at `/metrics/` and
uses their UIDs as instance identities. Match `OTEL_SERVICE_NAME`, namespace and
instance identity when enabling LiteLLM's `otel` callback too.

Enable `litellm_settings.callbacks: [prometheus]`. For a private demo the supplied
LiteLLM setting `require_auth_for_metrics_endpoint: false` allows scraping; otherwise
configure the Prometheus receiver's authorization for the protected endpoint. Use
one scrape owner. The product charts additionally collapse duplicate copies of
the same native LiteLLM series, keeping real replicas and native user/model labels
separate before aggregation. Custom Prometheus metadata labels need corresponding
query grouping if they partition counters; the Collector preserves those labels.

LiteLLM 1.98.0 native charts cover traffic, route latency, tokens, concurrency, backend
state and guardrails. Guardrail charts need an enabled guardrail and actual requests.
Guardrail `status=error` can include both policy rejections and execution failures;
LLM failure counters include guardrail rejections. Security and upstream-failure
monitors must use the deployment's actual policy and route selection.

## Explicitly resolved client dependencies

The optional `count/suse_ai_clients` path observes CLIENT spans that carry a
nonempty `server.address` and explicit `suse.ai.peer.service.name`,
`suse.ai.peer.service.namespace` and `suse.ai.peer.cluster` attributes. Resolution
belongs to the instrumentation/integration and must verify the actual endpoint
against known canonical service identities. A provider name alone is insufficient.
The caller's real `k8s.cluster.name` must match the resolved peer cluster.

The standard Count connector produces per-batch delta observations. The shared
observation pipeline normalizes them to `suse.ai.service.calls`, using the same
relation mapping as paired servicegraph calls. No separate trace relation mapping
is needed, and no server span or target component is fabricated. Zero observations
are dropped so unrelated traffic cannot keep an idle edge alive. The mapping's
15-minute expiry starts after the last observed call, with normal processing delay.

These gauges represent topology observations, not deduplicated request totals;
paired and client observations can describe one call. GenAI duration histogram
counts remain the source for provider request charts. Peer attributes should
appear on only one provider CLIENT span, not also its native HTTP child.

The Count connector is included in Contrib 0.156.0 and the product Collector
0.160.0 distribution; upstream marks it alpha. For integrations that do not emit
explicit peer identities this path creates no dependencies. Native service IDs
still omit cluster, so equal service names and logical namespaces across clusters
retain the companion's existing identity limitation.

## Databases observed from client spans

CLIENT spans for Milvus, Qdrant, OpenSearch and Elasticsearch can discover a
database dependency without server instrumentation. The normalized span must
contain `db.system.name` and a nonempty `server.address`; `server.port` is optional.
The example and product Collectors normalize legacy `db.system`, `net.peer.name`
(then `net.peer.ip`) and `net.peer.port`, preserving nonempty canonical values.
These are [standard database client attributes](https://opentelemetry.io/docs/specs/semconv/db/database-spans/).
No connection string, query text, credentials or custom SDK attributes are needed.
A product name alone is insufficient to identify a destination.

Unresolved endpoints appear in Overview and Data services as **observed database
dependencies**, with a calling-service link and endpoint-scoped traces. They are
not native services and receive no database-server charts or health monitors.
Their identity includes the caller's cluster (when reported), service namespace,
service name, database system, address and port. Caller replicas share one
observation; different callers, clusters, namespaces, endpoints and unknown versus
known ports remain separate. This describes a client's view of an endpoint, not
a globally unique physical database. The caller is not classified as a database,
and its Kubernetes metadata is not assigned to the destination. Like the other
readable identifiers, values are unescaped; embedded field separators retain the
documented collision limitation.

When an endpoint belongs to a known native service, configure its verified
association in the Collector or integration using the peer attributes above.
For example, add this processor **after** `transform/suse_ai_database` and before
exporting traces to the connectors. Replace the example cluster, endpoint and
service identity with values verified against your deployment and native topology:

```yaml
processors:
  transform/database_peers:
    error_mode: ignore
    trace_statements:
    - context: span
      conditions:
      - span.kind == SPAN_KIND_CLIENT and
        resource.attributes["k8s.cluster.name"] == "example-cluster" and
        span.attributes["db.system.name"] == "milvus" and
        span.attributes["server.address"] == "milvus.data.svc.cluster.local" and
        span.attributes["server.port"] == 19530 and
        (span.attributes["suse.ai.peer.service.name"] == nil or span.attributes["suse.ai.peer.service.name"] == "") and
        (span.attributes["suse.ai.peer.service.namespace"] == nil or span.attributes["suse.ai.peer.service.namespace"] == "") and
        (span.attributes["suse.ai.peer.cluster"] == nil or span.attributes["suse.ai.peer.cluster"] == "")
      statements:
      - set(span.attributes["suse.ai.peer.service.name"], "milvus")
      - set(span.attributes["suse.ai.peer.service.namespace"], "data")
      - set(span.attributes["suse.ai.peer.cluster"], "example-cluster")
```

This uses the existing service-call observation path and creates no inferred
destination. Do not infer a namespace from a short hostname, resolve across
clusters, or assume that `db.system.name` names a service. Native mappings cannot
look up endpoint ownership in the topology. Paired spans alone do not establish
this association for the client-only mapping. If resolution is enabled after an
unresolved observation, its old component and edge expire 15 minutes after their
last unresolved call; subsequent calls refresh only the native service edge.

The stock companion's optional-Kubernetes-metadata defect still affects the
calling service for non-Kubernetes workloads. The observed dependency and its
trace presentation do not require Kubernetes metadata, but they do not repair a
missing native caller or fabricate its hosting relations.

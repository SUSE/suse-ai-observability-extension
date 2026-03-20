# GenAI Provider/Model Discovery Pattern

This document describes how providers and models are automatically discovered from GenAI telemetry and turned into topology components with relations.

## Problem Statement

GenAI applications emit telemetry with provider and model information in different attribute layers:

- **Resource Attributes**: Service-level metadata (e.g., `suse.ai.component.name = "open-webui"`)
- **Span Attributes**: Request-level metadata (e.g., `gen_ai.provider.name = "ollama"`, `gen_ai.request.model = "llama3.2"`)
- **Metric Labels**: Time-series dimensions on `gen_ai_client_*` metrics

The challenge is to create topology components for providers and models that the application interacts with, even when those providers/models don't emit their own telemetry directly.

## Solution Architecture

### Data Flow

```
1. Application (Open WebUI, etc.)
   Emits OTel traces and metrics with:
   - Resource: suse.ai.component.name, suse.ai.component.type
   - Span/Metric: gen_ai.provider.name, gen_ai.request.model
              |
              | OTLP
              v
2. OTel Collector (suse-ai custom image)
   Splits data into parallel pipelines:
   a) metrics/infer-providers  -> inference-engine topology elements
   b) metrics/infer-models     -> llm-model topology elements
   c) traces/model-relations   -> provider -> model relations (peer.service)
   d) traces/provider-relations -> app -> provider relations (peer.service)
              |
              | OTLP
              v
3. SUSE Observability
   - OTel sync creates components via ID extractors
   - Component mapping assigns types, layers, categories
   - Relations resolved via externalId / identifiers
```

### Key Insight

Instead of processing telemetry in a Groovy monitor, the OTel Collector itself creates new topology elements by re-grouping and transforming the application's metrics and traces. Each pipeline reshapes existing data so that SUSE Observability's standard OTel sync interprets it as a distinct service.

## Implementation Components

### 1. OTel Collector Pipelines

**File**: `integrations/otel-collector/otel-values.yaml`

#### Provider Discovery (`metrics/infer-providers`)

Extracts inference engine components from application-emitted `gen_ai.*` metrics.

```yaml
# Filter to only gen_ai.* metrics
filter/genai-metrics-only:
  error_mode: ignore
  metrics:
    metric:
      - not(IsMatch(name, "gen_ai\\..*"))

# Re-group metrics so each provider becomes a separate resource
groupbyattrs/infer-providers:
  keys:
    - gen_ai.provider.name

# Set resource attributes so the metric appears as a new service
transform/infer-providers:
  error_mode: ignore
  metric_statements:
    - context: resource
      statements:
        - set(attributes["service.name"], attributes["gen_ai.provider.name"])
        - set(attributes["service.instance.id"], attributes["gen_ai.provider.name"])
        - set(attributes["suse.ai.managed"], "true")
        - set(attributes["suse.ai.component.name"], attributes["gen_ai.provider.name"])
        - set(attributes["suse.ai.component.type"], "inference-engine")
        - set(attributes["k8s.namespace.name"], "${env:SUSE_AI_NAMESPACE}")
```

**Pipeline**:
```yaml
metrics/infer-providers:
  receivers: [otlp]
  processors: [filter/genai-metrics-only, groupbyattrs/infer-providers,
               transform/infer-providers, resource, batch]
  exporters: [otlp]
```

#### Model Discovery (`metrics/infer-models`)

Extracts LLM model components from application-emitted `gen_ai.*` metrics.

```yaml
# Re-group metrics so each model becomes a separate resource
groupbyattrs/infer-models:
  keys:
    - gen_ai.request.model
    - gen_ai.provider.name  # kept for provider-specific type specialization

# Set resource attributes so the metric appears as a new service
transform/infer-models:
  error_mode: ignore
  metric_statements:
    - context: resource
      statements:
        - set(attributes["service.name"], attributes["gen_ai.request.model"])
        - set(attributes["service.instance.id"], attributes["gen_ai.request.model"])
        - set(attributes["suse.ai.managed"], "true")
        - set(attributes["suse.ai.component.name"], attributes["gen_ai.request.model"])
        - set(attributes["suse.ai.component.type"], "llm-model")
        - set(attributes["k8s.namespace.name"], "${env:SUSE_AI_NAMESPACE}")
```

**Pipeline**:
```yaml
metrics/infer-models:
  receivers: [otlp]
  processors: [filter/genai-metrics-only, groupbyattrs/infer-models,
               transform/infer-models, resource, batch]
  exporters: [otlp]
```

#### Provider-to-Model Relations (`traces/model-relations`)

Creates relations between providers and models using `peer.service`.

```yaml
# Drop spans without model info
filter/genai-spans:
  error_mode: ignore
  traces:
    span:
      - attributes["gen_ai.request.model"] == nil

# Re-group spans by provider (becomes the "source" service)
groupbyattrs/model-relations:
  keys:
    - gen_ai.provider.name

# Set service.name = provider, peer.service = model
transform/model-relations:
  error_mode: ignore
  trace_statements:
    - context: resource
      statements:
        - set(attributes["service.name"], attributes["gen_ai.provider.name"])
        - set(attributes["service.instance.id"], attributes["gen_ai.provider.name"])
    - context: span
      statements:
        - set(attributes["peer.service"], attributes["gen_ai.request.model"])
```

**Pipeline**:
```yaml
traces/model-relations:
  receivers: [routing/traces]
  processors: [filter/genai-spans, groupbyattrs/model-relations,
               transform/model-relations, batch]
  exporters: [otlp]
```

#### Application-to-Provider Relations (`traces/provider-relations`)

Creates relations between the originating application and the inference engine.

```yaml
# Set peer.service = provider so SUSE Observability sees app -> provider
transform/provider-relations:
  error_mode: ignore
  trace_statements:
    - context: span
      statements:
        - set(attributes["peer.service"], resource.attributes["gen_ai.provider.name"])
          where resource.attributes["gen_ai.provider.name"] != nil
```

**Pipeline**:
```yaml
traces/provider-relations:
  receivers: [routing/traces]
  processors: [filter/genai-spans, transform/provider-relations, batch]
  exporters: [otlp]
```

#### Trace Routing

All trace pipelines share a single receiver via a routing connector:

```yaml
connectors:
  routing/traces:
    error_mode: ignore
    table:
    - statement: route()
      pipelines: [traces/sampling, traces/spanmetrics,
                   traces/model-relations, traces/provider-relations]

service:
  pipelines:
    traces:
      receivers: [otlp, jaeger]
      processors: [filter/dropMissingK8sAttributes, memory_limiter, resource]
      exporters: [routing/traces]
```

### 2. Sync Functions (StackPack)

#### ID Extractor (`suse-ai-id-extractor.groovy`)

**File**: `stackpack/suse-ai/provisioning/templates/sync/suse-ai-id-extractor.groovy`

- Filters to only process components with `suse.ai.*` or `gen_ai.*` tags
- Skips components with `suse.ai.component.name` (those go to the Product sync)
- Prefixes externalId with `suse-ai:` to separate from the standard OTel StackPack
- Keeps the original OTel externalId as an identifier for cross-sync relation resolution

#### Product ID Extractor (`suse-ai-product-id-extractor.groovy`)

**File**: `stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy`

- Only processes components with `suse.ai.component.name`
- Creates a deterministic ID: `suse-ai:product:<type>:<name>` (e.g., `suse-ai:product:inference-engine:ollama`)
- Merges all instances of the same product into one logical component
- Adds `suse-ai:<otel-urn>` as identifier for cross-sync merging with the main SUSE AI sync component
- Does NOT add the unprefixed OTel URN — that would cause merging with the OTel StackPack's service component, breaking type and monitors

#### Component Mapping (`component-mapping-function.groovy`)

**File**: `stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy`

- Promotes `suse.ai.component.name` to the component display name
- Detects managed components via `suse.ai.managed` tag
- Maps `suse.ai.component.type` to specialized component types (e.g., `inference-engine.vllm`, `llm-model.ollama`)
- For `llm-model` types, further specializes based on `gen_ai.provider.name`
- Assigns layers: Applications (ui/app/agent), Services (default), Models (llm-model)
- Only adds `suse.ai.category` labels to product components (prefix `suse-ai:product:`) to prevent UI duplication

### 3. Monitor

**File**: `stackpack/suse-ai/provisioning/templates/monitors/genai-monitors.sty`

The GenAI monitor (`-3001`) checks whether metric streams are active for each component:

```yaml
- _type: Monitor
  id: -3001
  name: GenAI Application Metric Stream Active
  intervalSeconds: 60
  function: threshold
  arguments:
    query: sum(rate(gen_ai_client_operation_duration_seconds_count{}[5m])) by (suse_ai_component_name, suse_ai_component_type)
    threshold: 0.0001
    comparator: LTE
    failureState: DEVIATING
    urnTemplate: "suse-ai:product:${suse_ai_component_type}:${suse_ai_component_name}"
```

This monitors the health of discovered components by checking if GenAI operation duration metrics are flowing (request counts are derived from the histogram's `_count` series).

## Resulting Topology

When an application like Open WebUI sends requests to Ollama serving `llama3.2`:

```
[Open WebUI]  --(peer.service)--> [Ollama]  --(peer.service)--> [llama3.2]
  (ui)                         (inference-engine)              (llm-model.ollama)
  Applications layer           Services layer                  Models layer
```

All three components are created automatically from the application's telemetry, without requiring instrumentation on Ollama or the model itself.

## Key Design Decisions

### Why OTel Collector pipelines instead of Groovy monitors?

- The Collector already has the telemetry data with all needed attributes
- `groupbyattrs` + `transform` processors can reshape data to create new topology elements natively
- No need for HTTP queries, JSON parsing, or async workarounds in Groovy
- Relations are created via the standard `peer.service` mechanism that SUSE Observability already understands

### Why `groupbyattrs` for resource regrouping?

- `gen_ai.provider.name` and `gen_ai.request.model` start as metric labels / span attributes
- `groupbyattrs` promotes them to resource-level attributes and creates separate resource scopes
- Each resource scope becomes a separate service in SUSE Observability's topology

### Why separate provider and model pipelines?

- Providers become `inference-engine` components (Services layer)
- Models become `llm-model` components (Models layer)
- Different types, layers, and metric bindings apply to each
- The `gen_ai.provider.name` is kept in the model pipeline for provider-specific type specialization (`llm-model.vllm`, `llm-model.ollama`)

### Why two syncs (SUSE AI + SUSE AI Products)?

- The main **SUSE AI** sync creates per-instance components (one per pod/service-instance)
- The **SUSE AI Products** sync aggregates instances into logical product components (one "Milvus" regardless of how many pods)
- Category labels (`suse.ai.category`) are only on product components to avoid duplicate entries in views

### Why `peer.service` for relations?

- SUSE Observability's OTel integration automatically creates relations when spans have `peer.service` attributes
- Setting `peer.service` on transformed spans leverages existing relation creation without custom code
- `traces/provider-relations`: app's span gets `peer.service = provider` -> app depends on provider
- `traces/model-relations`: provider's regrouped span gets `peer.service = model` -> provider depends on model

## Topology Exporter (Product-to-Product Relations)

The `peer.service` approach above creates relations between OTel service components, but product components (which aggregate instances) don't get topology arrows. A custom OTel exporter (`topologyexporter` in `otelcol-suse-ai`) solves this by:

1. Consuming traces in a `traces/topology` pipeline
2. Discovering components and relations from `suse.ai.component.name`, `gen_ai.provider.name`, `gen_ai.request.model`, and `db.system` span attributes
3. Accumulating topology in memory over a flush window (default 60s)
4. Pushing full snapshots to SUSE Observability's `/receiver/stsAgent/intake` API
5. A dedicated "SUSE AI Topology" sync consumes the data with `MergePreferTheirs`

This creates explicit relations between product components (e.g., `open-webui → ollama → llama3.2`) using the same `suse-ai:product:{type}:{name}` externalId scheme, without breaking types or monitors.

**Design spec:** `otelcol-suse-ai/docs/specs/2026-03-19-topology-exporter-design.md`

## Limitations

### Requires GenAI-instrumented applications

Only works when applications emit `gen_ai.provider.name` and `gen_ai.request.model` in their telemetry. Applications using the OpenTelemetry GenAI semantic conventions (or the `suse-ai` SDK) will work automatically.

### Inferred components have limited metrics

Discovered providers and models only get the `gen_ai_client_*` metrics forwarded from the application. They don't get native engine metrics (e.g., vLLM queue depth) unless the engine also sends its own telemetry, which is handled by separate pipelines (`metrics` pipeline with `transform/vllm`).

### Model names are as reported by the application

The model name comes from `gen_ai.request.model` which is the name the application uses (e.g., `llama3.2`). If different applications use different aliases for the same model, they'll appear as separate components.

## Related Files

- `integrations/otel-collector/otel-values.yaml` - OTel Collector configuration with all discovery pipelines
- `stackpack/suse-ai/provisioning/templates/sync/suse-ai-id-extractor.groovy` - ID extractor for instance components
- `stackpack/suse-ai/provisioning/templates/sync/suse-ai-product-id-extractor.groovy` - ID extractor for product aggregation
- `stackpack/suse-ai/provisioning/templates/sync/component-mapping-function.groovy` - Component type/layer mapping
- `stackpack/suse-ai/provisioning/templates/sync/component-template.json.handlebars` - Component template
- `stackpack/suse-ai/provisioning/templates/sync/relation-template.json.handlebars` - Relation template
- `stackpack/suse-ai/provisioning/templates/monitors/genai-monitors.sty` - GenAI health monitors
- `stackpack/suse-ai/provisioning/templates/synchronization.sty` - Sync definitions

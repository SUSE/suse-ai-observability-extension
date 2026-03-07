# GenAI Provider/Model Discovery Pattern

This document describes the architectural pattern for discovering provider and model relationships from GenAI telemetry data.

## Problem Statement

GenAI applications emit telemetry with provider and model information, but this data exists in different layers:

- **Resource Attributes**: Service-level metadata (e.g., `suse.ai.component.name = "open-webui"`)
- **Span Attributes**: Request-level metadata (e.g., `gen_ai.provider.name = "ollama"`, `gen_ai.request.model = "llama3.2"`)
- **Metric Labels**: Time-series dimensions (e.g., Prometheus labels)

The challenge is to create topology components and relations that represent these provider/model connections, when the data flows through different systems (spans → metrics → topology).

## Solution Architecture

### Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│ 1. Application (Open WebUI / vLLM)                          │
│    Emits OTel traces with:                                  │
│    - Resource: suse.ai.component.name                       │
│    - Span: gen_ai.provider.name, gen_ai.request.model      │
└──────────────────────────────────────────────────────────────┘
                            ↓ OTLP
┌──────────────────────────────────────────────────────────────┐
│ 2. OTel Collector                                            │
│    a) Transform: Copy resource attrs → span attrs           │
│    b) SpanMetrics: Create metrics with dimensions           │
│    Output: genai_discovery_calls_total{                     │
│      suse_ai_component_name="open-webui",                   │
│      gen_ai_provider_name="ollama",                         │
│      gen_ai_request_model="llama3.2"                        │
│    }                                                         │
└──────────────────────────────────────────────────────────────┘
                            ↓ OTLP
┌──────────────────────────────────────────────────────────────┐
│ 3. VictoriaMetrics (SUSE Observability)                     │
│    Stores metrics with all labels                           │
└──────────────────────────────────────────────────────────────┘
                            ↓ HTTP Query (every 60s)
┌──────────────────────────────────────────────────────────────┐
│ 4. Groovy Monitor (CheckFunction)                           │
│    - Queries VictoriaMetrics API                            │
│    - Parses metric labels                                    │
│    - Stores in memory map:                                   │
│      memory['suse-ai:discovered-models'] = {                │
│        "open-webui": {                                       │
│          "ollama": ["llama3.2", "phi-3"],                   │
│          "vllm": ["qwen"]                                    │
│        }                                                     │
│      }                                                       │
└──────────────────────────────────────────────────────────────┘
                            ↓ Read by sync functions
┌──────────────────────────────────────────────────────────────┐
│ 5. Component/Relation Creation (Future)                     │
│    - Create provider components                             │
│    - Create model components                                │
│    - Create relations: UI → Provider → Model                │
└──────────────────────────────────────────────────────────────┘
```

## Implementation Components

### 1. OTel Collector Configuration

**File**: `integrations/otel-collector/complete-genai-config.yaml`

**Key Processors:**

```yaml
# Copy resource attributes to span attributes
transform/copy_resource_to_span:
  error_mode: ignore
  trace_statements:
    - context: span
      statements:
        - set(attributes["suse.ai.component.name"],
               resource.attributes["suse.ai.component.name"])
          where resource.attributes["suse.ai.component.name"] != nil
```

**Key Connectors:**

```yaml
# Create metrics from spans with custom dimensions
spanmetrics/genai:
  metrics_expiration: 5m
  namespace: genai_discovery
  dimensions:
    - name: gen_ai.provider.name
    - name: gen_ai.request.model
    - name: suse.ai.component.name
  histogram:
    disable: true  # Only need call counts
```

### 2. Groovy Monitor Function

**File**: `stackpack/suse-ai/provisioning/templates/functions/model-discovery-function.groovy`

**Key Logic:**

```groovy
// Query VictoriaMetrics
def vmUrl = "http://suse-observability-victoriametrics.suse-observability.svc.cluster.local:8428"
def query = "genai_discovery_calls_total"
def response = Http.get("${vmUrl}/api/v1/query?query=${encodedQuery}")

// Parse JSON and extract labels
def jsonResponse = new JsonSlurper().parseText(response.body)
jsonResponse.data.result.each { metricEntry ->
    def componentName = metricEntry.metric.suse_ai_component_name
    def provider = metricEntry.metric.gen_ai_provider_name
    def model = metricEntry.metric.gen_ai_request_model

    // Store in memory map
    if (!results[componentName]) results[componentName] = [:]
    if (!results[componentName][provider]) results[componentName][provider] = [] as Set
    results[componentName][provider].add(model)
}

memory['suse-ai:discovered-models'] = results
```

### 3. Monitor Definition

**File**: `stackpack/suse-ai/provisioning/templates/monitors/model-discovery-monitor.sty`

```yaml
- _type: CheckFunction
  id: -3100
  name: "SUSE AI Model Discovery Function"
  returnTypes: ["HEALTH_STATE_VALUE"]
  script: {{ include "templates/functions/model-discovery-function.groovy" }}

- _type: Monitor
  id: -3101
  name: "SUSE AI Model Discovery"
  intervalSeconds: 60  # Query every minute
  status: ENABLED
  function: -3100
```

## Key Design Decisions

### Why SpanMetrics Instead of Direct Span Processing?

**Decision**: Use `spanmetrics` connector to create metrics from spans, then query those metrics.

**Rationale**:
- Metrics are easier to query (HTTP/PromQL) than streaming spans
- Metrics aggregate data over time (useful for discovery)
- VictoriaMetrics provides stable, queryable interface
- Avoids dealing with async/streaming APIs in Groovy

### Why Memory Map Instead of Creating Components Directly?

**Decision**: Store discovered data in `memory` map, defer component creation to Phase 2.

**Rationale**:
- ID extractors can only return ONE component per Kafka message (architectural constraint)
- Creating multiple components (providers + models) requires different approach
- Memory map allows Phase 1 (discovery) to work independently
- Enables testing and validation before complex topology manipulation

### Why Transform Processor for Resource → Span?

**Decision**: Copy resource attributes to span attributes before spanmetrics.

**Rationale**:
- `spanmetrics` dimensions only read span attributes, not resource attributes
- Resource attributes are service-level (e.g., component name)
- Span attributes are request-level (e.g., provider, model)
- Need both in the same dimension space for discovery

### Why HTTP Query Instead of Telemetry API?

**Decision**: Use `Http.get()` to query VictoriaMetrics directly.

**Rationale**:
- `Telemetry.promql()` returns async streaming results (ZStream)
- Monitors run in synchronous context, need immediate results
- VictoriaMetrics HTTP API is simple JSON/REST
- Easier to debug and test

## Limitations and Trade-offs

### Limitation 1: ID Extractor Can't Create Multiple Components

**Impact**: Can't create provider and model components from a single Kafka message.

**Workaround**: Use memory map as intermediate storage, create components in Phase 2 via different mechanism.

### Limitation 2: Memory Map Not Persistent

**Impact**: Discovered data lost on StackState restart.

**Workaround**: Monitor runs every 60s, data repopulates quickly. Future: persist to component properties.

### Limitation 3: 60-Second Polling Delay

**Impact**: New providers/models take up to 60 seconds to appear.

**Workaround**: Acceptable for discovery use case. Decrease interval if needed (impacts load).

### Limitation 4: Requires Proper Instrumentation

**Impact**: Only works if applications emit spans with `gen_ai.*` attributes.

**Workaround**: Ensure all GenAI services use proper OTel instrumentation (e.g., suse-ai-filter.py for Open WebUI).

## Testing and Verification

### Step 1: Verify OTel Collector

```bash
# Check if new metrics exist
curl "http://localhost:8428/api/v1/query?query=genai_discovery_calls_total" | jq .
```

Expected: Metrics with labels `suse_ai_component_name`, `gen_ai_provider_name`, `gen_ai_request_model`

### Step 2: Verify Monitor Function

```bash
# Check if memory map is populated
sts script run --script "memory['suse-ai:discovered-models']"
```

Expected: JSON object with discovered providers and models

### Step 3: Verify Discovery Works

```bash
# Generate traffic
# - Use Open WebUI to chat with different models
# - Wait 60-120 seconds

# Check memory again
sts script run --script "memory['suse-ai:discovered-models']"
```

Expected: All used providers and models appear in the map

## Extensibility

### Adding New Data Sources

To add support for new GenAI services (e.g., LangChain, custom apps):

1. **Ensure proper instrumentation**: Service must emit traces with `gen_ai.provider.name` and `gen_ai.request.model` span attributes
2. **Add resource attributes**: Include `suse.ai.component.name` in resource attributes
3. **No collector changes needed**: Existing spanmetrics configuration will automatically pick up new data
4. **No monitor changes needed**: Queries all `genai_discovery_calls_total` regardless of source

### Adding Custom Dimensions

To track additional metadata (e.g., cost, region):

1. **Add to span attributes**: In application instrumentation
2. **Add to spanmetrics dimensions**: In collector config
3. **Update monitor function**: Parse additional labels
4. **Update memory map structure**: Store additional metadata

### Performance Tuning

**Increase polling frequency:**
```yaml
# In monitor definition
intervalSeconds: 30  # Poll every 30 seconds
```

**Reduce metric cardinality:**
```yaml
# In spanmetrics config
aggregation_temporality: cumulative
metrics_expiration: 5m  # Reduce retention
```

**Filter specific components:**
```groovy
// In monitor function
def query = 'genai_discovery_calls_total{suse_ai_component_name="open-webui"}'
```

## Future Enhancements

1. **Component Creation**: Implement Phase 2 to create provider/model topology components
2. **Relation Templates**: Create UI → Provider → Model relations
3. **Persistent Storage**: Store discovered data in component properties for persistence
4. **Change Detection**: Emit events when new providers/models discovered
5. **Usage Metrics**: Track request counts, latency per provider/model
6. **Cost Analysis**: Calculate costs per provider/model combination
7. **SLI/SLO Tracking**: Monitor health per provider/model

## Related Files

- `integrations/otel-collector/complete-genai-config.yaml` - Full OTel configuration
- `integrations/otel-collector/DEPLOYMENT_GUIDE.md` - Deployment instructions
- `stackpack/suse-ai/provisioning/templates/functions/model-discovery-function.groovy` - Discovery logic
- `stackpack/suse-ai/provisioning/templates/monitors/model-discovery-monitor.sty` - Monitor definition
- `knowledge/CERTAINS.md` - Verified facts and constraints

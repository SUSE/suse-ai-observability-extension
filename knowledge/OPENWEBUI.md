# Open WebUI Integration

**Current Status**: Fully integrated with metrics, traces, and related resources

## Overview

Open WebUI is monitored via a custom filter (`suse_ai_filter.py`) that generates OpenTelemetry-compliant metrics and traces, and a stackpack component type (`ui.open-webui`) that visualizes this telemetry in StackState.

## Architecture

### Filter (suse_ai_filter.py)

**Location**: `integrations/oi-filter/suse_ai_filter.py`

The filter runs as a pipeline in Open WebUI and captures all chat interactions.

**Resource Attributes** (set once during initialization):
- `service.name`: Configurable via `OTEL_SERVICE_NAME` env var (default: "Open WebUI")
- `suse.ai.component.name`: "open-webui" (hardcoded)
- `suse.ai.component.type`: "ui"
- `suse.ai.managed`: "true"
- `telemetry.sdk.name`: "suse-ai"

**Metrics Generated** (OpenTelemetry semantic conventions):
- `gen_ai.client.request.count` → Exported as `gen_ai_client_request_count_total`
- `gen_ai.client.token.usage` → Exported as `gen_ai_client_token_usage_sum` (histogram)
- `gen_ai.client.operation.duration` → Exported as `gen_ai_client_operation_duration_seconds_bucket` (histogram)
- `gen_ai.client.operation.cost` → Exported as `gen_ai_client_operation_cost_USD_sum` (histogram)

**Metric Attributes** (added to each metric observation):
- `gen_ai.operation.name`: "chat"
- `gen_ai.provider.name`: Provider name (ollama, openai, vllm, etc.)
- `gen_ai.request.model`: Model requested
- `gen_ai.response.model`: Model that responded
- `gen_ai.token.type`: "input" or "output" (for token usage metric only)
- `suse.ai.component.name`: "open-webui" (critical for querying!)

**IMPORTANT**: The `suse.ai.component.name` is added as a METRIC attribute, not just a resource attribute, so it appears as a Prometheus label `suse_ai_component_name="open-webui"`.

**Traces Generated**:
- Parent span per chat conversation
- Child spans for user messages and AI responses
- Traces filtered by resource attribute `suse.ai.component.name = "open-webui"`

### Component Type (ui.open-webui)

**Location**: `stackpack/suse-ai/provisioning/templates/component-types/products.sty`

**Component Identification**:
- Type: `ui.open-webui`
- URN pattern: `suse-ai:product:ui:${component-name}` (e.g., `suse-ai:product:ui:open-webui`)
- Created by: Product ID extractor when topology element has tag `suse.ai.component.name`

**ViewType Configuration**:
- Identifier: `urn:stackpack:suse-ai:shared:view-type:ui.open-webui`
- Tabs enabled: EVENTS, TRACES
- NoTopologyFilters flag set

**TraceBinding**:
- Filters traces by: `resource.suse.ai.component.name = ${tags.suse.ai.component.name}`
- Scope: `(label = "stackpack:suse-ai" and type = "ui.open-webui")`

**SpanToComponentBinding**:
- URN template: `suse-ai:product:ui:${resource.suse.ai.component.name}`
- Links spans back to the component

**Related Resources Queries**:
1. Service instances:
   ```stql
   type = "otel service instance" and label = "suse.ai.component.name:${tags.suse.ai.component.name}"
   ```
2. Services (parent):
   ```stql
   withNeighborsOf(direction = "up", components = (type = "otel service instance" and label = "suse.ai.component.name:${tags.suse.ai.component.name}"), levels = "1") and type = "otel service"
   ```

## Metric Bindings

**File**: `stackpack/suse-ai/provisioning/templates/metric-bindings/genai-metrics.sty`

All metrics filter by `suse_ai_component_name="${name}"` where `${name}` is the component name.

### 1. LLM Request Rate (ID: -2000)
- **Query**: `sum by (gen_ai_request_model) (rate(gen_ai_client_request_count_total{suse_ai_component_name="${name}"}[${__rate_interval}]))`
- **Unit**: reqps
- **Shows**: Request rate per model
- **Alias**: `${gen_ai_request_model}` (shows model names as separate lines)

### 2. Average Tokens per Request (ID: -2001)
- **Query**: `sum by (gen_ai_request_model) (rate(gen_ai_client_token_usage_sum{...}[5m])) / sum by (gen_ai_request_model) (rate(gen_ai_client_request_count_total{...}[5m]))`
- **Unit**: short
- **Shows**: Average tokens consumed per model
- **Alias**: `${gen_ai_request_model}`

### 3. Total Usage Cost (ID: -2002)
- **Query**: `sum(gen_ai_client_operation_cost_USD_sum{suse_ai_component_name="${name}"})`
- **Unit**: currencyUSD
- **Chart Type**: Gauge
- **Shows**: Cumulative total cost across all models
- **Alias**: Total Cost
- **Note**: Requires models to be in pricing.json

### 4. Operation Duration P95 (ID: -2003)
- **Query**: `histogram_quantile(0.95, sum by (gen_ai_request_model, le) (rate(gen_ai_client_operation_duration_seconds_bucket{...}[5m])))`
- **Unit**: s (seconds)
- **Shows**: 95th percentile latency per model
- **Alias**: `${gen_ai_request_model}`
- **Note**: Only works with providers that return `total_duration` (e.g., Ollama)

### 5. Token Usage by Type (ID: -2004)
- **Queries**:
  - Input: `sum by (gen_ai_request_model) (rate(gen_ai_client_token_usage_sum{..., gen_ai_token_type="input"}[5m]))`
  - Output: `sum by (gen_ai_request_model) (rate(gen_ai_client_token_usage_sum{..., gen_ai_token_type="output"}[5m]))`
- **Unit**: short
- **Shows**: Input and output token rates per model
- **Alias**: `${gen_ai_request_model} (Input)` / `${gen_ai_request_model} (Output)`

## Important Implementation Details

### Prometheus Metric Name Suffixes

OpenTelemetry appends the metric unit to the name when exporting to Prometheus:
- `unit="USD"` → `_USD_` suffix (e.g., `gen_ai_client_operation_cost_USD_sum`)
- `unit="s"` → `_seconds_` suffix (e.g., `gen_ai_client_operation_duration_seconds_bucket`)
- `unit="{token}"` → No suffix (dimensionless)

This is why queries must use the full suffixed names.

### Duration Metric Data Source

The duration metric extracts `total_duration` from the assistant message object (not from the `usage` sub-object):
```python
duration_ns = assistant_message_obj.get("total_duration", 0)
```

**Provider compatibility**:
- Ollama: ✅ Provides `total_duration` in nanoseconds
- OpenAI: ❌ Does not provide duration
- vLLM: Varies by configuration

### Cost Metric Requirements

Cost calculation requires:
1. Model name exists in `pricing.json`
2. Pricing data loaded successfully from URL (default: GitHub main branch)
3. Token counts available
4. Cost > 0

**Local Ollama models**: May not be in the default pricing.json. Add custom pricing or point to a custom pricing file via `PRICING_JSON` env var.

### Component Name in Queries

The component name "open-webui" is used in two ways:
1. **Component display name**: The human-readable name shown in StackState
2. **Metric label value**: The value of `suse_ai_component_name` in Prometheus queries

Both should match for queries to work correctly. The component name comes from the URN created by the product ID extractor.

## Deployment

### Filter Deployment
1. Update `integrations/oi-filter/suse_ai_filter.py`
2. Restart Open WebUI or reload the filter in Admin → Functions
3. Generate chat interactions to create new metrics/traces

### Stackpack Deployment
1. Update metric bindings or component type definitions
2. Run `task version-up && task stackpack-upload`
3. Refresh StackState UI to see changes

## Troubleshooting

### Metrics Not Appearing
- Check if filter is running (look for debug logs if enabled)
- Verify metric names include correct suffixes (_USD_, _seconds_)
- Confirm `suse_ai_component_name` label exists on metrics
- Check that component name matches between topology and queries

### Traces Not Showing
- Verify TRACES tab appears in component view (ViewType configured)
- Check TraceBinding filter uses `resource.suse.ai.component.name`
- Confirm traces exist with correct resource attribute
- Check scope query matches the component

### Related Resources Empty
- Verify OpenTelemetry stackpack is installed and running
- Check if otel service instances exist with label `suse.ai.component.name:open-webui`
- Confirm component tags include `suse.ai.component.name`

### Cost Metric Always Zero
- Enable debug logging in filter (`debug_log_enabled: true`)
- Check logs for "Undefined price for model X"
- Verify model name matches entries in pricing.json
- Consider adding custom pricing for local models

### Duration Metric Empty
- Check if LLM provider returns `total_duration` field
- Verify field is at message level, not in `usage` object
- For non-Ollama providers, this metric may not work

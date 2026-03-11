# Metric Bindings Guide

## ID Ranges

Metric binding IDs are negative integers organized by category:
- **-501 to -509**: vLLM system-scope metrics (consolidated multi-query bindings)
- **-510 to -519**: Available (gap)
- **-520 to -527**: vLLM per-model (genai-model) metrics
- **-540 to -568**: Individual product metrics (vLLM, Ollama, etc.)
- **-569 to -583**: Application-scoped GenAI metrics
- **-584 to -605**: Common GPU/infrastructure metrics
- **-700 to -705**: GenAI global metrics (genai-metrics.sty)
- **-2000 to -2004**: Milvus/OpenSearch/Elasticsearch metrics

Always check for ID conflicts across ALL `.sty` files before assigning a new ID.

## Multi-Query Metric Bindings

Combine multiple percentiles/series into a single chart:
```yaml
- id: -501
  name: E2E Latency
  queries:
    - expression: histogram_quantile(0.99, sum by (le) (rate(metric_bucket[5m])))
      alias: "P99"
      primary: true
    - expression: histogram_quantile(0.95, sum by (le) (rate(metric_bucket[5m])))
      alias: "P95"
    - expression: histogram_quantile(0.90, ...)
      alias: "P90"
    - expression: histogram_quantile(0.50, ...)
      alias: "P50"
    - expression: sum(rate(metric_sum[5m])) / sum(rate(metric_count[5m]))
      alias: "Avg"
```

## Scope Patterns

- **Application components**: `type in ("service", "application") AND label IN ("suse.ai.category:application")`
- **vLLM system scope**: `type = "inference-engine.vllm"`
- **Per-model scope**: `type = "genai.model"` (filter by `model_name="${name}"` in PromQL)

## PromQL Variable Substitution

- `${name}` → component name
- `${tags.service.name}` → service name tag
- `${__rate_interval}` → auto-calculated rate interval

## vLLM Metric Name Pattern

vLLM metrics may have `:` or `_` separators depending on version:
```
{__name__=~"vllm:e2e_request_latency_seconds_bucket|vllm_e2e_request_latency_seconds_bucket"}
```

## Component Type Wiring

Metric bindings are referenced in component type `.sty` files under `metrics`:
```yaml
metrics:
  - _type: "ComponentTypeMetricCategory"
    name: "Performance"
    bindings:
      - "urn:stackpack:suse-ai:shared:metric-binding:vllm:e2e-latency"
    defaultExpanded: true
```

## suse.ai.category vs suse.ai.component.type

These are redundant. `suse.ai.category` is the **normalized** version of `suse.ai.component.type`, derived by the `component-mapping-function.groovy`:
- `ui`, `frontend` → `ui`
- `app`, `application`, `service` → `application`
- `db`, `vectordb`, `vector-db` → `vectordb`
- `llm`, `model` → `genai.model`

All query views, metric binding scopes, and filters use `suse.ai.category`.

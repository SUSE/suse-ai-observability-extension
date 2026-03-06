# Open WebUI OTel Alignment - Changes Summary

**Date**: 2026-03-06
**Version**: 1.2.0
**Status**: Aligned with OpenTelemetry GenAI Semantic Conventions

## Overview

The Open WebUI filter has been updated to align with the official [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/). This ensures better interoperability with standard OTel tooling and compliance with industry best practices.

## Critical Issues Fixed

### 1. Incorrect Attribute Name for Provider
**Issue**: Using non-standard `gen_ai.system`
**Fix**: Changed to official `gen_ai.provider.name`
**Impact**: All spans and metrics now use the correct attribute name

**Files Changed**:
- `SemanticConvention.GEN_AI_SYSTEM` → `SemanticConvention.GEN_AI_PROVIDER_NAME`
- Added backward compatibility constant with deprecation note

### 2. Missing Token Type Attribute
**Issue**: `gen_ai.client.token.usage` histogram was missing required `gen_ai.token.type` attribute
**Fix**: Now recording separate observations for input and output tokens with proper token.type attribute
**Impact**: Metrics are now queryable by token type (input/output) as per OTel spec

**Before**:
```python
self.metrics["genai_client_usage_tokens"].record(total_tokens, metrics_attributes)
```

**After**:
```python
# Input tokens
self.metrics["genai_client_token_usage"].record(input_tokens, {..., "gen_ai.token.type": "input"})
# Output tokens
self.metrics["genai_client_token_usage"].record(output_tokens, {..., "gen_ai.token.type": "output"})
```

### 3. Duration Unit Conversion
**Issue**: Ollama returns `total_duration` in nanoseconds, but OTel expects seconds
**Fix**: Added conversion: `duration_seconds = duration_ns / 1_000_000_000.0`
**Impact**: Duration metrics now report correct values in seconds

### 4. Inconsistent SDK Naming
**Issue**: Tracer used "openlit" while resources used "suse-ai"
**Fix**: Unified to use `self.local_sdk_name` ("suse-ai") throughout
**Impact**: Consistent telemetry attribution

### 5. Removed Redundant Token Counters
**Issue**: Had separate counters for prompt/completion/total tokens (non-standard)
**Fix**: Removed in favor of standard histogram with token.type
**Impact**: Cleaner metric namespace, aligns with OTel spec

**Removed Metrics**:
- `gen_ai.usage.input_tokens` (counter)
- `gen_ai.usage.output_tokens` (counter)
- `gen_ai_usage_tokens_total` (counter)

**Retained**:
- `gen_ai.client.token.usage` (histogram with token.type attribute)

### 6. Cleaned Non-Standard Attributes
**Issue**: Custom attributes not in OTel namespace
**Fix**: Removed or moved to custom namespace

**Removed from Spans**:
- `gen_ai.environment` (not in spec)
- `gen_ai.application_name` (use service.name resource attribute instead)
- `gen_ai.endpoint` (not in spec)
- `telemetry.sdk.name` span attribute (should be resource attribute only)

**Retained in Spans** (Standard):
- `gen_ai.operation.name`
- `gen_ai.provider.name`
- `gen_ai.request.model`
- `gen_ai.response.model`
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- `gen_ai.conversation.id`
- `gen_ai.request.is_stream`

### 7. Custom Metrics Namespacing
**Issue**: Custom metrics used inconsistent naming
**Fix**: Aligned custom metrics to proper namespace

**Changes**:
- `gen_ai.total.requests` → `gen_ai.client.request.count`
- `gen_ai.usage.cost` → `gen_ai.client.operation.cost`

## Standard vs Custom Metrics

### Standard OTel Metrics (Compliant)
1. **`gen_ai.client.token.usage`** (Histogram)
   - Unit: `{token}`
   - Required attribute: `gen_ai.token.type` (input/output)
   - Tracks token consumption per operation

2. **`gen_ai.client.operation.duration`** (Histogram)
   - Unit: `s` (seconds)
   - Tracks end-to-end operation latency

### Custom SUSE AI Metrics (Extensions)
1. **`gen_ai.client.request.count`** (Counter)
   - Unit: `{request}`
   - Tracks total number of requests

2. **`gen_ai.client.operation.cost`** (Histogram)
   - Unit: `USD`
   - Tracks estimated cost per operation

## Span Attributes Alignment

### Inlet Span (User Message)
**Standard Attributes**:
- `gen_ai.operation.name`: "chat"
- `gen_ai.provider.name`: Provider name (openai, ollama, vllm, etc.)
- `gen_ai.conversation.id`: Chat session ID
- `gen_ai.request.model`: Model name
- `gen_ai.request.is_stream`: Boolean

**Events**:
- `gen_ai.user.message` with content (opt-in)

### Outlet Span (AI Response)
**Standard Attributes**:
- `gen_ai.operation.name`: "chat"
- `gen_ai.provider.name`: Provider name
- `gen_ai.request.model`: Requested model
- `gen_ai.response.model`: Actual responding model
- `gen_ai.usage.input_tokens`: Token count
- `gen_ai.usage.output_tokens`: Token count

**Custom Attributes**:
- `gen_ai.usage.cost`: Estimated cost in USD (only if pricing available)

**Events**:
- `gen_ai.assistant.message` with content (opt-in)

## Resource Attributes (Unchanged)

These remain compliant and well-structured:
```python
{
    "service.name": "Open WebUI",
    "service.version": "1.0",
    "deployment.environment": "default",
    "telemetry.sdk.name": "suse-ai",
    "suse.ai.managed": "true",
    "suse.ai.component.name": "Open WebUI",
    "suse.ai.component.type": "ui"
}
```

## Migration Impact

### For StackState Queries
✅ **No Breaking Changes** - The component type `ui.open-webui` remains unchanged
✅ **Better Metric Queries** - Can now filter by token type
⚠️ **Metric Name Changes** - Update any dashboards referencing old counter metrics

### For Downstream Consumers
✅ **Better Interoperability** - Standard attribute names work with OTel tooling
✅ **Correct Units** - Duration in seconds matches spec expectations
✅ **Token Breakdown** - Input/output tokens now queryable separately

## Testing Recommendations

1. **Verify metric cardinality**: Check that token.type dimension doesn't explode cardinality
2. **Test duration values**: Confirm operation durations are in reasonable second ranges (not nanoseconds)
3. **Validate provider names**: Ensure provider detection logic maps to standard names
4. **Cost tracking**: Verify cost calculations still work with pricing.json

## References

- [OTel GenAI Spans Spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/)
- [OTel GenAI Metrics Spec](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-metrics/)
- [OTel Resource Attributes](https://opentelemetry.io/docs/specs/semconv/resource/)

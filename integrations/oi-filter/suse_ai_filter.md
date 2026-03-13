# SUSE AI Monitoring Pipeline - Open WebUI Filter

An Open WebUI filter pipeline that generates OpenTelemetry-compliant traces and metrics for GenAI chat interactions, aligned with the [OTel GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/).

## How It Works

The filter hooks into Open WebUI's request lifecycle via `inlet` (before the request) and `outlet` (after the response). It creates OTel spans and records metrics for each chat completion, then exports them over OTLP/HTTP to a collector.

### Inlet (pre-request)

- Starts a trace span named `chat <model>` (e.g., `chat llama3.2`)
- Sets span attributes: `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.request.is_stream`, `gen_ai.conversation.id`
- Optionally captures `gen_ai.input.messages` (controlled by `capture_message_content` valve)
- Resolves the provider from Open WebUI model metadata (`owned_by` field)

### Outlet (post-response)

- Completes the span with: `gen_ai.response.model`, `gen_ai.response.id`, `gen_ai.response.finish_reasons`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`
- Optionally captures `gen_ai.output.messages`
- Records metrics (see below)
- Calculates cost from `pricing.json` when available

## OTel Semantic Conventions Implemented

### Traces

Span name follows the convention: `{gen_ai.operation.name} {gen_ai.request.model}` (e.g., `chat gpt-4`).

| Attribute | Source | Required |
|---|---|---|
| `gen_ai.operation.name` | Always `"chat"` | Yes |
| `gen_ai.provider.name` | Model metadata `owned_by` | Yes |
| `gen_ai.request.model` | Request body `model` | Yes |
| `gen_ai.response.model` | Response body `model` | Yes |
| `gen_ai.request.is_stream` | Request body `stream` | No (extra) |
| `gen_ai.conversation.id` | Open WebUI `chat_id` | No |
| `gen_ai.response.id` | Response `id` | No |
| `gen_ai.response.finish_reasons` | Response `finish_reason` (as list) | No |
| `gen_ai.usage.input_tokens` | Response `prompt_eval_count` or `prompt_tokens` | Conditional |
| `gen_ai.usage.output_tokens` | Response `eval_count` or `completion_tokens` | Conditional |
| `gen_ai.usage.cost` | Calculated from `pricing.json` | No (extra) |
| `gen_ai.input.messages` | Request messages (opt-in) | No |
| `gen_ai.output.messages` | Assistant response (opt-in) | No |

### Metrics

| Metric | Type | Unit | Description |
|---|---|---|---|
| `gen_ai.client.token.usage` | Histogram | `{token}` | Input and output token counts per request. Bucket boundaries: `[1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864]` |
| `gen_ai.client.operation.duration` | Histogram | `s` | End-to-end request duration. Bucket boundaries: `[0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92]` |
| `gen_ai.client.request.count` | Counter | `{request}` | Total number of requests (custom, not in OTel semconv) |
| `gen_ai.client.operation.cost` | Histogram | `USD` | Estimated cost per request (custom, not in OTel semconv) |

All metrics include these attributes per OTel semconv:

| Attribute | Description |
|---|---|
| `gen_ai.operation.name` | Operation type (always `"chat"`) |
| `gen_ai.provider.name` | Inference provider name |
| `gen_ai.request.model` | Requested model name |
| `gen_ai.response.model` | Responding model name |
| `gen_ai.token.type` | `"input"` or `"output"` (token usage metric only) |
| `suse.ai.component.name` | Always `"open-webui"` (custom, for topology discovery) |

### Resource Attributes

| Attribute | Value |
|---|---|
| `service.name` | Configurable (default: `"Open WebUI"`) |
| `service.version` | `"1.0"` |
| `deployment.environment` | `"default"` |
| `telemetry.sdk.name` | `"suse-ai"` |
| `suse.ai.managed` | `"true"` |
| `suse.ai.component.name` | `"open-webui"` |
| `suse.ai.component.type` | `"ui"` |

## Configuration

Configurable via Open WebUI Valves UI or environment variables:

| Valve | Environment Variable | Default | Description |
|---|---|---|---|
| `otlp_service_name` | `OTEL_SERVICE_NAME` | `"Open WebUI"` | Service name in OTel resource |
| `otlp_endpoint` | `OTEL_EXPORTER_HTTP_OTLP_ENDPOINT` | `http://opentelemetry-collector.observability.svc.cluster.local:4318` | OTLP/HTTP endpoint |
| `capture_message_content` | - | `true` | Capture input/output message content in spans |
| `debug_log_enabled` | - | `false` | Enable debug logging |
| `pricing_information` | `PRICING_JSON` | GitHub-hosted `pricing.json` | URL to model pricing JSON |

## Integration with SUSE AI Observability

The `suse.ai.*` resource attributes and `suse.ai.component.name` metric label enable automatic topology discovery in SUSE Observability. The OTel Collector uses these attributes to:

- Create the Open WebUI component in the topology
- Infer inference engine components from `gen_ai.provider.name`
- Infer LLM model components from `gen_ai.request.model`
- Create relations between app, providers, and models

See `knowledge/GENAI_TOPOLOGY_INFERENCE.md` for details on how this works.

## Dependencies

- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp-proto-http`
- `opentelemetry-semantic-conventions`
- `pydantic`

## Changelog

### Version 2.0.0 (2026-03-13)

What's new:

* Aligned traces and metrics with OpenTelemetry GenAI semantic conventions.
* Standard metric names: `gen_ai.client.token.usage`, `gen_ai.client.operation.duration`.
* Standard span attributes: `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.response.finish_reasons`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`.
* Histogram bucket boundaries follow OTel semconv recommendations.
* Opt-in message content capture via `gen_ai.input.messages` / `gen_ai.output.messages`.
* Custom `suse.ai.*` resource attributes for topology discovery.
* Custom metrics: `gen_ai.client.request.count` (counter), `gen_ai.client.operation.cost` (histogram).
* Cost estimation from configurable `pricing.json`.
* Immediate telemetry initialization for Open WebUI 0.6.41+ compatibility.
* Thread-safe span tracking.

### Version 1.1.0 (2025-10-20)

What's new:

* Support for vLLM as inference server.

Fixes:

* Fix failure to process OpenAI payloads.

### Version 1.0.0 (2025-05-30)

What's new:

* Infer tracing data and metrics for user chats with Ollama models.
* Custom configurations through the UI or environment variables.

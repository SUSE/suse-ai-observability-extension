# OpenTelemetry GenAI Semantic Conventions

This document summarizes the semantic conventions for Generative AI (GenAI) and Large Language Models (LLMs) as defined by the OpenTelemetry project.

## 1. Inference Spans

Spans representing GenAI operations (calls to a model) should use the following attributes.

### Required Attributes
| Key | Type | Description | Examples |
| :--- | :--- | :--- | :--- |
| `gen_ai.operation.name` | string | Name of the operation. | `chat`, `text_completion`, `embeddings` |
| `gen_ai.provider.name` | string | The GenAI provider. | `openai`, `anthropic`, `ollama`, `vllm` |

### Required (Conditional / Recommended)
| Key | Type | Description |
| :--- | :--- | :--- |
| `gen_ai.request.model` | string | The name of the model requested. |
| `gen_ai.response.model` | string | The name of the model that actually responded. |
| `gen_ai.usage.input_tokens` | int | Number of tokens in the prompt. |
| `gen_ai.usage.output_tokens` | int | Number of tokens in the response. |
| `server.address` | string | The address of the GenAI server. |
| `server.port` | int | The port of the GenAI server. |

### Opt-In (Sensitive Data)
| Key | Type | Description |
| :--- | :--- | :--- |
| `gen_ai.input.messages` | JSON | Full chat history provided. |
| `gen_ai.output.messages` | JSON | Full responses returned. |

## 2. Resource Attributes

Resource attributes identify the entity producing the telemetry (the "Application" or "System").

| Key | Type | Description |
| :--- | :--- | :--- |
| `service.name` | string | The logical name of the service. |
| `service.namespace` | string | The namespace (e.g., K8s namespace). |
| `telemetry.sdk.name` | string | Set to `suse-ai` for our instrumentation. |
| `suse.ai.managed` | bool | Indicates if the resource is managed by SUSE AI. |
| `suse.ai.component.name` | string | See examples in ARCH.md. |
| `suse.ai.component.type` | string | See examples in ARCH.md. |

## 3. Metrics

### Standard Metric Names
*   `gen_ai.client.token.usage`: Counter for tokens (input/output).
*   `gen_ai.client.operation.duration`: Histogram for request latency.
*   `gen_ai.server.request.duration`: Latency as measured by the server.

### Metric Attributes
*   `gen_ai.operation.name`
*   `gen_ai.provider.name`
*   `gen_ai.request.model`
*   `error.type`

## 4. OTel-to-Prometheus Metric Name Conversion

When OTel metrics are exported via the Prometheus exporter, the names are transformed:

### Naming Rules
*   Dots (`.`) become underscores (`_`): `gen_ai.client.token.usage` → `gen_ai_client_token_usage`
*   Unit suffixes are appended automatically: a histogram with `unit="USD"` gets `_USD` appended → `gen_ai_client_operation_cost_USD_bucket`
*   Histogram metrics get three series: `_bucket`, `_sum`, `_count`
*   Counter metrics get `_total` suffix: `gen_ai.client.request.count` → `gen_ai_client_request_count_total`

### Actual Prometheus Metric Names (from our filter)
| OTel Name | Prometheus Name(s) |
| :--- | :--- |
| `gen_ai.client.request.count` | `gen_ai_client_request_count_total` |
| `gen_ai.client.token.usage` | `gen_ai_client_token_usage_sum`, `_bucket`, `_count` |
| `gen_ai.client.operation.duration` (unit=s) | `gen_ai_client_operation_duration_seconds_bucket`, `_sum`, `_count` |
| `gen_ai.client.operation.cost` (unit=USD) | `gen_ai_client_operation_cost_USD_bucket`, `_sum`, `_count` |

### Token Type Filtering
*   Input tokens: `gen_ai_client_token_usage_sum{gen_ai_token_type="input"}`
*   Output tokens: `gen_ai_client_token_usage_sum{gen_ai_token_type="output"}`
*   Total tokens: `gen_ai_client_token_usage_sum` (no filter)

## 5. Span Attributes vs Events

Per OTel GenAI semconv:
*   `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` → span attributes (kept)
*   `gen_ai.usage.total_tokens` → NOT a standard attribute, should NOT be set on spans
*   `gen_ai.output.type` → NOT a standard attribute, should NOT be set on spans
*   `gen_ai.input.messages` and `gen_ai.output.messages` → opt-in, JSON-serialized arrays
*   `finish_reason` → belongs inside the output message object, not as a span attribute

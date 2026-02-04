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
| `gen_ai.system` | string | (Legacy/Extended) The type of AI system (Ollama, vLLM). |

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

## 4. SUSE AI Extensions

To support dynamic topology inference in StackState, we extend these with:
*   `stackpack: suse-ai`: Identifies GenAI-relevant resources.
*   `gen_ai.models`: A comma-separated list of models detected at the resource level (aggregated from spans).

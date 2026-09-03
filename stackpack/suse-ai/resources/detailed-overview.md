## Prerequisites

The SUSE AI Observability StackPack expects OpenTelemetry traces and metrics from instrumented GenAI applications and infrastructure. To get started:

1. **Instrument your applications** with OpenTelemetry SDKs that support GenAI semantic conventions (e.g., `gen_ai.operation.name`, `gen_ai.provider.name`).
2. **Add SUSE AI resource attributes** where applicable:
   - `suse.ai.managed` – boolean flag to distinguish platform vs. user components.
   - `suse.ai.component.type` – functional role (e.g., `inference-engine`, `vectordb`, `agent`).
   - `suse.ai.component.name` – logical name (if distinct from `service.name`).
3. **Configure the OpenTelemetry collector** to forward telemetry to SUSE Observability.

See the [SUSE AI Observability documentation](https://documentation.suse.com/suse-ai/1.0/html/AI-monitoring/index.html) for detailed setup instructions.

### Kubeflow

The StackPack monitors three Kubeflow components:

- **KServe**: per-InferenceService request volume and latency plus controller
  reconciliation and workqueue health.
- **Kubeflow Pipelines**: run outcomes, KFP API and gRPC activity, Argo workflow
  phases, controller latency, queues, pod outcomes, and instrumented demo model
  quality.
- **Kubeflow Model Registry**: topology plus authenticated synthetic API
  availability, duration, response validation, size, and errors.

The companion demo applications also emit agent tool execution, RAG retrieval
quality, and generated scenario metrics. These bindings appear on the matching
agent and application components.

## Installation

Click **Install** to enable SUSE AI Observability monitoring.

### Prerequisites

The StackPack requires OpenTelemetry telemetry with GenAI semantic conventions and SUSE AI resource attributes. Before installing, ensure:

1. **Your applications are instrumented** with OpenTelemetry SDKs that emit GenAI semantic conventions (e.g., `gen_ai.operation.name`, `gen_ai.provider.name`).
2. **SUSE AI resource attributes are set** on your components:
   - `suse.ai.component.type` -- functional role (e.g., `inference-engine`, `vectordb`, `agent`).
   - `suse.ai.component.name` -- logical name (if distinct from `service.name`).
3. **The OpenTelemetry collector is configured** to forward traces and metrics to SUSE Observability.

See the [SUSE AI Observability documentation](https://documentation.suse.com/suse-ai/1.0/html/AI-monitoring/index.html) for detailed setup instructions.

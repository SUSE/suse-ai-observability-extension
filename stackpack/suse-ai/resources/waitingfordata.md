## Waiting for data

The SUSE AI Observability StackPack is installed and waiting for GenAI telemetry data to arrive.

### Checklist

To start seeing AI components in SUSE Observability:

1. **Instrument your applications** with OpenTelemetry SDKs that support [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) (e.g., `gen_ai.operation.name`, `gen_ai.provider.name`).
2. **Add SUSE AI resource attributes** to distinguish components:
   - `suse.ai.component.type` -- functional role (e.g., `inference-engine`, `vectordb`, `agent`).
   - `suse.ai.component.name` -- logical name (if distinct from `service.name`).
3. **Configure the OpenTelemetry collector** to forward traces and metrics to SUSE Observability.

Once data arrives, components will appear automatically in the **AI Applications** view.

See the [SUSE AI Observability documentation](https://documentation.suse.com/suse-ai/1.0/html/AI-monitoring/index.html) for detailed setup instructions.

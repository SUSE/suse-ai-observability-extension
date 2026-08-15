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

### Kubeflow

If you want to monitor Kubeflow components (Pipelines, KServe, Model Registry), two configuration steps are required.

1. **Set the Kubeflow namespace** in your OTel collector Helm values:

   ```yaml
   extraEnvs:
     - name: KUBEFLOW_NAMESPACE
       value: "kubeflow"   # change if your install uses a different namespace
   ```

2. **Enable metric aggregation** on each KServe `InferenceService` so the queue-proxy exposes runtime metrics on the `http-usermetric` port:

   ```yaml
   metadata:
     annotations:
       serving.kserve.io/enable-metric-aggregation: "true"
       serving.kserve.io/enable-prometheus-scraping: "true"
   ```

Once these are in place, the OTel collector picks up KServe metrics through Kubernetes pod discovery; no further per-`InferenceService` configuration is required.

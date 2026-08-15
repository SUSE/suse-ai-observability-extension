## The SUSE AI Observability StackPack is installed

### What's included

- **AI Applications view** -- a dedicated topology view showing all discovered GenAI components, with columns for request rate, token usage, and cost.
- **Metric bindings** -- pre-configured charts for application, agent, RAG,
  generated demo traffic, vLLM, vector database, KServe, Kubeflow Pipelines, and
  Model Registry signals.
- **Health monitors** -- automatic checks for GenAI data flow, inference
  performance, pipeline health, controller queues, and registry availability.
- **Per-model drill-down** -- individual model components under vLLM inference engines with dedicated performance charts.

### What's next

If you haven't already, ensure your GenAI applications and infrastructure are instrumented with OpenTelemetry and sending data to SUSE Observability. See the [SUSE AI Observability documentation](https://documentation.suse.com/suse-ai/1.0/html/AI-monitoring/index.html) for details.

### Kubeflow

If your environment includes Kubeflow, the StackPack additionally surfaces:

- **KServe inference engines** -- request rate, prediction and step latency,
  reconciliation health, and workqueue depth across `InferenceService` resources
  (component type: `inference-engine.kserve`).
- **Kubeflow Pipelines control plane** -- pipeline outcomes, KFP API and gRPC
  activity, Argo workflow phases, reconciliation latency, pod outcomes, and queue
  health (component type: `workflow-engine.kubeflow-pipelines`).
- **Kubeflow Model Registry** -- authenticated synthetic API availability,
  duration, response validation, response size, and connection errors (component
  type: `ml-registry.kubeflow`).

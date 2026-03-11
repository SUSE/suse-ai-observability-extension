## The SUSE AI Observability StackPack is installed

### What's included

- **AI Applications view** -- a dedicated topology view showing all discovered GenAI components, with columns for request rate, token usage, and cost.
- **Metric bindings** -- pre-configured charts for application metrics (request count, token usage, operation duration, cost) and vLLM inference engine metrics (latency percentiles, token throughput, GPU cache usage, running/waiting requests).
- **Health monitors** -- automatic health checks that detect when GenAI data stops arriving from application components.
- **Per-model drill-down** -- individual model components under vLLM inference engines with dedicated performance charts.

### What's next

If you haven't already, ensure your GenAI applications and infrastructure are instrumented with OpenTelemetry and sending data to SUSE Observability. See the [SUSE AI Observability documentation](https://documentation.suse.com/suse-ai/1.0/html/AI-monitoring/index.html) for details.

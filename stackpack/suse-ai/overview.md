## SUSE AI Observability StackPack

The SUSE AI Observability StackPack provides out-of-the-box support for monitoring Generative AI (GenAI) workloads and infrastructure. It transforms raw OpenTelemetry telemetry into a high-level architectural map, categorizing components into logical groups:

- **User Workloads & Interfaces**: Applications, agents, and frontends that consume GenAI services.
- **Platform Components**: Inference engines, model proxies, vector databases, search engines, and orchestration tools.
- **GPU Nodes**: Physical or virtual Kubernetes nodes hosting NVIDIA GPUs.

The StackPack automatically discovers GenAI components based on standard OpenTelemetry GenAI semantic conventions and SUSE AI-specific resource attributes (`suse.ai.component.type`, `suse.ai.component.name`). It provides topology visualization, metric bindings, and health monitors for AI‑specific metrics like token usage, inference latency, GPU memory, and cache utilization.
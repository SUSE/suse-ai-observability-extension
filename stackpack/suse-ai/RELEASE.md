# SUSE AI Observability StackPack

## Version 0.1.110

- Initial release of the SUSE AI Observability StackPack.
- Provides topology mapping for GenAI components based on OpenTelemetry semantic conventions.
- Supports categorization into User Workloads, Platform Components, and GPU Nodes.
- Includes metric bindings and health monitors for AI‑specific metrics (token usage, inference latency, GPU memory, etc.).
- Uses `suse-ai:` prefix for component URNs to avoid conflicts with standard OpenTelemetry components.
# SUSE AI Observability StackPack

## Version 0.1.241

- Consolidated vLLM latency charts into multi-query bindings (P99/P95/P90/P50/Avg in a single chart).
- Added per-model component views for vLLM inference engines with dedicated performance metrics.
- Added "Top Models by Usage" metric binding for vLLM.
- Fixed application metric bindings to use correct OTel-to-Prometheus metric names.
- Added Total Tokens and Total Cost columns to the AI Applications view.
- Added Operation Duration (P95) metric binding for application components.
- Bound GenAI health monitor to application components.
- Updated documentation links.

## Version 0.1.110

- Initial release of the SUSE AI Observability StackPack.
- Provides topology mapping for GenAI components based on OpenTelemetry semantic conventions.
- Supports categorization into User Workloads, Platform Components, and GPU Nodes.
- Includes metric bindings and health monitors for AI-specific metrics (token usage, inference latency, GPU memory, etc.).
- Uses `suse-ai:` prefix for component URNs to avoid conflicts with standard OpenTelemetry components.

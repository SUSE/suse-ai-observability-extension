# Governance - SUSE AI Observability StackPack

This document tracks the roadmap, design principles, and task list for the SUSE AI Observability Extension.

## 1. Vision
Provide a robust, dynamic, and automated way to observe GenAI architectures (LLMs, Vector DBs, AI Applications) by leveraging OpenTelemetry Semantic Conventions and custom topology inference.

## 2. Design Principles
*   **OTel First**: Adhere strictly to [OpenTelemetry Semantic Conventions](./OTEL_CONVENTIONS.md) for GenAI.
*   **Zero Conf Inference**: Automate the identification of systems (Ollama, vLLM, Milvus) from telemetry data.
*   **Parallel Topology**: Maintain a clean GenAI-specific topology layer using the `openlit:` prefix to avoid conflicts with standard OTel components.
*   **Unified Identity**: A single physical resource (e.g., a K8s pod) can represent multiple logical components (App, System, Model).

## 3. Roadmap & Tasks

### Stage 1: Standard Alignment (In Progress)
- [ ] Document OTel Semantic Conventions for GenAI (`OTEL_CONVENTIONS.md`).
- [ ] Implement conventions in `suse_ai_filter.py`.
- [ ] Replace "openlit" mentions with "suse-ai" in instrumentation metadata.
- [ ] Aggregate model and system information at the Resource level in the filter.

### Stage 2: Topology Robustness
- [ ] Refine Groovy mappers to support new OTel attributes.
- [ ] Fix "Failed to find externalId" relation errors by standardizing ID prefixing.
- [ ] Implement dynamic model component creation from aggregated resource tags.

### Stage 3: UI & Experience
- [ ] Link custom `ComponentTypes` (vLLM, Ollama, Milvus) to their specific icons and metrics.
- [ ] Create specialized views for AI Applications vs. AI Infrastructure.
- [ ] Add metric bindings for token usage, cost, and latency at all topology levels.

### Stage 4: Documentation & Best Practices
- [ ] Create `docs/instrumentation/` folder.
- [ ] Document best practices for user applications to participate in the GenAI topology.
- [ ] Provide examples for Python (LangChain, LlamaIndex) and JS/TS.

## 4. Design Decisions
Tracked in [DESIGN_DECISIONS.md](./DESIGN_DECISIONS.md).

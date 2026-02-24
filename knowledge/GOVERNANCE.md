# Governance - SUSE AI Observability StackPack

This document tracks the roadmap, design principles, and task list for the SUSE AI Observability Extension.

## 1. Vision
Provide a robust, dynamic, and automated way to observe GenAI architectures (LLMs, Vector DBs, AI Applications) by leveraging OpenTelemetry Semantic Conventions and custom topology inference.

## 2. Design Principles
*   **OTel First**: Adhere strictly to [OpenTelemetry Semantic Conventions](./OTEL_CONVENTIONS.md) for GenAI.
*   **Architectural Abstraction**: Prioritize high-level logical components (Apps, Systems, Models) over low-level infrastructure (Pods, Instances).
*   **Zero Conf Inference**: Automate the identification of systems (Ollama, vLLM, Milvus) and their relationships from telemetry data.
*   **Parallel Topology**: Maintain a clean GenAI-specific topology layer using the `openlit:` prefix to avoid ownership conflicts.
*   **Multiplexed Mapping**: One OTel payload can spawn multiple topology nodes to represent different architectural dimensions.

## 3. Component Promotion & Inference Rules

1.  **Identity Rule**: All logical components MUST be prefixed with `openlit:<type>:` to maintain a parallel namespace.
2.  **Promotion Rule**: Components should be created even if they don't emit their own Resource telemetry (e.g., inferring Ollama from Open WebUI's `gen_ai.system` attribute).
3.  **Relationship Rule**: 
    - `uses` relations are created when an App reports a dependency on a System.
    - `runs` relations are created when a System reports hosting specific Models.
4.  **Metric Binding Rule**: All logical components MUST have relevant metrics bound to them based on their custom `ComponentType`.

## 4. Roadmap & Tasks

### Stage 1: Standard Alignment (Completed)
- [x] Document OTel Semantic Conventions for GenAI (`OTEL_CONVENTIONS.md`).
- [x] Implement conventions in `suse_ai_filter.py`.
- [x] Replace "openlit" mentions with "suse-ai" in instrumentation metadata.

### Stage 2: Topology Robustness (In Progress)
- [x] Refine Groovy mappers to support new OTel attributes.
- [x] Fix relation errors by standardizing prefixing in mappers.
- [x] Implement multi-model inference via list-based ID extraction.
- [ ] Implement "Heartbeat" promotion in OTel Collector for metric-only components.

### Stage 3: UI & Experience (In Progress)
- [x] Link custom `ComponentTypes` to icons and metrics.
- [x] Create specialized views for AI Applications vs. AI Infrastructure.
- [x] Hide low-level service instances from GenAI-specific views.
- [ ] Implement "Architectural Layout" in SUSE Observability views.

## 4. Design Decisions
Tracked in [DESIGN_DECISIONS.md](./DESIGN_DECISIONS.md).

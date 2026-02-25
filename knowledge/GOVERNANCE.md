# Governance - SUSE AI Observability StackPack

This document tracks the roadmap, design principles, and task list for the SUSE AI Observability Extension.
Notice that in previous iterations knowledge was created. We are starting the stackpack implementation from scratch, but using the knowledge we gathered in previous iterations.

## 1. Vision
Provide a robust, dynamic, and automated way to observe GenAI architectures (LLMs, Vector DBs, AI Applications) by leveraging OpenTelemetry Semantic Conventions and custom topology inference.
We identify components based on the data from a Kafka topic, `sts_topo_opentelemetry_collector`, and instructions about the data format are available in knowledge/INFO_STRUCTURE.md
You can inspect the data from the kafka in realtime using the commands in `sts topic describe --name sts_topo_opentelemetry_collector --limit 50 --file tmp/realtime_data.json` and then reading the tmp/realtime_data.json.

## 2. Design Principles
*   **OTel First**: Adhere strictly to [OpenTelemetry Semantic Conventions](./OTEL_CONVENTIONS.md) for GenAI.
*   **Architectural Abstraction**: Prioritize high-level logical components (Apps, Systems, Models) over low-level infrastructure (Pods, Instances).
*   **Zero Conf Inference**: Automate the identification of systems (Ollama, vLLM, Milvus) and their relationships from telemetry data.
*   **Parallel Topology**: Maintain a clean GenAI-specific topology layer using the `suse-ai:` prefix to avoid ownership conflicts.
*   **Multiplexed Mapping**: One OTel payload can spawn multiple topology nodes to represent different architectural dimensions.

## 3. Component Promotion & Inference Rules

1.  **Identity Rule**: All logical components MUST be prefixed with `suse-ai:<type>:` to maintain a parallel namespace.
2.  **Promotion Rule**: Components should be created even if they don't emit their own Resource telemetry (e.g., inferring Ollama from Open WebUI's `gen_ai.system` attribute).
4.  **Metric Binding Rule**: All logical components MUST have relevant metrics bound to them based on their custom `ComponentType`.

## 4. Roadmap & Tasks

### Stage 1: Standard Alignment (Completed)
- [ ] Search for contradictions in the knowledge. If some contradiction is found, use the information in ARCH.md as the source of truth. If undecided, ask for human feedback.
- [ ] Use the OpenTelemetry stackpack as a reference structure for the suse-ai stackpack. Full path is: /home/thbertoldi/suse/stackstate/stackpacks/stackpacks/open-telemetry
- [ ] Read additional instructions for stackpack creation in the markdown files inside /home/thbertoldi/suse/stackstate/stackpacks
- [ ] Create the base for our new stackpack, in a new folder suse-ai
- [ ] Adapt the the files in setup/stackpack to a structure similar to the OpenTelemetry stackpack in the suse-ai stackpack.
- [ ] You can (and should) use the stackstate cli for verifying your work.
- [ ] Our goal is to build our first StackPack for SUSE AI.

### Stage 2: Topology Robustness (In Progress)
- [ ] Refine Groovy mappers to support the new OTel attributes.

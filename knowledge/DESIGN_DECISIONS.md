# Design Decisions - SUSE AI Observability StackPack

This document records the architectural and implementation decisions made for the project.

## 1. Instrumentation Identity
*   **Decision**: We use `suse-ai` as the primary identifier for our instrumentation SDK/tool.
*   **Rationale**: Distinguish SUSE AI telemetry from other GenAI observability tools (like OpenLIT or OpenInference) while remaining compatible with OTel conventions.
*   **Application**: Set `telemetry.sdk.name: suse-ai` in all Resource Attributes.

## 2. Topology Identity (The `suse-ai:` Prefix)
*   **Decision**: Maintain the `suse-ai:` prefix for `externalId`s in the SUSE Observability graph.
*   **Rationale**: The sync engine requires a unique namespace to prevent "claim conflicts" with the standard OpenTelemetry StackPack. Changing this prefix would require a full topology migration. We treat `suse-ai:` as the "GenAI Observability Layer" namespace.

## 3. Dynamic Inference via Multiplexing
*   **Decision**: Use multiple `Sync` nodes in the `.sty` template to infer multiple components from a single OTel payload.
*   **Rationale**: A single physical service (e.g., a vLLM pod) acts as an Application, a GenAI System, and may host multiple Models. Standard OTel mapping only allows one component per payload. Multiplexing allows us to represent all these dimensions.

## 4. Resource-Level Aggregation
*   **Decision**: Aggregate low-cardinality metadata (like model names) from spans into Resource Attributes at the filter level.
*   **Rationale**: Topology components in SUSE Observability are primarily based on Resources. By moving model names to Resource Attributes, we enable the sync engine to dynamically create "Model" components that are linked to the "System" component.

## 5. View Grouping via Labels
*   **Decision**: Use labels (e.g., `suse.ai.managed:true`) rather than strict OTel `typeName`s for grouping components in UI views.
*   **Rationale**: Standard OTel components often share `typeName: service`. Labels allow us to create flexible, overlapping views (e.g., "All AI Systems" including both LLMs and Vector DBs).

## 6. Modular Provisioning
*   **Decision**: Split the StackPack into modular `.sty` files (`shared.sty`, `synchronization.sty`, etc.) included into a master `suse-ai.sty`.
*   **Rationale**: Ease of maintenance and debugging. 
*   **Implementation**: Provisioning imports `shared.sty` (for global URNs like Domains) and `suse-ai.sty` (for instance-specific nodes) sequentially.

## 7. Component Identity Promotion
*   **Decision**: Move name and type promotion logic from Handlebars templates into the Groovy `ComponentMappingFunction`.
*   **Rationale**: Keeps templates clean and allows for complex fallback logic (e.g., checking `suse.ai.component.name` then `service.name` then `externalId`) in a more readable script format.

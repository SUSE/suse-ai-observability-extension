# Successor Handover: SUSE AI Observability StackPack

## 1. Project Context
The goal is to provide deep observability for GenAI architectures (LLMs, Vector DBs, AI Apps) using OpenTelemetry. We use Groovy scripts within a SUSE Observability StackPack to transform raw OTel telemetry into high-level architectural topology.

## 2. Session Achievements (Feb 25, 2026)
*   **Scaffolding**: Created the full directory structure in `stackpack/suse-ai/`.
*   **Provisioning**: Implemented `SuseAiProvision.groovy` with a two-phase import strategy.
*   **Topology Definition**: 
    - Defined `Domain` (GenAI) and `MainMenuGroup`.
    - Created multiple `ComponentTypes` (application, agent, ui, inference-engine, vectordb, genai.model, etc.).
    - Defined AI-specific `RelationTypes` (uses, queries, orchestrates, runs).
*   **Sync Logic**:
    - Implemented a custom `IdExtractorFunction` that adds the `suse-ai:` prefix to managed components.
    - Developed a `ComponentMappingFunction` that promotes names and types from OTel tags.
    - Created Handlebars templates for components and relations.
*   **Metrics & Monitors**: 
    - Ported key LLM metrics (Request Rate, Tokens, Cost).
    - Ported GPU Node NVIDIA XID error monitors.

## 3. Current Implementation Status
*   **StackPack Version**: 0.1.50
*   **Installation State**: The StackPack is currently failing provisioning due to a `NamespaceSnapshotException`. It seems some nodes are not being resolved within the provided namespace during the second phase of import.
*   **Crucial Discovery**: The Handlebars templates in `synchronization.sty` needed escaping for the `{{ element... }}` tags to prevent premature resolution.

## 4. Next Steps for Successor
1.  **Fix Provisioning Namespace**: Investigate why `shared.sty` nodes are not resolvable when referenced by `suse-ai.sty` nodes. You might need to merge them back into a single snapshot OR ensure they share the same namespace `urn:stackpack:suse-ai:shared:`.
2.  **Verify Script Escaping**: Double-check `synchronization.sty` to ensure ALL `{{ ... }}` tags intended for the Sync Engine (not Provisioning time) are escaped as `\{{ ... \}}`.
3.  **Restore Icons**: Once provisioning is stable, ensure all `iconbase64` fields are active and correctly prefixed.
4.  **Test Data Flow**: Once `INSTALLED`, use `sts topology-sync list` to check if the `SUSE AI` sync is receiving data from the OTel topic.

## 5. Resources
*   **Kubeconfig**: `/home/thbertoldi/Downloads/local (57).yaml`
*   **Pod Logs**: `kubectl --kubeconfig "/home/thbertoldi/Downloads/local (57).yaml" logs suse-observability-server-5f8b6b9b8-mzs55 -n suse-observability`
*   **Taskfile**: `task version-up`, `task stackpack-upload`.

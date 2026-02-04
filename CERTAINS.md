# Session Learnings: GenAI Observability StackPack

## 1. State of Work
*   **Version**: 1.30.89
*   **Status**: Successfully applied project-specific component types and fixed template resolution issues.
*   **Outcome**: 
    *   `urn:stackpack:openlit:shared:component-type:genai-app` is now used for GenAI Applications.
    *   System-specific types like `urn:stackpack:openlit:shared:component-type:dbsystem-milvus` are now correctly applied.
    *   Fixed `openlit-component-template.json.handlebars` and related templates to use dynamic type resolution (`element.type.name`) instead of hardcoded OTel types.
    *   Consolidated ID extraction logic into `genai-multiplexed-id-extractor.groovy` with strict type checking.
    *   New Sync node `v2` is running cleanly without ID extraction errors.

## 2. Technical Certainties

### OTel Alignment
*   Use `gen_ai.provider.name` for the AI system/vendor.
*   Use `gen_ai.operation.name` for the action (e.g., `chat`).
*   Resource Attributes are used for "Logical" topology, while Spans provide "Operation" and "Model" context.

### Identifier Strategy
*   Prefixing: `openlit:app:`, `openlit:system:`, `openlit:model:`.
*   This prevents ownership conflicts with the standard OTel StackPack.

### Template Resolution
*   Handbars Templates: Must use dynamic expressions like `\{{ resolveOrCreate "ComponentType" element.type.name element.type.name \}}` to support custom component types defined in the StackPack. Hardcoding types in templates overrides mapper logic.

### Sync Architecture
*   Function Dependencies: The sync engine prevents deleting `IdExtractorFunction` or `ComponentMappingFunction` if existing `Sync` nodes or `TopologyDataQuery` objects still depend on them. Renaming or re-IDing functions requires careful coordination or creating new Sync nodes.

## 3. Implementation Rules
1.  **Strict OTel Names**: Follow the naming patterns in `OTEL_CONVENTIONS.md`.
2.  **Prefix Consistency**: Always use `openlit:app:` for services and `openlit:system:` for service instances.
3.  **SDK Name**: Always use `suse-ai` as the SDK identifier.

## 4. Current Tasks
*   [Completed] Consolidate Apps and Systems sync nodes.
*   [Completed] Apply project-specific component types via updated templates.
*   [In Progress] Verifying relation creation between Apps and Systems in the topology.
*   [Pending] Refine Model mapping logic to support multiple models from a single resource attribute.

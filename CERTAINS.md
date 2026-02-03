# Session Learnings: GenAI Observability StackPack

## 1. State of Work
*   **Version**: 1.10.38
*   **Status**: Synchronization is **Running** and **Consuming Data**, but errors persist.
*   **Outcome**: Components and relations show as "Created" in sync stats, but are **not visible** in the graph or UI.
*   **Critical Discovery**: The standard OpenTelemetry StackPack "claims" components with standard URNs. If our GenAI sync uses the same `externalId`, a "claim conflict" occurs, and the components may be hidden or ownership may be unstable.

## 2. Technical Certainties

### Data Source & Topic
*   Topic: `sts_topo_opentelemetry_collector` contains wrapped `TopologyElement` objects.
*   The data contains both `TopologyComponent` and `TopologyRelation` payloads.

### Identifier Strategy
*   **MUST** use a unique prefix (e.g., `openlit:`) for ALL `externalId`s and `identifiers` to distinguish GenAI components from standard OTel components.
*   Relation `sourceId` and `targetId` must match these prefixed IDs exactly.
*   Failure to find a source/target component results in `Failed to find externalId ... This component should be synchronized first` errors.

### Groovy Mapping
*   Returning a `Map` from the mapper is preferred for the primary component.
*   Use `context.component` and `context.relation` for additional (inferred) elements.
*   **Types**: Always convert values to raw Strings (`.toString()`) to avoid `GString` signature mismatches.

### Template & Handlebars
*   `resolve "Domain" <urn>` and `resolve "Layer" <urn>` are the most stable ways to associate components with domains/layers.
*   If `resolve` fails, it can cause silent synchronization failures or "NullPointerException" when the engine tries to log the error.

## 3. Implementation Rules

1.  **Prefixing**: Every ID from the GenAI topic must be prefixed with `openlit:`.
2.  **Consistency**: ID extractors and mappers must apply the same prefixing logic.
3.  **Labels**: Every GenAI component must have the `gen_ai_app`, `gen_ai_system`, or `gen_vectordb_system` label to appear in the extension's views.
4.  **Domain/Layer**: Place components in standard OTel domains/layers initially to prove visibility, then move to custom domains once stable.

## 4. Current Blockers
*   `NullPointerException` in `String.replaceAll` within the sync engine suggests a template or mapper failure that is being incorrectly handled by the engine's error logger.
*   Relations failing to find their source/target components due to mismatched prefixing.

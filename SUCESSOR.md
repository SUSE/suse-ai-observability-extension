# Successor Handover: SUSE AI Observability StackPack

## 1. Project Context
The goal is to provide deep observability for GenAI architectures (LLMs, Vector DBs, AI Apps) using OpenTelemetry. We are porting inference logic from Go to Groovy scripts within a SUSE Observability StackPack. Telemetry data arrives via the `sts_topo_opentelemetry_collector` topic.

## 2. Architectural Blueprint

### The "Multiplexed Sync" Strategy
Since the StackState Groovy environment **disallows side-effects** (e.g., calling `context.component()` or `context.relation()` results in `SecurityException`), we use a Multiplexed Sync approach:
1.  **Multiple Sync Nodes**: In `genai-observability-instance-template.sty`, we define separate `Sync` nodes for Apps, Systems, and Models.
2.  **Unique ID Extractors**: Each Sync node has its own `IdExtractorFunction`. This allows a single OTel payload (like a `service` resource) to trigger the creation of multiple logical components in StackState.
3.  **Transformation Mappers**: Each Sync uses a specific mapper (`service-mapper.groovy`, `system-mapper.groovy`, `model-mapper.groovy`) to shape the OTel payload into the desired component type.

### Identifier Strategy (Crucial)
To avoid "claim conflicts" with the standard OTel StackPack, all GenAI components use a mandatory prefix based on their logical role:
*   **Apps**: `openlit:app:<urn>`
*   **Systems**: `openlit:system:<urn>`
*   **Models**: `openlit:model:<urn>`

**Note**: Even though we rebranded to `suse-ai`, we keep the `openlit:` prefix for the topology namespace to maintain consistency with existing data.

## 3. Implementation Details

### OTel Alignment
*   **Instrumentation SDK**: Telemetry produced by our filters/instrumentation should set `telemetry.sdk.name: suse-ai`.
*   **Semantic Conventions**: Follow `OTEL_CONVENTIONS.md`. Use `gen_ai.provider.name`, `gen_ai.operation.name`, and `gen_ai.request.model`.
*   **Resource Aggregation**: The `suse_ai_filter.py` aggregates model names into a `gen_ai.models` attribute at the resource level to facilitate topology inference.

### Groovy Constraints
*   **No Side-Effects**: Do not use `context.component()` or `context.relation()`. Return the `element` directly from the mapper.
*   **Type Safety**: Always call `.toString()` on IDs and names. `GStrings` cause `ClassCastException` in the sync engine.
*   **Handlebars Escaping**: If a `.handlebars` file is included in an STY file via `{{ include ... }}`, all internal Handlebars tags must be escaped: `\{{ element.externalId \}}`.

## 4. Current State (v1.30.70)
*   **Apps & Systems**: Successfully created as parallel components using the multiplexed sync.
*   **Models**: Inference logic implemented in `model-mapper.groovy` using the aggregated resource attributes.
*   **Branding**: Instrumentation metadata updated from "openlit" to "suse-ai".
*   **Relations**: Mapping logic implemented for `provided-by`, `uses`, and `runs`. Note: Error counts are currently high due to cross-sync component resolution issues.

## 5. Successor Task List
1.  **Consolidate Syncs**: Consider merging the Apps and Systems syncs into a single Sync node in `genai-observability-instance-template.sty` to resolve cross-sync relation errors.
2.  **User Documentation**: Refine `docs/instrumentation/best_practices.md` with more concrete code examples.
3.  **UI Verification**: Confirm if icons appear for the new `openlit:system:` components.
4.  **Metric Aggregation**: Ensure that `gen_ai.client.token.usage` metrics are correctly associated with the `openlit:app:` and `openlit:system:` components.

## 6. Key Documentation
*   `OTEL_CONVENTIONS.md`: Official naming standards.
*   `GOVERNANCE.md`: Project roadmap and status.
*   `DESIGN_DECISIONS.md`: Why we did things the way we did.
*   `CERTAINS.md`: Verifiable facts about the current environment.

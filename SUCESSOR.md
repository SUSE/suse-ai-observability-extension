# Successor Handover: GenAI Observability StackPack

## 1. Project Context
The goal is to port the GenAI topology inference logic from a Go-based runtime to Groovy scripts within a SUSE Observability StackPack. The topology is built from OpenTelemetry data arriving on the `sts_topo_opentelemetry_collector` topic.

## 2. Key Components
*   **Topic**: `sts_topo_opentelemetry_collector`. Contains `TopologyElement` wrappers.
*   **ID Extractor**: `genai-component-id-extractor.groovy` and `genai-relation-id-extractor.groovy`. They apply a mandatory `openlit:` prefix to all IDs to avoid "claim conflicts" with the standard OTel StackPack.
*   **Mapper**: `service-mapper.groovy`. Identifies GenAI apps (Milvus, Ollama, vLLM, etc.) and enriches the `element` with labels like `gen_ai_app`.
*   **Template**: `openlit-component-template.json.handlebars`. Converts mapper `tags` into StackState `Labels`. Uses `resolveOrCreate` for Domain/Layer URNs to prevent silent rendering failures.

## 3. Critical Learnings (Important!)
*   **Prefixing is Mandatory**: Standard OTel components own the unprefixed URNs. Our sync must prefix EVERYTHING with `openlit:` to ensure we don't get kicked out by the OTel sync.
*   **Labels are the UI Key**: The UI views filter on `label = 'gen_ai_app'`. The mapper puts `gen_ai_app: true` in tags, and the template must produce a label named exactly `gen_ai_app`.
*   **Strict Types**: In Groovy, always call `.toString()` on URNs and names. `GStrings` will break the `context.component` and `context.relation` signatures.
*   **Safe Handlebars**: Avoid `get`. Use `resolveOrCreate` or `resolve` with verified URNs. A failed Handlebars render results in a `NullPointerException` in the sync engine logs.

## 4. Current Status
*   As of version **1.30.0**, the synchronization is running and emitting components with correct labels.
*   Relations between components (e.g., `uses`) are being established using the same `openlit:` prefix strategy.

## 5. Next Steps
1.  **AI Models/Systems**: Continue porting logic from `internal/watcher/` Go files into `service-mapper.groovy` using `context.component` for side-effect component creation.
2.  **Verify Relations**: Ensure that relations between services and inferred systems/models correctly link using the `openlit:` prefix.
3.  **UI Verification**: Always check if new components appear in the "SUSE AI" menu in the UI.

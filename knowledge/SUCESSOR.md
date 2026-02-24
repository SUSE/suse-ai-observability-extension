# Successor Handover: SUSE AI Observability StackPack

## 1. Project Context
The goal is to provide deep observability for GenAI architectures (LLMs, Vector DBs, AI Apps) using OpenTelemetry. We use Groovy scripts within a SUSE Observability StackPack to transform raw OTel telemetry into high-level architectural topology.

## 2. Key Technical Standards (v1.31.54)

### SUSE AI Managed Convention
*   **Opt-in Signal**: Services managed by this extension must include the resource attribute `suse.ai.managed = "true"`.
*   **Redundancy Removal**: Do NOT use legacy labels like `gen_ai.app` or `stackpack: suse-ai`. Rely strictly on the managed flag and the specific component types.
*   **Ephemeral Components**: Components inferred from others (e.g., Models) are marked with `suse.ai.ephemeral = "true"`.

### Identifier Strategy
*   **Prefixing**: `openlit:app:<urn>`, `openlit:system:<urn>`, `openlit:model:<urn>`.
*   **OTel Alignment**: Always include the original OTel URN as an identifier in the `identifiers` list to ensure proper binding with OTel resources and monitors.

### Workspace & Tools
*   **Knowledge Base**: All project knowledge (.md files) is in the `knowledge/` directory. Consult it ALWAYS.
*   **Taskfile**: Use `task version-up` to increment version and `task stackpack-upload` to build and deploy.
*   **Debugging**: Place temporary scripts in the `tmp/` folder (git-ignored). Use `task sts-script FILE=tmp/your_script.groovy` to run them.
*   **CLI Cheatsheet**: Refer to `knowledge/CLI_CHEATSHEET.md` for common `sts` commands.

## 3. Current Implementation Status

### Mappers & Syncs
*   **Multiplexed Mapper**: Consolidates App, System, and Model creation. Correctly identifies Milvus, Ollama, vLLM, and OpenSearch.
*   **Namespace column**: Fixed. The `namespaceIdentifier` property is populated using the `service.namespace` attribute.
*   **Relations**: `uses` (App -> System) and `runs` (System -> Model) are correctly inferred and mapped.

### Demo Application
*   Located in `setup/genai-observability-demo`.
*   Updated to follow the `suse.ai.managed=true` convention.
*   Removed hardcoded "ZUSE" system name; names are now dynamically inferred from telemetry.

## 4. Successor Task List
1.  **Monitor Verification**: Ensure all monitors in `provisioning/monitors` are correctly binding to the new `openlit:*` URNs using the added aliases.
2.  **View Refinement**: Audit `views.sty` to ensure all AI components are visible in the intended menus without duplication.
3.  **Operation Support**: The `operation-mapper.groovy` is prepared but may need alignment with the consolidated sync strategy if more granular tracing is required.
4.  **Metric Mapping**: Verify that token usage and cost metrics are correctly appearing on the component highlights.

## 5. Knowledge Base
*   `knowledge/ARCH.md`: Architectural blueprint.
*   `knowledge/CERTAINS.md`: Technical certainties and implementation history.
*   `knowledge/OTEL_CONVENTIONS.md`: Naming standards.
*   `knowledge/CLI_CHEATSHEET.md`: CLI command references.
*   `knowledge/DESIGN_DECISIONS.md`: Rationales for key implementation choices.

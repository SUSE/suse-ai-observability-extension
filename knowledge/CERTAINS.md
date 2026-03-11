# Verified Facts - GenAI Observability StackPack

## 1. Icon Validation
*   **Fact**: `ComponentType` and `ViewType` icons in STY files must be valid base64 strings.
*   **Fact**: PNG format with the `data:image/png;base64,` prefix is reliably accepted by the StackState backend. 
*   **Fact**: SVG format requires the `data:image/svg+xml;base64,` prefix.
*   **Fact**: Large base64 icon strings in `products.sty` must be single-line strings. Multiline base64 strings without proper YAML folding (like `>`) can cause validation failures like `iconbase64: Must be a valid icon.`.

## 2. Provisioning Constraints
*   **Fact**: `importSnapshot` using an empty node list (`nodes: []`) is NOT allowed and will result in a provisioning error.
*   **Fact**: If any node in an imported snapshot is missing a required field (based on its `_type` schema), the entire transaction is rolled back.
*   **Fact**: `Sync` nodes REQUIRE the `componentActions` field to be present, even if empty (`componentActions: []`).
*   **Fact**: `Sync` nodes only support `SyncActionCreateComponent` and `SyncActionCreateOnMerge` for component-related actions. `SyncActionCreateRelation` is NOT supported in `componentActions`.
*   **Fact**: Every node in the `nodes:` list must have a unique `id` (negative integer) and a unique `identifier` (URN). Duplicate IDs or identifiers across different STY files will cause `NamespaceSnapshotError`.

## 3. Handlebars Path Resolution
*   **Fact**: The `include` helper resolves paths starting from the `provisioning/` folder within the ZIP.
*   **Fact**: Double prefixes (e.g., `provisioning/provisioning/...`) cause `NoSuchFileException`.

## 4. Component Schema
*   **Fact**: Modern StackState schemas for `ComponentType` require the `externalComponent` field.
*   **Fact**: `QueryView` nodes require a `queryVersion` (e.g., `"0.0.1"`) to be properly indexed in some versions.
*   **Fact**: `ComponentType` nodes within `highlights` must have an `about` section defined, or they will fail with `Object is missing required member 'about'`.

## 5. Synchronization Logic
*   **Fact**: `IdExtractorFunction` returning `null` effectively filters out components from a synchronization.
*   **Fact**: `getOrCreate` helper provides robustness by falling back to auto-generated types if a specific URN is missing.
*   **Fact**: The `IdExtractorFunction` API signature is `Sts.createId(String externalId, Set<String> identifiers, String typeName)`.
*   **Fact**: Two distinct IdExtractorFunctions are used: `suse-ai-id-extractor.groovy` (adds `suse-ai:` prefix to OTel external IDs) and `suse-ai-product-id-extractor.groovy` (creates aggregated product IDs based on `suse.ai.component.name` and `suse.ai.component.type` tags).
*   **Fact**: Merging multiple STY files into a single `importSnapshot` master file prevents `NamespaceSnapshotException` caused by cross-file references.

## 6. Data Flow & Categorization
*   **Fact**: The SUSE AI synchronization uses a `suse-ai:` prefix for all components to ensure they remain separate from standard OTel components.
*   **Fact**: Multiplexed mapping is achieved by having two `Sync` nodes: one for Core mirroring (`suse-ai:<URN>`) and one for Product grouping (`suse-ai:product:<type>:<name>`).
*   **Fact**: The `component-mapping-function.groovy` adds a `suse.ai.category` label to all managed components (e.g., `suse.ai.category:application`, `suse.ai.category:vectordb`).
*   **Fact**: The `runs-relation-template.json.handlebars` file exists but is not referenced in the synchronization configuration; only `relation-template.json.handlebars` is used for all relation generation.
*   **Fact**: `QueryView` queries in `shared.sty` use `label = 'suse.ai.category:<category>'` instead of `type STARTSWITH` (which is unsupported in STQL) to correctly group specialized product types in the UI menus.

## 7. Product Component Types & Metric Bindings
*   **Fact**: Product-specific component types (e.g., inference-engine.vllm, vectordb.milvus) are defined in `products.sty`.
*   **Fact**: Metric bindings in `product-metrics.sty` use unique product-scoped identifiers (e.g., `urn:stackpack:suse-ai:shared:metric-binding:vllm:e2e-latency-avg`) to avoid global URN collisions.
*   **Fact**: All 170+ metric bindings in `product-metrics.sty` have unique negative IDs ranging from -500 downwards.
*   **Fact**: Top-level list items in included STY files MUST be indented with exactly 2 spaces (`  - _type: ...`).
*   **Fact**: The `genai-system-active` monitor uses the aligned URN pattern: `suse-ai:product:inference-engine:${gen_ai_system}`.

## 8. Taskfile Commands
*   **Fact**: The `stackpack-uninstall` task in `Taskfile.yaml` correctly uninstalls all instances with status 'INSTALLED' or 'ERROR'.

## 9. Documentation & Packaging

*   **Fact**: The StackPack's user‑facing markdown files (`overview.md`, `detailed‑overview.md`, `configuration.md`, `provisioning.md`, `waitingfordata.md`, `enabled.md`, `RELEASE.md`) reside in `stackpack/suse‑ai/resources/` and are referenced via `configurationUrls` in `stackpack.conf`.
*   **Fact**: The `configurationUrls` mapping follows the state machine: `NOT_INSTALLED` → `configuration.md`, `PROVISIONING` → `provisioning.md`, `WAITING_FOR_DATA` → `waitingfordata.md`, `INSTALLED` → `enabled.md`, `DEPROVISIONING` → `configuration.md`, `ERROR` → `configuration.md`.
*   **Fact**: The `overviewUrl`, `detailedOverviewUrl`, and `releaseNotes` fields in `stackpack.conf` resolve relative to the `resources/` directory inside the packaged `.sts` zip.
*   **Fact**: The `logoUrl` in `stackpack.conf` also resolves relative to `resources/`. The logo file MUST be placed in `stackpack/suse-ai/resources/logo.png`, not at the stackpack root.
*   **Fact**: The `stackpack-upload` task in `Taskfile.yaml` zips only `stackpack.conf`, `provisioning/`, and `resources/`. Files at the stackpack root (outside these directories) are NOT included in the `.sts` package.
*   **Fact**: Any markdown or asset files at the stackpack root (e.g., `stackpack/suse-ai/logo.png`, `stackpack/suse-ai/overview.md`) are unused duplicates — only the copies under `resources/` are packaged and served.

## 10. View Types
*   **Fact**: The GPU Nodes ViewType (`urn:stackpack:suse-ai:shared:view-type:gpu-nodes`) provides a detailed table with GPU-specific columns and metrics, extending the existing QueryView.
*   **Fact**: ViewType columns can reference metric bindings from both the SUSE AI stackpack (`urn:stackpack:suse-ai:shared:metric-binding:common:node-gpu-*`) and external stackpacks (`urn:stackpack:stackstate-k8s-agent-v2:shared:metric-binding:host-*`).
*   **Fact**: The `pathToIdentifier` for label‑based columns must point to a unique component identifier (e.g., `internalIP` for nodes) to correctly resolve component links.
*   **Fact**: ViewType files must be included in `suse-ai.sty` via `{{ include "templates/view-types/<file>.sty" "yaml" }}` to be provisioned. Creating the file alone is not sufficient.
*   **Fact**: QueryViews reference ViewTypes via `viewType: urn:stackpack:suse-ai:shared:view-type:<name>`. Without this reference, the QueryView uses the default table layout (no icon, no custom columns).
*   **Fact**: ViewType IDs use the -6000 range (e.g., -6001 for AI Applications, -6002 for All GenAI Components, up to -6009 for ML Registries).

## 11. Monitors
*   **Fact**: The OpenSearch cluster status monitors (red and yellow) are defined in `templates/monitors/opensearch/monitor.sty` with IDs -3002 and -3003.
*   **Fact**: The red monitor triggers a CRITICAL state when `elasticsearch_cluster_health{status="red"} > 0`, extracting component name via `label_replace`.
*   **Fact**: The yellow monitor triggers a DEVIATING state when `elasticsearch_cluster_health{status="yellow"} > 0`, extracting component name via `label_replace`.
*   **Fact**: Both monitors use `label_replace` to transform `elasticsearch_cluster_name` labels (e.g., "opensearch-cluster" → "opensearch") into `product_name` for URN matching.
*   **Fact**: Monitors attach to product components using URN pattern `suse-ai:product:search-engine:${product_name}` where `product_name` is derived from metric labels.
*   **Fact**: Remediation hints for OpenSearch monitors are located in `templates/monitors/opensearch/remediation-red.md.hbs` and `remediation-yellow.md.hbs` and are included using the Handlebars helper: `{{ include "templates/monitors/opensearch/remediation-red.md.hbs" "identity" }}`

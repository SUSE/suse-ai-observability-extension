# Verified Facts - GenAI Observability StackPack

## 1. Icon Validation
*   **Fact**: `ComponentType` and `ViewType` icons in STY files must be valid base64 strings.
*   **Fact**: PNG format with the `data:image/png;base64,` prefix is reliably accepted by the StackState backend. 
*   **Fact**: SVG format requires the `data:image/svg+xml;base64,` prefix.
*   **Fact**: Large base64 icon strings in `products.sty` must be single-line strings enclosed in double quotes. Multiline base64 strings without proper YAML folding (like `>`) can cause validation failures like `iconbase64: Must be a valid icon.`.

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
*   **Fact**: Merging multiple STY files into a single `importSnapshot` master file prevents `NamespaceSnapshotException` caused by cross-file references.

## 6. Data Flow
*   **Fact**: The SUSE AI synchronization uses a `suse-ai:` prefix for all components to ensure they remain separate from standard OTel components.
*   **Fact**: To create relations between AI components and original OTel components, the `RelationTemplateFunction` must correctly resolve target URNs, often requiring identifiers to be passed through the mapping function.

## 7. Product Component Types
*   **Fact**: Product-specific component types (e.g., inference-engine.vllm, vectordb.qdrant) are defined in `products.sty` with fields for health, type (ComponentTypeSource), and labels (TagsSource).
*   **Fact**: Metric bindings for product components are migrated from old definitions (`setup/stackpack/metrics/`) into `product-metrics.sty`. These MUST use product-scoped identifiers (e.g., `urn:stackpack:suse-ai:shared:metric-binding:vllm:e2e-latency-avg`) to avoid global URN collisions.
*   **Fact**: All STY files included in the master `suse-ai.sty` should NOT contain their own `nodes:` key. The `nodes:` key should only appear once at the root of the rendered template.
*   **Fact**: Top-level list items in included STY files MUST be indented with exactly 2 spaces (`  - _type: ...`). Failing to indent list items will break the YAML block mapping of the `nodes:` key in the parent file.
*   **Fact**: UI QueryView includes both generic `ui` type and product-specific `ui.*` types using `type STARTSWITH 'ui.'` clause.

## 8. Taskfile Commands
*   **Fact**: The `stackpack-uninstall` task in `Taskfile.yaml` uses `sts stackpack list-instances --name suse-ai -o json` and `jq` to filter instances with status 'INSTALLED' or 'ERROR', then loops to uninstall each instance with `sts stackpack uninstall --id "$ID" --name suse-ai`.
*   **Fact**: The uninstall task will uninstall all installed instances of the SUSE AI Observability stackpack, not just the first found.

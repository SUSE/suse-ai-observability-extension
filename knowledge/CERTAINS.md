# Verified Facts - GenAI Observability StackPack

## 1. Icon Validation
*   **Fact**: `ComponentType` and `ViewType` icons in STY files must be valid base64 strings.
*   **Fact**: PNG format with the `data:image/png;base64,` prefix is reliably accepted by the StackState backend. 
*   **Fact**: SVG format requires the `data:image/svg+xml;base64,` prefix.

## 2. Provisioning Constraints
*   **Fact**: `importSnapshot` using an empty node list (`nodes: []`) is NOT allowed and will result in a provisioning error.
*   **Fact**: If any node in an imported snapshot is missing a required field (based on its `_type` schema), the entire transaction is rolled back.
*   **Fact**: The `IdExtractorFunction` can use a native body `DEFAULT_ID_EXTRACTOR_FUNCTION` or a custom Groovy script.

## 3. Handlebars Path Resolution
*   **Fact**: The `include` helper resolves paths starting from the `provisioning/` folder within the ZIP.
*   **Fact**: Double prefixes (e.g., `provisioning/provisioning/...`) cause `NoSuchFileException`.

## 4. Component Schema
*   **Fact**: Modern StackState schemas for `ComponentType` require the `externalComponent` field.
*   **Fact**: `QueryView` nodes require a `queryVersion` (e.g., `"0.0.1"`) to be properly indexed in some versions.

## 6. Template & Scripting Facts
*   **Fact**: The `include` helper in STY files produces multiline base64 output which breaks YAML if used inside double quotes. Single-line base64 should be used or embedded directly.
*   **Fact**: `IdExtractorFunction` returning `null` effectively filters out components from a synchronization.
*   **Fact**: `ResolveOrCreate` helper requires specific capitalization for the second argument (e.g., `"ComponentType"`, `"RelationType"`, `"Layer"`, `"Domain"`, `"Environment"`).
*   **Fact**: Merging multiple STY files into a single `importSnapshot` master file prevents `NamespaceSnapshotException` caused by cross-file references.
*   **Fact**: The `suse-ai` synchronization uses a separate component strategy with a `suse-ai:` prefix to ensure clean ownership and avoid collisions with the standard OTel sync.
*   **Fact**: Linking SUSE AI components to original OTel components is achieved by adding the original URN to the `identifiers` list in the ID extractor and using a custom `SyncActionCreateRelation` in the component synchronization settings.



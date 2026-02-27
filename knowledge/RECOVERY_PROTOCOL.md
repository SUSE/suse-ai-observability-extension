# SUSE AI Observability - Recovery Protocol

This document tracks critical findings and recovery steps for the StackPack.

## 1. Template Paths
- **Rule**: All `include` paths in STY files are relative to the `provisioning/` directory if not using a relative prefix (`./`).
- **Discovery**: StackState's Handlebars engine automatically prepends `provisioning/` to include paths. If you use `include "templates/foo.sty"`, it looks for `provisioning/templates/foo.sty`.
- **Fixed Path Map**:
  - `templates/suse-ai.sty` -> `templates/shared.sty` (Relative to zip root / provisioning)

## 2. Namespace & Context
- **Rule**: `MainMenuGroup`, `Domain`, and `QueryView` SHOULD stay in the `shared` namespace (`urn:stackpack:suse-ai:shared:`) for global visibility.
- **Rule**: Use `context().stackPack().importSnapshot(...)` for shared objects. Using `context().instance()` can lead to `NamespaceSnapshotException` if those objects are later referenced by global nodes.

## 3. Component Identity
- **Strategy**: **suse-ai: Prefix**.
- **Reasoning**: We use a custom `IdExtractorFunction` to prefix `externalId` with `suse-ai:`. 
- **Merging**: To ensure data still links, we add the original OTel URN to the `identifiers` list in the component template.

## 4. Groovy Scripting & Handlebars Escaping
- **Rule**: When using Handlebars syntax (`{{ ... }}`) inside a Groovy script that is itself included in a template, you must escape the braces: `\{{ ... \}}`.
- **Reasoning**: If not escaped, the StackPack importer tries to resolve the variables (like `element.data`) during provisioning time, instead of leaving them for the Sync engine to resolve during data flow.

## 5. Schema Validation (Mandatory Fields)
- **Rule**: `ComponentType` highlights MUST include:
    - `events`: `_type: "ComponentTypeEvents"`
    - `metrics`: `[]` (empty list if none)
    - `relatedResources`: `[]` (empty list if none)
    - `externalComponent`: `_type: "ComponentTypeExternalComponent"`
- **Failure Symptom**: `spray.json.DeserializationException: Object is missing required member 'events'`.

## 6. Icon Prefixing
- **Rule**: Icons included via `base64` helper need the manual `data:image/...;base64,` prefix in the YAML string.
- **Example**: `iconbase64: "data:image/svg+xml;base64,{{ include "icons/foo.svg" "base64" }}"`.

## 7. YAML Syntax & Indentation
- **Rule**: All top-level items in included `.sty` files must be indented with 2 spaces to fit under the `nodes:` key of the master template.
- **Rule**: Nested properties must follow strict YAML indentation (usually +2 spaces per level).
- **Rule**: Do not include `nodes:` root in child `.sty` files.
- **Rule**: Base64 strings should be single-line double-quoted strings if they are very long, to avoid folding issues in the StackState parser.

## 8. Duplicate Identifiers & IDs
- **Rule**: All `MetricBinding` nodes must have a unique `identifier`. For product-specific metrics, use the format `urn:stackpack:suse-ai:shared:metric-binding:<product>:<metric-name>`.
- **Rule**: All nodes must have a unique negative integer `id`. Use a dedicated range for product metrics (e.g., `-500` and below) to avoid collisions with core components.

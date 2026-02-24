# Verified Facts - GenAI Observability StackPack

## 1. Icon Validation
*   **Fact**: `ComponentType` and `ViewType` icons in STY files must be valid base64 strings.
*   **Fact**: PNG format with the `data:image/png;base64,` prefix is reliably accepted by the StackState backend. SVG format often fails validation with "Must be a valid icon" if not properly formatted or prefixed.

## 2. Namespace & URN Strategy
*   **Fact**: Global UI elements (`MainMenuGroup`, `QueryView`) work best in the `shared` namespace for visibility.
*   **Fact**: During intensive development/debugging, placing `Domain` and `ComponentType` in the `instance` namespace (`urn:stackpack:suse-ai:instance:{{instanceId}}:...`) bypasses resolution and locking issues between version upgrades.

## 3. OTel Claiming Strategy
*   **Fact**: To claim standard OpenTelemetry components without breaking existing data, use a separate `Sync` that reads from the `sts_topo_opentelemetry_collector` topic.
*   **Fact**: Use a unique prefix (like `suse-ai:`) for the `externalId` in the `IdExtractorFunction` to prevent ownership conflicts with the standard OTel Sync, while keeping the original URN as a secondary identifier for merging.

## 4. Handlebars Helpers
*   **Fact**: `resolveOrCreate` is the preferred helper for linking components to types and domains.
*   **Fact**: The helper is case-sensitive (`resolveOrCreate`, NOT `resolveorcreate`).
*   **Fact**: Type names passed to the helper (e.g., `componenttype`, `domain`, `layer`) should be lowercase to match established conventions in older StackPacks, although behavior may vary by platform version.

## 5. Component Identification
*   **Fact**: Detection of GenAI components in the OTel collector topic can be done using tags (also quoted as labels) such as `suse.ai.managed: true`, `suse.ai.component.name: <name of the component>`, `suse.ai.component.type: <type of the component>`.

# SUSE AI Observability - Recovery Protocol

This document tracks critical findings and recovery steps for the StackPack.

## 1. Template Paths
- **Rule**: All `include` paths in STY files are relative to the file being parsed IF using relative syntax (`./` or `../`).
- **Discovery**: In v1.31.141-143, we discovered that StackState's Handlebars engine resolves `include` paths relative to the zip root when no prefix is used, or relative to the caller when `../` is used.
- **Fixed Path Map**:
  - `templates/genai-observability.sty` -> `./domains.sty`
  - `templates/component-types/genai-app.sty` -> `../../icons-svg/genai_app.svg`

## 2. Namespace & Context
- **Rule**: `MainMenuGroup`, `Domain`, and `QueryView` MUST stay in the `shared` namespace (`urn:stackpack:openlit:shared:`) to be visible in the global UI.
- **Rule**: `DataSource`, `Sync`, and `Monitor` MUST stay in the `instance` namespace (`urn:stackpack:openlit:instance:{{instanceId}}:`) for proper ownership.

## 3. Component Identity
- **Strategy**: **Claim OTel URN**.
- **Reasoning**: To ensure metrics and traces from the standard OTel collector "stick" to our components, we must use the same `externalId`. We override the `domain` and `type` in the Mapper.

## 4. Groovy Scripting
- **Validation**: Always use `npm-groovy-lint`.
- **String Interpolation**: Avoid `${var}` in Groovy strings if they are embedded in STY files, as Handlebars might try to resolve them first. Use `"string" + var` instead.

## 5. Handlebars & UI Resolution
- **Rule**: Use `resolveOrCreate` (camelCase) for reliable node linking.
- **Rule**: Type names inside the helper (e.g. `componenttype`) should be lowercase.
- **Rule**: If a component shows `domain: 0` or URN as name in metadata, the resolution failed. Check if the URN in the `resolveOrCreate` call matches the node's identifier EXACTLY (including namespace).
- **Rule**: Use PNG icons with `data:image/png;base64,` prefix to avoid validation errors.

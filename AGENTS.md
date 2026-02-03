# Agent Rules & Constraints - GenAI Observability StackPack

## 1. Versioning Protocol
*   **NEVER** reuse a version number. Every upload to the `sts` CLI must have an incremented version in `stackpack.conf`.
*   **Overwrite Strategy**: Always use `--unlocked-strategy overwrite` when upgrading to ensure your changes are actually applied.

## 2. Code & Documentation Integrity
*   **NO GO CODE**: The Go runtime is being replaced by Groovy scripts. Do not add or restore Go code.
*   **Preserve Docs**: Never delete or overwrite markdown files provided by the user (e.g., `CERTAINS.md`, `session.md`, `HOW_OTEL_WORKS.md`) unless explicitly updating them with new findings.
*   **Updating CERTAINS.md**: Update this file at the end of every successful loop with **verifiable** facts only.

## 3. Workflow with SUSE Observability CLI (sts)
*   **Verification First**: Before claiming success, use `sts topology-sync list` and `sts topology-sync describe` to check for errors.
*   **Topology Query**: Use `sts script run --script "Topology.query(...)"` to verify if components actually exist in the graph. Note: STQL syntax is strict (e.g., `name = 'value'`).
*   **Component Visibility**: If components are in the graph but not in the UI, check `views.sty` for filtering logic (labels and types).

## 4. Technical Constraints
*   **Identifier Prefixing**: Use a consistent prefix (like `openlit:`) if you need to separate GenAI components from standard OTel components to avoid ownership conflicts.
*   **Type Safety**: StackState Groovy APIs are strict. Convert all URNs and Names to raw Strings using `.toString()`.
*   **Template Resolution**: The `resolve` and `get` helpers in Handlebars will cause synchronization errors if the target URN does not exist. Use `resolveOrCreate` if the URN might be missing.

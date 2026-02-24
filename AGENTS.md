# Agent Rules & Constraints - GenAI Observability StackPack

## 1. Versioning Protocol
*   **NEVER** reuse a version number. Every upload to the `sts` CLI must have an incremented version in `stackpack.conf`.
*   **Overwrite Strategy**: Always use `--unlocked-strategy overwrite` when upgrading to ensure your changes are actually applied.

## 2. Code & Documentation Integrity
*   **NO GO CODE**: The Go runtime is being replaced by Groovy scripts. Do not add or restore Go code.
*   **Preserve Docs**: Never delete or overwrite markdown files provided by the user (e.g., `knowledge/CERTAINS.md`) unless explicitly updating them with new findings.
*   **Updating knowledge/CERTAINS.md**: Update this file at the end of every successful loop with **verifiable** facts only.

## 3. Workflow with SUSE Observability CLI (sts)
*   **Version Updates**: Prefer using the `Taskfile` for building and managing version updates.
*   **Verification First**: Before claiming success, use `sts topology-sync list` and `sts topology-sync describe` to check for errors.

## 4. Technical Constraints
*   **Knowledge Base**: All project knowledge (architecture, conventions, design decisions, etc.) is located in the `knowledge/` directory (excluding `AGENTS.md` and `README.md`).
*   **Consult Knowledge**: Always consult the files in `knowledge/` before interacting with or modifying the project to ensure alignment with established patterns.
*   **Identifier Prefixing**: Use a consistent prefix (like `suse-ai:`) if you need to separate GenAI components from standard OTel components to avoid ownership conflicts.

*   **Type Safety**: StackState Groovy APIs are strict. Convert all URNs and Names to raw Strings using `.toString()`.
*   **Template Resolution**: The `resolve` and `get` helpers in Handlebars will cause synchronization errors if the target URN does not exist. Use `resolveOrCreate` if the URN might be missing.

## 5. Tooling & Validation
*   **Groovy Linting**: Always use `npm-groovy-lint` before finalizing changes to Groovy scripts to ensure syntax and style compliance.
*   **Groovy LSP**: A language server is available at `~/groovy-language-server/build/libs/groovy-language-server-all.jar` for advanced development support.

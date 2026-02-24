# SUSE Observability (sts) CLI Cheatsheet

This document contains useful commands for interacting with SUSE Observability via the `sts` CLI.

## 1. Scripting (STSL / Groovy)
You can run Groovy scripts directly against the StackState API. This is extremely useful for debugging topology, checking metrics, or verifying sync logic.

*   **Run script from file**:
    ```bash
    sts script run --file "path/to/script.groovy"
    ```
*   **Run script from string**:
    ```bash
    sts script run --script "Topology.query('type = \"service\"')"
    ```
*   **With arguments**:
    ```bash
    sts script run --script "x + y" --arguments-script "[x: 1, y: 2]"
    ```

## 2. StackPack Management
*   **Upload StackPack**:
    ```bash
    sts stackpack upload --file "path/to/stackpack.sts"
    ```
*   **Upgrade Instance**:
    ```bash
    # Use --unlocked-strategy overwrite to ensure changes are applied even if files are modified
    sts stackpack upgrade --name openlit --unlocked-strategy overwrite
    ```
*   **List Instances**:
    ```bash
    sts stackpack list-instances --name openlit
    ```

## 3. Topology Synchronization
*   **List Syncs**:
    ```bash
    sts topology-sync list
    ```
*   **Describe Sync**:
    ```bash
    sts topology-sync describe --id <sync-id>
    ```
*   **Clear Sync Errors**:
    ```bash
    sts topology-sync clear-errors --id <sync-id>
    ```

## 4. Graph & Queries (STQL)
*   **Query Topology**:
    ```bash
    sts graph query --query "label = 'gen_ai_app'"
    ```

## 5. Monitors
*   **List Monitors**:
    ```bash
    sts monitor list
    ```

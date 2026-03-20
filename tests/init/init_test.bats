#!/usr/bin/env bats

# Tests for init.sh — the StackPack install/uninstall script.
#
# Strategy: source init.sh functions without executing main,
# mock the `sts` CLI, and verify behavior.

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INIT_SCRIPT="$REPO_ROOT/init.sh"

# --- Helpers ---

# Create a mock sts command that records calls and returns configurable output
setup() {
    export MOCK_DIR="$(mktemp -d)"
    export MOCK_STS="$MOCK_DIR/sts"
    export MOCK_LOG="$MOCK_DIR/calls.log"

    # Default mock: succeed with empty JSON
    cat > "$MOCK_STS" << 'MOCK'
#!/bin/bash
echo "$@" >> "${MOCK_LOG}"
# Default: return empty instances
if [[ "$*" == *"list-instances"* ]]; then
    echo '{"instances": []}'
elif [[ "$*" == *"upload"* ]] || [[ "$*" == *"install"* ]] || [[ "$*" == *"upgrade"* ]] || [[ "$*" == *"uninstall"* ]]; then
    echo "OK"
fi
exit 0
MOCK
    chmod +x "$MOCK_STS"

    # Put mock dir first in PATH so our mock sts is found
    export PATH="$MOCK_DIR:$PATH"

    # Set required env vars with test values
    export STACKSTATE_API_URL="https://test.example.com"
    export STACKSTATE_TOKEN="test-token-123"
    export STACKSTATE_TOKEN_TYPE="api"
}

teardown() {
    rm -rf "$MOCK_DIR"
}

# Source just the functions from init.sh without executing main.
# We do this by replacing the main block.
source_init_functions() {
    # Extract everything except the main block (last 5 lines)
    local temp="$MOCK_DIR/init_functions.sh"
    head -n -5 "$INIT_SCRIPT" > "$temp"
    source "$temp"
}

# Read all sts calls that were made
get_sts_calls() {
    cat "$MOCK_LOG" 2>/dev/null || echo ""
}

# --- Env Validation Tests ---

@test "init.sh fails when STACKSTATE_API_URL is not set" {
    unset STACKSTATE_API_URL
    run bash "$INIT_SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"STACKSTATE_API_URL is not set"* ]]
}

@test "init.sh fails when STACKSTATE_TOKEN is not set" {
    unset STACKSTATE_TOKEN
    run bash "$INIT_SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"STACKSTATE_TOKEN is not set"* ]]
}

@test "init.sh fails when STACKSTATE_TOKEN_TYPE is not set" {
    unset STACKSTATE_TOKEN_TYPE
    run bash "$INIT_SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"STACKSTATE_TOKEN_TYPE is not set"* ]]
}

@test "init.sh fails when KUBERNETES_CLUSTERS is not set during install" {
    run bash "$INIT_SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"KUBERNETES_CLUSTERS is not set"* ]]
}

@test "init.sh warns and defaults invalid STACKSTATE_TOKEN_TYPE" {
    export STACKSTATE_TOKEN_TYPE="invalid"
    export KUBERNETES_CLUSTERS="test-cluster"
    run bash "$INIT_SCRIPT"
    [[ "$output" == *"defaulting to 'api'"* ]]
}

# --- Install Flow Tests ---

@test "install calls sts with correct auth flags for api token" {
    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    # Should use --api-token flag
    [[ "$calls" == *"--api-token test-token-123"* ]]
    [[ "$calls" == *"--url https://test.example.com"* ]]
}

@test "install calls sts with correct auth flags for service token" {
    export STACKSTATE_TOKEN_TYPE="service"
    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"--service-token test-token-123"* ]]
}

@test "install uses --skip-ssl when STS_SKIP_SSL is true" {
    export STS_SKIP_SSL="true"
    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"--skip-ssl"* ]]
}

@test "install installs kubernetes-v2 for each cluster" {
    export KUBERNETES_CLUSTERS="cluster-a,cluster-b"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"install --name kubernetes-v2"*"kubernetes_cluster_name=cluster-a"* ]]
    [[ "$calls" == *"install --name kubernetes-v2"*"kubernetes_cluster_name=cluster-b"* ]]
}

@test "install installs open-telemetry stackpack" {
    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"install --name open-telemetry"* ]]
}

@test "install uploads suse-ai stackpack" {
    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"upload --file"* ]]
}

@test "install installs suse-ai when no instance exists" {
    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"install --name suse-ai"* ]]
}

@test "install upgrades suse-ai when instance already installed" {
    # Mock sts to return an installed instance for suse-ai
    cat > "$MOCK_STS" << 'MOCK'
#!/bin/bash
echo "$@" >> "${MOCK_LOG}"
if [[ "$*" == *"list-instances"*"suse-ai"* ]]; then
    echo '{"instances": [{"id": "1", "status": "INSTALLED", "config": {}}]}'
elif [[ "$*" == *"list-instances"* ]]; then
    echo '{"instances": []}'
else
    echo "OK"
fi
exit 0
MOCK
    chmod +x "$MOCK_STS"

    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"upgrade --name suse-ai --unlocked-strategy overwrite"* ]]
}

@test "install skips kubernetes-v2 when already installed for cluster" {
    cat > "$MOCK_STS" << 'MOCK'
#!/bin/bash
echo "$@" >> "${MOCK_LOG}"
if [[ "$*" == *"list-instances"*"kubernetes-v2"* ]]; then
    echo '{"instances": [{"id": "1", "status": "INSTALLED", "config": {"kubernetes_cluster_name": "my-cluster"}}]}'
elif [[ "$*" == *"list-instances"* ]]; then
    echo '{"instances": []}'
else
    echo "OK"
fi
exit 0
MOCK
    chmod +x "$MOCK_STS"

    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    [[ "$output" == *"kubernetes-v2 already installed for cluster"* ]]
}

# --- Uninstall Flow Tests ---

@test "uninstall removes instances with INSTALLED status" {
    cat > "$MOCK_STS" << 'MOCK'
#!/bin/bash
echo "$@" >> "${MOCK_LOG}"
if [[ "$*" == *"list-instances"*"suse-ai"* ]]; then
    echo '{"instances": [{"id": "42", "status": "INSTALLED"}]}'
else
    echo "OK"
fi
exit 0
MOCK
    chmod +x "$MOCK_STS"

    export UNINSTALL="true"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"uninstall --id 42 --name suse-ai"* ]]
}

@test "uninstall removes instances with ERROR status" {
    cat > "$MOCK_STS" << 'MOCK'
#!/bin/bash
echo "$@" >> "${MOCK_LOG}"
if [[ "$*" == *"list-instances"*"suse-ai"* ]]; then
    echo '{"instances": [{"id": "99", "status": "ERROR"}]}'
else
    echo "OK"
fi
exit 0
MOCK
    chmod +x "$MOCK_STS"

    export UNINSTALL="true"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"uninstall --id 99 --name suse-ai"* ]]
}

@test "uninstall handles no instances gracefully" {
    export UNINSTALL="true"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    [[ "$output" == *"No suse-ai stackpack instances to uninstall"* ]]
}

# --- Script Structure Tests ---

@test "init.sh is valid bash" {
    run bash -n "$INIT_SCRIPT"
    [ "$status" -eq 0 ]
}

@test "init.sh uses set -e" {
    head -5 "$INIT_SCRIPT" | grep -q "set -e"
}

#!/usr/bin/env bats

# Tests for init.sh — the StackPack install/uninstall script.
#
# Strategy: mock the `sts` CLI via PATH override, run init.sh,
# and verify the correct sts commands were issued.

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INIT_SCRIPT="$REPO_ROOT/init.sh"

setup() {
    export MOCK_DIR="$(mktemp -d)"
    export MOCK_STS="$MOCK_DIR/sts"
    export MOCK_LOG="$MOCK_DIR/calls.log"

    cat > "$MOCK_STS" << 'MOCK'
#!/bin/bash
echo "$@" >> "${MOCK_LOG}"
if [[ "$*" == *"list-instances"* ]]; then
    echo '{"instances": []}'
else
    echo "OK"
fi
exit 0
MOCK
    chmod +x "$MOCK_STS"
    export PATH="$MOCK_DIR:$PATH"

    export STACKSTATE_API_URL="https://test.example.com"
    export STACKSTATE_TOKEN="test-token-123"
    export STACKSTATE_TOKEN_TYPE="api"
}

teardown() {
    rm -rf "$MOCK_DIR"
}

get_sts_calls() {
    cat "$MOCK_LOG" 2>/dev/null || echo ""
}

# --- Env Validation ---

@test "fails when STACKSTATE_API_URL is not set" {
    unset STACKSTATE_API_URL
    run bash "$INIT_SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"STACKSTATE_API_URL is not set"* ]]
}

@test "fails when STACKSTATE_TOKEN is not set" {
    unset STACKSTATE_TOKEN
    run bash "$INIT_SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"STACKSTATE_TOKEN is not set"* ]]
}

@test "fails when KUBERNETES_CLUSTERS is not set during install" {
    run bash "$INIT_SCRIPT"
    [ "$status" -ne 0 ]
    [[ "$output" == *"KUBERNETES_CLUSTERS is not set"* ]]
}

# --- Install Flow ---

@test "install uses --api-token flag for api token type" {
    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"--api-token test-token-123"* ]]
    [[ "$calls" == *"--url https://test.example.com"* ]]
}

@test "install uses --service-token flag for service token type" {
    export STACKSTATE_TOKEN_TYPE="service"
    export KUBERNETES_CLUSTERS="my-cluster"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"--service-token test-token-123"* ]]
}

@test "install installs kubernetes-v2 for each cluster" {
    export KUBERNETES_CLUSTERS="cluster-a,cluster-b"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    calls=$(get_sts_calls)
    [[ "$calls" == *"install --name kubernetes-v2"*"kubernetes_cluster_name=cluster-a"* ]]
    [[ "$calls" == *"install --name kubernetes-v2"*"kubernetes_cluster_name=cluster-b"* ]]
}

@test "install upgrades suse-ai when instance already installed" {
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

# --- Uninstall Flow ---

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

@test "uninstall handles no instances gracefully" {
    export UNINSTALL="true"
    run bash "$INIT_SCRIPT"
    [ "$status" -eq 0 ]

    [[ "$output" == *"No suse-ai stackpack instances to uninstall"* ]]
}

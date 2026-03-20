#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# SUSE Observability Test Environment Setup
#
# Provisions a local K3d cluster and deploys SUSE Observability via Helm
# for integration testing.
#
# Usage:
#   ./setup.sh up       Create cluster and deploy StackState
#   ./setup.sh down     Tear down cluster
#   ./setup.sh status   Check if the environment is running
#   ./setup.sh env      Print environment variables for tests
#
# Required environment variables (for 'up'):
#   SUSE_OBSERVABILITY_LICENSE    - SUSE Observability license key
#   APPCO_EMAIL                   - Application Collection email
#   APPCO_TOKEN                   - Application Collection access token
#
# Optional:
#   K3D_CLUSTER_NAME              - Cluster name (default: suse-obs-test)
#   SUSE_OBS_CHART_VERSION        - Helm chart version (default: 2.6.3)
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults
K3D_CLUSTER_NAME="${K3D_CLUSTER_NAME:-suse-obs-test}"
NAMESPACE="suse-observability"
CHART_VERSION="${SUSE_OBS_CHART_VERSION:-2.6.3}"
HELM_REPO_URL="https://charts.rancher.com/server-charts/prime/suse-observability"
HELM_REPO_NAME="suse-observability"
BOOTSTRAP_TOKEN="suseobservability"
API_KEY=""
ADMIN_PASSWORD=""
KUBECONFIG_PATH="${SCRIPT_DIR}/.kubeconfig"

log()  { echo "[INFO]  $*"; }
warn() { echo "[WARN]  $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

# --- Prerequisite checks ---

check_prerequisites() {
    local missing=()
    for cmd in k3d kubectl helm jq curl; do
        command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        fail "Missing required tools: ${missing[*]}"
    fi
}

# --- Cluster lifecycle ---

create_cluster() {
    if k3d cluster list 2>/dev/null | grep -q "$K3D_CLUSTER_NAME"; then
        log "K3d cluster '$K3D_CLUSTER_NAME' already exists"
        return
    fi

    log "Creating K3d cluster '$K3D_CLUSTER_NAME'..."
    k3d cluster create "$K3D_CLUSTER_NAME" \
        --api-port 6550 \
        --agents 1 \
        --k3s-arg "--disable=traefik@server:0" \
        --wait

    k3d kubeconfig get "$K3D_CLUSTER_NAME" > "$KUBECONFIG_PATH"
    export KUBECONFIG="$KUBECONFIG_PATH"
    log "Cluster created. Kubeconfig at $KUBECONFIG_PATH"
}

delete_cluster() {
    if k3d cluster list 2>/dev/null | grep -q "$K3D_CLUSTER_NAME"; then
        log "Deleting K3d cluster '$K3D_CLUSTER_NAME'..."
        k3d cluster delete "$K3D_CLUSTER_NAME"
        rm -f "$KUBECONFIG_PATH"
        log "Cluster deleted."
    else
        log "No cluster '$K3D_CLUSTER_NAME' found."
    fi
}

# --- Helm deployment ---

deploy_stackstate() {
    [[ -n "${SUSE_OBSERVABILITY_LICENSE:-}" ]] || fail "SUSE_OBSERVABILITY_LICENSE is not set"
    [[ -n "${APPCO_EMAIL:-}" ]] || fail "APPCO_EMAIL is not set"
    [[ -n "${APPCO_TOKEN:-}" ]] || fail "APPCO_TOKEN is not set"

    log "Adding Helm repo..."
    helm repo add "$HELM_REPO_NAME" "$HELM_REPO_URL" 2>/dev/null || true
    helm repo update "$HELM_REPO_NAME"

    log "Creating namespace..."
    kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    log "Creating registry secret..."
    kubectl create secret docker-registry application-collection \
        --namespace "$NAMESPACE" \
        --docker-server=dp.apps.rancher.io \
        --docker-username="$APPCO_EMAIL" \
        --docker-password="$APPCO_TOKEN" \
        --dry-run=client -o yaml | kubectl apply -f -

    # Note: We create the secret directly in K8s rather than using the chart's
    # pull-secret subchart or global.imagePullSecrets, because the elasticsearch
    # exporter subchart has an incompatible imagePullSecrets helper that expects
    # plain strings, not {name: ...} objects.

    # Step 1: Use helm template to generate baseConfig with auto-generated
    # credentials (apiKey, adminPassword). This is how the suse-ai-stack
    # Ansible playbook does it — the chart generates these internally.
    local values_dir="$SCRIPT_DIR/.helm-values"
    mkdir -p "$values_dir"

    log "Generating base configuration via helm template..."
    helm template suse-observability-values \
        "$HELM_REPO_NAME/suse-observability-values" \
        --namespace "$NAMESPACE" \
        --set "license=$SUSE_OBSERVABILITY_LICENSE" \
        --set "baseUrl=http://localhost:8080" \
        --set "sizing.profile=trial" \
        --output-dir "$values_dir"

    # The values chart outputs several values files with generated secrets
    local templates_dir="$values_dir/suse-observability-values/templates"
    local base_config="$templates_dir/baseConfig_values.yaml"
    local sizing_config="$templates_dir/sizing_values.yaml"
    local affinity_config="$templates_dir/affinity_values.yaml"

    if [[ ! -f "$base_config" ]]; then
        fail "helm template did not generate baseConfig_values.yaml"
    fi

    # Remove YAML document separators and source comments from all generated files
    for f in "$templates_dir"/*.yaml; do
        sed -i '/^---$/d; /^# Source:/d' "$f"
    done

    # Extract generated credentials for later use
    ADMIN_PASSWORD=$(tail -n 1 "$base_config" | awk '{print $NF}')
    API_KEY=$(grep -A2 "apiKey:" "$base_config" | awk '/key:/ {print $2}' | tr -d '"')

    # Create overrides values file.
    # Note: adminPassword is already set as a bcrypt hash in baseConfig_values.yaml
    # — do NOT override it here or the plaintext gets double-hashed.
    cat > "$values_dir/overrides.yaml" <<AUTHEOF
global:
  storageClass: local-path
stackstate:
  authentication:
    serviceToken:
      bootstrap:
        token: "$BOOTSTRAP_TOKEN"
        roles:
          - stackstate-admin
AUTHEOF

    # Step 2: Install using all generated values files (mirrors the Ansible playbook)
    log "Deploying SUSE Observability (chart version $CHART_VERSION, trial profile)..."

    local values_args=()
    [[ -f "$affinity_config" ]] && values_args+=(--values "$affinity_config")
    values_args+=(--values "$base_config")
    [[ -f "$sizing_config" ]] && values_args+=(--values "$sizing_config")
    values_args+=(--values "$values_dir/overrides.yaml")

    helm upgrade --install suse-observability \
        "$HELM_REPO_NAME/suse-observability" \
        --namespace "$NAMESPACE" \
        --version "$CHART_VERSION" \
        "${values_args[@]}" \
        --wait \
        --timeout 15m

    log "Admin password: $ADMIN_PASSWORD"
    log "API key: $API_KEY"
    log "Bootstrap token: $BOOTSTRAP_TOKEN"

    # Save credentials for test use
    echo "$ADMIN_PASSWORD" > "$SCRIPT_DIR/.admin-password"
    echo "$API_KEY" > "$SCRIPT_DIR/.api-key"
}

# --- Wait for readiness ---

wait_for_ready() {
    log "Waiting for StackState to be ready..."

    local components=(
        "suse-observability-correlate"
        "suse-observability-receiver"
        "suse-observability-router"
        "suse-observability-ui"
    )

    for component in "${components[@]}"; do
        log "  Waiting for $component..."
        kubectl rollout status deployment/"$component" \
            --namespace "$NAMESPACE" \
            --timeout=300s 2>/dev/null || \
        kubectl rollout status statefulset/"$component" \
            --namespace "$NAMESPACE" \
            --timeout=300s 2>/dev/null || \
            warn "  $component not found as deployment or statefulset"
    done

    # Start port-forward for local access
    log "Starting port-forward (router:8080 -> localhost:8080)..."
    kubectl port-forward -n "$NAMESPACE" svc/suse-observability-router 8080:8080 \
        > /dev/null 2>&1 &
    local pf_pid=$!
    echo "$pf_pid" > "$SCRIPT_DIR/.port-forward.pid"
    sleep 2

    # Wait for the API to respond through port-forward
    log "Waiting for API to respond..."
    local attempts=0
    local max_attempts=60
    while [[ $attempts -lt $max_attempts ]]; do
        if curl -sf http://localhost:8080/api/server/info >/dev/null 2>&1; then
            log "StackState API is responding at http://localhost:8080"
            return
        fi
        attempts=$((attempts + 1))
        sleep 5
    done
    fail "StackState API did not become ready within $((max_attempts * 5))s"
}

# --- Environment output ---

print_env() {
    local api_key
    if [[ -f "$SCRIPT_DIR/.api-key" ]]; then
        api_key=$(cat "$SCRIPT_DIR/.api-key")
    else
        api_key="<run setup.sh up first>"
    fi

    cat <<EOF
# Add these to your shell or .env file:
export STACKSTATE_API_URL=http://localhost:8080
export STACKSTATE_API_TOKEN=$BOOTSTRAP_TOKEN
export STACKSTATE_TOKEN_TYPE=service-token
export STACKSTATE_SKIP_TLS=true
export STACKSTATE_API_KEY=$api_key
export OTEL_ENDPOINT=http://localhost:4317
export KUBECONFIG=$KUBECONFIG_PATH
EOF
}

print_status() {
    if k3d cluster list 2>/dev/null | grep -q "$K3D_CLUSTER_NAME"; then
        echo "Cluster: running"
        export KUBECONFIG="$KUBECONFIG_PATH"
        kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | \
            awk '{printf "  %-55s %s\n", $1, $3}'
    else
        echo "Cluster: not running"
    fi
}

# --- Main ---

case "${1:-help}" in
    up)
        check_prerequisites
        create_cluster
        deploy_stackstate
        wait_for_ready
        echo ""
        log "Environment is ready."
        print_env
        ;;
    down)
        # Kill port-forward if running
        if [[ -f "$SCRIPT_DIR/.port-forward.pid" ]]; then
            kill "$(cat "$SCRIPT_DIR/.port-forward.pid")" 2>/dev/null || true
            rm -f "$SCRIPT_DIR/.port-forward.pid"
        fi
        delete_cluster
        rm -f "$SCRIPT_DIR/.admin-password" "$SCRIPT_DIR/.api-key"
        rm -rf "$SCRIPT_DIR/.helm-values"
        ;;
    status)
        print_status
        ;;
    env)
        print_env
        ;;
    *)
        echo "Usage: $0 {up|down|status|env}"
        echo ""
        echo "  up      Create K3d cluster and deploy SUSE Observability"
        echo "  down    Tear down cluster and clean up"
        echo "  status  Show cluster and pod status"
        echo "  env     Print environment variables for integration tests"
        echo ""
        echo "Required env vars for 'up':"
        echo "  SUSE_OBSERVABILITY_LICENSE  - License key"
        echo "  APPCO_EMAIL                 - Application Collection email"
        echo "  APPCO_TOKEN                 - Application Collection access token"
        exit 1
        ;;
esac

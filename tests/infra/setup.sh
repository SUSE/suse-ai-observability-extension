#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEMO_APPS_DIR="$(cd "$REPO_ROOT/.." && pwd)/suse-ai-demo-apps"

K3D_CLUSTER_NAME="${K3D_CLUSTER_NAME:-suse-obs-test}"
NAMESPACE="suse-observability"
AI_NAMESPACE="suse-private-ai"
CHART_VERSION="${SUSE_OBS_CHART_VERSION:-2.6.3}"
HELM_REPO_URL="https://charts.rancher.com/server-charts/prime/suse-observability"
HELM_REPO_NAME="suse-observability"
BOOTSTRAP_TOKEN="suseobservability"
API_KEY=""
ADMIN_PASSWORD=""
KUBECONFIG_PATH="${SCRIPT_DIR}/.kubeconfig"

DEPLOY_QDRANT="${DEPLOY_QDRANT:-true}"
DEPLOY_OLLAMA="${DEPLOY_OLLAMA:-true}"
DEPLOY_DEMO_APPS="${DEPLOY_DEMO_APPS:-true}"
DEPLOY_MILVUS="${DEPLOY_MILVUS:-false}"
DEPLOY_OPENSEARCH="${DEPLOY_OPENSEARCH:-false}"
DEPLOY_VLLM="${DEPLOY_VLLM:-false}"

OTEL_COLLECTOR_IMAGE="${OTEL_COLLECTOR_IMAGE:-otel/opentelemetry-collector-contrib:0.147.0}"

log()  { echo "[INFO]  $*"; }
warn() { echo "[WARN]  $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

check_prerequisites() {
    local missing=()
    for cmd in k3d kubectl helm jq curl; do
        command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        fail "Missing required tools: ${missing[*]}"
    fi
}

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

    local templates_dir="$values_dir/suse-observability-values/templates"
    local base_config="$templates_dir/baseConfig_values.yaml"
    local sizing_config="$templates_dir/sizing_values.yaml"
    local affinity_config="$templates_dir/affinity_values.yaml"

    if [[ ! -f "$base_config" ]]; then
        fail "helm template did not generate baseConfig_values.yaml"
    fi

    for f in "$templates_dir"/*.yaml; do
        sed -i '/^---$/d; /^# Source:/d' "$f"
    done

    ADMIN_PASSWORD=$(tail -n 1 "$base_config" | awk '{print $NF}')
    API_KEY=$(grep -A2 "apiKey:" "$base_config" | awk '/key:/ {print $2}' | tr -d '"')

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

    echo "$ADMIN_PASSWORD" > "$SCRIPT_DIR/.admin-password"
    echo "$API_KEY" > "$SCRIPT_DIR/.api-key"
}

deploy_otel_collector() {
    log "Creating AI namespace '$AI_NAMESPACE'..."
    kubectl create namespace "$AI_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

    kubectl create secret generic otel-collector-env \
        --namespace "$AI_NAMESPACE" \
        --from-literal="API_KEY=$API_KEY" \
        --dry-run=client -o yaml | kubectl apply -f -

    log "Adding OpenTelemetry Helm repo..."
    helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts 2>/dev/null || true
    helm repo update open-telemetry

    local otel_image_repo="${OTEL_COLLECTOR_IMAGE%:*}"
    local otel_image_tag="${OTEL_COLLECTOR_IMAGE##*:}"

    log "Deploying OTel Collector (image: $OTEL_COLLECTOR_IMAGE)..."
    helm upgrade --install otel-collector \
        open-telemetry/opentelemetry-collector \
        --namespace "$AI_NAMESPACE" \
        --values "$SCRIPT_DIR/otel-values.yaml" \
        --set "image.repository=$otel_image_repo" \
        --set "image.tag=$otel_image_tag" \
        --wait \
        --timeout 5m

    log "OTel Collector deployed."
}

deploy_component() {
    local name="$1"
    local manifest="$SCRIPT_DIR/components/${name}.yaml"

    if [[ ! -f "$manifest" ]]; then
        warn "Manifest not found: $manifest"
        return 1
    fi

    log "Deploying $name..."
    kubectl apply -f "$manifest"

    kubectl rollout status deployment/"$name" \
        --namespace "$AI_NAMESPACE" \
        --timeout=120s 2>/dev/null || \
        warn "$name deployment not ready within timeout"
}

deploy_ai_components() {
    if [[ "$DEPLOY_QDRANT" == "true" ]]; then
        deploy_component "qdrant"
    fi

    if [[ "$DEPLOY_OLLAMA" == "true" ]]; then
        deploy_component "ollama"
    fi

    if [[ "$DEPLOY_MILVUS" == "true" ]]; then
        deploy_component "milvus"
    fi

    if [[ "$DEPLOY_OPENSEARCH" == "true" ]]; then
        deploy_component "opensearch"
    fi

    if [[ "$DEPLOY_VLLM" == "true" ]]; then
        deploy_component "vllm"
    fi
}

deploy_demo_apps() {
    if [[ ! -d "$DEMO_APPS_DIR/helm/suse-ai-demo" ]]; then
        warn "Demo apps Helm chart not found at $DEMO_APPS_DIR/helm/suse-ai-demo"
        warn "Clone suse-ai-demo-apps alongside this repository to enable demo apps."
        return 1
    fi

    if [[ "$DEPLOY_QDRANT" != "true" ]]; then
        warn "Demo apps require QDrant — enabling DEPLOY_QDRANT"
        DEPLOY_QDRANT="true"
        deploy_component "qdrant"
    fi
    if [[ "$DEPLOY_OLLAMA" != "true" ]]; then
        warn "Demo apps require Ollama — enabling DEPLOY_OLLAMA"
        DEPLOY_OLLAMA="true"
        deploy_component "ollama"
    fi

    local demo_values="$SCRIPT_DIR/demo-apps/values.yaml"

    local set_args=()
    if [[ "$DEPLOY_VLLM" != "true" ]]; then
        set_args+=(--set "llmService.replicas=0")
    fi

    log "Deploying demo apps..."
    helm upgrade --install suse-ai-demo \
        "$DEMO_APPS_DIR/helm/suse-ai-demo" \
        --namespace "$AI_NAMESPACE" \
        --values "$demo_values" \
        "${set_args[@]}" \
        --wait \
        --timeout 5m

    log "Demo apps deployed."
}

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

    log "Starting port-forward (router:8080 -> localhost:8080)..."
    kubectl port-forward -n "$NAMESPACE" svc/suse-observability-router 8080:8080 \
        > /dev/null 2>&1 &
    local pf_pid=$!
    echo "$pf_pid" > "$SCRIPT_DIR/.port-forward.pid"
    sleep 2

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

print_env() {
    local api_key
    if [[ -f "$SCRIPT_DIR/.api-key" ]]; then
        api_key=$(cat "$SCRIPT_DIR/.api-key")
    else
        api_key="<run setup.sh up first>"
    fi

    cat <<EOF
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

        echo ""
        echo "SUSE Observability ($NAMESPACE):"
        kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | \
            awk '{printf "  %-55s %s\n", $1, $3}'

        echo ""
        echo "AI Components ($AI_NAMESPACE):"
        kubectl get pods -n "$AI_NAMESPACE" --no-headers 2>/dev/null | \
            awk '{printf "  %-55s %s\n", $1, $3}'
    else
        echo "Cluster: not running"
    fi
}

case "${1:-help}" in
    up)
        check_prerequisites
        create_cluster
        deploy_stackstate
        wait_for_ready
        deploy_otel_collector
        deploy_ai_components
        if [[ "$DEPLOY_DEMO_APPS" == "true" ]]; then
            deploy_demo_apps
        fi
        echo ""
        log "Environment is ready."
        print_env
        ;;
    down)
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
        echo "  up      Create K3d cluster and deploy full stack"
        echo "  down    Tear down cluster and clean up"
        echo "  status  Show cluster and pod status"
        echo "  env     Print environment variables for integration tests"
        echo ""
        echo "Required env vars for 'up':"
        echo "  SUSE_OBSERVABILITY_LICENSE  - License key"
        echo "  APPCO_EMAIL                 - Application Collection email"
        echo "  APPCO_TOKEN                 - Application Collection access token"
        echo ""
        echo "Component control (defaults):"
        echo "  DEPLOY_QDRANT=true          - QDrant vector database"
        echo "  DEPLOY_OLLAMA=true          - Ollama inference engine (CPU)"
        echo "  DEPLOY_DEMO_APPS=true       - Demo RAG pipeline apps"
        echo ""
        echo "Component control (opt-in):"
        echo "  DEPLOY_MILVUS=false         - Milvus vector database"
        echo "  DEPLOY_OPENSEARCH=false     - OpenSearch"
        echo "  DEPLOY_VLLM=false           - vLLM inference engine (CPU)"
        echo ""
        echo "OTel Collector:"
        echo "  OTEL_COLLECTOR_IMAGE=otel/opentelemetry-collector-contrib:0.147.0"
        exit 1
        ;;
esac

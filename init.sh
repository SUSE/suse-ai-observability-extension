#!/bin/bash
set -e

log() { echo "[INFO]  $*"; }
warn() { echo "[WARN]  $*"; }
fail() {
  echo "[ERROR] $*"
  exit 1
}

# --- Validate environment ---

REQUIRED_VARS=(STACKSTATE_API_URL STACKSTATE_TOKEN STACKSTATE_TOKEN_TYPE)
for var in "${REQUIRED_VARS[@]}"; do
  [[ -n "${!var}" ]] || fail "$var is not set"
done

if [[ "$STACKSTATE_TOKEN_TYPE" != "service" && "$STACKSTATE_TOKEN_TYPE" != "api" ]]; then
  warn "STACKSTATE_TOKEN_TYPE must be 'service' or 'api'; defaulting to 'api'"
  STACKSTATE_TOKEN_TYPE="api"
fi

# --- Build the sts base command with auth and TLS flags ---

STS_CMD=(sts --url "$STACKSTATE_API_URL" --"${STACKSTATE_TOKEN_TYPE}-token" "$STACKSTATE_TOKEN")

if [[ "${STS_SKIP_SSL:-}" == "true" ]]; then
  STS_CMD+=(--skip-ssl)
elif [[ -n "${STS_CA_CERT_PATH:-}" && -f "$STS_CA_CERT_PATH" ]]; then
  STS_CMD+=(--ca-cert-path "$STS_CA_CERT_PATH")
fi

run_sts() { "${STS_CMD[@]}" "$@"; }

# --- Helpers ---

stackpack_has_instance() {
  local name="$1" jq_filter="$2"
  run_sts stackpack list-instances --name "$name" -o json | jq -e "$jq_filter" >/dev/null 2>&1
}

ensure_stackpack() {
  local name="$1"
  shift
  local params=("$@")

  if stackpack_has_instance "$name" '.instances | length > 0'; then
    log "$name stackpack already installed"
    return
  fi

  log "Installing $name stackpack..."
  run_sts stackpack install --name "$name" "${params[@]}" ||
    fail "Could not install $name stackpack"
  log "$name stackpack installed"
}

# --- Uninstall ---

uninstall() {
  log "Starting suse-ai uninstall..."

  local ids
  ids=$(run_sts stackpack list-instances --name suse-ai -o json |
    jq -r '.instances[] | select(.status == "INSTALLED" or .status == "ERROR") | .id')

  if [[ -z "$ids" ]]; then
    log "No suse-ai stackpack instances to uninstall"
    return
  fi

  while IFS= read -r id; do
    log "Uninstalling suse-ai instance $id..."
    run_sts stackpack uninstall --id "$id" --name suse-ai ||
      fail "Could not uninstall suse-ai instance $id"
    log "suse-ai instance $id uninstalled"
  done <<<"$ids"

  log "Uninstall completed successfully."
}

# --- Install ---

install() {
  [[ -n "${KUBERNETES_CLUSTERS:-}" ]] || fail "KUBERNETES_CLUSTERS is not set"

  IFS=',' read -ra CLUSTERS <<<"$KUBERNETES_CLUSTERS"
  [[ ${#CLUSTERS[@]} -gt 0 ]] || fail "KUBERNETES_CLUSTERS is empty"

  log "Starting SUSE AI Observability install..."
  log "Clusters: ${CLUSTERS[*]}"

  # Step 1: kubernetes-v2 stackpack for each cluster
  for cluster in "${CLUSTERS[@]}"; do
    cluster="${cluster#"${cluster%%[![:space:]]*}"}"
    cluster="${cluster%"${cluster##*[![:space:]]}"}"
    local filter=".instances | any(.config.kubernetes_cluster_name == \"$cluster\")"

    if stackpack_has_instance kubernetes-v2 "$filter"; then
      log "kubernetes-v2 already installed for cluster '$cluster'"
    else
      log "Installing kubernetes-v2 for cluster '$cluster'..."
      run_sts stackpack install --name kubernetes-v2 -p kubernetes_cluster_name="$cluster" ||
        fail "Could not install kubernetes-v2 for cluster '$cluster'"
      log "kubernetes-v2 installed for cluster '$cluster'"
    fi
  done

  # Step 2: OpenTelemetry stackpack
  ensure_stackpack open-telemetry

  # Step 3: Upload and install/upgrade suse-ai stackpack
  log "Uploading suse-ai stackpack..."
  if run_sts stackpack upload --file /mnt/suse-ai.sts; then
    log "suse-ai stackpack uploaded"
  else
    warn "Could not upload suse-ai stackpack; assuming it already exists"
  fi

  if stackpack_has_instance suse-ai '.instances | any(.status == "INSTALLED")'; then
    log "Upgrading suse-ai stackpack..."
    run_sts stackpack upgrade --name suse-ai --unlocked-strategy overwrite ||
      fail "Could not upgrade suse-ai stackpack"
    log "suse-ai stackpack upgraded"
  else
    log "Installing suse-ai stackpack..."
    run_sts stackpack install --name suse-ai ||
      fail "Could not install suse-ai stackpack"
    log "suse-ai stackpack installed"
  fi

  log "Installation completed successfully."
}

# --- Cleanup legacy (v1.5.0 and below) ---

cleanup_legacy() {
  log "Starting legacy cleanup (v1.5.0 resources)..."

  # 1. Remove the "GenAI Observability" main menu group
  local menu_id
  menu_id=$(run_sts settings list --type MainMenuGroup -o json |
    jq -r '.settings[] | select(.name == "GenAI Observability") | .id')

  if [[ -z "$menu_id" ]]; then
    log "No legacy GenAI Observability menu found"
  else
    log "Removing legacy GenAI Observability menu (id=$menu_id)..."
    run_sts settings delete --ids "$menu_id" ||
      fail "Could not delete legacy menu $menu_id"
    log "Legacy menu removed"
  fi

  # 2. Uninstall autosync stackpack instances matching cluster names
  if [[ -z "${KUBERNETES_CLUSTERS:-}" ]]; then
    warn "KUBERNETES_CLUSTERS not set, skipping autosync cleanup"
    log "Legacy cleanup completed (menu only)."
    return
  fi

  IFS=',' read -ra CLUSTERS <<<"$KUBERNETES_CLUSTERS"

  for cluster in "${CLUSTERS[@]}"; do
    cluster="${cluster#"${cluster%%[![:space:]]*}"}"
    cluster="${cluster%"${cluster##*[![:space:]]}"}"
    local instance_id
    instance_id=$(run_sts stackpack list-instances --name autosync -o json |
      jq -r --arg url "$cluster" \
        '.instances | map(select(.config.sts_instance_url == $url and (.status == "INSTALLED" or .status == "ERROR" or .status == "WAITING_FOR_DATA")))[0].id // empty')

    if [[ -z "$instance_id" ]]; then
      log "No legacy autosync instance for cluster '$cluster'"
    else
      log "Uninstalling legacy autosync instance $instance_id (cluster='$cluster')..."
      run_sts stackpack uninstall --id "$instance_id" --name autosync ||
        fail "Could not uninstall legacy autosync instance $instance_id"
      log "Legacy autosync instance $instance_id uninstalled"
    fi
  done

  log "Legacy cleanup completed successfully."
}

# --- Main ---

if [[ "${CLEANUP_LEGACY:-}" == "true" ]]; then
  cleanup_legacy
elif [[ "${UNINSTALL:-}" == "true" ]]; then
  uninstall
else
  install
fi

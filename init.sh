#!/usr/bin/env bash
set -euo pipefail

log() { echo "[INFO]  $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

STS_CMD=("${STS_BIN:-sts}")
if [[ -n "${STS_CONTEXT:-}" ]]; then
  STS_CMD+=(--context "$STS_CONTEXT")
else
  for var in STACKSTATE_API_URL STACKSTATE_TOKEN STACKSTATE_TOKEN_TYPE; do
    [[ -n "${!var:-}" ]] || fail "$var is not set"
  done
  [[ "$STACKSTATE_TOKEN_TYPE" == service || "$STACKSTATE_TOKEN_TYPE" == api ]] ||
    fail "STACKSTATE_TOKEN_TYPE must be service or api"
  STS_CMD+=(--url "$STACKSTATE_API_URL" "--${STACKSTATE_TOKEN_TYPE}-token" "$STACKSTATE_TOKEN")
fi
if [[ "${STS_SKIP_SSL:-}" == true ]]; then
  STS_CMD+=(--skip-ssl)
elif [[ -n "${STS_CA_CERT_PATH:-}" ]]; then
  [[ -f "$STS_CA_CERT_PATH" ]] || fail "STS_CA_CERT_PATH does not exist"
  STS_CMD+=(--ca-cert-path "$STS_CA_CERT_PATH")
fi
WAIT_SECONDS=${STS_WAIT_SECONDS:-300}
[[ "$WAIT_SECONDS" =~ ^[1-9][0-9]*$ ]] || fail 'STS_WAIT_SECONDS must be a positive integer'
run_sts() { "${STS_CMD[@]}" "$@"; }

read_instances() {
  instances=$(run_sts stackpack list-instances --name "$1" -o json) || fail "Cannot read $1 instances"
  jq -e '.instances | type == "array"' <<<"$instances" >/dev/null || fail 'Invalid instance response'
}

read_catalog() {
  catalog=$(run_sts stackpack list -o json) || fail 'Cannot read StackPack catalog'
  jq -e '.stackpacks | type == "array"' <<<"$catalog" >/dev/null || fail 'Invalid catalog response'
}

wait_removed() {
  local name=$1 deadline=$((SECONDS + WAIT_SECONDS))
  while true; do
    read_instances "$name"
    [[ $(jq '.instances | length' <<<"$instances") == 0 ]] && return
    (( SECONDS < deadline )) || fail "Timed out waiting for $name removal"
    sleep 2
  done
}

uninstall_ai() {
  read_catalog
  if ! jq -e 'any(.stackpacks[]; .name == "suse-ai")' <<<"$catalog" >/dev/null; then
    log 'SUSE AI is absent from the catalog'
    return
  fi
  read_instances suse-ai
  while IFS= read -r id; do
    [[ -n "$id" ]] || continue
    log "Uninstalling suse-ai instance $id"
    run_sts stackpack uninstall --name suse-ai --id "$id" || fail 'Uninstall failed'
  done < <(jq -r '.instances[] | select(.status != "DEPROVISIONING") | .id' <<<"$instances")
  wait_removed suse-ai
  log 'SUSE AI has no installed instances'
}

read_clusters() {
  [[ -n "${KUBERNETES_CLUSTERS:-}" ]] || fail 'KUBERNETES_CLUSTERS is not set'
  [[ "$KUBERNETES_CLUSTERS" != ,* && "$KUBERNETES_CLUSTERS" != *, ]] || fail 'Empty cluster name'
  IFS=',' read -r -a clusters <<<"$KUBERNETES_CLUSTERS"
  for i in "${!clusters[@]}"; do
    local cluster=${clusters[$i]}
    cluster="${cluster#"${cluster%%[![:space:]]*}"}"
    cluster="${cluster%"${cluster##*[![:space:]]}"}"
    [[ -n "$cluster" ]] || fail 'Empty cluster name'
    clusters[i]=$cluster
  done
}

ensure_companion() {
  local name=$1 cluster=${2:-} matching filter='.instances'
  if [[ "$name" == kubernetes-v2 ]]; then
    # shellcheck disable=SC2016 # $cluster is supplied to jq with --arg.
    filter='[.instances[] | select(.config.kubernetes_cluster_name == $cluster)]'
  fi
  read_instances "$name"
  matching=$(jq --arg cluster "$cluster" "$filter" <<<"$instances")
  if [[ $(jq 'length' <<<"$matching") != 0 ]]; then
    jq -e 'all(.status == "INSTALLED" or .status == "WAITING_FOR_DATA")' <<<"$matching" >/dev/null ||
      fail "$name has an incomplete or failed instance; inspect it before retrying"
    log "$name ${cluster:+for $cluster }already installed"
    return
  fi
  local parameters=()
  if [[ -n "$cluster" ]]; then parameters=(-p "kubernetes_cluster_name=$cluster"); fi
  # CLI --wait waits for INSTALLED even when provisioning succeeded and the
  # companion is waiting for its first telemetry. Accept either ready state.
  run_sts stackpack install --name "$name" "${parameters[@]}" ||
    fail "Could not install $name"
  local deadline=$((SECONDS + WAIT_SECONDS))
  while true; do
    read_instances "$name"
    matching=$(jq --arg cluster "$cluster" "$filter" <<<"$instances")
    if jq -e 'length > 0 and all(.status == "INSTALLED" or .status == "WAITING_FOR_DATA")' <<<"$matching" >/dev/null; then
      log "$name ${cluster:+for $cluster }configured"
      return
    fi
    if jq -e 'any(.status == "ERROR" or .status == "DEPROVISIONING")' <<<"$matching" >/dev/null; then
      fail "$name provisioning failed; inspect its instance"
    fi
    (( SECONDS < deadline )) || fail "Timed out waiting for $name provisioning"
    sleep 2
  done
}

install_ai() {
  local archive=${SUSE_AI_ARCHIVE:-/mnt/suse-ai.sts} manifest version current next versions
  [[ -r "$archive" ]] || fail "Cannot read $archive"
  unzip -tqq "$archive" || fail 'Invalid StackPack ZIP'
  manifest=$(unzip -p "$archive" stackpack.yaml) || fail 'Archive has no stackpack.yaml'
  version=$(sed -nE 's/^version: ([0-9]+\.[0-9]+\.[0-9]+)$/\1/p' <<<"$manifest")
  [[ "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || fail 'Invalid release version'
  grep -qx 'name: suse-ai' <<<"$manifest" || fail 'Archive is not suse-ai'
  grep -Eq "^schemaVersion: ['\"]?2\.0['\"]?$" <<<"$manifest" || fail 'Archive is not schema 2.0'
  read_clusters
  # Detect downgrade/error cases before changing companion installations.
  read_catalog
  if jq -e 'any(.stackpacks[]; .name == "suse-ai")' <<<"$catalog" >/dev/null; then
    read_instances suse-ai
  else
    instances='{"instances":[]}'
  fi
  [[ $(jq '.instances | length' <<<"$instances") -le 1 ]] || fail 'Expected at most one SUSE AI instance'
  current=$(jq -r '.instances[0].stackPackVersion // empty' <<<"$instances")
  if [[ -n "$current" ]]; then
    jq -e 'all(.instances[]; .status == "INSTALLED")' <<<"$instances" >/dev/null ||
      fail 'SUSE AI has an incomplete or failed instance; inspect it before retrying'
    if [[ "$current" != "$version" && $(printf '%s\n' "$current" "$version" | sort -V | tail -n 1) != "$version" ]]; then
      fail "Installed $current is newer than bundled $version; refusing a downgrade"
    fi
  fi
  for cluster in "${clusters[@]}"; do ensure_companion kubernetes-v2 "$cluster"; done
  ensure_companion open-telemetry
  if [[ "$current" == "$version" ]]; then
    log "suse-ai $version is already installed; no changes"
    return
  fi

  read_catalog
  versions='{"versions":[]}'
  if jq -e 'any(.stackpacks[]; .name == "suse-ai")' <<<"$catalog" >/dev/null; then
    versions=$(run_sts stackpack list-versions --name suse-ai -o json) || fail 'Cannot read SUSE AI versions'
    jq -e '.versions | type == "array"' <<<"$versions" >/dev/null || fail 'Invalid versions response'
  fi
  if jq -e --arg version "$version" 'any(.versions[]; .version == $version)' <<<"$versions" >/dev/null; then
    log "suse-ai $version is already uploaded; using the immutable catalog version"
  else
    log "Uploading $archive ($version)"
    run_sts stackpack upload --file "$archive" || fail 'Upload failed; no installation attempted'
  fi

  if [[ -z "$current" ]]; then
    run_sts stackpack install --name suse-ai --stackpack-version "$version" \
      --unlocked-strategy overwrite --wait --timeout "${WAIT_SECONDS}s" || fail 'Installation failed'
  else
    read_catalog
    next=$(jq -r '.stackpacks[] | select(.name == "suse-ai") | .nextVersion.version // empty' <<<"$catalog")
    [[ "$next" == "$version" ]] ||
      fail "Server offers upgrade $current -> ${next:-none}, not bundled $version; refusing an unpinned upgrade"
    log "Upgrading suse-ai $current -> $version"
    run_sts stackpack upgrade --name suse-ai --unlocked-strategy overwrite \
      --wait --timeout "${WAIT_SECONDS}s" ||
      fail 'Upgrade failed. Inspect the instance; no automatic destructive reinstall was attempted.'
  fi
  read_instances suse-ai
  jq -e --arg version "$version" '.instances | length == 1 and all(.status == "INSTALLED" and .stackPackVersion == $version)' \
    <<<"$instances" >/dev/null || fail 'Installed state/version does not match the bundled StackPack'
  log "suse-ai $version installed"
}

# Explicit maintenance for installations older than 2.x. Handle owned 2.x
# settings through StackPack upgrade/uninstall, not ad-hoc deletion.
cleanup_legacy() {
  local menus ids autosync
  menus=$(run_sts settings list --type MainMenuGroup -o json) || fail 'Cannot read menus'
  while IFS= read -r id; do
    [[ -n "$id" ]] || continue
    run_sts settings delete --ids "$id" || fail 'Cannot remove legacy menu'
  done < <(jq -r '.settings[] | select(.name == "GenAI Observability") | .id' <<<"$menus")
  [[ -n "${KUBERNETES_CLUSTERS:-}" ]] || return 0
  read_clusters
  read_instances autosync
  autosync=$instances
  for cluster in "${clusters[@]}"; do
    ids=$(jq -r --arg cluster "$cluster" '.instances[] | select(.config.sts_instance_type == "suse-ai" and .config.sts_instance_url == $cluster) | .id' <<<"$autosync")
    while IFS= read -r id; do
      [[ -n "$id" ]] || continue
      run_sts stackpack uninstall --name autosync --id "$id" || fail 'Legacy autosync uninstall failed'
    done <<<"$ids"
  done
}

if [[ "${CLEANUP_LEGACY:-}" == true ]]; then
  cleanup_legacy
elif [[ "${UNINSTALL:-}" == true ]]; then
  uninstall_ai
else
  install_ai
fi

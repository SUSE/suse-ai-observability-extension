#!/bin/bash
set -euo pipefail

readonly STACKPACK_NAME="genai-observability"
readonly STACKPACK_DIR="/mnt"
readonly STACKPACK_ARCHIVE="/tmp/${STACKPACK_NAME}.sts"

INSTANCE_TYPE="${INSTANCE_TYPE:-openlit}"

log_info() {
    echo "[INFO] $*"
}

log_error() {
    echo "[ERROR] $*" >&2
}

log_success() {
    echo "[SUCCESS] $*"
}

log_section() {
    echo ""
    echo "=============================================="
    echo "$*"
    echo "=============================================="
}

validate_environment() {
    local required_vars=("STACKSTATE_API_URL" "STACKSTATE_TOKEN" "STACKSTATE_TOKEN_TYPE" "KUBERNETES_CLUSTER")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
        fi
    done

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables: ${missing_vars[*]}"
        exit 1
    fi

    if [[ "$STACKSTATE_TOKEN_TYPE" != "service" && "$STACKSTATE_TOKEN_TYPE" != "api" ]]; then
        log_info "STACKSTATE_TOKEN_TYPE must be 'service' or 'api'; defaulting to 'api'"
        STACKSTATE_TOKEN_TYPE="api"
    fi
}

sts_auth_args() {
    echo "--url" "$STACKSTATE_API_URL" "--${STACKSTATE_TOKEN_TYPE}-token" "$STACKSTATE_TOKEN"
}

run_sts() {
    local cmd=("sts" "$@")
    local auth_args
    read -ra auth_args <<< "$(sts_auth_args)"
    "${cmd[@]}" "${auth_args[@]}"
}

# -----------------------------------------------------------------------------
# StackPack + STS CLI stuff
# -----------------------------------------------------------------------------
create_stackpack_archive() {
    log_info "Creating StackPack archive..."
    
    if [[ ! -f "${STACKPACK_DIR}/stackpack.conf" ]]; then
        log_error "stackpack.conf not found in ${STACKPACK_DIR}"
        exit 1
    fi

    (cd "${STACKPACK_DIR}" && zip -r "${STACKPACK_ARCHIVE}" stackpack.conf provisioning resources)
    
    log_info "Archive created: ${STACKPACK_ARCHIVE}"
}

is_stackpack_available() {
    local result
    result=$(run_sts stackpack list -o json | \
        jq --arg NAME "$STACKPACK_NAME" '.stackpacks | any(.name == $NAME)')
    [[ "${result}" == "true" ]]
}

is_stackpack_installed() {
    local result
    result=$(run_sts stackpack list-instances --name "$STACKPACK_NAME" -o json | \
        jq --arg CLUSTER "$KUBERNETES_CLUSTER" \
        '.instances | any(.config.kubernetes_cluster_name == $CLUSTER)')
    [[ "${result}" == "true" ]]
}

get_installed_instance_id() {
    run_sts stackpack list-instances --name "$STACKPACK_NAME" -o json | \
        jq -r --arg CLUSTER "$KUBERNETES_CLUSTER" \
        '.instances | map(select(.config.kubernetes_cluster_name == $CLUSTER and .status == "INSTALLED"))[0].id // empty'
}

upload_stackpack() {
    log_info "Uploading StackPack..."
    create_stackpack_archive
    run_sts stackpack upload --file "${STACKPACK_ARCHIVE}"
    log_success "StackPack uploaded successfully"
}

install_stackpack() {
    log_info "Installing StackPack with parameters:"
    log_info "  - kubernetes_cluster_name: $KUBERNETES_CLUSTER"
    log_info "  - instance_type: $INSTANCE_TYPE"

    run_sts stackpack install --name "$STACKPACK_NAME" \
        -p "kubernetes_cluster_name=$KUBERNETES_CLUSTER" \
        -p "instance_type=$INSTANCE_TYPE"

    log_success "StackPack installed successfully"
}

uninstall_stackpack() {
    local instance_id
    instance_id=$(get_installed_instance_id)

    if [[ -z "$instance_id" ]]; then
        log_info "No installed instance found for cluster: $KUBERNETES_CLUSTER"
        return 0
    fi

    log_info "Uninstalling StackPack instance (ID: $instance_id)..."
    run_sts stackpack uninstall --id "$instance_id" --name "$STACKPACK_NAME"
    log_success "StackPack uninstalled successfully"
}
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------

main_uninstall() {
    log_section "Starting Uninstall Process"
    uninstall_stackpack
}

main_install() {
    log_section "Starting GenAI Observability Installation"

    log_info "Checking if StackPack is available..."
    if ! is_stackpack_available; then
        upload_stackpack
    else
        log_info "StackPack already available"
    fi

    log_info "Checking if StackPack is installed for cluster: $KUBERNETES_CLUSTER..."
    if is_stackpack_installed; then
        log_info "StackPack already installed for cluster: $KUBERNETES_CLUSTER"
    else
        install_stackpack
    fi

    log_section "Installation Completed Successfully"
}

main() {
    validate_environment

    if [[ "${UNINSTALL:-}" == "true" ]]; then
        main_uninstall
    else
        main_install
    fi
}

main "$@"

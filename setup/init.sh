#!/bin/bash
set -e

# Function to build TLS flags for sts commands
build_tls_flags() {
  local tls_flags=""
  # Priority order: skip-ssl > ca-cert-path > ca-cert-base64-data
  if [[ "${STS_SKIP_SSL:-}" == "true" ]]; then
    tls_flags="--skip-ssl"
  elif [[ -n "${STS_CA_CERT_PATH:-}" && -f "$STS_CA_CERT_PATH" ]]; then
    tls_flags="--ca-cert-path $STS_CA_CERT_PATH"
  fi
  echo "$tls_flags"
}

# Function to run sts commands with TLS flags
run_sts() {
  local tls_flags=$(build_tls_flags)
  if [[ -n "$tls_flags" ]]; then
    sts $tls_flags "$@"
  else
    sts "$@"
  fi
}

for var in STACKSTATE_API_URL STACKSTATE_TOKEN STACKSTATE_TOKEN_TYPE KUBERNETES_CLUSTER; do
  if [ -z "${!var}" ]; then
    echo "Error: $var is not set"
    exit 1
  fi
done
if [[ "$STACKSTATE_TOKEN_TYPE" != "service" && "$STACKSTATE_TOKEN_TYPE" != "api" ]]; then
  echo "Warning: STACKSTATE_TOKEN_TYPE must be 'service' or 'api'; defaulting to 'api'"
  STACKSTATE_TOKEN_TYPE="api"
fi
if [ "${UNINSTALL:-}" = "true" ]; then
  echo "Starting uninstall process..."
  MENU_ID=$(run_sts settings list --type MainMenuGroup -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq -r '.settings[] | select(.name == "GenAI Observability") | .id')
  if [ -z "$MENU_ID" ]; then
    echo "No GenAI Observability menu to clean"
  else
    echo "Removing GenAI Observability menu..."
    run_sts settings delete --ids "$MENU_ID" --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
  fi
  STACKPACK_ID=$(run_sts stackpack list-instances --name autosync -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq --arg URL "$KUBERNETES_CLUSTER" '.instances | map(select(.config.sts_instance_url == $URL and .status == "INSTALLED"))[0].id // empty')
  if [ -z "$STACKPACK_ID" ]; then
    echo "No autosync stackpack instance to clean"
  else
    echo "Uninstalling autosync stackpack instance"
    run_sts stackpack uninstall --id "$STACKPACK_ID" --name autosync --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
  fi
  exit 0
fi
echo "Starting GenAI Observability install..."

echo "Ensuring autosync stackpack is available..."
AUTOSYNC_AVAILABLE=$(run_sts stackpack list -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq '.stackpacks | any(.name == "autosync")')
if [ "${AUTOSYNC_AVAILABLE:-}" != "true" ]; then
  echo "Uploading autosync stackpack..."
  run_sts stackpack upload --file /mnt/autosync-3.2.1-stac-0-bump-1037-203fef5-SNAPSHOT.sts --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi
echo "Ensuring autosync stackpack is installed..."
AUTOSYNC_INSTALLED=$(run_sts stackpack list-instances --name autosync -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq '.instances | any(.config.sts_instance_type == "openlit")')
if [ "${AUTOSYNC_INSTALLED:-}" != "true" ]; then
  echo "Installing autosync stackpack..."
  run_sts stackpack install -n autosync -p sts_instance_type=openlit -p sts_instance_url="$KUBERNETES_CLUSTER" --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi
echo "Ensuring open-telemetry stackpack is installed..."
OTEL_AVAILABLE=$(run_sts stackpack list-instances --name open-telemetry -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq '.instances | length != 0')
if [ "${OTEL_AVAILABLE:-}" != "true" ]; then
  echo "Installing open-telemetry stackpack..."
  run_sts stackpack install --name open-telemetry --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi
echo "Ensuring kubernetes-v2 stackpack is installed..."
K8S_AVAILABLE=$(run_sts stackpack list-instances --name kubernetes-v2 -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq --arg CLUSTER_NAME "$KUBERNETES_CLUSTER" 'any(.instances[]; .config.kubernetes_cluster_name == $CLUSTER_NAME)')
if [ "${K8S_AVAILABLE:-}" != "true" ]; then
  echo "Installing kubernetes-v2 stackpack..."
  run_sts stackpack install --name kubernetes-v2 -p kubernetes_cluster_name="$KUBERNETES_CLUSTER" --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi
echo "Applying settings..."
declare -a SETTING_FILES=(
  "/mnt/menu/llm.yaml"
  "/mnt/overview/genai_system.yaml"
  "/mnt/overview/gpu_nodes.yaml"
  "/mnt/overview/vector_db_system.yaml"
  "/mnt/overview/genai_apps.yaml"
  "/mnt/components/genai_system_ollama.yaml"
  "/mnt/components/genai_system_openai.yaml"
  "/mnt/components/genai_system_vllm.yaml"
  "/mnt/components/genai_model.yaml"
  "/mnt/components/genai_dbsystem_milvus.yaml"
  "/mnt/components/genai_dbsystem_opensearch.yaml"
  "/mnt/metrics/gpu_nodes.yaml"
  "/mnt/metrics/gpu_pods.yaml"
  "/mnt/metrics/genai_systems.yaml"
  "/mnt/metrics/db_systems.yaml"
  "/mnt/metrics/genai_apps.yaml"
  "/mnt/metrics/vllm.yaml"
  "/mnt/metrics/vllm_model.yaml"
  "/mnt/metrics/opensearch.yaml"
)

for file in "${SETTING_FILES[@]}"; do
  if [ -f "$file" ]; then
    echo "Applying $file..."
    run_sts settings apply -f "$file" --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
  else
    echo "Warning: File $file not found, skipping..."
  fi
done

echo "Defining monitors..."
if [ -f "/mnt/monitors/monitors.yaml" ]; then
  run_sts monitor apply -f "/mnt/monitors/monitors.yaml" --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
else
  echo "Warning: Monitors file not found, skipping..."
fi
echo "Installation completed successfully."
exit 0

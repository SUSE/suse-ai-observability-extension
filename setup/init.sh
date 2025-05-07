#!/bin/bash
set -e

for var in STACKSTATE_API_URL STACKSTATE_API_TOKEN KUBERNETES_CLUSTER; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set"
        exit 1
    fi
done

if [ "${UNINSTALL:-}" = "true" ]; then
    echo "Starting uninstall process..."
    MENU_ID=$(sts settings list --type MainMenuGroup -o json --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN" | jq -r '.settings[] | select(.name == "GenAI Observability") | .id')
    if [ -z "$MENU_ID" ]; then
        echo "No GenAI Observability menu to clean"
    else
        echo "Removing GenAI Observability menu..."
        sts settings delete --ids "$MENU_ID" --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"
    fi
    STACKPACK_ID=$(sts stackpack list-instances --name autosync -o json --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"  | jq --arg URL "$KUBERNETES_CLUSTER" '.instances | map(select(.config.sts_instance_url == $URL and .status == "INSTALLED"))[0].id // empty')
    if [ -z "$STACKPACK_ID" ]; then
        echo "No autosync stackpack instance to clean"
    else
        echo "Uninstalling autosync stackpack instance"
        sts stackpack uninstall --id "$STACKPACK_ID" --name autosync --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"
    fi
    exit 0
fi
echo "Starting GenAI Observability install..."

echo "Ensuring autosync stackpack is available..."
AUTOSYNC_AVAILABLE=$(sts stackpack list -o json  --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN" | jq '.stackpacks | any(.name == "autosync")')
if [ "${AUTOSYNC_AVAILABLE:-}" != "true" ]; then
    echo "Uploading autosync stackpack..."
    sts stackpack upload --file /mnt/autosync-3.2.1-stac-0-bump-1037-203fef5-SNAPSHOT.sts --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"
fi
echo "Installing autosync stackpack..."
sts stackpack install -n autosync -p sts_instance_type=openlit -p sts_instance_url="$KUBERNETES_CLUSTER" --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"
echo "Ensuring open-telemetry stackpack is installed..."
OTEL_AVAILABLE=$(sts stackpack list-instances --name open-telemetry -o json --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN" | jq '.instances | length != 0')
if [ "${OTEL_AVAILABLE:-}" != "true" ]; then
    echo "Installing open-telemetry stackpack..."
    sts stackpack install --name open-telemetry --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"
fi
echo "Ensuring kubernetes-v2 stackpack is installed..."
K8S_AVAILABLE=$(sts stackpack list-instances --name kubernetes-v2 -o json --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN" | jq --arg CLUSTER_NAME "$KUBERNETES_CLUSTER" 'any(.instances[]; .config.kubernetes_cluster_name == $CLUSTER_NAME)')
if [ "${K8S_AVAILABLE:-}" != "true" ]; then
    echo "Installing kubernetes-v2 stackpack..."
    sts stackpack install --name kubernetes-v2 -p kubernetes_cluster_name="$KUBERNETES_CLUSTER" --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"
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
    "/mnt/components/genai_dbsystem_milvus.yaml"
    "/mnt/metrics/gpu_nodes.yaml"
    "/mnt/metrics/gpu_pods.yaml"
    "/mnt/metrics/genai_systems.yaml"
    "/mnt/metrics/db_systems.yaml"
    "/mnt/metrics/genai_apps.yaml"
)

for file in "${SETTING_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Applying $file..."
        sts settings apply -f "$file" --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"
    else
        echo "Warning: File $file not found, skipping..."
    fi
done

echo "Defining monitors..."
if [ -f "/mnt/monitors/monitors.yaml" ]; then
    sts monitor apply -f "/mnt/monitors/monitors.yaml" --url "$STACKSTATE_API_URL" --api-token "$STACKSTATE_API_TOKEN"
else
    echo "Warning: Monitors file not found, skipping..."
fi
echo "Installation completed successfully."
exit 0

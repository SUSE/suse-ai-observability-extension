#!/bin/bash
set -e

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
    MENU_ID=$(sts settings list --type MainMenuGroup -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq -r '.settings[] | select(.name == "GenAI Observability") | .id')
    if [ -z "$MENU_ID" ]; then
        echo "No GenAI Observability menu to clean"
    else
        echo "Removing GenAI Observability menu..."
        sts settings delete --ids "$MENU_ID" --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
    fi
    STACKPACK_ID=$(sts stackpack list-instances --name autosync -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"  | jq --arg URL "$KUBERNETES_CLUSTER" '.instances | map(select(.config.sts_instance_url == $URL and .status == "INSTALLED"))[0].id // empty')
    if [ -z "$STACKPACK_ID" ]; then
        echo "No autosync stackpack instance to clean"
    else
        echo "Uninstalling autosync stackpack instance"
        sts stackpack uninstall --id "$STACKPACK_ID" --name autosync --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
    fi
    exit 0
fi
echo "Starting GenAI Observability install..."

echo "Ensuring autosync stackpack is available..."
AUTOSYNC_AVAILABLE=$(sts stackpack list -o json  --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq '.stackpacks | any(.name == "autosync")')
if [ "${AUTOSYNC_AVAILABLE:-}" != "true" ]; then
    echo "Uploading autosync stackpack..."
    sts stackpack upload --file /mnt/autosync-3.2.1-stac-0-bump-1037-203fef5-SNAPSHOT.sts --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi
echo "Ensuring autosync stackpack is installed..."
AUTOSYNC_INSTALLED=$(sts stackpack list-instances --name autosync -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq '.instances | any(.config.sts_instance_type == "openlit")')
if [ "${AUTOSYNC_INSTALLED:-}" != "true" ]; then
    echo "Installing autosync stackpack..."
    sts stackpack install -n autosync -p sts_instance_type=openlit -p sts_instance_url="$KUBERNETES_CLUSTER" --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi
echo "Ensuring open-telemetry stackpack is installed..."
OTEL_AVAILABLE=$(sts stackpack list-instances --name open-telemetry -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq '.instances | length != 0')
if [ "${OTEL_AVAILABLE:-}" != "true" ]; then
    echo "Installing open-telemetry stackpack..."
    sts stackpack install --name open-telemetry --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi
echo "Ensuring kubernetes-v2 stackpack is installed..."
K8S_AVAILABLE=$(sts stackpack list-instances --name kubernetes-v2 -o json --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | jq --arg CLUSTER_NAME "$KUBERNETES_CLUSTER" 'any(.instances[]; .config.kubernetes_cluster_name == $CLUSTER_NAME)')
if [ "${K8S_AVAILABLE:-}" != "true" ]; then
    echo "Installing kubernetes-v2 stackpack..."
    sts stackpack install --name kubernetes-v2 -p kubernetes_cluster_name="$KUBERNETES_CLUSTER" --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi
echo "Applying settings..."

echo "Creating Stackpack STS file..."
zip -r /mnt/genai-observability-stackpack.sts /mnt/stackpack.conf /mnt/provisioning /mnt/resources

echo "LS 1"
ls .

echo "LS 2"
ls /mnt/

echo "Uploading Stackpack..."
sts stackpack upload --file /mnt/genai-observability-stackpack.sts --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"

echo "Installing Stackpack..."
sts stackpack install --name genai-observability --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"

echo "Installation completed successfully."
exit 0

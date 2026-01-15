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

INSTANCE_TYPE="${INSTANCE_TYPE:-openlit}"

STACKPACK_NAME="genai-observability"

if [ "${UNINSTALL:-}" = "true" ]; then
    echo "Starting uninstall process..."
    
    STACKPACK_ID=$(sts stackpack list-instances --name "$STACKPACK_NAME" -o json \
        --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | \
        jq --arg CLUSTER "$KUBERNETES_CLUSTER" \
        '.instances | map(select(.config.kubernetes_cluster_name == $CLUSTER and .status == "INSTALLED"))[0].id // empty')
    
    if [ -z "$STACKPACK_ID" ]; then
        echo "No $STACKPACK_NAME stackpack instance found for cluster $KUBERNETES_CLUSTER"
    else
        echo "Uninstalling $STACKPACK_NAME stackpack instance (ID: $STACKPACK_ID)..."
        sts stackpack uninstall --id "$STACKPACK_ID" --name "$STACKPACK_NAME" \
            --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
        echo "Uninstall completed successfully."
    fi
    exit 0
fi

echo "Starting GenAI Observability installation..."

echo "Checking if $STACKPACK_NAME stackpack is available..."
STACKPACK_AVAILABLE=$(sts stackpack list -o json \
    --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | \
    jq --arg NAME "$STACKPACK_NAME" '.stackpacks | any(.name == $NAME)')

if [ "${STACKPACK_AVAILABLE:-}" != "true" ]; then
    echo "Uploading $STACKPACK_NAME stackpack..."
    zip -r /mnt/genai-observability-stackpack.sts /mnt/stackpack.conf /mnt/provisioning /mnt/resources
    sts stackpack upload --file /mnt/genai-observability-stackpack.sts \
        --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi

echo "Checking if $STACKPACK_NAME is already installed for cluster $KUBERNETES_CLUSTER..."
STACKPACK_INSTALLED=$(sts stackpack list-instances --name "$STACKPACK_NAME" -o json \
    --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN" | \
    jq --arg CLUSTER "$KUBERNETES_CLUSTER" \
    '.instances | any(.config.kubernetes_cluster_name == $CLUSTER)')

if [ "${STACKPACK_INSTALLED:-}" = "true" ]; then
    echo "$STACKPACK_NAME is already installed for cluster $KUBERNETES_CLUSTER"
else
    echo "Installing $STACKPACK_NAME stackpack..."
    echo "  - kubernetes_cluster_name: $KUBERNETES_CLUSTER"
    echo "  - instance_type: $INSTANCE_TYPE"
    
    sts stackpack install --name "$STACKPACK_NAME" \
        -p kubernetes_cluster_name="$KUBERNETES_CLUSTER" \
        -p instance_type="$INSTANCE_TYPE" \
        --url "$STACKSTATE_API_URL" --"$STACKSTATE_TOKEN_TYPE"-token "$STACKSTATE_TOKEN"
fi

echo ""
echo "=============================================="
echo "Installation completed successfully!"
echo "=============================================="
echo ""
exit 0

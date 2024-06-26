#!/bin/bash

# Function to handle the selection
handle_selection() {
    case $1 in
        node1|node2|node3|node4)
            NODE_SELECTION="$1"
            ;;
        *)
            echo "Invalid selection: $1. Please select node1, node2, node3, or node4."
            exit 1 # Indicates invalid selection
            ;;
    esac
}

# Check if the correct number of arguments are provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <current_signer_node> <new_signer_node>"
    exit 1
fi

# Assign arguments to variables
CURRENT_SIGNER_NODE=$1
NEW_SIGNER_NODE=$2

# Handle selections
handle_selection "$CURRENT_SIGNER_NODE"
handle_selection "$NEW_SIGNER_NODE"

# Function to get environment variable from a Docker container
get_env_var() {
    local container=$1
    local var_name=$2
    docker exec "$container" printenv "$var_name"
}

# Get environment variables from the current signer node container
ETHERBASE_CURRENT=$(get_env_var "$CURRENT_SIGNER_NODE" "ETHERBASE_${CURRENT_SIGNER_NODE^^}")
IP_CURRENT=$(get_env_var "$CURRENT_SIGNER_NODE" "IP_${CURRENT_SIGNER_NODE^^}")
WS_PORT_CURRENT=$(get_env_var "$CURRENT_SIGNER_NODE" "WS_PORT_${CURRENT_SIGNER_NODE^^}")

# Get the etherbase of the new signer node
ETHERBASE_NEW=$(get_env_var "$NEW_SIGNER_NODE" "ETHERBASE_${NEW_SIGNER_NODE^^}")

# Check if environment variables were retrieved successfully
if [ -z "$ETHERBASE_CURRENT" ] || [ -z "$IP_CURRENT" ] || [ -z "$WS_PORT_CURRENT" ] || [ -z "$ETHERBASE_NEW" ]; then
    echo "Error: Could not retrieve necessary environment variables."
    exit 1
fi

# Construct the Geth command
GETH_CMD="geth --exec \"clique.propose('${ETHERBASE_NEW}',true)\" attach ws://${IP_CURRENT}:${WS_PORT_CURRENT}"

# Construct the Docker command
DOCKER_CMD="docker exec -it ${CURRENT_SIGNER_NODE} $GETH_CMD"

# Execute the Docker command
echo "Executing command: $DOCKER_CMD"
eval "$DOCKER_CMD"

echo "Signer ${ETHERBASE_NEW} added to the network using ${CURRENT_SIGNER_NODE}."

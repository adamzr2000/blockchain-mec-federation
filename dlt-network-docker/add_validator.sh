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

# Debug: Print current and new signer node selections
echo "Current signer node: $CURRENT_SIGNER_NODE"
echo "New signer node: $NEW_SIGNER_NODE"

# Handle selections
handle_selection "$CURRENT_SIGNER_NODE"
handle_selection "$NEW_SIGNER_NODE"

# Source the environment variables from the corresponding .env files
source "./../config/dlt/${CURRENT_SIGNER_NODE}.env"
source "./../config/dlt/${NEW_SIGNER_NODE}.env"

# Extract the ID from the node names
CURRENT_SIGNER_ID=${CURRENT_SIGNER_NODE: -1}
NEW_SIGNER_ID=${NEW_SIGNER_NODE: -1}

# Extract the environment variables for the current signer node
ETHERBASE_CURRENT_VAR="ETHERBASE_NODE_${CURRENT_SIGNER_ID}"
IP_CURRENT_VAR="IP_NODE_${CURRENT_SIGNER_ID}"
WS_PORT_CURRENT_VAR="WS_PORT_NODE_${CURRENT_SIGNER_ID}"

ETHERBASE_CURRENT=${!ETHERBASE_CURRENT_VAR}
IP_CURRENT=${!IP_CURRENT_VAR}
WS_PORT_CURRENT=${!WS_PORT_CURRENT_VAR}

# Extract the etherbase of the new signer node
ETHERBASE_NEW_VAR="ETHERBASE_NODE_${NEW_SIGNER_ID}"
ETHERBASE_NEW=${!ETHERBASE_NEW_VAR}

# Debug: Print the retrieved environment variables
echo "Current signer node environment variables:"
echo "ETHERBASE_CURRENT: $ETHERBASE_CURRENT"
echo "IP_CURRENT: $IP_CURRENT"
echo "WS_PORT_CURRENT: $WS_PORT_CURRENT"

echo "New signer node environment variables:"
echo "ETHERBASE_NEW: $ETHERBASE_NEW"

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

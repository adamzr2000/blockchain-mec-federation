#!/bin/bash

# Function to handle the selection
handle_selection() {
    if [[ $1 =~ ^node[0-9]+$ ]]; then
        NODE_SELECTION="$1"
    else
        echo "Invalid selection: $1. Please select a valid node in the format nodeX, where X is a number."
        exit 1 # Indicates invalid selection
    fi
}

# Check if an argument is provided
if [ $# -eq 0 ]; then
    NODE_SELECTION="node2"
else
    handle_selection "$1"
fi

# Proceed with the operation
START_CMD="./${NODE_SELECTION}_start.sh"

DOCKER_CMD="docker run -d --name $NODE_SELECTION --hostname $NODE_SELECTION --network host --rm \
-v $(pwd)/../config/dlt/$NODE_SELECTION.env:/dlt-network/$NODE_SELECTION.env \
-v $(pwd)/../docker-images/dlt-node/scripts/genesis.json:/dlt-network/genesis.json \
-v $(pwd)/../docker-images/dlt-node/scripts/password.txt:/dlt-network/password.txt \
-v $(pwd)/../docker-images/dlt-node/scripts/${NODE_SELECTION}_start.sh:/dlt-network/${NODE_SELECTION}_start.sh \
dlt-node $START_CMD"

echo "Starting $NODE_SELECTION with command $START_CMD..."
eval "$DOCKER_CMD"

echo "$NODE_SELECTION started successfully."

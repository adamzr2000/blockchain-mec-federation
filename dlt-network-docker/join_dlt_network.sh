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

# Function to handle validators parameter
handle_validators() {
    if [[ $1 =~ ^[0-9]+$ ]] && [ $1 -ge 3 ]; then
        VALIDATORS="$1"
    else
        echo "Invalid validators value: $1. It must be a number greater than or equal to 3."
        exit 1 # Indicates invalid validators value
    fi
}

# Check if at least one argument is provided
if [ $# -eq 0 ]; then
    NODE_SELECTION="node2"
else
    handle_selection "$1"
    if [ $# -ge 2 ]; then
        handle_validators "$2"
    fi
fi

# Set the genesis file based on validators parameter
if [ -z "$VALIDATORS" ]; then
    GENESIS_FILE="genesis.json"
else
    GENESIS_FILE="genesis_${VALIDATORS}_validators.json"
fi

# Proceed with the operation
START_CMD="./${NODE_SELECTION}_start.sh"

DOCKER_CMD="docker run -d --name $NODE_SELECTION --hostname $NODE_SELECTION --network host --rm \
-v $(pwd)/../config/dlt/$NODE_SELECTION.env:/dlt-network/$NODE_SELECTION.env \
-v $(pwd)/../docker-images/dlt-node/scripts/$GENESIS_FILE:/dlt-network/genesis.json \
-v $(pwd)/../docker-images/dlt-node/scripts/password.txt:/dlt-network/password.txt \
-v $(pwd)/../docker-images/dlt-node/scripts/${NODE_SELECTION}_start.sh:/dlt-network/${NODE_SELECTION}_start.sh \
dlt-node $START_CMD"

echo "Starting $NODE_SELECTION with command $START_CMD..."
eval "$DOCKER_CMD"

echo "$NODE_SELECTION started successfully."

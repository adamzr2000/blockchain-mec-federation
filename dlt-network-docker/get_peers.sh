#!/bin/bash

# Check if the correct number of arguments are provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <node>"
    exit 1
fi

# Assign argument to variable
NODE=$1

# Path to the .env file
ENV_FILE="./../config/dlt/${NODE}.env"

# Check if the .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file $ENV_FILE does not exist."
    exit 1
fi

# Source the environment variables from the corresponding .env file
source "$ENV_FILE"

# Extract the ID from the node name
NODE_ID=${NODE: -2}

# Extract the environment variables for the node
IP_VAR="IP_NODE_${NODE_ID}"
WS_PORT_VAR="WS_PORT_NODE_${NODE_ID}"

# Debugging: print the variable names
echo "IP_VAR: $IP_VAR"
echo "WS_PORT_VAR: $WS_PORT_VAR"

IP=$(eval echo \$$IP_VAR)
WS_PORT=$(eval echo \$$WS_PORT_VAR)

# Debugging: print the values of IP and WS_PORT
echo "IP: $IP"
echo "WS_PORT: $WS_PORT"

# Check if IP and WS_PORT are not empty
if [ -z "$IP" ] || [ -z "$WS_PORT" ]; then
    echo "Error: IP or WS_PORT is not set."
    exit 1
fi

# Construct the Geth command to get the number of peers
GETH_CMD="geth --exec 'net.peerCount' attach ws://${IP}:${WS_PORT}"

# Debugging: print the Geth command
echo "GETH_CMD: $GETH_CMD"

# Construct the Docker command to get the number of peers
DOCKER_CMD="docker exec -it ${NODE} sh -c \"$GETH_CMD\""

# Debugging: print the Docker command
echo "DOCKER_CMD: $DOCKER_CMD"

# Execute the Docker command
eval "$DOCKER_CMD"


# #!/bin/bash

# # Check if the correct number of arguments are provided
# if [ $# -ne 1 ]; then
#     echo "Usage: $0 <node>"
#     exit 1
# fi

# # Assign argument to variable
# NODE=$1

# # Source the environment variables from the corresponding .env file
# source "./../config/dlt/${NODE}.env" 2>/dev/null

# # Extract the ID from the node name
# NODE_ID=${NODE: -1}

# # Extract the environment variables for the node
# IP_VAR="IP_NODE_${NODE_ID}"
# WS_PORT_VAR="WS_PORT_NODE_${NODE_ID}"

# IP=$(eval echo \$$IP_VAR)
# WS_PORT=$(eval echo \$$WS_PORT_VAR)

# # Construct the Geth command to get the number of peers
# GETH_CMD="geth --exec 'net.peerCount' attach ws://${IP}:${WS_PORT}"

# # Construct the Docker command to get the number of peers
# DOCKER_CMD="docker exec -it ${NODE} sh -c \"$GETH_CMD\""

# # Execute the Docker command
# echo "Executing command to get number of peers: $DOCKER_CMD"
# eval "$DOCKER_CMD"

#!/bin/bash

# Check if a parameter is passed and if it is greater than or equal to 2
if [ -z "$1" ] || [ "$1" -lt 2 ]; then
  echo "Error: A mandatory parameter must be provided, and it must be at least 2."
  exit 1
fi

# Assign the parameter to a variable
NODES=$1

# Define the base command and directory
BASE_COMMAND="cd /home/netcom/blockchain-mec-federation/dlt-network-docker/ &&"

# Function to execute a command via SSH and print debug information
execute_ssh_command() {
  local node_ip=$1
  local command=$2
  echo "Executing on ${node_ip}: ${command}"
  ssh netcom@${node_ip} "${command}"
  if [ $? -ne 0 ]; then
    echo "Error: Command failed on ${node_ip}"
  else
    echo "Success: Command executed on ${node_ip}"
  fi
}

# Start the DLT network on the first node
# execute_ssh_command "10.5.99.1" "${BASE_COMMAND} ./start_dlt_network.sh"

# Wait for 5 seconds after the first command
# echo "Waiting for 5 seconds..."
# sleep 5

# Loop to join the DLT network from node 2 to the specified number of nodes
for ((i=2; i<=NODES; i++)); do
  NODE_IP="10.5.99.${i}"
  NODE_NAME="node${i}"
  execute_ssh_command "${NODE_IP}" "${BASE_COMMAND} ./join_dlt_network.sh ${NODE_NAME} 30"
  sleep 3
done

#!/bin/bash

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
execute_ssh_command "10.5.99.1" "${BASE_COMMAND} ./start_dlt_network.sh"

# Wait for 5 seconds after the first command
echo "Waiting for 15 seconds..."
sleep 15

# Loop to join the DLT network from node 2 to node 30
for i in {2..6}; do
  NODE_IP="10.5.99.${i}"
  NODE_NAME="node${i}"
  execute_ssh_command "${NODE_IP}" "${BASE_COMMAND} ./join_dlt_network.sh ${NODE_NAME} 30"
  sleep 5
done

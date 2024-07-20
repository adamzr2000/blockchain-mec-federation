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

# Stop the DLT network on the first node
execute_ssh_command "10.5.99.1" "${BASE_COMMAND} ./stop_dlt_network.sh"

# Loop to kill the docker containers from node 2 to node 30
for i in {2..30}; do
  NODE_IP="10.5.99.${i}"
  NODE_NAME="node${i}"
  execute_ssh_command "${NODE_IP}" "docker kill ${NODE_NAME}"
done

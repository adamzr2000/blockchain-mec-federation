#!/bin/bash

# Define the base command and directory
BASE_COMMAND="cd /home/netcom/blockchain-mec-federation && git pull"

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

# Loop to execute git pull on all nodes from 1 to 30
for i in {1..30}; do
  NODE_IP="10.5.99.${i}"
  execute_ssh_command "${NODE_IP}" "${BASE_COMMAND}"
done

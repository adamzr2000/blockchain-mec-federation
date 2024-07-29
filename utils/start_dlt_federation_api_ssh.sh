#!/bin/bash

# Check if both parameters are passed and if they are greater than or equal to 1
if [ -z "$1" ] || [ "$1" -lt 1 ] || [ -z "$2" ] || [ "$2" -lt 1 ]; then
  echo "Error: Two mandatory parameters must be provided, and they must be at least 1."
  echo "Usage: $0 <NUM_CONSUMERS> <NUM_PROVIDERS>"
  exit 1
fi

# Assign the parameters to variables
NUM_CONSUMERS=$1
NUM_PROVIDERS=$2

# Function to execute a command via SSH and print debug information
execute_ssh_command() {
  local node_ip=$1
  local command=$2
  echo "Executing on ${node_ip}: ${command}"
  ssh netcom@${node_ip} "bash -l -c '${command}'"
  if [ $? -ne 0 ]; then
    echo "Error: Command failed on ${node_ip}"
  else
    echo "Success: Command executed on ${node_ip}"
  fi
}

# Loop to start the app for consumers from node 1 to NUM_CONSUMERS (included)
for i in $(seq 1 ${NUM_CONSUMERS}); do
  NODE_IP="10.5.99.${i}"
  CONFIG_FILE="config/federation/${NUM_CONSUMERS}-offer/consumer${i}.env"
  COMMAND="cd /home/netcom/blockchain-mec-federation && ./start_app.sh ${CONFIG_FILE}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

# Loop to start the app for providers from node NUM_CONSUMERS + 1 to NUM_CONSUMERS + NUM_PROVIDERS (included)
for i in $(seq $((NUM_CONSUMERS + 1)) $((NUM_CONSUMERS + NUM_PROVIDERS))); do
  NODE_IP="10.5.99.${i}"
  PROVIDER_INDEX=$((i - NUM_CONSUMERS))
  CONFIG_FILE="config/federation/${NUM_CONSUMERS}-offer/provider${PROVIDER_INDEX}.env"
  COMMAND="cd /home/netcom/blockchain-mec-federation && ./start_app.sh ${CONFIG_FILE}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

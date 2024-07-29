#!/bin/bash

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

NUM_CONSUMERS=10
NUM_PROVIDERS=20

# Loop to start the app for consumers from node 1 to NUM_CONSUMERS (included)
for i in $(seq 1 ${NUM_CONSUMERS}); do
  NODE_IP="10.5.99.${i}"
  CONFIG_FILE="config/federation/${NUM_CONSUMERS}-offer/consumer${i}.env"
  COMMAND="cd /home/netcom/blockchain-mec-federation && ./start_app.sh ${CONFIG_FILE}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

# Loop to start the app for providers from node NUM_CONSUMERS + 1 to NUM_PROVIDERS (included)
for i in $(seq $((NUM_CONSUMERS + 1)) $((NUM_CONSUMERS + NUM_PROVIDERS))); do
  NODE_IP="10.5.99.${i}"
  PROVIDER_INDEX=$((i - NUM_CONSUMERS))
  CONFIG_FILE="config/federation/${NUM_CONSUMERS}-offer/provider${PROVIDER_INDEX}.env"
  COMMAND="cd /home/netcom/blockchain-mec-federation && ./start_app.sh ${CONFIG_FILE}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

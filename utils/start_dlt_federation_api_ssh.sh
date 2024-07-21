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

# Loop to start the app for consumers from node 1 to node 10
for i in {1..10}; do
  NODE_IP="10.5.99.${i}"
  CONFIG_FILE="config/federation/10-offer/consumer${i}.env"
  COMMAND="cd /home/netcom/blockchain-mec-federation && ./start_app.sh ${CONFIG_FILE}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

# Loop to start the app for providers from node 11 to node 30
for i in {11..30}; do
  NODE_IP="10.5.99.${i}"
  PROVIDER_INDEX=$((i - 10))
  CONFIG_FILE="config/federation/10-offer/provider${PROVIDER_INDEX}.env"
  COMMAND="cd /home/netcom/blockchain-mec-federation && ./start_app.sh ${CONFIG_FILE}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

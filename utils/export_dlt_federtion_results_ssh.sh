#!/bin/bash

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

# Loop to move CSV files for consumers from node 1 to node 10
for i in {1..10}; do
  NODE_IP="10.5.99.${i}"
  CONFIG_FILE="10-offer/30-mec-systems/consumer-${i}/"
  GIT_TAG="10-offer-cons${i}"
  COMMAND="cd /home/netcom/blockchain-mec-federation/experiments && mv consumer/*.csv ${CONFIG_FILE} && cd ../utils && ./push_to_git.sh ${GIT_TAG}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

# Loop to move CSV files for providers from node 11 to node 30
for i in {11..30}; do
  NODE_IP="10.5.99.${i}"
  PROVIDER_INDEX=$((i - 10))
  CONFIG_FILE="10-offer/30-mec-systems/provider-${PROVIDER_INDEX}/"
  GIT_TAG="10-offer-prov${PROVIDER_INDEX}"
  COMMAND="cd /home/netcom/blockchain-mec-federation/experiments && mv provider/*.csv ${CONFIG_FILE} && cd ../utils && ./push_to_git.sh ${GIT_TAG}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

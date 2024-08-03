#!/bin/bash

# Check if correct number of arguments is provided
if [ "$#" -ne 3 ]; then
  echo "Usage: $0 NUM_CONSUMERS NUM_PROVIDERS OFFERS"
  exit 1
fi

# Constants from user input
NUM_CONSUMERS=$1
NUM_PROVIDERS=$2
OFFERS=$3

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

# Loop to move CSV files for consumers
for i in $(seq 1 $NUM_CONSUMERS); do
  NODE_IP="10.5.99.${i}"
  CONFIG_FILE="${OFFERS}-offer/30-mec-systems/consumer-${i}/"
  GIT_TAG="${OFFERS}-offer-cons${i}"
  COMMAND="cd /home/netcom/blockchain-mec-federation/experiments && git pull && mv consumer/*.csv ${CONFIG_FILE} && cd ../utils && ./push_to_git.sh ${GIT_TAG}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

# Loop to move CSV files for providers
for i in $(seq $(($NUM_CONSUMERS + 1)) $(($NUM_CONSUMERS + $NUM_PROVIDERS))); do
  NODE_IP="10.5.99.${i}"
  PROVIDER_INDEX=$((i - $NUM_CONSUMERS))
  CONFIG_FILE="${OFFERS}-offer/30-mec-systems/provider-${PROVIDER_INDEX}/"
  GIT_TAG="${OFFERS}-offer-prov${PROVIDER_INDEX}"
  COMMAND="cd /home/netcom/blockchain-mec-federation/experiments && git pull && mv provider/*.csv ${CONFIG_FILE} && cd ../utils && ./push_to_git.sh ${GIT_TAG}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

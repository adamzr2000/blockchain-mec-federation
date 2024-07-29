#!/bin/bash

NUM_PARTICIPANTS=2

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


# Loop to move CSV files for consumers from node 1 to node 30
for i in {1..30}; do
  NODE_IP="10.5.99.${i}"
  GIT_TAG="${NUM_PARTICIPANTS}-mec-systems-participant${i}"
  COMMAND="cd /home/netcom/blockchain-mec-federation/experiments && git pull && cd ../utils && ./push_to_git.sh ${GIT_TAG}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done


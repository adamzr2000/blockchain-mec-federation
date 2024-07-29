#!/bin/bash

# Check if a parameter is passed and if it is greater than or equal to 1
if [ -z "$1" ] || [ "$1" -lt 1 ]; then
  echo "Error: A mandatory parameter must be provided, and it must be at least 1."
  exit 1
fi

# Assign the parameter to a variable
NUM_PARTICIPANTS=$1

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

# Loop to move CSV files for consumers from node 1 to the specified number of participants
for ((i=1; i<=NUM_PARTICIPANTS; i++)); do
  NODE_IP="10.5.99.${i}"
  GIT_TAG="${NUM_PARTICIPANTS}-mec-systems-participant${i}"
  COMMAND="cd /home/netcom/blockchain-mec-federation/experiments && git pull && cd ../utils && ./push_to_git.sh ${GIT_TAG}"
  execute_ssh_command "${NODE_IP}" "${COMMAND}"
done

#!/bin/bash

# Function to generate and execute the SSH command
execute_ssh_clean_command() {
  local node_ip=$1
  local command="cd /home/netcom/blockchain-mec-federation/experiments/10-offer/30-mec-systems && rm consumer-*/*.csv && rm provider-*/*.csv"
  echo "Executing on ${node_ip}: ${command}"
  ssh netcom@${node_ip} "${command}"
  if [ $? -ne 0 ]; then
    echo "Error: Command failed on ${node_ip}"
  else
    echo "Success: Command executed on ${node_ip}"
  fi
}

# Loop to run the clean_all.sh script on all nodes from 1 to 30
for i in {1..30}; do
  NODE_IP="10.5.99.${i}"
  execute_ssh_clean_command "${NODE_IP}"
done

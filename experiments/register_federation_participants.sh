#!/bin/bash

# Number of participants (set as a static variable)
PARTICIPANTS=30

# Function to execute a curl command and print debug information
execute_curl_command() {
  local participant_ip=$1
  local url="http://${participant_ip}:8000/register_domain"
  echo "Executing curl on ${url}"
  curl -X POST "${url}"
  if [ $? -ne 0 ]; then
    echo "Error: Command failed for ${url}"
  else
    echo "Success: Command executed for ${url}"
  fi
}

# Loop to register domains for all participants
for i in $(seq 1 $PARTICIPANTS); do
  PARTICIPANT_IP="10.5.99.${i}"
  execute_curl_command "${PARTICIPANT_IP}"
  echo "Waiting for 3 seconds..."
  sleep 3
done

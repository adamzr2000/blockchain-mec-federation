#!/bin/bash

# Constants for scalability
NUM_CONSUMERS=20
NUM_PROVIDERS=10

# Function to execute a curl command and print debug information
execute_curl_command() {
  local url=$1
  echo "Executing curl on ${url}"
  curl -X DELETE "${url}"
  if [ $? -ne 0 ]; then
    echo "Error: Command failed for ${url}"
  else
    echo "Success: Command executed for ${url}"
  fi
}

# Loop to delete services for consumer nodes
for i in $(seq 1 $NUM_CONSUMERS); do
  NODE_IP="10.5.99.${i}"
  SERVICE_URL="http://${NODE_IP}:8000/delete_docker_service?name=mec-app_1"
  VXLAN_URL="http://${NODE_IP}:8000/delete_vxlan"
  execute_curl_command "${SERVICE_URL}"
  execute_curl_command "${VXLAN_URL}"
done

# Loop to delete services for provider nodes
for i in $(seq $(($NUM_CONSUMERS + 1)) $(($NUM_CONSUMERS + $NUM_PROVIDERS))); do
  NODE_IP="10.5.99.${i}"
  VXLAN_ID=$((200 + i))
  SERVICE_URL_1="http://${NODE_IP}:8000/delete_docker_service?name=federated-mec-app_1"
  SERVICE_URL_2="http://${NODE_IP}:8000/delete_docker_service?name=federated-mec-app_2"
  VXLAN_URL_1="http://${NODE_IP}:8000/delete_vxlan"
  VXLAN_URL_2="http://${NODE_IP}:8000/delete_vxlan?vxlan_id=${VXLAN_ID}&docker_net_name=federated-net-2"
  
  execute_curl_command "${SERVICE_URL_1}"
  execute_curl_command "${SERVICE_URL_2}"
  execute_curl_command "${VXLAN_URL_1}"
  execute_curl_command "${VXLAN_URL_2}"
done
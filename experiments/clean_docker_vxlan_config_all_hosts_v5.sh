#!/bin/bash

# Constants for scalability
NUM_CONSUMERS=25
NUM_PROVIDERS=5

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
  VXLAN_ID=$((200 + i))
  SERVICE_URL="http://${NODE_IP}:8000/delete_docker_service?name=mec-app_1"
  VXLAN_URL="http://${NODE_IP}:8000/delete_vxlan?vxlan_id=${VXLAN_ID}&docker_net_name=federation-net"
  execute_curl_command "${SERVICE_URL}"
  execute_curl_command "${VXLAN_URL}"
done

# Loop to delete services for provider nodes
for i in $(seq 1 $NUM_PROVIDERS); do
  PROVIDER_NODE_IP="10.5.99.$((NUM_CONSUMERS + i))"

  # First delete the federated MEC apps
  for j in $(seq 0 4); do
    SERVICE_URL="http://${PROVIDER_NODE_IP}:8000/delete_docker_service?name=federated-mec-app-${j}_1"
    execute_curl_command "${SERVICE_URL}"
  done
  
  # Then delete the VXLANs
  for j in $(seq 0 4); do
    CONSUMER_INDEX=$((i * 5 - 4 + j))
    VXLAN_ID=$((200 + CONSUMER_INDEX))
    for k in $(seq 0 4); do
      VXLAN_URL="http://${PROVIDER_NODE_IP}:8000/delete_vxlan?vxlan_id=${VXLAN_ID}&docker_net_name=federation-net-${k}"
      execute_curl_command "${VXLAN_URL}"
    done
  done
done

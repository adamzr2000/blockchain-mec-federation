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
for i in $(seq 1 $NUM_PROVIDERS); do
  PROVIDER_NODE_IP="10.5.99.$((NUM_CONSUMERS + i))"
  CONSUMER_1=$((2 * i - 1))
  CONSUMER_2=$((2 * i))
  VXLAN_ID_1=$((200 + CONSUMER_1))
  VXLAN_ID_2=$((200 + CONSUMER_2))
  
  SERVICE_URL_1="http://${PROVIDER_NODE_IP}:8000/delete_docker_service?name=federated-mec-app_1"
  SERVICE_URL_2="http://${PROVIDER_NODE_IP}:8000/delete_docker_service?name=federated-mec-app-2_1"
  VXLAN_URL_11="http://${PROVIDER_NODE_IP}:8000/delete_vxlan?vxlan_id=${VXLAN_ID_1}&docker_net_name=federation-net"
  VXLAN_URL_12="http://${PROVIDER_NODE_IP}:8000/delete_vxlan?vxlan_id=${VXLAN_ID_2}&docker_net_name=federation-net"
  VXLAN_URL_21="http://${PROVIDER_NODE_IP}:8000/delete_vxlan?vxlan_id=${VXLAN_ID_1}&docker_net_name=federation-net-2"
  VXLAN_URL_22="http://${PROVIDER_NODE_IP}:8000/delete_vxlan?vxlan_id=${VXLAN_ID_2}&docker_net_name=federation-net-2"

  execute_curl_command "${SERVICE_URL_1}"
  execute_curl_command "${SERVICE_URL_2}"
  execute_curl_command "${VXLAN_URL_11}"
  execute_curl_command "${VXLAN_URL_12}"
  execute_curl_command "${VXLAN_URL_21}"
  execute_curl_command "${VXLAN_URL_22}"

done

#!/bin/bash

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

# Loop to delete services for nodes 1 to 10
for i in {1..10}; do
  NODE_IP="10.5.99.${i}"
  SERVICE_URL="http://${NODE_IP}:8000/delete_docker_service?name=mec-app_1"
  VXLAN_URL="http://${NODE_IP}:8000/delete_vxlan"
  execute_curl_command "${SERVICE_URL}"
  execute_curl_command "${VXLAN_URL}"
done

# Loop to delete services for nodes 11 to 30
for i in {11..30}; do
  NODE_IP="10.5.99.${i}"
  if [ ${i} -eq 11 ]; then
    SERVICE_URL="http://${NODE_IP}:8000/delete_docker_service?name=federated-mec-app_1"
  else
    SERVICE_URL="http://${NODE_IP}:8000/delete_docker_service?name=mec-app_1"
  fi
  VXLAN_URL="http://${NODE_IP}:8000/delete_vxlan"
  execute_curl_command "${SERVICE_URL}"
  execute_curl_command "${VXLAN_URL}"
done

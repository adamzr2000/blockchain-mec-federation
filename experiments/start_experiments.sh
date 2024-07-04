#!/bin/bash

# Script for experiments of migrating the entire object detection service

# Constants
EXPORT_RESULTS="false"
BASE_URL_CONSUMER="http://10.5.99.1:8000"
BASE_URL_PROVIDER1="http://10.5.99.2:8000"
BASE_URL_PROVIDER2="http://10.5.99.3:8000"
LOGS_DIR="logs"

# Consumer Endpoints
EXPERIMENTS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/start_experiments_consumer?export_to_csv=${EXPORT_RESULTS}&providers=1"
DEPLOY_CONTAINERS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/deploy_docker_service?image=mec-app&name=mec-app&network=bridge&replicas=1"
DELETE_VXLAN_RESOURCES_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/delete_vxlan"
DELETE_CONTAINERS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/delete_docker_service?name=mec-app"

# Provider Endpoints
## Provider 1
EXPERIMENTS_PROVIDER1_ENDPOINT="${BASE_URL_PROVIDER1}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=20"
DELETE_VXLAN_RESOURCES_PROVIDER1_ENDPOINT="${BASE_URL_PROVIDER1}/delete_vxlan"
DELETE_CONTAINERS_PROVIDER1_ENDPOINT="${BASE_URL_PROVIDER1}/delete_docker_service?name=federated-mec-app"

## Provider 2
EXPERIMENTS_PROVIDER2_ENDPOINT="${BASE_URL_PROVIDER2}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=20"
DELETE_VXLAN_RESOURCES_PROVIDER2_ENDPOINT="${BASE_URL_PROVIDER2}/delete_vxlan"
DELETE_CONTAINERS_PROVIDER2_ENDPOINT="${BASE_URL_PROVIDER2}/delete_docker_service?name=federated-mec-app"

# Function to validate input
validate_input() {
    local num_tests=$1
    if [[ $num_tests -lt 1 || $num_tests -gt 20 ]]; then
        echo "The number of tests must be between 1 and 20."
        exit 1
    fi
}

# Function to deploy consumer container
deploy_consumer_container() {
    curl -X POST "${DEPLOY_CONTAINERS_CONSUMER_ENDPOINT}" | jq
    sleep 2
}

# Function to start experiments
start_experiments() {
    local test_number=$1

    # Deploy consumer container
    deploy_consumer_container

    # Start the provider1 experiment in the background and save the log
    curl -X POST "${EXPERIMENTS_PROVIDER1_ENDPOINT}" -o "${LOGS_DIR}/provider1_output_test${test_number}.txt" &

    # Start the consumer experiment, wait for it to finish, and save the log
    curl -X POST "${EXPERIMENTS_CONSUMER_ENDPOINT}" -o "${LOGS_DIR}/consumer_output_test${test_number}.txt"

    # Ensure background processes have finished
    wait

    # Cleanup resources
    cleanup_resources
}

# Function to cleanup resources
cleanup_resources() {
    curl -X DELETE "$DELETE_CONTAINERS_PROVIDER1_ENDPOINT" | jq
    sleep 2

    curl -X DELETE "$DELETE_VXLAN_RESOURCES_PROVIDER1_ENDPOINT" | jq
    sleep 2

    curl -X DELETE "$DELETE_CONTAINERS_CONSUMER_ENDPOINT" | jq
    sleep 2

    curl -X DELETE "$DELETE_VXLAN_RESOURCES_CONSUMER_ENDPOINT" | jq
    sleep 2
}

# Main function to run experiments
run_experiments() {
    local num_tests=$1

    for ((i=1; i<=num_tests; i++))
    do
        echo "Starting experiment $i of $num_tests..."
        start_experiments $i
        echo "Experiment $i completed."
    done

    echo "All experiments completed."
}

# Create logs directory if not exists
mkdir -p "${LOGS_DIR}"

# Ask the user for the number of tests to run
read -p "Enter the number of tests to run (1-20): " num_tests

# Validate the input
validate_input $num_tests

# Run the experiments
run_experiments $num_tests

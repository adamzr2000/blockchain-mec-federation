#!/bin/bash

# Constants
LOGS_DIR="logs"
EXPORT_RESULTS="false"
NUMBER_OF_PROVIDERS=1  # Set the number of providers here

BASE_URL_CONSUMER="http://10.5.99.1:8000"
BASE_URL_PROVIDER1="http://10.5.99.2:8000"
BASE_URL_PROVIDER2="http://10.5.99.3:8000"
BASE_URL_PROVIDER3="http://10.5.99.4:8000"
BASE_URL_PROVIDER4="http://10.5.99.5:8000"
BASE_URL_PROVIDER5="http://10.5.99.6:8000"
BASE_URL_PROVIDER6="http://10.5.99.7:8000"
BASE_URL_PROVIDER7="http://10.5.99.8:8000"
BASE_URL_PROVIDER8="http://10.5.99.9:8000"
BASE_URL_PROVIDER9="http://10.5.99.10:8000"

# Consumer Endpoints
EXPERIMENTS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/start_experiments_consumer?export_to_csv=${EXPORT_RESULTS}&providers=${NUMBER_OF_PROVIDERS}"
DEPLOY_CONTAINERS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/deploy_docker_service?image=mec-app&name=mec-app&network=bridge&replicas=1"
DELETE_VXLAN_RESOURCES_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/delete_vxlan"
DELETE_CONTAINERS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/delete_docker_service?name=mec-app"

# Provider Endpoints
EXPERIMENTS_PROVIDER_ENDPOINTS=(
    "${BASE_URL_PROVIDER1}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=12"
    "${BASE_URL_PROVIDER2}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=18"
    "${BASE_URL_PROVIDER3}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=30"
    "${BASE_URL_PROVIDER4}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=50"
    "${BASE_URL_PROVIDER5}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=40"
    "${BASE_URL_PROVIDER6}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=45"
    "${BASE_URL_PROVIDER7}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=25"
    "${BASE_URL_PROVIDER8}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=35"
    "${BASE_URL_PROVIDER9}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=70"
)

DELETE_CONTAINERS_PROVIDER_ENDPOINTS=(
    "${BASE_URL_PROVIDER1}/delete_docker_service?name=federated-mec-app"
    "${BASE_URL_PROVIDER2}/delete_docker_service?name=federated-mec-app"
    "${BASE_URL_PROVIDER3}/delete_docker_service?name=federated-mec-app"
    "${BASE_URL_PROVIDER4}/delete_docker_service?name=federated-mec-app"
    "${BASE_URL_PROVIDER5}/delete_docker_service?name=federated-mec-app"
    "${BASE_URL_PROVIDER6}/delete_docker_service?name=federated-mec-app"
    "${BASE_URL_PROVIDER7}/delete_docker_service?name=federated-mec-app"
    "${BASE_URL_PROVIDER8}/delete_docker_service?name=federated-mec-app"
    "${BASE_URL_PROVIDER9}/delete_docker_service?name=federated-mec-app"
)

DELETE_VXLAN_RESOURCES_PROVIDER_ENDPOINTS=(
    "${BASE_URL_PROVIDER1}/delete_vxlan"
    "${BASE_URL_PROVIDER2}/delete_vxlan"
    "${BASE_URL_PROVIDER3}/delete_vxlan"
    "${BASE_URL_PROVIDER4}/delete_vxlan"
    "${BASE_URL_PROVIDER5}/delete_vxlan"
    "${BASE_URL_PROVIDER6}/delete_vxlan"
    "${BASE_URL_PROVIDER7}/delete_vxlan"
    "${BASE_URL_PROVIDER8}/delete_vxlan"
    "${BASE_URL_PROVIDER9}/delete_vxlan"
)

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
    echo "Deploying consumer container..."
    curl -X POST "${DEPLOY_CONTAINERS_CONSUMER_ENDPOINT}" | tee -a "${LOGS_DIR}/deploy_consumer_container.log"
    sleep 2
}

# Function to start experiments
start_experiments() {
    local test_number=$1

    echo "Starting experiment $test_number..."
    echo "Starting experiment $test_number..." >> "${LOGS_DIR}/experiment_${test_number}.log"

    # Deploy consumer container
    deploy_consumer_container >> "${LOGS_DIR}/experiment_${test_number}.log" 2>&1

    # Start the provider experiments in the background and save the logs
    for ((i=1; i<=NUMBER_OF_PROVIDERS; i++)); do
        echo "Starting provider $i experiment for test $test_number..."
        curl -X POST "${EXPERIMENTS_PROVIDER_ENDPOINTS[$i-1]}" -o "${LOGS_DIR}/provider${i}_output_test${test_number}.txt" &
    done

    # Start the consumer experiment, wait for it to finish, and save the log
    echo "Starting consumer experiment for test $test_number..."
    curl -X POST "${EXPERIMENTS_CONSUMER_ENDPOINT}" -o "${LOGS_DIR}/consumer_output_test${test_number}.txt"

    # Ensure background processes have finished
    echo "Waiting for background processes to complete for test $test_number..."
    wait

    # Cleanup resources
    echo "Cleaning up resources for test $test_number..."
    cleanup_resources $test_number >> "${LOGS_DIR}/experiment_${test_number}.log" 2>&1

    echo "Experiment $test_number completed."
    echo "Experiment $test_number completed." >> "${LOGS_DIR}/experiment_${test_number}.log"
}

# Function to cleanup resources
cleanup_resources() {
    local test_number=$1
    for ((i=1; i<=NUMBER_OF_PROVIDERS; i++)); do
        echo "Deleting containers for provider $i for test $test_number..."
        curl -X DELETE "${DELETE_CONTAINERS_PROVIDER_ENDPOINTS[$i-1]}" | tee -a "${LOGS_DIR}/cleanup_provider${i}_test${test_number}.log"
        sleep 2
        echo "Deleting VXLAN resources for provider $i for test $test_number..."
        curl -X DELETE "${DELETE_VXLAN_RESOURCES_PROVIDER_ENDPOINTS[$i-1]}" | tee -a "${LOGS_DIR}/cleanup_provider${i}_test${test_number}.log"
        sleep 2
    done

    echo "Deleting consumer containers for test $test_number..."
    curl -X DELETE "$DELETE_CONTAINERS_CONSUMER_ENDPOINT" | tee -a "${LOGS_DIR}/cleanup_consumer_test${test_number}.log"
    sleep 2

    echo "Deleting VXLAN resources for consumer for test $test_number..."
    curl -X DELETE "$DELETE_VXLAN_RESOURCES_CONSUMER_ENDPOINT" | tee -a "${LOGS_DIR}/cleanup_consumer_test${test_number}.log"
    sleep 2
}

# Main function to run experiments
run_experiments() {
    local num_tests=$1

    for ((i=1; i<=num_tests; i++)); do
        echo "Starting experiment $i of $num_tests..."
        start_experiments $i
        echo "Experiment $i of $num_tests completed."
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

#!/bin/bash

# Constants
LOGS_DIR="logs"
EXPORT_RESULTS="true"

# Set the number of providers here
NUMBER_OF_PROVIDERS=2  

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
BASE_URL_PROVIDER10="http://10.5.99.11:8000"
BASE_URL_PROVIDER11="http://10.5.99.12:8000"
BASE_URL_PROVIDER12="http://10.5.99.13:8000"
BASE_URL_PROVIDER13="http://10.5.99.14:8000"
BASE_URL_PROVIDER14="http://10.5.99.15:8000"
BASE_URL_PROVIDER15="http://10.5.99.16:8000"
BASE_URL_PROVIDER16="http://10.5.99.17:8000"
BASE_URL_PROVIDER17="http://10.5.99.18:8000"
BASE_URL_PROVIDER18="http://10.5.99.19:8000"
BASE_URL_PROVIDER19="http://10.5.99.20:8000"


# Consumer Endpoints
EXPERIMENTS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/start_experiments_consumer?export_to_csv=${EXPORT_RESULTS}&providers=${NUMBER_OF_PROVIDERS}"
DEPLOY_CONTAINERS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/deploy_docker_service?image=mec-app&name=mec-app&network=bridge&replicas=1"
DELETE_VXLAN_RESOURCES_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/delete_vxlan"
DELETE_CONTAINERS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/delete_docker_service?name=mec-app"

# Provider Endpoints
## Provider 1
EXPERIMENTS_PROVIDER1_ENDPOINT="${BASE_URL_PROVIDER1}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=12"
DELETE_VXLAN_RESOURCES_PROVIDER1_ENDPOINT="${BASE_URL_PROVIDER1}/delete_vxlan"
DELETE_CONTAINERS_PROVIDER1_ENDPOINT="${BASE_URL_PROVIDER1}/delete_docker_service?name=federated-mec-app"

## Provider 2 (winner with lowest offer)
EXPERIMENTS_PROVIDER2_ENDPOINT="${BASE_URL_PROVIDER2}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=18"
DELETE_VXLAN_RESOURCES_PROVIDER2_ENDPOINT="${BASE_URL_PROVIDER2}/delete_vxlan"
DELETE_CONTAINERS_PROVIDER2_ENDPOINT="${BASE_URL_PROVIDER2}/delete_docker_service?name=federated-mec-app"

## Provider 3
EXPERIMENTS_PROVIDER3_ENDPOINT="${BASE_URL_PROVIDER3}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=30"

## Provider 4
EXPERIMENTS_PROVIDER4_ENDPOINT="${BASE_URL_PROVIDER4}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=50"

## Provider 5
EXPERIMENTS_PROVIDER5_ENDPOINT="${BASE_URL_PROVIDER5}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=40"

## Provider 6
EXPERIMENTS_PROVIDER6_ENDPOINT="${BASE_URL_PROVIDER6}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=45"

## Provider 7
EXPERIMENTS_PROVIDER7_ENDPOINT="${BASE_URL_PROVIDER7}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=25"

## Provider 8
EXPERIMENTS_PROVIDER8_ENDPOINT="${BASE_URL_PROVIDER8}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=35"

## Provider 9
EXPERIMENTS_PROVIDER9_ENDPOINT="${BASE_URL_PROVIDER9}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=70"

## Provider 10
EXPERIMENTS_PROVIDER10_ENDPOINT="${BASE_URL_PROVIDER10}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=60"

## Provider 11
EXPERIMENTS_PROVIDER11_ENDPOINT="${BASE_URL_PROVIDER11}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=32"

## Provider 12
EXPERIMENTS_PROVIDER12_ENDPOINT="${BASE_URL_PROVIDER12}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=25"

## Provider 13
EXPERIMENTS_PROVIDER13_ENDPOINT="${BASE_URL_PROVIDER13}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=28"

## Provider 14
EXPERIMENTS_PROVIDER14_ENDPOINT="${BASE_URL_PROVIDER14}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=21"

## Provider 15
EXPERIMENTS_PROVIDER15_ENDPOINT="${BASE_URL_PROVIDER15}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=39"

## Provider 16
EXPERIMENTS_PROVIDER16_ENDPOINT="${BASE_URL_PROVIDER16}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=47"

## Provider 17
EXPERIMENTS_PROVIDER17_ENDPOINT="${BASE_URL_PROVIDER17}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=55"

## Provider 18
EXPERIMENTS_PROVIDER18_ENDPOINT="${BASE_URL_PROVIDER18}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=52"

## Provider 19
EXPERIMENTS_PROVIDER19_ENDPOINT="${BASE_URL_PROVIDER19}/start_experiments_provider?export_to_csv=${EXPORT_RESULTS}&price=15"

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

    # Start the provider2 experiment in the background and save the log
    curl -X POST "${EXPERIMENTS_PROVIDER2_ENDPOINT}" -o "${LOGS_DIR}/provider2_output_test${test_number}.txt" &

    # # Start the provider3 experiment in the background and save the log
    # curl -X POST "${EXPERIMENTS_PROVIDER3_ENDPOINT}" -o "${LOGS_DIR}/provider3_output_test${test_number}.txt" &

    # # Start the provider4 experiment in the background and save the log
    # curl -X POST "${EXPERIMENTS_PROVIDER4_ENDPOINT}" -o "${LOGS_DIR}/provider4_output_test${test_number}.txt" &

    # # Start the provider5 experiment in the background and save the log
    # curl -X POST "${EXPERIMENTS_PROVIDER5_ENDPOINT}" -o "${LOGS_DIR}/provider5_output_test${test_number}.txt" &

    # # Start the provider6 experiment in the background and save the log
    # curl -X POST "${EXPERIMENTS_PROVIDER6_ENDPOINT}" -o "${LOGS_DIR}/provider6_output_test${test_number}.txt" &

    # # Start the provider7 experiment in the background and save the log
    # curl -X POST "${EXPERIMENTS_PROVIDER7_ENDPOINT}" -o "${LOGS_DIR}/provider7_output_test${test_number}.txt" &

    # # Start the provider8 experiment in the background and save the log
    # curl -X POST "${EXPERIMENTS_PROVIDER8_ENDPOINT}" -o "${LOGS_DIR}/provider8_output_test${test_number}.txt" &

    # # Start the provider9 experiment in the background and save the log
    # curl -X POST "${EXPERIMENTS_PROVIDER9_ENDPOINT}" -o "${LOGS_DIR}/provider9_output_test${test_number}.txt" &

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
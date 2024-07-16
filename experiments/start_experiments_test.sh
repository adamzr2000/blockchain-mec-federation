#!/bin/bash

# Constants
LOGS_DIR="logs"
EXPORT_RESULTS="true"

# Set the number of providers here
NUMBER_OF_PROVIDERS=29 

# Base URLs
BASE_URL_CONSUMER="http://10.5.99.1:8000"

BASE_URLS_PROVIDER=("http://10.5.99.2:8000" "http://10.5.99.3:8000" "http://10.5.99.4:8000" "http://10.5.99.5:8000"
"http://10.5.99.6:8000" "http://10.5.99.7:8000" "http://10.5.99.8:8000" "http://10.5.99.9:8000"
"http://10.5.99.10:8000" "http://10.5.99.11:8000" "http://10.5.99.12:8000" "http://10.5.99.13:8000"
"http://10.5.99.14:8000" "http://10.5.99.15:8000" "http://10.5.99.16:8000" "http://10.5.99.17:8000"
"http://10.5.99.18:8000" "http://10.5.99.19:8000" "http://10.5.99.20:8000" "http://10.5.99.21:8000"
"http://10.5.99.22:8000" "http://10.5.99.23:8000" "http://10.5.99.24:8000" "http://10.5.99.25:8000"
"http://10.5.99.26:8000" "http://10.5.99.27:8000" "http://10.5.99.28:8000" "http://10.5.99.29:8000"
"http://10.5.99.30:8000" "http://10.5.99.31:8000" "http://10.5.99.32:8000" "http://10.5.99.33:8000"
"http://10.5.99.34:8000" "http://10.5.99.35:8000" "http://10.5.99.36:8000" "http://10.5.99.37:8000"
"http://10.5.99.38:8000" "http://10.5.99.39:8000" "http://10.5.99.40:8000" "http://10.5.99.41:8000"
"http://10.5.99.42:8000" "http://10.5.99.43:8000" "http://10.5.99.44:8000" "http://10.5.99.45:8000"
"http://10.5.99.46:8000" "http://10.5.99.47:8000" "http://10.5.99.48:8000" "http://10.5.99.49:8000"
"http://10.5.99.50:8000")

# Function to generate random prices ensuring provider1 is the lowest
generate_prices() {
    local num_providers=$1
    PRICES=(10) # Provider1 price is set to a low value
    for ((i=1; i<num_providers; i++)); do
        PRICES+=($((RANDOM % 90 + 11))) # Random prices between 11 and 100 for other providers
    done
}

# Consumer Endpoints
EXPERIMENTS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/start_experiments_consumer?export_to_csv=${EXPORT_RESULTS}&providers=${NUMBER_OF_PROVIDERS}"
DEPLOY_CONTAINERS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/deploy_docker_service?image=mec-app&name=mec-app&network=bridge&replicas=1"
DELETE_VXLAN_RESOURCES_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/delete_vxlan"
DELETE_CONTAINERS_CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/delete_docker_service?name=mec-app"

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

# Function to generate start experiments function based on the number of providers
generate_start_experiments_function() {
    local num_providers=$1
    echo "# Function to start experiments"
    echo "start_experiments() {"
    echo "    local test_number=\$1"
    echo ""
    echo "    # Deploy consumer container"
    echo "    deploy_consumer_container"
    echo ""
    for ((i=0; i<num_providers; i++)); do
        echo "    # Start the provider$((i+1)) experiment in the background and save the log"
        echo "    EXPERIMENTS_PROVIDER_ENDPOINT=\"\${BASE_URLS_PROVIDER[$i]}/start_experiments_provider?export_to_csv=\${EXPORT_RESULTS}&price=\${PRICES[$i]}\""
        echo "    curl -X POST \"\${EXPERIMENTS_PROVIDER_ENDPOINT}\" -o \"\${LOGS_DIR}/provider$((i+1))_output_test\${test_number}.txt\" &"
        echo ""
    done
    echo "    # Start the consumer experiment, wait for it to finish, and save the log"
    echo "    curl -X POST \"\${EXPERIMENTS_CONSUMER_ENDPOINT}\" -o \"\${LOGS_DIR}/consumer_output_test\${test_number}.txt\""
    echo ""
    echo "    # Ensure background processes have finished"
    echo "    wait"
    echo ""
    echo "    # Cleanup resources"
    echo "    cleanup_resources"
    echo "}"
}

# Function to cleanup resources (only for consumer and provider1)
cleanup_resources() {
    DELETE_CONTAINERS_PROVIDER1_ENDPOINT="${BASE_URLS_PROVIDER[0]}/delete_docker_service?name=federated-mec-app"
    DELETE_VXLAN_RESOURCES_PROVIDER1_ENDPOINT="${BASE_URLS_PROVIDER[0]}/delete_vxlan"

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

# Generate random prices for providers
generate_prices $NUMBER_OF_PROVIDERS

# Generate the start_experiments function based on the number of providers
eval "$(generate_start_experiments_function $NUMBER_OF_PROVIDERS)"

# Run the experiments
run_experiments $num_tests

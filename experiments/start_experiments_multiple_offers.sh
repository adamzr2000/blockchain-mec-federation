#!/bin/bash

# Constants
EXPORT_RESULTS="false"

# Base URLs
BASE_URLS=(
    "http://10.5.99.1:8000" "http://10.5.99.2:8000" "http://10.5.99.3:8000" "http://10.5.99.4:8000"
    "http://10.5.99.5:8000" "http://10.5.99.6:8000" "http://10.5.99.7:8000" "http://10.5.99.8:8000"
    "http://10.5.99.9:8000" "http://10.5.99.10:8000" "http://10.5.99.11:8000" "http://10.5.99.12:8000"
    "http://10.5.99.13:8000" "http://10.5.99.14:8000" "http://10.5.99.15:8000" "http://10.5.99.16:8000"
    "http://10.5.99.17:8000" "http://10.5.99.18:8000" "http://10.5.99.19:8000" "http://10.5.99.20:8000"
    "http://10.5.99.21:8000" "http://10.5.99.22:8000" "http://10.5.99.23:8000" "http://10.5.99.24:8000"
    "http://10.5.99.25:8000" "http://10.5.99.26:8000" "http://10.5.99.27:8000" "http://10.5.99.28:8000"
    "http://10.5.99.29:8000" "http://10.5.99.30:8000"
)

# Function to generate random prices for providers
generate_prices() {
    local num_providers=$1
    PRICES=() # Initialize an empty array for prices
    for ((i=0; i<num_providers; i++)); do
        PRICES+=($((RANDOM % 91 + 10))) # Random prices between 10 and 100 for all providers
    done
}

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
    local endpoint=$1
    curl -X POST "${endpoint}/deploy_docker_service?image=mec-app&name=mec-app&network=bridge&replicas=1" | jq
    sleep 2
}

# Function to generate start experiments function based on the number of providers
generate_start_experiments_function() {
    local num_consumers=$1
    local num_providers=$2
    local total_participants=$((num_consumers + num_providers))
    local providers_to_wait=$((num_providers / num_consumers))

    echo "# Function to start experiments"
    echo "start_experiments() {"
    echo "    local test_number=\$1"
    echo ""
    echo "    # Deploy consumer containers"
    for ((i=0; i<num_consumers; i++)); do
        echo "    deploy_consumer_container \"\${BASE_URLS[$i]}\""
        echo ""
    done
    echo "    # Generate random prices for providers"
    echo "    generate_prices $num_providers"
    echo ""
    local consumer_index=0
    for ((i=num_consumers; i<total_participants; i++)); do
        local consumer_domain="consumer-$((consumer_index + 1))"
        echo "    # Start the provider$((i-num_consumers+1)) experiment in the background"
        echo "    EXPERIMENTS_PROVIDER_ENDPOINT=\"\${BASE_URLS[$i]}/start_experiments_provider_v2?export_to_csv=\${EXPORT_RESULTS}&price=\${PRICES[$((i-num_consumers))]}&matching_domain_name=${consumer_domain}\""
        echo "    echo Running: curl -X POST \"\${EXPERIMENTS_PROVIDER_ENDPOINT}\" &"
        echo "    curl -X POST \"\${EXPERIMENTS_PROVIDER_ENDPOINT}\" &"
        echo ""
        consumer_index=$(( (consumer_index + 1) % num_consumers ))
    done
    echo "    # Start the consumer experiments and wait for them to finish"
    for ((i=0; i<num_consumers-1; i++)); do
        echo "    EXPERIMENTS_CONSUMER_ENDPOINT=\"\${BASE_URLS[$i]}/start_experiments_consumer_v2?export_to_csv=\${EXPORT_RESULTS}&providers=$providers_to_wait\""
        echo "    echo Running: curl -X POST \"\${EXPERIMENTS_CONSUMER_ENDPOINT}\" &"
        echo "    curl -X POST \"\${EXPERIMENTS_CONSUMER_ENDPOINT}\" &"
        echo ""
    done
     # Start the last consumer experiment without running it in the background
    echo "    EXPERIMENTS_CONSUMER_ENDPOINT=\"\${BASE_URLS[$((num_consumers-1))]}/start_experiments_consumer_v2??export_to_csv=\${EXPORT_RESULTS}&providers=$providers_to_wait\""
    echo "    curl -X POST \"\${EXPERIMENTS_CONSUMER_ENDPOINT}\""
    echo ""
    echo "    # Ensure background processes have finished"
    echo "    wait"
    echo ""
    echo "    # Cleanup resources"
    echo "    cleanup_resources $num_consumers $num_providers"
    echo "}"
}

# Function to cleanup resources for consumers and the winning provider
cleanup_resources() {
    local num_consumers=$1
    local num_providers=$2
    local total_participants=$((num_consumers + num_providers))

    for ((i=0; i<num_consumers; i++)); do
        local endpoint="${BASE_URLS[$i]}"
        echo "Cleaning up consumer $((i+1)) at $endpoint"
        curl -X DELETE "${endpoint}/delete_docker_service?name=mec-app" | jq &
        sleep 2
        curl -X DELETE "${endpoint}/delete_vxlan" | jq &
    done

    for ((i=num_consumers; i<total_participants; i++)); do
        local endpoint="${BASE_URLS[$i]}"
        echo "Cleaning up provider $((i-num_consumers+1)) at $endpoint"
        curl -X DELETE "${endpoint}/delete_docker_service?name=federated-mec-app" | jq &
        sleep 2
        curl -X DELETE "${endpoint}/delete_vxlan" | jq &
    done

    echo "Waiting for all cleanup processes to complete..."
    wait
    echo "Cleanup completed."
}

# Main function to run experiments
run_experiments() {
    local num_tests=$1
    local num_consumers=$2
    local num_providers=$3

    for ((i=1; i<=num_tests; i++))
    do
        echo "Starting experiment $i of $num_tests..."
        start_experiments $i
        echo "Experiment $i completed."
    done

    echo "All experiments completed."
}

# Ask the user for the number of tests to run
read -p "Enter the number of tests to run (1-20): " num_tests

# Validate the input
validate_input $num_tests

# Ask the user for the number of consumers
read -p "Enter the number of consumers: " num_consumers

# Ask the user for the number of providers
read -p "Enter the number of providers: " num_providers

# Check that the total participants do not exceed available endpoints
if ((num_consumers + num_providers > 30)); then
    echo "The total number of participants cannot exceed 30."
    exit 1
fi

# Generate the start_experiments function based on the number of consumers and providers
eval "$(generate_start_experiments_function $num_consumers $num_providers)"

# Run the experiments
run_experiments $num_tests $num_consumers $num_providers
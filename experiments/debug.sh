#!/bin/bash

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

# Function to generate start experiments function based on the number of providers
generate_start_experiments_function() {
    local num_consumers=$1
    local num_providers=$2
    local total_participants=$((num_consumers + num_providers))

    echo "# Function to start experiments"
    echo "start_experiments() {"
    echo "    local test_number=\$1"
    echo ""
    echo "    # Simulate deploying consumer containers"
    for ((i=0; i<num_consumers; i++)); do
        echo "    echo Deploying consumer container: \${BASE_URLS[$i]}"
        echo "    echo Command: curl -X POST \${BASE_URLS[$i]}/deploy_docker_service?image=mec-app\&name=mec-app\&network=bridge\&replicas=1"
        echo ""
    done
    echo "    # Simulate generating random prices for providers"
    echo "    generate_prices $num_providers"
    echo "    echo Generated prices: \${PRICES[@]}"
    echo ""
    local consumer_index=0
    for ((i=num_consumers; i<total_participants; i++)); do
        local consumer_domain="consumer-$((consumer_index + 1))"
        echo "    # Simulate starting provider$((i-num_consumers+1)) experiment"
        echo "    echo Starting provider$((i-num_consumers+1)) experiment with matching domain ${consumer_domain} and price \${PRICES[$((i-num_consumers))]}"
        echo "    echo Command: curl -X POST \${BASE_URLS[$i]}/start_experiments_provider_v2?export_to_csv=true\&price=\${PRICES[$((i-num_consumers))]}\&matching_domain_name=${consumer_domain}"
        echo ""
        consumer_index=$(( (consumer_index + 1) % num_consumers ))
    done
    echo "    # Simulate starting consumer experiments"
    for ((i=0; i<num_consumers; i++)); do
        echo "    echo Starting consumer$((i+1)) experiment"
        echo "    echo Command: curl -X POST \${BASE_URLS[$i]}/start_experiments_consumer_v2?export_to_csv=true\&providers=$num_providers"
        echo ""
    done
    echo "    # Simulate ensuring background processes have finished"
    echo "    echo Waiting for all background processes to finish"
    echo "}"
}

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

# Simulate running the experiments
echo "Simulating experiments..."
start_experiments 1
echo "Simulation completed."

import time

# Constants
EXPORT_RESULTS = "true"
BASE_URLS = [
    "http://10.5.99.1:8000", "http://10.5.99.2:8000", "http://10.5.99.3:8000", "http://10.5.99.4:8000",
    "http://10.5.99.5:8000", "http://10.5.99.6:8000", "http://10.5.99.7:8000", "http://10.5.99.8:8000",
    "http://10.5.99.9:8000", "http://10.5.99.10:8000", "http://10.5.99.11:8000", "http://10.5.99.12:8000",
    "http://10.5.99.13:8000", "http://10.5.99.14:8000", "http://10.5.99.15:8000", "http://10.5.99.16:8000",
    "http://10.5.99.17:8000", "http://10.5.99.18:8000", "http://10.5.99.19:8000", "http://10.5.99.20:8000",
    "http://10.5.99.21:8000", "http://10.5.99.22:8000", "http://10.5.99.23:8000", "http://10.5.99.24:8000",
    "http://10.5.99.25:8000", "http://10.5.99.26:8000", "http://10.5.99.27:8000", "http://10.5.99.28:8000",
    "http://10.5.99.29:8000", "http://10.5.99.30:8000"
]

NUM_CONSUMERS = 20
NUM_PROVIDERS = 10
NUM_TESTS = 1  # Set the number of tests to run

def generate_prices():
    """ Generate prices for providers as [1, 2, 3, ... NUM_PROVIDERS] """
    return list(range(1, NUM_PROVIDERS + 1))

def deploy_consumer_container(endpoint):
    """ Deploy consumer container """
    print(f"DEBUG: Deploying consumer container at {endpoint}")
    print(f"DEBUG: curl -X POST {endpoint}/deploy_docker_service?image=mec-app&name=mec-app&network=bridge&replicas=1")

def run_command(command):
    """ Print the command that would be run """
    print(f"DEBUG: Running: {' '.join(command)}")

def cleanup_resources():
    """Clean up resources for consumer and provider nodes."""
    for i in range(1, NUM_CONSUMERS + 1):
        node_ip = f"10.5.99.{i}"
        service_url = f"http://{node_ip}:8000/delete_docker_service?name=mec-app_1"
        vxlan_url = f"http://{node_ip}:8000/delete_vxlan"
        run_command(["curl", "-X", "DELETE", service_url])
        run_command(["curl", "-X", "DELETE", vxlan_url])

    for i in range(1, NUM_PROVIDERS + 1):
        provider_node_ip = f"10.5.99.{NUM_CONSUMERS + i}"
        consumer_1 = 2 * i - 1
        consumer_2 = 2 * i
        vxlan_id_1 = 200 + consumer_1
        vxlan_id_2 = 200 + consumer_2
        
        service_url_1 = f"http://{provider_node_ip}:8000/delete_docker_service?name=federated-mec-app_1"
        service_url_2 = f"http://{provider_node_ip}:8000/delete_docker_service?name=federated-mec-app-2_1"
        vxlan_url_11 = f"http://{provider_node_ip}:8000/delete_vxlan?vxlan_id={vxlan_id_1}&docker_net_name=federated-net"
        vxlan_url_12 = f"http://{provider_node_ip}:8000/delete_vxlan?vxlan_id={vxlan_id_2}&docker_net_name=federated-net"
        vxlan_url_21 = f"http://{provider_node_ip}:8000/delete_vxlan?vxlan_id={vxlan_id_1}&docker_net_name=federated-net-2"
        vxlan_url_22 = f"http://{provider_node_ip}:8000/delete_vxlan?vxlan_id={vxlan_id_2}&docker_net_name=federated-net-2"

        run_command(["curl", "-X", "DELETE", service_url_1])
        run_command(["curl", "-X", "DELETE", service_url_2])
        run_command(["curl", "-X", "DELETE", vxlan_url_11])
        run_command(["curl", "-X", "DELETE", vxlan_url_12])
        run_command(["curl", "-X", "DELETE", vxlan_url_21])
        run_command(["curl", "-X", "DELETE", vxlan_url_22])

    print("DEBUG: Cleanup completed.")
    time.sleep(2)

def start_experiments(test_number):
    """ Start experiments based on the number of consumers and providers """
    total_participants = NUM_CONSUMERS + NUM_PROVIDERS

    print(f"DEBUG: Starting experiment {test_number}...")
    
    # Deploy consumer containers
    for i in range(NUM_CONSUMERS):
        deploy_consumer_container(BASE_URLS[i])
    
    # Generate prices for providers
    prices = generate_prices()
    print(f"DEBUG: Generated prices: {prices}")

    processes = []
    consumer_index = 0

    # Start the provider experiments
    for i in range(NUM_CONSUMERS, total_participants):
        price = prices[i - NUM_CONSUMERS]
        EXPERIMENTS_PROVIDER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_provider_v4?export_to_csv={EXPORT_RESULTS}&price={price}&offers={NUM_CONSUMERS}"
        run_command(["curl", "-X", "POST", EXPERIMENTS_PROVIDER_ENDPOINT])
        consumer_index = (consumer_index + 1) % NUM_CONSUMERS
    
    # Start the consumer experiments and wait for them to finish
    for i in range(NUM_CONSUMERS):
        matching_price = (i // 2) + 1  # Adjusted to match 2 consumers per provider
        EXPERIMENTS_CONSUMER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_consumer_v4?export_to_csv={EXPORT_RESULTS}&providers={NUM_PROVIDERS}&matching_price={matching_price}"
        run_command(["curl", "-X", "POST", EXPERIMENTS_CONSUMER_ENDPOINT])

    print(f"DEBUG: Experiment {test_number} completed.")
    print("DEBUG: Cleaning up resources...")
    cleanup_resources()

def validate_input(num_tests):
    """ Validate the input """
    if num_tests < 1 or num_tests > 20:
        print("DEBUG: The number of tests must be between 1 and 20.")
        exit(1)

def run_experiments(num_tests):
    """ Main function to run experiments """
    for i in range(1, num_tests + 1):
        start_experiments(i)

    print("DEBUG: All experiments completed.")

if __name__ == "__main__":
    validate_input(NUM_TESTS)
    run_experiments(NUM_TESTS)

import subprocess
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

NUM_CONSUMERS = 25
NUM_PROVIDERS = 5
NUM_TESTS = 1  # Set the number of tests to run

def generate_prices():
    """ Generate prices for providers as [1, 2, 3, ... NUM_PROVIDERS] """
    return list(range(1, NUM_PROVIDERS + 1))

def deploy_consumer_container(endpoint):
    """ Simulate deploying consumer container """
    print(f"Simulating deployment of consumer container at {endpoint}")
    print(f"curl -X POST {endpoint}/deploy_docker_service?image=mec-app&name=mec-app&network=bridge&replicas=1")

def run_command(command):
    """ Simulate running a command and capture its output """
    print(f"Simulating: {' '.join(command)}")

def cleanup_resources():
    """Simulate cleaning up resources for consumer and provider nodes."""
    for i in range(1, NUM_CONSUMERS + 1):
        node_ip = f"10.5.99.{i}"
        vxlan_id = 200 + i
        service_url = f"http://{node_ip}:8000/delete_docker_service?name=mec-app_1"
        vxlan_url = f"http://{node_ip}:8000/delete_vxlan?vxlan_id={vxlan_id}&docker_net_name=federation-net"
        run_command(["curl", "-X", "DELETE", service_url])
        run_command(["curl", "-X", "DELETE", vxlan_url])

    for i in range(1, NUM_PROVIDERS + 1):
        provider_node_ip = f"10.5.99.{NUM_CONSUMERS + i}"

        # First delete the federated MEC apps
        for j in range(5):
            service_url = f"http://{provider_node_ip}:8000/delete_docker_service?name=federated-mec-app-{j}_1"
            run_command(["curl", "-X", "DELETE", service_url])
        
        # Then delete the VXLANs
        for j in range(5):
            consumer_index = (i - 1) * 5 + j + 1
            vxlan_id = 200 + consumer_index
            for k in range(5):
                vxlan_url = f"http://{provider_node_ip}:8000/delete_vxlan?vxlan_id={vxlan_id}&docker_net_name=federation-net-{k}"
                run_command(["curl", "-X", "DELETE", vxlan_url])

    print("Cleanup simulation completed.")
    time.sleep(2)

def start_experiments(test_number):
    """ Simulate starting experiments based on the number of consumers and providers """
    total_participants = NUM_CONSUMERS + NUM_PROVIDERS

    print(f"Starting experiment {test_number} simulation...")
    
    # Simulate deploying consumer containers
    for i in range(NUM_CONSUMERS):
        deploy_consumer_container(BASE_URLS[i])
    
    # Generate prices for providers
    prices = generate_prices()
    print(f"Generated prices: {prices}")

    processes = []
    consumer_index = 0

    # Simulate starting the provider experiments
    for i in range(NUM_CONSUMERS, total_participants):
        price = prices[i - NUM_CONSUMERS]
        EXPERIMENTS_PROVIDER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_provider_v4?export_to_csv={EXPORT_RESULTS}&price={price}&offers={NUM_CONSUMERS}"
        processes.append(run_command(["curl", "-X", "POST", EXPERIMENTS_PROVIDER_ENDPOINT]))
        consumer_index = (consumer_index + 1) % NUM_CONSUMERS
    
    # Simulate starting the consumer experiments
    for i in range(NUM_CONSUMERS):
        matching_price = (i // 5) + 1  # Adjusted to match 5 consumers per provider
        EXPERIMENTS_CONSUMER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_consumer_v4?export_to_csv={EXPORT_RESULTS}&providers={NUM_PROVIDERS}&matching_price={matching_price}"
        processes.append(run_command(["curl", "-X", "POST", EXPERIMENTS_CONSUMER_ENDPOINT]))
    
    print(f"Experiment {test_number} simulation completed.")
    print("Simulating cleanup of resources...")
    cleanup_resources()
    time.sleep(3)

def validate_input(num_tests):
    """ Validate the input """
    if num_tests < 1 or num_tests > 20:
        print("The number of tests must be between 1 and 20.")
        exit(1)

def run_experiments(num_tests):
    """ Main function to simulate running experiments """
    for i in range(1, num_tests + 1):
        start_experiments(i)

    print("All experiment simulations completed.")

if __name__ == "__main__":
    validate_input(NUM_TESTS)
    run_experiments(NUM_TESTS)

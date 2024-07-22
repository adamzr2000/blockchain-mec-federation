import time

# Constants
EXPORT_RESULTS = "false"
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

NUM_CONSUMERS = 10
NUM_PROVIDERS = 20
NUM_TESTS = 2  # Set the number of tests to run

def generate_prices():
    """ Generate prices for providers as [1, 2, 3, ... 20] """
    return list(range(1, NUM_PROVIDERS + 1))

def deploy_consumer_container(endpoint):
    """ Simulate deploying consumer container """
    print(f"Simulating deployment of consumer container at {endpoint}")

def run_command(command):
    """ Simulate running a command and print its output """
    print(f"Simulating: {' '.join(command)}")
    return None

def cleanup_resources():
    """ Simulate cleanup resources for consumers and the winning provider """
    for i in range(NUM_CONSUMERS):
        endpoint = BASE_URLS[i]
        print(f"Simulating cleanup for consumer {i+1} at {endpoint}")
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_docker_service?name=mec-app"])
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_vxlan"])

    for i in range(NUM_CONSUMERS, NUM_CONSUMERS + NUM_PROVIDERS):
        endpoint = BASE_URLS[i]
        print(f"Simulating cleanup for provider {i-NUM_CONSUMERS+1} at {endpoint}")
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_docker_service?name=federated-mec-app"])
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_vxlan"])

    print("Simulated cleanup completed.")
    time.sleep(2)

def start_experiments(test_number):
    """ Simulate starting experiments based on the number of consumers and providers """
    total_participants = NUM_CONSUMERS + NUM_PROVIDERS

    print(f"Starting simulated experiment {test_number}...")
    
    # Simulate deploying consumer containers
    for i in range(NUM_CONSUMERS):
        deploy_consumer_container(BASE_URLS[i])
    
    # Generate prices for providers
    prices = generate_prices()
    print(f"Simulated generated prices: {prices}")

    consumer_index = 0

    # Simulate starting the provider experiments
    for i in range(NUM_CONSUMERS, total_participants):
        matching_price = prices[i - NUM_CONSUMERS]
        EXPERIMENTS_PROVIDER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_provider_v3?export_to_csv={EXPORT_RESULTS}&providers={NUM_PROVIDERS}&matching_price={matching_price}"
        run_command(["curl", "-X", "POST", EXPERIMENTS_PROVIDER_ENDPOINT])
        consumer_index = (consumer_index + 1) % NUM_CONSUMERS
    
    # Simulate starting the consumer experiments
    for i in range(NUM_CONSUMERS - 1):
        price = (i + 1) * 2
        EXPERIMENTS_CONSUMER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_consumer_v3?export_to_csv={EXPORT_RESULTS}&price={price}&offers={total_participants}"
        run_command(["curl", "-X", "POST", EXPERIMENTS_CONSUMER_ENDPOINT])
    
    # Simulate starting the last consumer experiment without running it in the background
    price = NUM_CONSUMERS * 2
    EXPERIMENTS_CONSUMER_ENDPOINT = f"{BASE_URLS[NUM_CONSUMERS - 1]}/start_experiments_consumer_v3?export_to_csv={EXPORT_RESULTS}&price={price}&offers={total_participants}"
    run_command(["curl", "-X", "POST", EXPERIMENTS_CONSUMER_ENDPOINT])

    print(f"Simulated experiment {test_number} completed.")
    print("Simulating cleanup of resources...")
    cleanup_resources()

def validate_input(num_tests):
    """ Validate the input """
    if num_tests < 1 or num_tests > 20:
        print("The number of tests must be between 1 and 20.")
        exit(1)

def run_experiments(num_tests):
    """ Main function to simulate running experiments """
    for i in range(1, num_tests + 1):
        start_experiments(i)

    print("All simulated experiments completed.")

if __name__ == "__main__":
    validate_input(NUM_TESTS)
    run_experiments(NUM_TESTS)

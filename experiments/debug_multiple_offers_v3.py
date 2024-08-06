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

NUM_CONSUMERS = 10
NUM_PROVIDERS = 20
NUM_TESTS = 1  # Set the number of tests to run

def generate_prices():
    """ Generate prices for providers as [1, 2, 3, ... NUM_PROVIDERS] """
    return list(range(1, NUM_PROVIDERS + 1))

def deploy_consumer_container(endpoint):
    """ Deploy consumer container """
    print(f"Simulating deployment of consumer container at {endpoint}")

def run_command(command):
    """ Run a command and capture its output """
    print(f"Simulating: {' '.join(command)}")
    class Process:
        def wait(self):
            print("Simulating process wait")
    return Process()

def cleanup_resources(num_consumers, num_providers):
    """ Cleanup resources for consumers and the winning provider """
    for i in range(num_consumers):
        endpoint = BASE_URLS[i]
        print(f"Simulating cleanup of consumer {i+1} at {endpoint}")
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_docker_service?name=mec-app"]).wait()
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_vxlan"]).wait()

    for i in range(num_consumers, num_consumers + num_providers):
        endpoint = BASE_URLS[i]
        print(f"Simulating cleanup of provider {i-num_consumers+1} at {endpoint}")
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_docker_service?name=federated-mec-app"]).wait()
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_vxlan"]).wait()

    print("Simulated cleanup completed.")
    time.sleep(2)

def start_experiments(test_number):
    """ Start experiments based on the number of consumers and providers """
    total_participants = NUM_CONSUMERS + NUM_PROVIDERS

    print(f"Starting simulated experiment {test_number}...")
    
    # Deploy consumer containers
    for i in range(NUM_CONSUMERS):
        deploy_consumer_container(BASE_URLS[i])
    
    # Generate prices for providers
    prices = generate_prices()
    print(f"Simulated generated prices: {prices}")

    processes = []
    consumer_index = 0

    # Start the provider experiments
    for i in range(NUM_CONSUMERS, total_participants):
        price = prices[i - NUM_CONSUMERS]
        EXPERIMENTS_PROVIDER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_provider_v3?export_to_csv={EXPORT_RESULTS}&price={price}&offers={NUM_CONSUMERS}"
        processes.append(run_command(["curl", "-X", "POST", EXPERIMENTS_PROVIDER_ENDPOINT]))
        consumer_index = (consumer_index + 1) % NUM_CONSUMERS
    
    # Start the consumer experiments and wait for them to finish
    for i in range(NUM_CONSUMERS-1):
        matching_price = (i + 1) * 2
        EXPERIMENTS_CONSUMER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_consumer_v3?export_to_csv={EXPORT_RESULTS}&providers={NUM_PROVIDERS}&matching_price={matching_price}"
        processes.append(run_command(["curl", "-X", "POST", EXPERIMENTS_CONSUMER_ENDPOINT]))
    
    # Start the last consumer experiment without running it in the background
    matching_price = NUM_CONSUMERS * 2
    EXPERIMENTS_CONSUMER_ENDPOINT = f"{BASE_URLS[NUM_CONSUMERS - 1]}/start_experiments_consumer_v3?export_to_csv={EXPORT_RESULTS}&providers={NUM_PROVIDERS}&matching_price={matching_price}"
    run_command(["curl", "-X", "POST", EXPERIMENTS_CONSUMER_ENDPOINT]).wait()

    for process in processes:
        process.wait()

    print(f"Simulated experiment {test_number} completed.")
    print("Simulated cleanup of resources...")
    cleanup_resources(NUM_CONSUMERS, NUM_PROVIDERS)
    time.sleep(3)

def validate_input(num_tests):
    """ Validate the input """
    if num_tests < 1 or num_tests > 20:
        print("The number of tests must be between 1 and 20.")
        exit(1)

def run_experiments(num_tests):
    """ Main function to run experiments """
    for i in range(1, num_tests + 1):
        start_experiments(i)

    print("All simulated experiments completed.")

if __name__ == "__main__":
    validate_input(NUM_TESTS)
    run_experiments(NUM_TESTS)

import subprocess
import time
import random

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

def generate_prices(num_providers):
    """ Generate random prices for providers """
    prices = [random.randint(10, 100) for _ in range(num_providers)]
    return prices

def deploy_consumer_container(endpoint):
    """ Deploy consumer container """
    print(f"Deploying consumer container at {endpoint}")
    result = subprocess.run(
        ["curl", "-X", "POST", f"{endpoint}/deploy_docker_service?image=mec-app&name=mec-app&network=bridge&replicas=1"], 
        capture_output=True, text=True, check=True
    )
    print(result.stdout)

def run_command(command):
    """ Run a command and capture its output """
    print(f"Running: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return process

def cleanup_resources(num_consumers, num_providers):
    """ Cleanup resources for consumers and the winning provider """
    for i in range(num_consumers):
        endpoint = BASE_URLS[i]
        print(f"Cleaning up consumer {i+1} at {endpoint}")
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_docker_service?name=mec-app"]).wait()
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_vxlan"]).wait()

    for i in range(num_consumers, num_consumers + num_providers):
        endpoint = BASE_URLS[i]
        print(f"Cleaning up provider {i-num_consumers+1} at {endpoint}")
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_docker_service?name=federated-mec-app"]).wait()
        run_command(["curl", "-X", "DELETE", f"{endpoint}/delete_vxlan"]).wait()

    print("Cleanup completed.")
    time.sleep(2)

def start_experiments(test_number, num_consumers, num_providers):
    """ Start experiments based on the number of consumers and providers """
    total_participants = num_consumers + num_providers
    providers_to_wait = num_providers // num_consumers

    print(f"Starting experiment {test_number}...")
    
    # Deploy consumer containers
    for i in range(num_consumers):
        deploy_consumer_container(BASE_URLS[i])
    
    # Generate random prices for providers
    prices = generate_prices(num_providers)
    print(f"Generated prices: {prices}")

    processes = []
    consumer_index = 0

    # Start the provider experiments
    for i in range(num_consumers, total_participants):
        consumer_domain = f"consumer-{consumer_index + 1}"
        EXPERIMENTS_PROVIDER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_provider_v2?export_to_csv={EXPORT_RESULTS}&price={prices[i - num_consumers]}&matching_domain_name={consumer_domain}"
        processes.append(run_command(["curl", "-X", "POST", EXPERIMENTS_PROVIDER_ENDPOINT]))
        consumer_index = (consumer_index + 1) % num_consumers
    
    # Start the consumer experiments and wait for them to finish
    for i in range(num_consumers - 1):
        EXPERIMENTS_CONSUMER_ENDPOINT = f"{BASE_URLS[i]}/start_experiments_consumer_v2?export_to_csv={EXPORT_RESULTS}&providers={providers_to_wait}"
        processes.append(run_command(["curl", "-X", "POST", EXPERIMENTS_CONSUMER_ENDPOINT]))
    
    # Start the last consumer experiment without running it in the background
    EXPERIMENTS_CONSUMER_ENDPOINT = f"{BASE_URLS[num_consumers - 1]}/start_experiments_consumer_v2?export_to_csv={EXPORT_RESULTS}&providers={providers_to_wait}"
    run_command(["curl", "-X", "POST", EXPERIMENTS_CONSUMER_ENDPOINT]).wait()

    for process in processes:
        process.wait()

    print(f"Experiment {test_number} completed.")
    print("Cleaning up resources...")
    cleanup_resources(num_consumers, num_providers)

def validate_input(num_tests):
    """ Validate the input """
    if num_tests < 1 or num_tests > 20:
        print("The number of tests must be between 1 and 20.")
        exit(1)

def run_experiments(num_tests, num_consumers, num_providers):
    """ Main function to run experiments """
    for i in range(1, num_tests + 1):
        start_experiments(i, num_consumers, num_providers)

    print("All experiments completed.")

if __name__ == "__main__":
    num_tests = int(input("Enter the number of tests to run (1-20): "))
    validate_input(num_tests)

    num_consumers = int(input("Enter the number of consumers: "))
    num_providers = int(input("Enter the number of providers: "))

    if num_consumers + num_providers > 30:
        print("The total number of participants cannot exceed 30.")
        exit(1)

    run_experiments(num_tests, num_consumers, num_providers)

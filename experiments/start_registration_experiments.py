import subprocess
import time
import random

# Constants
EXPORT_RESULTS = "true"
NUM_PARTICIPANTS = 20
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


def run_command(command):
    """ Run a command and capture its output """
    print(f"Running: {' '.join(command)}")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return process

def cleanup_resources():
    """ Cleanup resources """
    for i in range(NUM_PARTICIPANTS):
        endpoint = BASE_URLS[i]
        print(f"Cleaning up participant {i+1} at {endpoint}")
        run_command(["curl", "-X", "DELETE", f"{endpoint}/unregister_domain"]).wait()
    print("Cleanup completed.")
    time.sleep(2)

def start_experiments(test_number):
    """ Start experiments based """

    print(f"Starting experiment {test_number}...")
    
    processes = []

    # Start the provider experiments
    for i in range(NUM_PARTICIPANTS):
        participant_name = f"participant{i + 1}"
        EXPERIMENTS_ENDPOINT = f"{BASE_URLS[i]}/register_domain?name={participant_name}&export_to_csv={EXPORT_RESULTS}&participants={NUM_PARTICIPANTS}"
        processes.append(run_command(["curl", "-X", "POST", EXPERIMENTS_ENDPOINT]))
    
    for process in processes:
        process.wait()

    print(f"Experiment {test_number} completed.")
    print("Cleaning up resources...")
    cleanup_resources()

def validate_input(num_tests):
    """ Validate the input """
    if num_tests < 1 or num_tests > 20:
        print("The number of tests must be between 1 and 20.")
        exit(1)

def run_experiments(num_tests):
    """ Main function to run experiments """
    for i in range(1, num_tests + 1):
        start_experiments(i)

    print("All experiments completed.")

if __name__ == "__main__":
    num_tests = int(input("Enter the number of tests to run (1-20): "))
    validate_input(num_tests)
    run_experiments(num_tests)

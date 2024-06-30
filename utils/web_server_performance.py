import requests
import time

# Configuration
consumer_url = 'http://localhost:5000/'
n_requests = 100  # Number of requests for latency and error rate tests
monitor_duration = 60  # Duration for monitoring availability (in seconds)

# Functions for measurements
def measure_latency(url, n_requests=10):
    latencies = []
    for _ in range(n_requests):
        start_time = time.time()
        try:
            response = requests.get(url)
            latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            latencies.append(latency)
        except requests.RequestException:
            latencies.append(None)
    return latencies

def measure_throughput(url, n_requests=10):
    start_time = time.time()
    for _ in range(n_requests):
        try:
            response = requests.get(url)
        except requests.RequestException:
            pass
    end_time = time.time()
    throughput = n_requests / (end_time - start_time)
    return throughput

def monitor_availability(url, duration=60):
    availability = []
    start_time = time.time()
    while time.time() - start_time < duration:
        availability.append(check_availability(url))
        time.sleep(1)  # Check every second
    return availability

def check_availability(url):
    try:
        response = requests.get(url)
        return response.status_code == 200
    except requests.RequestException:
        return False

def measure_error_rate(url, n_requests=10):
    error_count = 0
    for _ in range(n_requests):
        try:
            response = requests.get(url)
            if response.status_code != 200:
                error_count += 1
        except requests.RequestException:
            error_count += 1
    return error_count / n_requests * 100

# Perform measurements
latencies = measure_latency(consumer_url, n_requests)
throughput = measure_throughput(consumer_url, n_requests)
availability = monitor_availability(consumer_url, monitor_duration)
error_rate = measure_error_rate(consumer_url, n_requests)

# Print results
# print("Latency measurements (ms):", latencies)
average_latency = sum(latency for latency in latencies if latency is not None) / len([latency for latency in latencies if latency is not None])
print("Average Latency (ms):", average_latency)
print("Throughput (requests/second):", throughput)
print("Availability (%):", sum(availability) / len(availability) * 100)
print("Error Rate (%):", error_rate)

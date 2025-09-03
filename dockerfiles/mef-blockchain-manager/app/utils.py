# utils.py

import re
import logging
import csv
import ipaddress
import requests
import yaml
from pathlib import Path

# Get the logger defined in main.py
logger = logging.getLogger(__name__)

def extract_service_requirements(requirements):
    """
    Extracts service and replicas from the requirements string.

    Args:
    - requirements (str): String containing service and replicas in the format "service=A;replicas=B".

    Returns:
    - tuple: A tuple containing extracted service and replicas.
    """
    match = re.match(r'service=(.*?);replicas=(.*)', requirements)

    if match:
        requested_service = match.group(1)
        replicas = match.group(2)
        return requested_service, replicas
    else:
        logger.error(f"Invalid requirements format: {requirements}")
        return None, None

def extract_service_endpoint(endpoint):
    """
    Extracts the IP address, VXLAN ID, VXLAN port, and Docker subnet from the endpoint string.

    Args:
    - endpoint (str): String containing the endpoint information in the format "ip_address=A;vxlan_id=B;vxlan_port=C;docker_subnet=D".

    Returns:
    - tuple: A tuple containing the extracted IP address, VXLAN ID, VXLAN port, and Docker subnet.
    """
    match = re.match(r'ip_address=(.*?);vxlan_id=(.*?);vxlan_port=(.*?);docker_subnet=(.*)', endpoint)

    if match:
        ip_address = match.group(1)
        vxlan_id = match.group(2)
        vxlan_port = match.group(3)
        docker_subnet = match.group(4)
        return ip_address, vxlan_id, vxlan_port, docker_subnet
    else:
        logger.error(f"Invalid endpoint format: {endpoint}")
        return None, None, None, None

def create_csv_file(role, header, data):
    # Determine the base directory based on the role
    base_dir = Path("experiments") / role
    base_dir.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

    # Find the next available file index
    existing_files = list(base_dir.glob("federation_events_{}_test_*.csv".format(role)))
    indices = [int(f.stem.split('_')[-1]) for f in existing_files if f.stem.split('_')[-1].isdigit()]
    next_index = max(indices) + 1 if indices else 1

    # Construct the file name
    file_name = base_dir / f"federation_events_{role}_test_{next_index}.csv"

    # Open and write to the file
    with open(file_name, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)  # Write the header
        writer.writerows(data)  # Write the data

    logger.info(f"Data saved to {file_name}")

def create_csv_file_registration(participants, name, header, data):
    # Determine the base directory based on the role
    number_of_mec_systems = f"{participants}-mec-systems"
    base_dir = Path("experiments/registration-time") / number_of_mec_systems
    base_dir.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

    # Find the next available file index
    existing_files = list(base_dir.glob("federation_registration_{}_test_*.csv".format(name)))
    indices = [int(f.stem.split('_')[-1]) for f in existing_files if f.stem.split('_')[-1].isdigit()]
    next_index = max(indices) + 1 if indices else 1

    # Construct the file name
    file_name = base_dir / f"federation_registration_{name}_test_{next_index}.csv"

    # Open and write to the file
    with open(file_name, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)  # Write the header
        writer.writerows(data)  # Write the data

    logger.info(f"Data saved to {file_name}")


def extract_ip_from_url(url):
    # Regular expression pattern to match an IP address in a URL
    pattern = r'http://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):\d+'
    match = re.match(pattern, url)
    
    if match:
        return match.group(1)
    else:
        return None
    

def create_smaller_subnet(original_cidr, third_octet_value):
    # Split the CIDR notation into IP and subnet mask parts
    ip, _ = original_cidr.split('/')

    # Split the IP into its octets
    octets = ip.split('.')

    octets[2] = third_octet_value

    # Reassemble the IP address
    new_ip = '.'.join(octets)

    # Combine the new IP address with the new subnet mask /24
    new_cidr = f"{new_ip}/24"

    return new_cidr


def extract_domain_name_from_service_id(service_id):
    # Extracting the domain_name using regular expression
    match = re.search(r'service\d+-(.+)', service_id)
    if match:
        return match.group(1)
    else:
        return ""

def get_ip_range_from_subnet(subnet: str) -> str:
    try:
        # Parse the subnet
        network = ipaddress.ip_network(subnet)

        # Get the first and last IP address in the range
        first_ip = str(network.network_address + 1)  # Skip the network address
        last_ip = str(network.broadcast_address - 1)  # Skip the broadcast address

        # Return the range in "first_ip-last_ip" format
        return f"{first_ip}-{last_ip}"
    
    except ValueError as e:
        return f"Invalid subnet: {e}"

def validate_endpoint(endpoint: str) -> bool:
    """
    Validates the 'endpoint' string.
    Expected format: 'ip_address=<ip_address>;vxlan_id=<vxlan_id>;vxlan_port=<vxlan_port>;federation_net=<federation_net>'
    """
    pattern = r'^ip_address=\d{1,3}(\.\d{1,3}){3};vxlan_id=\d+;vxlan_port=\d+;federation_net=\d{1,3}(\.\d{1,3}){3}/\d+$'
    if re.match(pattern, endpoint):
        return True
    return False

def test_connectivity(api_url, target):
    payload = {"target": target}
    response = requests.post(f"{api_url}/test_connectivity", json=payload)
    return response.json()

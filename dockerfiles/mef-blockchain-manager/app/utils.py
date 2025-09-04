# utils.py

import re
import logging
import csv
import ipaddress
import time
import requests
from pathlib import Path

# Get the logger defined in main.py
logger = logging.getLogger(__name__)

def extract_service_endpoint(endpoint):
    """
    Extracts the IP address, VXLAN ID, VXLAN port, and Docker subnet from the endpoint string.

    Args:
    - endpoint (str): String containing the endpoint information in the format "ip_address=A;vxlan_id=B;vxlan_port=C;federation_net=D".

    Returns:
    - tuple: A tuple containing the extracted IP address, VXLAN ID, VXLAN port, and Docker subnet.
    """
    match = re.match(r'ip_address=(.*?);vxlan_id=(.*?);vxlan_port=(.*?);federation_net=(.*)', endpoint)

    if match:
        ip_address = match.group(1)
        vxlan_id = match.group(2)
        vxlan_port = match.group(3)
        federation_net = match.group(4)
        return ip_address, vxlan_id, vxlan_port, federation_net
    else:
        logger.error(f"Invalid endpoint format: {endpoint}")
        return None, None, None, None

def create_csv_file(file_path, header, data):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)  # ensure /experiments exists

    with open(file_path, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(data)
    logger.info(f"Data saved to {file_path}")
    
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
    # Split CIDR
    ip, _ = original_cidr.split('/')

    # Split IP into octets (strings)
    octets = ip.split('.')

    # Ensure the 3rd octet is a string and valid (0–255)
    if isinstance(third_octet_value, int):
        val = third_octet_value
    else:
        val = int(str(third_octet_value))

    if not (0 <= val <= 255):
        raise ValueError(f"Invalid third octet: {third_octet_value}")

    octets[2] = str(val)

    # Reassemble as /24
    new_ip = ".".join(octets)
    return f"{new_ip}/24"


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

# MEO request utilities
def deploy_service(meo_endpoint, image, name, net, replicas, timeout=60, interval=2.0):
    params = {"image": image, "name": name, "network": net, "replicas": replicas}
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            r = requests.post(meo_endpoint, params=params, timeout=10)
            if r.ok:
                d = r.json()
                if d.get("success") is True:
                    data = d.get("data", {})
                    return {
                        "service_name": data.get("service_name", {}).get("value"),
                        "container_ips": data.get("container_ips", {}) or {},
                        "message": d.get("message", "")
                    }
                last = d.get("message")
            else:
                last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def service_ips(meo_endpoint, name, timeout=60, interval=2.0):
    params={"name":name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.get(meo_endpoint,params=params,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True:
                    data=d.get("data",{})
                    return {"service_name":data.get("service_name",{}).get("value"),
                            "container_ips":data.get("container_ips",{}) or {},
                            "message":d.get("message","")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def delete_service(meo_endpoint, name, timeout=60, interval=2.0):
    params={"name":name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.delete(meo_endpoint,params=params,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True:
                    return {"message":d.get("message","deleted")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def exec_cmd(meo_endpoint, container_name, cmd, timeout=60, interval=1.0):
    params={"container_name":container_name,"cmd":cmd}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.post(meo_endpoint,params=params,timeout=15)
            if r.ok:
                d=r.json()
                if d.get("success") is True:
                    data=d.get("data",{})
                    return {
                        "container": data.get("container"),
                        "exit_code": data.get("exit_code"),
                        "stdout": data.get("stdout",""),
                        "stderr": data.get("stderr",""),
                        "message": d.get("message",""),
                    }
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def configure_vxlan(meo_endpoint, local_ip, remote_ip, interface_name, vxlan_id, dst_port, subnet, ip_range, docker_net_name, timeout=60, interval=2.0):
    p={"local_ip":local_ip,"remote_ip":remote_ip,"interface_name":interface_name,"vxlan_id":vxlan_id,"dst_port":dst_port,"subnet":subnet,"ip_range":ip_range,"docker_net_name":docker_net_name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.post(meo_endpoint,params=p,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True: return {"message":d.get("message","ok")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def delete_vxlan(meo_endpoint, vxlan_id, docker_net_name, timeout=60, interval=2.0):
    p={"vxlan_id":vxlan_id,"docker_net_name":docker_net_name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.delete(meo_endpoint,params=p,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True: return {"message":d.get("message","ok")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")

def attach_to_network(meo_endpoint, container_name, network_name, timeout=60, interval=2.0):
    p={"container_name":container_name,"network_name":network_name}
    end=time.time()+timeout; last=None
    while time.time()<end:
        try:
            r=requests.post(meo_endpoint,params=p,timeout=10)
            if r.ok:
                d=r.json()
                if d.get("success") is True: return {"message":d.get("message","ok")}
                last=d.get("message")
            else: last=f"HTTP {r.status_code}"
        except Exception as e: last=str(e)
        time.sleep(interval)
    raise RuntimeError(f"timeout: {last}")
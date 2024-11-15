import os
import json
import time
import yaml
import requests
import csv
import subprocess
import sys
import re
from pathlib import Path
import docker
import logging

from dotenv import load_dotenv, find_dotenv
from web3 import Web3, HTTPProvider, WebsocketProvider
from web3.middleware import geth_poa_middleware
from fastapi import FastAPI, HTTPException, Query

# Define your tags
tags_metadata = [
    {
        "name": "Default DLT federation functions",
        "description": "General DLT federation functions for both consumer and provider domains.",
    },
    {
        "name": "Consumer DLT federation functions",
        "description": "DLT federation functions for consumer domains.",
    },
    {
        "name": "Provider DLT federation functions",
        "description": "DLT federation functions for provider domains",
    },
]

app = FastAPI(
    title="DLT Service Federation API Documentation",
    openapi_tags=tags_metadata,
    description="""
- This API provides endpoints for interacting with the DLT and a custom-built Docker orchestrator.

- The federation procedures are stored and deployed on a Federation Smart Contract, which is running on top of a permissioned blockchain network (private PoA Ethereum).

- ADs communicate with the Federation Smart Contract through transactions.

---

### Federation steps:

**1) REGISTRATION (initial procedure)**

ADs register to the Federation SC with a single-transaction registration, using its unique blockchain address.

**2) ANNOUNCEMENT & NEGOTIATION**

Consumer AD announces that it needs service federation (service extension or new service).

Provider AD(s) listen for federation events. If they receive an offer, they analyze if they can satisfy the requirements and send back a positive answer with the service price.

**3) ACCEPTANCE & DEPLOYMENT**

Consumer AD analyzes all collected answers and chooses an offer of a single provider domain.

Provider AD starts the deployment of the requested federated service.

**4) USAGE & CHARGING**

Once the provider deploys the federated service, it notifies the consumer AD with connection details, and both domains establish data plane connectivity.

"""
)


# Function to check if an environment variable is set
def check_env_var(var_name):
    value = os.getenv(var_name)
    if not value:
        raise EnvironmentError(f"Environment variable {var_name} is not set.")
    return value

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from the federation .env file passed as a command-line argument
federation_env_file = os.getenv('FEDERATION_ENV_FILE')
if federation_env_file:
    load_dotenv(federation_env_file)
else:
    raise EnvironmentError("Environment variable FEDERATION_ENV_FILE is not set.")

# Load general environment variables from the dlt-node .env file
dlt_node_env_file = os.getenv('DLT_NODE_ENV_FILE')
if dlt_node_env_file:
    load_dotenv(dlt_node_env_file, override=True)
else:
    raise EnvironmentError("Environment variable DLT_NODE_ENV_FILE is not set.")

# Load general environment variables from the smart-contract .env file
smart_contract_env_file = os.getenv('SMART_CONTRACT_ENV_FILE')
if smart_contract_env_file:
    load_dotenv(smart_contract_env_file, override=True)
else:
    raise EnvironmentError("Environment variable SMART_CONTRACT_ENV_FILE is not set.")


# Load configuration from environment variables
domain = os.getenv('DOMAIN_FUNCTION').strip().lower()
domain_name = os.getenv('DOMAIN_NAME')
dlt_node_id = os.getenv('DLT_NODE_ID')
interface_name = os.getenv('INTERFACE_NAME')

# Configure Web3
eth_node_url = os.getenv(f'WS_NODE_{dlt_node_id}_URL')

try:
    web3 = Web3(WebsocketProvider(eth_node_url))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)

    # Check if connected to the Ethereum node
    if web3.isConnected():
        # Attempt to get the Geth version to confirm a successful connection
        geth_version = web3.clientVersion
        logger.info(f"Successfully connected to Ethereum node {eth_node_url} - Version: {geth_version}")
        
    else:
        logger.error(f"Failed to connect to the Ethereum node {eth_node_url}")
except Exception as e:
    logger.error(f"An error occurred while trying to connect to the Ethereum node: {e}")

# Load smart contract ABI
contract_abi = json.load(open("smart-contracts/build/contracts/Federation.json"))["abi"]
contract_address = web3.toChecksumAddress(os.getenv('CONTRACT_ADDRESS'))
Federation_contract = web3.eth.contract(abi=contract_abi, address=contract_address)

# Retrieve private key and blockchain address for the domain
private_key = os.getenv(f'PRIVATE_KEY_NODE_{dlt_node_id}')
block_address = os.getenv(f'ETHERBASE_NODE_{dlt_node_id}')

# General setup
ip_address = os.getenv(f'IP_NODE_{dlt_node_id}')

# Number that is used to prevent transaction replay attacks and ensure the order of transactions.
nonce = web3.eth.getTransactionCount(block_address)

# Address of the miner (node that adds a block to the blockchain)
coinbase = block_address

# Initialize variables
service_id = ''
service_endpoint_consumer = ''
service_consumer_address = ''
service_requirements = ''
bids_event = None
service_endpoint_provider = ''
federated_host = ''
service_price = 0
bid_index = 0
winner = coinbase
manager_address = ''
winnerChosen_event = None
domain_registered = False

vxlan_id = str(200+ int(dlt_node_id))
vxlan_port = str(int(4789) + int(dlt_node_id))
docker_subnet = f"10.{dlt_node_id}.0.0/16"
docker_ip_range = f"10.{dlt_node_id}.{dlt_node_id}.0/24"

# Initialize domain-specific configurations and variables
if domain == "consumer":
    # Consumer-specific variables
    service_endpoint_consumer = f"ip_address={ip_address};vxlan_id={vxlan_id};vxlan_port={vxlan_port};docker_subnet={docker_subnet}"
    # service_endpoint_consumer = ip_address
    service_consumer_address = block_address
    service_requirements = 'service=mec-app;replicas=1'
    bids_event = None  # Placeholder for event listener setup

else:  # Provider
    # Provider-specific variables
    service_endpoint_provider = f"ip_address={ip_address};vxlan_id={vxlan_id};vxlan_port={vxlan_port};docker_subnet={docker_subnet}"
    # service_endpoint_provider = ip_address
    federated_host = ''  # Placeholder for federated service deployment
    service_price = 0
    bid_index = 0
    manager_address = ''  # Placeholder for manager contract address
    winnerChosen_event = None  # Placeholder for event listener setup

# Validate connectivity to Docker and get the version information
try:
    client = docker.from_env()
    version_info = client.version()
    logger.info(f"Successfully connected to Docker daemon - Version: {version_info['Version']}")
except Exception as e:
    logger.error(f"Failed to connect to Docker daemon: {e}")

logger.info(f"Configuration completed for {domain_name} with IP address {ip_address}")

#-------------------------- Initialize TEST variables ------------------------------#
# List to store the timestamps of each federation step
federation_step_times = []
#----------------------------------------------------------------------------------#

def send_signed_transaction(build_transaction):
    """
    Sends a signed transaction to the blockchain network using the private key.
    
    Args:
        build_transaction (dict): The transaction data to be sent.
    
    Returns:
        str: The transaction hash of the sent transaction.
    """
    global nonce
    # Sign the transaction
    signed_txn = web3.eth.account.signTransaction(build_transaction, private_key)

    # Send the signed transaction
    tx_hash = web3.eth.sendRawTransaction(signed_txn.rawTransaction)

    # Increment the nonce
    nonce += 1

    return tx_hash.hex()

def AnnounceService():
    """
    Consumer AD announces the need for a federated service. 
    This transaction includes the service requirements, consumer's endpoint, and a unique service identifier.
    
    Returns:
        Filter: A filter for catching the 'NewBid' event that is emitted when a new bid is placed for the announced service.
    """
    global service_id
    # service_id = 'service' + str(int(time.time()))
    service_id = 'service' + str(int(time.time())) + '-' + domain_name
    announce_transaction = Federation_contract.functions.AnnounceService(
        _requirements=web3.toBytes(text=service_requirements),
        _endpoint_consumer=web3.toBytes(text=service_endpoint_consumer),
        _id=web3.toBytes(text=service_id)
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })
    
    # Send the signed transaction
    tx_hash = send_signed_transaction(announce_transaction)
    block = web3.eth.getBlock('latest')
    block_number = block['number']
    event_filter = Federation_contract.events.NewBid.createFilter(fromBlock=web3.toHex(block_number))    
    return event_filter

def GetBidInfo(bid_index):
    """
    Consumer AD retrieves information about a specific bid based on its index.
    
    Args:
        bid_index (int): The index of the bid for which information is requested.
    
    Returns:
        tuple: Contains information about the bid.
    """
    bid_info = Federation_contract.functions.GetBid(_id=web3.toBytes(text=service_id), bider_index=bid_index, _creator=block_address).call()
    return bid_info

def GetBidCount():
    bids_entered = Federation_contract.functions.GetBidCount(_id=web3.toBytes(text=service_id), _creator=block_address).call()
    return int(bids_entered)

def ChooseProvider(bid_index):
    """
    Consumer AD chooses a provider from the list of bids based on the bid index. 
    
    Args:
        bid_index (int): The index of the bid that identifies the chosen provider.
    """
    choose_transaction = Federation_contract.functions.ChooseProvider(
        _id=web3.toBytes(text=service_id),
        bider_index=bid_index
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })

    # Send the signed transaction
    tx_hash = send_signed_transaction(choose_transaction)

def GetServiceState(service_id):
    """
    Returns the current state of the service identified by the service ID.
    
    Args:
        service_id (str): The unique identifier of the service.
    
    Returns:
        int: The state of the service (0 for Open, 1 for Closed, 2 for Deployed).
    """    
    service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=service_id)).call()
    return service_state

def GetDeployedInfo(service_id, domain):
    """
    Consumer AD retrieves the deployment information of a service, including the service ID, provider's endpoint, and external IP (exposed IP for the federated service).
    
    Args:
        service_id (str): The unique identifier of the service.
    
    Returns:
        tuple: Contains the external IP and provider's endpoint of the deployed service.
    """    
    if domain == "consumer":
        service_id_bytes = web3.toBytes(text=service_id)  # Convert string to bytes
        service_id, service_endpoint_provider, federated_host = Federation_contract.functions.GetServiceInfo(
            _id=service_id_bytes, provider=False, call_address=block_address).call()
        _service_id = service_id.rstrip(b'\x00')  # Apply rstrip on bytes-like object
        _service_endpoint_provider = service_endpoint_provider.rstrip(b'\x00')
        _federated_host = federated_host.rstrip(b'\x00')
        return _federated_host, _service_endpoint_provider
    else:
        service_id_bytes = web3.toBytes(text=service_id)  # Convert string to bytes
        service_id, service_endpoint_provider, federated_host = Federation_contract.functions.GetServiceInfo(
            _id=service_id_bytes, provider=True, call_address=block_address).call()
        _service_id = service_id.rstrip(b'\x00')  # Apply rstrip on bytes-like object
        _service_endpoint_consumer = service_endpoint_provider.rstrip(b'\x00')
        _federated_host = ""
        return _federated_host, _service_endpoint_consumer

def ServiceAnnouncementEvent():
    """
    Creates a filter to catch the 'ServiceAnnouncement' event emitted when a service is announced. This function
    can be used to monitor new service announcements in real-time.
    
    Returns:
        Filter: A filter for catching the 'ServiceAnnouncement' event.
    """    
    block = web3.eth.getBlock('latest')
    blocknumber = block['number']
    # logger.info(f"Latest block: {blocknumber}")
    event_filter = Federation_contract.events.ServiceAnnouncement.createFilter(fromBlock=web3.toHex(blocknumber))
    return event_filter

def PlaceBid(service_id, service_price):
    """
    Provider AD places a bid offer for a service, including the service ID, offered price, and provider's endpoint.
    
    Args:
        service_id (str): The unique identifier of the service for which the bid is placed.
        service_price (int): The price offered for providing the service.
    
    Returns:
        Filter: A filter for catching the 'ServiceAnnouncementClosed' event that is emitted when a service
                announcement is closed.
    """
    place_bid_transaction = Federation_contract.functions.PlaceBid(
        _id=web3.toBytes(text=service_id),
        _price=service_price,
        _endpoint=web3.toBytes(text=service_endpoint_provider)
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })

    # Send the signed transaction
    tx_hash = send_signed_transaction(place_bid_transaction)

    block = web3.eth.getBlock('latest')
    block_number = block['number']
    # logger.info(f"Latest block: {block_number}")

    event_filter = Federation_contract.events.ServiceAnnouncementClosed.createFilter(fromBlock=web3.toHex(block_number))

    return event_filter

def CheckWinner(service_id):
    """
    Checks if the caller is the winning provider for a specific service after the consumer has chosen a provider.
    
    Args:
        service_id (str): The unique identifier of the service.
    
    Returns:
        bool: True if the caller is the winning provider, False otherwise.
    """
    state = GetServiceState(service_id)
    result = False
    if state == 1:
        result = Federation_contract.functions.isWinner(_id=web3.toBytes(text=service_id), _winner=block_address).call()
        # print("Am I a Winner? ", result)
    return result


def ServiceDeployed(service_id, federated_host):
    """
    Provider AD confirms the operation of a service deployment.
    This transaction includes the external IP and the service ID, and it records the successful deployment.
    
    Args:
        service_id (str): The unique identifier of the service.
        federated_host (str): The external IP address for the deployed service (~ exposed IP).
    """
    service_deployed_transaction = Federation_contract.functions.ServiceDeployed(
        info=web3.toBytes(text=federated_host),
        _id=web3.toBytes(text=service_id)
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })

    # Send the signed transaction
    tx_hash = send_signed_transaction(service_deployed_transaction)

def DisplayServiceState(service_id):
    """
    Displays the current state of a service based on its ID. The state is printed to the console.
    
    Args:
        service_id (str): The unique identifier of the service.
    """    
    current_service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=service_id)).call()
    if current_service_state == 0:
        print("\nService state", "Open")
    elif current_service_state == 1:
        print("\nService state", "Closed")
    elif current_service_state == 2:
        print("\nService state", "Deployed")
    else:
        logger.error(f"Error: state for service {service_id} is {current_service_state}")

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


def deploy_docker_containers(image, name, network, replicas, env_vars=None, container_port=5000, start_host_port=5000):
    containers = []
    try:
        for i in range(replicas):
            container_name = f"{name}_{i+1}"
            ports = {}
            if container_port is not None and start_host_port is not None:
                host_port = start_host_port + i
                ports[f'{container_port}/tcp'] = host_port

            container = client.containers.run(
                image=image,
                name=container_name,
                network=network,
                detach=True,
                auto_remove=True,
                ports=ports
            )
            containers.append(container)
        
        # Wait for containers to be ready
        for container in containers:
            while True:
                container.reload()
                if container.status == "running":
                    logger.info(f"Container {container_name} deployed successfully.")
                    break
                time.sleep(1)  # Brief pause to avoid tight loop

        return containers
    except Exception as e:
        logger.error(f"Failed to deploy containers: {e}")
        return []

def delete_docker_containers(name):
    try:
        containers = client.containers.list(all=True, filters={"name": name})
        for container in containers:
            container_name = container.name
            container.remove(force=True)
            
            # Wait for container to be removed
            while True:
                remaining_containers = client.containers.list(all=True, filters={"name": container_name})
                if not remaining_containers:
                    logger.info(f"Container {container_name} deleted successfully.")
                    break
                
    except Exception as e:
        logger.error(f"Failed to delete containers: {e}")

def scale_docker_containers(name, action, replicas):
    try:
        existing_containers = client.containers.list(all=True, filters={"name": name})
        current_replicas = len(existing_containers)
        
        if action.lower() == "up":
            new_replicas = current_replicas + replicas
            for i in range(current_replicas, new_replicas):
                container_name = f"{name}_{i+1}"
                container = client.containers.run(
                    image=existing_containers[0].image.tags[0],
                    name=container_name,
                    network=existing_containers[0].attrs['HostConfig']['NetworkMode'],
                    detach=True,
                    command="sh -c 'while true; do sleep 3600; done'"
                )
                logger.info(f"Container {container_name} deployed successfully.")
        elif action.lower() == "down":
            new_replicas = max(0, current_replicas - replicas)
            for i in range(current_replicas - 1, new_replicas - 1, -1):
                container_name = f"{name}_{i+1}"
                container = client.containers.get(container_name)
                container.remove(force=True)
                logger.info(f"Container {container_name} deleted successfully.")
        else:
            logger.error("Invalid action. Use 'up' or 'down'.")
            return
    except Exception as e:
        logger.error(f"Failed to scale containers: {e}")


def get_container_ips(name):
    container_ips = {}
    try:
        containers = client.containers.list(all=True, filters={"name": name})
        if not containers:
            logger.error(f"No containers found with name: {name}")
            return container_ips
        
        for container in containers:
            container.reload()  # Refresh container data
            network_settings = container.attrs['NetworkSettings']['Networks']
            for network_name, network_data in network_settings.items():
                ip_address = network_data['IPAddress']
                container_ips[container.name] = ip_address
                # print(f"Container {container.name} in network {network_name} has IP address: {ip_address}")
        return container_ips
    except Exception as e:
        print(f"Failed to get IP addresses for containers: {e}")
        return container_ips

def attach_container_to_network(container_name, network_name):
    try:
        # Retrieve the container
        container = client.containers.get(container_name)
    except NotFound:
        logger.error(f"Container '{container_name}' not found.")

    try:
        # Retrieve the network
        network = client.networks.get(network_name)
    except NotFound:
        logger.error(f"Network '{network_name}' not found.")

    try:
        # Attach the container to the network
        network.connect(container)
        logger.info(f"Container '{container_name}' successfully attached to network '{network_name}'.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

def execute_command_in_container(container_name, command):

    try:
        # Retrieve the container
        container = client.containers.get(container_name)
    except NotFound:
        logger.error(f"Container '{container_name}' not found.")
        return
    except APIError as e:
        logger.error(f"Error retrieving container '{container_name}': {str(e)}")
        return

    try:
        # Execute the command in the container
        result = container.exec_run(command, tty=True)
        if result.exit_code == 0:
            # logger.info(f"Successfully executed command '{command}' in container '{container_name}'.")
            print(result.output.decode('utf-8'))
        else:
            logger.error(f"Failed to execute command '{command}' in container '{container_name}'.")
            print(result.output.decode('utf-8'))
    except APIError as e:
        print(f"Error executing command '{command}' in container '{container_name}': {str(e)}")

# -------------------------------------------- Docker API FUNCTIONS --------------------------------------------#
@app.post("/deploy_docker_service", tags=["Docker Functions"], summary="Deploy docker service")
def deploy_docker_containers_endpoint(image: str, name: str, network: str, replicas: int):
    try:
        containers = deploy_docker_containers(image, name, network, replicas)
        ips = get_container_ips(name)
        return {"service-name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/delete_docker_service", tags=["Docker Functions"], summary="Delete docker service")
def delete_docker_containers_endpoint(name: str):
    try:
        delete_docker_containers(name)
        return {"message": f"Deleted containers with name {name} successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/configure_vxlan", tags=["Docker Functions"], summary="Configure Docker network and VXLAN")
def configure_docker_network_and_vxlan_endpoint(local_ip: str, remote_ip: str, interface_name: str, vxlan_id: str, dst_port: str, subnet: str, ip_range: str, docker_net_name: str = 'federation-net'):
    try:
        configure_docker_network_and_vxlan(local_ip, remote_ip, interface_name, vxlan_id, dst_port, subnet, ip_range,'netcom;', docker_net_name)
        return {"message": f"created federated docker network and vxlan connection successfully"}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

@app.delete("/delete_vxlan", tags=["Docker Functions"], summary="Delete Docker network and VXLAN")
def delete_docker_network_and_vxlan_endpoint(vxlan_id: str = '200', docker_net_name: str = 'federation-net'):
    try:
        delete_docker_network_and_vxlan('netcom;', vxlan_id, docker_net_name)
        return {"message": f"deleted federated docker network and vxlan configuration successfully"}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

# ------------------------------------------------------------------------------------------------------------------------------#



# -------------------------------------------- DLT API FUNCTIONS --------------------------------------------#
@app.get("/web3_info",
         summary="Get Web3 and Ethereum node info",
         tags=["Default DLT federation functions"],
         description="Endpoint to get Web3 and Ethereum node info")
async def web3_info_endpoint():
    try:
        logger.info(f"IP address: {ip_address}")
        logger.info(f"Ethereum address: {block_address}")
        logger.info(f"Ethereum node: {eth_node_url}")
        logger.info(f"Federation contract address: {contract_address}")
        message = {
            "ip-address": ip_address,
            "ethereum-node-url": eth_node_url,
            "ethereum-address": block_address,
            "contract-address": contract_address,
            "domain-name": domain_name,
            "service-id": service_id
        }
        return {"web3-info": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tx_receipt",
         summary="Get transaction receipt for a specified transaction hash",
         tags=["Default DLT federation functions"],
         description="""
         This endpoint retrieves and provides detailed information about a specific transaction on the Ethereum blockchain. 
         The transaction receipt includes:

         - **Block Details**: Information about the block containing the transaction, including the block hash and block number.
         - **Gas Usage**: The amount of gas used by this transaction (`gasUsed`) and the cumulative gas used by this and preceding transactions in the block (`cumulativeGasUsed`).
         - **Transaction Status**: Indicates if the transaction was successful (`status` is `1`) or failed (`status` is `0`).
         - **Sender and Receiver**: The address of the sender (`from`) and the recipient (`to`).
         - **Logs**: An array of logs generated by this transaction, each containing details like the log's address, topics, data, and more.
         - **Bloom Filter**: A bloom filter representing all logs generated by the transaction, used for quick log lookups.
         - **Effective Gas Price**: The actual gas price paid by the transaction.
         
         This receipt helps users understand the outcome and impact of their transactions on the blockchain.
         """)
async def tx_receipt_endpoint(tx_hash: str):
    try:
        # Get the transaction receipt
        receipt = web3.eth.get_transaction_receipt(tx_hash)

        if receipt:
            # Convert HexBytes to strings for JSON serialization
            receipt_dict = dict(receipt)
            receipt_dict['blockHash'] = receipt_dict['blockHash'].hex()
            receipt_dict['transactionHash'] = receipt_dict['transactionHash'].hex()
            receipt_dict['logsBloom'] = receipt_dict['logsBloom'].hex()
            receipt_dict['logs'] = [dict(log) for log in receipt_dict['logs']]
            for log in receipt_dict['logs']:
                log['blockHash'] = log['blockHash'].hex()
                log['transactionHash'] = log['transactionHash'].hex()
                log['topics'] = [topic.hex() for topic in log['topics']]

            return receipt_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# # @app.post("/register_domain",
# #           summary="Register a domain",
# #           tags=["Default DLT federation functions"],
# #           description="Endpoint to register a domain in the smart contract")
# # def register_domain_endpoint(name: str = domain_name, export_to_csv: bool = False, participants: int = 2):
# #     global domain_registered
# #     global nonce
# #     header = ['step', 'timestamp']
# #     data = []

# #     try:
# #         if not domain_registered:
# #             # Record the time when the transaction is being sent
# #             send_time = time.time()
# #             data.append(["send_registration_transaction", send_time])

# #             # Build the transaction for the addOperator function
# #             add_operator_transaction = Federation_contract.functions.addOperator(Web3.toBytes(text=name)).buildTransaction({
# #                 'from': block_address,
# #                 'nonce': nonce,
# #             })

# #             # Send the signed transaction
# #             tx_hash = send_signed_transaction(add_operator_transaction)

# #             # Wait for the transaction receipt
# #             receipt = web3.eth.waitForTransactionReceipt(tx_hash)

# #             # Record the time when the transaction is confirmed
# #             confirm_time = time.time()
# #             data.append(["confirm_registration_transaction", confirm_time])

# #             # Calculate the time taken for the transaction to be processed
# #             processing_time = confirm_time - send_time

# #             if receipt.status == 1:  # Transaction was successful
# #                 domain_registered = True
# #                 logger.info(f"Domain {name} has been registered in {processing_time:.2f} seconds")

# #                 if export_to_csv:
# #                     create_csv_file_registration(participants, name, header, data)

# #                 return {"tx-hash": tx_hash, "processing_time": processing_time}
# #             else:
# #                 raise HTTPException(status_code=500, detail="Transaction failed")

# #         else:
# #             error_message = f"Domain {name} is already registered in the SC"
# #             raise HTTPException(status_code=500, detail=error_message)
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/register_domain",
          summary="Register a domain",
          tags=["Default DLT federation functions"],
          description="Endpoint to register a domain in the smart contract")
def register_domain_endpoint(name: str = domain_name, export_to_csv: bool = False, participants: int = 2):
    global domain_registered
    global nonce
    header = ['step', 'timestamp']
    data = []

    try:
        if not domain_registered:
            # Start time of the process
            process_start_time = time.time()
            # Record the time when the transaction is being sent
            send_time = time.time() - process_start_time
            data.append(["send_registration_transaction", send_time])

            # Build the transaction for the addOperator function
            add_operator_transaction = Federation_contract.functions.addOperator(Web3.toBytes(text=name)).buildTransaction({
                'from': block_address,
                'nonce': nonce,
            })

            # Send the signed transaction
            tx_hash = send_signed_transaction(add_operator_transaction)

            isRegistered=False

            block = web3.eth.getBlock('latest')
            block_number = block['number']
            event_filter = Federation_contract.events.OperatorRegistered.createFilter(fromBlock=web3.toHex(block_number))    

            while isRegistered == False:
                new_events = event_filter.get_all_entries()
                for event in new_events:
                    my_name = web3.toText(event['args']['name'])
                    my_name = my_name.rstrip('\x00')
                   
                    if name == my_name:
                        # Record the time when the transaction is confirmed
                        confirm_time = time.time() - process_start_time
                        data.append(["confirm_registration_transaction", confirm_time])
                        isRegistered = True
                        logger.info(f"Event: {event}")

            domain_registered = True

            total_duration = time.time() - process_start_time
            logger.info(f"Domain {name} has been registered in {total_duration:.2f} seconds")

            if export_to_csv:
                # Export the data to a csv file only if export_to_csv is True
                create_csv_file_registration(participants, name, header, data)
                logger.info(f"Data exported to CSV for {name}.")
            else:
                logger.warning("CSV export not requested.")
            
            return {"tx-hash": tx_hash}

        else:
            error_message = f"Domain {name} is already registered in the SC"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/unregister_domain",
          summary="Unregister a domain",
          tags=["Default DLT federation functions"],
          description="Endpoint to unregister a domain in the smart contract")
def unregister_domain_endpoint():
    global domain_registered
    global nonce

    try:
        if domain_registered:

            # Build the transaction for the addOperator function
            del_operator_transaction = Federation_contract.functions.removeOperator().buildTransaction({
                'from': block_address,
                'nonce': nonce,
            })

            # Send the signed transaction
            tx_hash = send_signed_transaction(del_operator_transaction)

            # Wait for the transaction receipt
            receipt = web3.eth.waitForTransactionReceipt(tx_hash)

            if receipt.status == 1:  # Transaction was successful
                domain_registered = False
                logger.info(f"Domain has been unregistered")

                return {"tx-hash": tx_hash}
            else:
                raise HTTPException(status_code=500, detail="Transaction failed")

        else:
            error_message = f"Domain is not registered in the SC"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/create_service_announcement",
          summary="Create a service announcement", 
          tags=["Consumer DLT federation functions"],
          description="Endpoint to create a service announcement")
def create_service_announcement_endpoint(requirements: str = service_requirements, endpoint: str = service_endpoint_consumer):
    global bids_event
    global service_id
    try:
        service_id = 'service' + str(int(time.time()))
        announce_transaction = Federation_contract.functions.AnnounceService(
            _requirements=web3.toBytes(text=requirements),
            _endpoint_consumer=web3.toBytes(text=endpoint),
            _id=web3.toBytes(text=service_id)
        ).buildTransaction({
            'from': block_address,
            'nonce': nonce
        })
        
        # Send the signed transaction
        tx_hash = send_signed_transaction(announce_transaction)
        block = web3.eth.getBlock('latest')
        block_number = block['number']
        bids_event = Federation_contract.events.NewBid.createFilter(fromBlock=web3.toHex(block_number))    

        logger.info(f"Service announcement sent to the SC - Service ID: {service_id}")
        return {"tx-hash": tx_hash, "service-id": service_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_service_state",
         summary="Get service state",
         tags=["Default DLT federation functions"],
         description="Endpoint to get the state of a service (specified by its ID)")
async def check_service_state_endpoint(service_id: str):
    try:
        current_service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=service_id)).call()
        if current_service_state == 0:
            return {"state": "open"}
        elif current_service_state == 1:
            return {"state": "closed"}
        elif current_service_state == 2:
            return {"state": "deployed"}
        else:
            return { "error" : f"service-id {service_id}, state is {current_service_state}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_deployed_info",
         summary="Get deployed info",
         tags=["Default DLT federation functions"],
         description="Endpoint to get deployed info for a service.") 
async def check_deployed_info_endpoint(service_id: str):
    try:
        # Service deployed info
        federated_host, service_endpoint = GetDeployedInfo(service_id, domain)  
        return {"service-endpoint": service_endpoint.decode('utf-8'), "federated-host": federated_host.decode('utf-8')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/check_service_announcements",
         summary="Check announcements",
         tags=["Provider DLT federation functions"], 
         description="Endpoint to check for new announcements")
async def check_service_announcements_endpoint():
    try:
        new_service_event = Federation_contract.events.ServiceAnnouncement()  

        # Determine the current block number
        current_block = web3.eth.blockNumber

        # Calculate the start block for the event search (last 20 blocks)
        start_block = max(0, current_block - 20)  # Ensure start block is not negative

        # Fetch new events from the last 20 blocks
        new_events = new_service_event.createFilter(fromBlock=start_block, toBlock='latest').get_all_entries()

        open_services = []
        message = ""

        for event in new_events:
            service_id = web3.toText(event['args']['id']).rstrip('\x00')
            requirements = web3.toText(event['args']['requirements']).rstrip('\x00')
            tx_hash = web3.toHex(event['transactionHash'])
            address = event['address']
            block_number = event['blockNumber']
            event_name = event['event']

            if GetServiceState(service_id) == 0:
                open_services.append(service_id)

        if len(open_services) > 0:
            service_details = {
                    "service-id": service_id,
                    "requirements": requirements,
                    "tx-hash": tx_hash,
                    "block": block_number,
                    "event_name": event_name
            }
            logger.info(f"Announcement received: {new_events}")
            return {"announcements": service_details}
        else:
            return {"error": "No new services announced in the last 20 blocks."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/place_bid",
          summary="Place a bid",
          tags=["Provider DLT federation functions"],
          description="Endpoint to place a bid for a service")
def place_bid_endpoint(service_id: str, service_price: int):
    global winnerChosen_event 
    try:
        place_bid_transaction = Federation_contract.functions.PlaceBid(
            _id=web3.toBytes(text=service_id),
            _price=service_price,
            _endpoint=web3.toBytes(text=service_endpoint_provider)
        ).buildTransaction({
            'from': block_address,
            'nonce': nonce
        })

        # Send the signed transaction
        tx_hash = send_signed_transaction(place_bid_transaction)

        block = web3.eth.getBlock('latest')
        block_number = block['number']
        # logger.info(f"Latest block: {block_number}")

        winnerChosen_event = Federation_contract.events.ServiceAnnouncementClosed.createFilter(fromBlock=web3.toHex(block_number))

        logger.info("Bid offer sent to the SC")
        return {"tx-hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/check_bids',
         summary="Check bids",
         tags=["Consumer DLT federation functions"],
         description="Endpoint to check bids for a service")  
async def check_bids_endpoint(service_id: str):
    global bids_event
    message = ""
    new_events = bids_event.get_all_entries()
    bidderArrived = False
    try:
        for event in new_events:
            # New bid received
            event_id = str(web3.toText(event['args']['_id']))
            # service id, service id, index of the bid
            logger.info(f"{service_id}, {web3.toText(event['args']['_id'])}, {event['args']['max_bid_index']}")
            bid_index = int(event['args']['max_bid_index'])
            bidderArrived = True 
            if int(bid_index) >= 1:
                bid_info = GetBidInfo(int(bid_index-1))
                logger.info(bid_info)
                message = {
                    "provider-address": bid_info[0],
                    "service-price": bid_info[1],
                    "bid-index": bid_info[2]
                }
                break
        if bidderArrived:
            return {"bids": message}

        else:
            return {"error": f"No bids found for the service {service_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/choose_provider',
          summary="Choose provider",
          tags=["Consumer DLT federation functions"],
          description="Endpoint to choose a provider")
def choose_provider_endpoint(bid_index: int, service_id: str):
    global bids_event
    try:
        new_events = bids_event.get_all_entries()
        for event in new_events:
            event_id = str(web3.toText(event['args']['_id'])).rstrip('\x00')
            logger.info(f"Provider chosen! (bid index: {bid_index})")

            choose_transaction = Federation_contract.functions.ChooseProvider(
                _id=web3.toBytes(text=service_id),
                bider_index=bid_index
            ).buildTransaction({
                'from': block_address,
                'nonce': nonce
            })

            # Send the signed transaction
            tx_hash = send_signed_transaction(choose_transaction)

            # Service closed (state 1)
        return {"tx-hash": tx_hash}    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_winner", 
         summary="Check for winner",
         tags=["Provider DLT federation functions"],
         description="Endpoint to check if there is a winner for a service")
async def check_winner_endpoint(service_id: str):
    global winnerChosen_event 
    try:
        new_events = winnerChosen_event.get_all_entries()
        winnerChosen = False
        # Ask to the Federation SC if there is a winner
        for event in new_events:
            event_serviceid = web3.toText(event['args']['_id']).rstrip('\x00')
            if event_serviceid == service_id:
                # Winner choosen
                winnerChosen = True
                break
        if winnerChosen:
            return {"winner-chosen": "yes"}
        else:
            return {"winner-chosen": "no"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_if_i_am_winner",
         summary="Check if I am winner",
         tags=["Provider DLT federation functions"],
         description="Endpoint to check if provider is the winner")
async def check_if_I_am_Winner_endpoint(service_id: str):
    try:
        am_i_winner = CheckWinner(service_id)
        if am_i_winner == True:
            logger.info(f"I am the winner for the service {service_id}")
            return {"am-i-winner": "yes"}
        else:
            logger.warning(f"I am not the winner for the service {service_id}")
            return {"am-i-winner": "no"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deploy_service",
          summary="Deploy service",
          tags=["Provider DLT federation functions"],
          description="Endpoint for provider to deploy service")
def deploy_service_endpoint(service_id: str, federated_host: str = "0.0.0.0"):
    try:
        if CheckWinner(service_id):
            ServiceDeployed(service_id, federated_host)
            service_deployed_transaction = Federation_contract.functions.ServiceDeployed(
                info=web3.toBytes(text=federated_host),
                _id=web3.toBytes(text=service_id)
            ).buildTransaction({
                'from': block_address,
                'nonce': nonce
            })

            # Send the signed transaction
            tx_hash = send_signed_transaction(service_deployed_transaction)


            logger.info("Service deployed")
            return {"tx-hash": tx_hash}
        else:
            return {"error": "You are not the winner"}   
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    


def configure_docker_network_and_vxlan(local_ip, remote_ip, interface_name, vxlan_id, dst_port, subnet, ip_range, sudo_password='netcom;', docker_net_name = 'federation-net'):
    script_path = './utils/docker_host_setup_vxlan.sh'
    
    # Construct the command with arguments
    command = [
        'sudo', '-S', 'bash', script_path,
        '-l', local_ip,
        '-r', remote_ip,
        '-i', interface_name,
        '-v', vxlan_id,
        '-p', dst_port,
        '-s', subnet,
        '-d', ip_range,
        '-n', docker_net_name
    ]

    try:
        # Run the command with sudo and password
        result = subprocess.run(command, input=sudo_password.encode() + b'\n', check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Print the output of the script
        print(result.stdout.decode())
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred while running the script: {e.stderr.decode()}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

def delete_docker_network_and_vxlan(sudo_password = 'netcom;', vxlan_id = 200, docker_net_name = 'federation-net'):
    script_path = './utils/clean_vxlan_config.sh'
    
    # Construct the command with arguments
    command = [
        'sudo', '-S', 'bash', script_path,
        '-n', docker_net_name,
        '-v', vxlan_id
    ]
    
    try:
        # Run the command with sudo and password
        result = subprocess.run(command, input=sudo_password.encode() + b'\n', check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Print the output of the script
        print(result.stdout.decode())
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occurred while running the script: {e.stderr.decode()}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")


def extract_ip_from_url(url):
    # Regular expression pattern to match an IP address in a URL
    pattern = r'http://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):\d+'
    match = re.match(pattern, url)
    
    if match:
        return match.group(1)
    else:
        return None

def create_smaller_subnet(original_cidr, dlt_node_id):
    # Split the CIDR notation into IP and subnet mask parts
    ip, _ = original_cidr.split('/')

    # Split the IP into its octets
    octets = ip.split('.')

    # Replace the third octet with the dlt_node_id
    octets[2] = dlt_node_id

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
# ------------------------------------------------------------------------------------------------------------------------------#
@app.post("/start_experiments_consumer")
def start_experiments_consumer(export_to_csv: bool = False, providers: int = 2):
    try:
        header = ['step', 'timestamp']
        data = []
        
        if domain == 'consumer':
            
            # Start time of the process
            process_start_time = time.time()
            
            global bids_event
            
            # Service Announcement Sent
            t_service_announced = time.time() - process_start_time
            data.append(['service_announced', t_service_announced])
            bids_event = AnnounceService()

            logger.info(f"Service Announcement sent to the SC - Service ID: {service_id}")

            # Consumer AD wait for provider bids
            bidderArrived = False

            logger.info("Waiting for bids...")
            while bidderArrived == False:
                new_events = bids_event.get_all_entries()
                for event in new_events:
                    
                    # # Bid Offer Received
                    # t_bid_offer_received = time.time() - process_start_time
                    # data.append(['bid_offer_received', t_bid_offer_received])

                    event_id = str(web3.toText(event['args']['_id']))
                    
                    # Choosing provider

                    # service id, service id, index of the bid
                    # print(service_id, web3.toText(event['args']['_id']), event['args']['max_bid_index'])
                    logger.info("Bid offer received")
                    bid_index = int(event['args']['max_bid_index'])
                    bidderArrived = True 

                    # Received bids
                    lowest_price = None
                    best_bid_index = 0

                    # Received bids
                    if int(bid_index) == providers:
                        # ------ #
                        t_bid_offer_received = time.time() - process_start_time
                        data.append(['bid_offer_received', t_bid_offer_received])
                        # ------ #
                        # Loop through all bid indices and print their information
                        for i in range(bid_index):
                            bid_info = GetBidInfo(i)
                            logger.info(f"Bid {i}: {bid_info}")
                            bid_price = int(bid_info[1]) 
                            if lowest_price is None or bid_price < lowest_price:
                                lowest_price = bid_price
                                best_bid_index = int(bid_info[2])
                                # logger.info(f"New lowest price: {lowest_price} with bid index: {best_bid_index}")

                            
                        # Winner choosen 
                        t_winner_choosen = time.time() - process_start_time
                        data.append(['winner_choosen', t_winner_choosen])
                        
                        ChooseProvider(best_bid_index)
                        logger.info(f"Provider Choosen - Bid Index: {best_bid_index}")

                        # Service closed (state 1)
                        #DisplayServiceState(service_id)
                        break

            # Consumer AD wait for provider confirmation
            serviceDeployed = False 
            while serviceDeployed == False:
                serviceDeployed = True if GetServiceState(service_id) == 2 else False
            
            # Confirmation received
            t_confirm_deployment_received = time.time() - process_start_time
            data.append(['confirm_deployment_received', t_confirm_deployment_received])
            
            t_establish_vxlan_connection_with_provider_start = time.time() - process_start_time
            data.append(['establish_vxlan_connection_with_provider_start', t_establish_vxlan_connection_with_provider_start])

            # Service deployed info
            federated_host, service_endpoint_provider = GetDeployedInfo(service_id, domain)
        
            federated_host = federated_host.decode('utf-8')
            service_endpoint_provider = service_endpoint_provider.decode('utf-8')

            endpoint_ip, endpoint_vxlan_id, endpoint_vxlan_port, endpoint_docker_subnet = extract_service_endpoint(service_endpoint_provider)

            logger.info(f"Federated Service Info - Service Endpoint Provider: {service_endpoint_provider}, Federated Host: {federated_host}")

            configure_docker_network_and_vxlan(ip_address, endpoint_ip, interface_name, '200', '4789', docker_subnet, docker_ip_range)

            attach_container_to_network("mec-app_1", "federation-net")

            t_establish_vxlan_connection_with_provider_finished = time.time() - process_start_time
            data.append(['establish_vxlan_connection_with_provider_finished', t_establish_vxlan_connection_with_provider_finished])
           
            total_duration = time.time() - process_start_time

            logger.info(f"Federation process completed in {total_duration:.2f} seconds")

            federated_host_ip = extract_ip_from_url(federated_host)
            if federated_host_ip is None:
                logger.error(f"Could not extract IP from '{federated_host}'")

            logger.info(f"Monitoring connection with federated host ({federated_host_ip})")
            monitor_connection_command = f"ping -c 10 {federated_host_ip}"
            execute_command_in_container("mec-app_1", monitor_connection_command)

            if export_to_csv:
                # Export the data to a csv file only if export_to_csv is True
                create_csv_file(domain, header, data)
                logger.info(f"Data exported to CSV for {domain}.")
            else:
                logger.warning("CSV export not requested.")

            return {"message": f"Federation process completed in {total_duration:.2f} seconds"}
        else:
            error_message = "You must be consumer to run this code"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    

@app.post("/start_experiments_provider")
def start_experiments_provider(export_to_csv: bool = False, price: int = 10):
    try:
        header = ['step', 'timestamp']
        data = []
        
        if domain == 'provider':
            
            # Start time of the process
            process_start_time = time.time()

            global winnerChosen_event 
            service_id = ''
            newService_event = ServiceAnnouncementEvent()
            newService = False
            open_services = []

            # Provider AD wait for service announcements
            logger.info("Subscribed to federation events...")
            while newService == False:
                new_events = newService_event.get_all_entries()
                for event in new_events:
                    service_id = web3.toText(event['args']['id'])
                    
                    requirements = web3.toText(event['args']['requirements'])

                    requested_service, requested_replicas = extract_service_requirements(requirements.rstrip('\x00'))
                    
                    if GetServiceState(service_id) == 0:
                        open_services.append(service_id)
                # print("OPEN =", len(open_services)) 
                if len(open_services) > 0:
                    
                    # Announcement received
                    t_announce_received = time.time() - process_start_time
                    data.append(['announce_received', t_announce_received])
                    
                    logger.info(f"Announcement Received - Service ID: {service_id}, Requested Service: {repr(requested_service)}, Requested Replicas: {repr(requested_replicas)}")
                    print(new_events)
                    newService = True
                
            service_id = open_services[-1]

            # Place a bid offer to the Federation SC
            t_bid_offer_sent = time.time() - process_start_time
            data.append(['bid_offer_sent', t_bid_offer_sent])
            winnerChosen_event = PlaceBid(service_id, price)

            logger.info(f"Bid Offer sent to the SC - Service ID: {service_id}, Price: {price} €")
            
            # Ask to the Federation SC if there is a winner (wait...)
        
            winnerChosen = False
            while winnerChosen == False:
                new_events = winnerChosen_event.get_all_entries()
                for event in new_events:
                    event_serviceid = web3.toText(event['args']['_id'])
                    if event_serviceid == service_id:
                        
                        # Winner choosen received
                        t_winner_received = time.time() - process_start_time
                        data.append(['winner_received', t_winner_received])
                        winnerChosen = True
                        break
            
            am_i_winner = False
            while am_i_winner == False:
                # Provider AD ask if he is the winner
                am_i_winner = CheckWinner(service_id)
                if am_i_winner == True:
                    logger.info(f"I am the winner for {service_id}")
                    # Start deployment of the requested federated service
                    logger.info("Start deployment of the requested federated service...")
                    t_deployment_start = time.time() - process_start_time
                    data.append(['deployment_start', t_deployment_start])
                    break
                else:
                    # If not the winner, log and return the message
                    logger.info(f"I am not the winner for {service_id}")
                    t_other_provider_choosen = time.time() - process_start_time
                    data.append(['other_provider_choosen', t_other_provider_choosen])
                    if export_to_csv:
                        # Export the data to a csv file only if export_to_csv is True
                        create_csv_file(domain, header, data)
                        logger.info(f"Data exported to CSV for {domain}.")
                        return {"message": f"I am not the winner for {service_id}"}
                    else:
                        logger.warning("CSV export not requested.")
                        return {"message": f"I am not the winner for {service_id}"}

            # Service deployed info
            federated_host, service_endpoint_consumer = GetDeployedInfo(service_id, domain)

            service_endpoint_consumer = service_endpoint_consumer.decode('utf-8')

            endpoint_ip, endpoint_vxlan_id, endpoint_vxlan_port, endpoint_docker_subnet = extract_service_endpoint(service_endpoint_consumer)
            net_range = create_smaller_subnet(endpoint_docker_subnet, dlt_node_id)

            logger.info(f"Service Endpoint Consumer: {service_endpoint_consumer}")

            # Sets up the federation docker network and the VXLAN network interface
            configure_docker_network_and_vxlan(ip_address, endpoint_ip, interface_name, '200', '4789', endpoint_docker_subnet, net_range)


            container_port=5000
            exposed_ports=5000

            # Deploy docker service and wait to be ready and get an IP address
            deploy_docker_containers(
                image=requested_service,
                name=f"federated-{requested_service}",
                network="federation-net",
                replicas=int(requested_replicas),
                env_vars={"SERVICE_ID": f"{domain_name} MEC system"},
                container_port=container_port,
                start_host_port=exposed_ports
            )          

            container_ips = get_container_ips(requested_service)
            if container_ips:
                first_container_name = next(iter(container_ips))
                federated_host = container_ips[first_container_name]
                        
            # Deployment finished
            t_deployment_finished = time.time() - process_start_time
            data.append(['deployment_finished', t_deployment_finished])
                
            # Deployment confirmation sent
            t_confirm_deployment_sent = time.time() - process_start_time
            data.append(['confirm_deployment_sent', t_confirm_deployment_sent])
            federated_host=f"http://{federated_host}:{exposed_ports}"
            ServiceDeployed(service_id, federated_host)

            total_duration = time.time() - process_start_time

            logger.info(f"Service Deployed - Federated Host: {federated_host}")
 
            DisplayServiceState(service_id)
                
            if export_to_csv:
                # Export the data to a csv file only if export_to_csv is True
                create_csv_file(domain, header, data)
                logger.info(f"Data exported to CSV for {domain}.")
            else:
                logger.warning("CSV export not requested.")

            return {"message": f"Federation process completed successfully - {domain}"}
        else:
            error_message = "You must be provider to run this code"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  
# ------------------------------------------------------------------------------------------------------------------------------#

# ------------------------------------------------------------------------------------------------------------------------------#
@app.post("/start_experiments_consumer_v2")
def start_experiments_consumer_v2(export_to_csv: bool = False, providers: int = 2):
    try:
        header = ['step', 'timestamp']
        data = []
        
        if domain == 'consumer':
            
            # Start time of the process
            process_start_time = time.time()
            
            global bids_event
            
            # Service Announcement Sent
            t_service_announced = time.time() - process_start_time
            data.append(['service_announced', t_service_announced])
            bids_event = AnnounceService()

            logger.info(f"Service Announcement sent to the SC - Service ID: {service_id}")

            # Consumer AD wait for provider bids
            bidderArrived = False

            logger.info("Waiting for bids...")
            while bidderArrived == False:
                new_events = bids_event.get_all_entries()
                for event in new_events:
                    
                    # # Bid Offer Received
                    # t_bid_offer_received = time.time() - process_start_time
                    # data.append(['bid_offer_received', t_bid_offer_received])

                    event_id = str(web3.toText(event['args']['_id']))
                    
                    # Choosing provider

                    # service id, service id, index of the bid
                    # print(service_id, web3.toText(event['args']['_id']), event['args']['max_bid_index'])
                    logger.info("Bid offer received")
                    bid_index = int(event['args']['max_bid_index'])
                    bidderArrived = True 

                    # Received bids
                    lowest_price = None
                    best_bid_index = 0

                    # Received bids
                    if int(bid_index) == providers:
                        # ------ #
                        t_bid_offer_received = time.time() - process_start_time
                        data.append(['bid_offer_received', t_bid_offer_received])
                        # ------ #
                        # Loop through all bid indices and print their information
                        for i in range(bid_index):
                            bid_info = GetBidInfo(i)
                            logger.info(f"Bid {i}: {bid_info}")
                            bid_price = int(bid_info[1]) 
                            if lowest_price is None or bid_price < lowest_price:
                                lowest_price = bid_price
                                best_bid_index = int(bid_info[2])
                                # logger.info(f"New lowest price: {lowest_price} with bid index: {best_bid_index}")

                            
                        # Winner choosen 
                        t_winner_choosen = time.time() - process_start_time
                        data.append(['winner_choosen', t_winner_choosen])
                        
                        ChooseProvider(best_bid_index)
                        logger.info(f"Provider Choosen - Bid Index: {best_bid_index}")

                        # Service closed (state 1)
                        #DisplayServiceState(service_id)
                        break

            # Consumer AD wait for provider confirmation
            serviceDeployed = False 
            while serviceDeployed == False:
                serviceDeployed = True if GetServiceState(service_id) == 2 else False
            
            # Confirmation received
            t_confirm_deployment_received = time.time() - process_start_time
            data.append(['confirm_deployment_received', t_confirm_deployment_received])
            
            t_establish_vxlan_connection_with_provider_start = time.time() - process_start_time
            data.append(['establish_vxlan_connection_with_provider_start', t_establish_vxlan_connection_with_provider_start])

            # Service deployed info
            federated_host, service_endpoint_provider = GetDeployedInfo(service_id, domain)
        
            federated_host = federated_host.decode('utf-8')
            service_endpoint_provider = service_endpoint_provider.decode('utf-8')

            logger.info(f"Federated Service Info - Service Endpoint Provider: {service_endpoint_provider}, Federated Host: {federated_host}")

            # Sets up the federation docker network and the VXLAN network interface
            configure_docker_network_and_vxlan(ip_address, service_endpoint_provider, interface_name, vxlan_id, vxlan_port, docker_subnet, docker_ip_range)

            attach_container_to_network("mec-app_1", "federation-net")

            t_establish_vxlan_connection_with_provider_finished = time.time() - process_start_time
            data.append(['establish_vxlan_connection_with_provider_finished', t_establish_vxlan_connection_with_provider_finished])
           
            total_duration = time.time() - process_start_time

            logger.info(f"Federation process completed in {total_duration:.2f} seconds")

            federated_host_ip = extract_ip_from_url(federated_host)
            if federated_host_ip is None:
                logger.error(f"Could not extract IP from '{federated_host}'")

            logger.info(f"Monitoring connection with federated host ({federated_host_ip})")
            monitor_connection_command = f"ping -c 10 {federated_host_ip}"
            execute_command_in_container("mec-app_1", monitor_connection_command)

            if export_to_csv:
                # Export the data to a csv file only if export_to_csv is True
                create_csv_file(domain, header, data)
                logger.info(f"Data exported to CSV for {domain}.")
            else:
                logger.warning("CSV export not requested.")

            return {"message": f"Federation process completed in {total_duration:.2f} seconds"}
        else:
            error_message = "You must be consumer to run this code"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    

@app.post("/start_experiments_provider_v2")
def start_experiments_provider_v2(export_to_csv: bool = False, price: int = 10, matching_domain_name: str = 'consumer-1'):
    try:
        header = ['step', 'timestamp']
        data = []
        
        if domain == 'provider':
            
            # Start time of the process
            process_start_time = time.time()

            global winnerChosen_event 
            service_id = ''
            newService_event = ServiceAnnouncementEvent()
            newService = False
            open_services = []

            # Provider AD wait for service announcements
            logger.info("Subscribed to federation events...")
            while newService == False:
                new_events = newService_event.get_all_entries()
                for event in new_events:
                    service_id = web3.toText(event['args']['id'])
                    
                    requirements = web3.toText(event['args']['requirements'])

                    requested_service, requested_replicas = extract_service_requirements(requirements.rstrip('\x00'))

                    offer_domain_owner = extract_domain_name_from_service_id(service_id)

                    # logger.info(f"Processing event - Service ID: {service_id}, Requirements: {requirements}, Requested Service: {requested_service}, Requested Replicas: {requested_replicas}, Offer Domain Owner: {offer_domain_owner}, Matching Domain Name: {matching_domain_name}")

                    if GetServiceState(service_id) == 0 and offer_domain_owner.rstrip('\x00') == matching_domain_name:
                        logger.info(f"Open services updated: {open_services}")
                        open_services.append(service_id)

                # print("OPEN =", len(open_services)) 
                if len(open_services) > 0:
                    
                    # Announcement received
                    t_announce_received = time.time() - process_start_time
                    data.append(['announce_received', t_announce_received])
                    
                    logger.info(f"Announcement Received - Service ID: {service_id}, Requested Service: {repr(requested_service)}, Requested Replicas: {repr(requested_replicas)}")
                    print(new_events)
                    newService = True
                
            service_id = open_services[-1]

            # Place a bid offer to the Federation SC
            t_bid_offer_sent = time.time() - process_start_time
            data.append(['bid_offer_sent', t_bid_offer_sent])
            winnerChosen_event = PlaceBid(service_id, price)

            logger.info(f"Bid Offer sent to the SC - Service ID: {service_id}, Price: {price} €")
            
            # Ask to the Federation SC if there is a winner (wait...)
        
            winnerChosen = False
            while winnerChosen == False:
                new_events = winnerChosen_event.get_all_entries()
                for event in new_events:
                    event_serviceid = web3.toText(event['args']['_id'])
                    if event_serviceid == service_id:
                        
                        # Winner choosen received
                        t_winner_received = time.time() - process_start_time
                        data.append(['winner_received', t_winner_received])
                        winnerChosen = True
                        break
            
            am_i_winner = False
            while am_i_winner == False:
                # Provider AD ask if he is the winner
                am_i_winner = CheckWinner(service_id)
                if am_i_winner == True:
                    logger.info(f"I am the winner for {service_id}")
                    # Start deployment of the requested federated service
                    logger.info("Start deployment of the requested federated service...")
                    t_deployment_start = time.time() - process_start_time
                    data.append(['deployment_start', t_deployment_start])
                    break
                else:
                    # If not the winner, log and return the message
                    logger.info(f"I am not the winner for {service_id}")
                    t_other_provider_choosen = time.time() - process_start_time
                    data.append(['other_provider_choosen', t_other_provider_choosen])
                    if export_to_csv:
                        # Export the data to a csv file only if export_to_csv is True
                        create_csv_file(domain, header, data)
                        logger.info(f"Data exported to CSV for {domain}.")
                        return {"message": f"I am not the winner for {service_id}"}
                    else:
                        logger.warning("CSV export not requested.")
                        return {"message": f"I am not the winner for {service_id}"}

            # Service deployed info
            federated_host, service_endpoint_consumer = GetDeployedInfo(service_id, domain)

            service_endpoint_consumer = service_endpoint_consumer.decode('utf-8')

            logger.info(f"Service Endpoint Consumer: {service_endpoint_consumer}")

            # Sets up the federation docker network and the VXLAN network interface
            configure_docker_network_and_vxlan(ip_address, service_endpoint_consumer, interface_name, vxlan_id, vxlan_port, docker_subnet, docker_ip_range)


            container_port=5000
            exposed_ports=5000

            # Deploy docker service and wait to be ready and get an IP address
            deploy_docker_containers(
                image=requested_service,
                name=f"federated-{requested_service}",
                network="federation-net",
                replicas=int(requested_replicas),
                env_vars={"SERVICE_ID": f"{domain_name} MEC system"},
                container_port=container_port,
                start_host_port=exposed_ports
            )          

            container_ips = get_container_ips(requested_service)
            if container_ips:
                first_container_name = next(iter(container_ips))
                federated_host = container_ips[first_container_name]
                        
            # Deployment finished
            t_deployment_finished = time.time() - process_start_time
            data.append(['deployment_finished', t_deployment_finished])
                
            # Deployment confirmation sent
            t_confirm_deployment_sent = time.time() - process_start_time
            data.append(['confirm_deployment_sent', t_confirm_deployment_sent])
            federated_host=f"http://{federated_host}:{exposed_ports}"
            ServiceDeployed(service_id, federated_host)

            total_duration = time.time() - process_start_time

            logger.info(f"Service Deployed - Federated Host: {federated_host}")
 
            DisplayServiceState(service_id)
                
            if export_to_csv:
                # Export the data to a csv file only if export_to_csv is True
                create_csv_file(domain, header, data)
                logger.info(f"Data exported to CSV for {domain}.")
            else:
                logger.warning("CSV export not requested.")

            return {"message": f"Federation process completed successfully - {domain}"}
        else:
            error_message = "You must be provider to run this code"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  
# ------------------------------------------------------------------------------------------------------------------------------#

# ------------------------------------------------------------------------------------------------------------------------------#
@app.post("/start_experiments_consumer_v3")
def start_experiments_consumer_v3(export_to_csv: bool = False, providers: int = 2, matching_price: int = 2):
    try:
        header = ['step', 'timestamp']
        data = []
        
        if domain == 'consumer':
            
            # Start time of the process
            process_start_time = time.time()
            
            global bids_event
            global service_id
            
            # Service Announcement Sent
            t_service_announced = time.time() - process_start_time
            data.append(['service_announced', t_service_announced])
            bids_event = AnnounceService()

            logger.info(f"Service Announcement sent to the SC - Service ID: {service_id}")

            # Consumer AD wait for provider bids
            bidderArrived = False

            logger.info("Waiting for bids...")
            while not bidderArrived:
                new_events = bids_event.get_all_entries()
                for event in new_events:
                    
                    # # Bid Offer Received
                    # t_bid_offer_received = time.time() - process_start_time
                    # data.append(['bid_offer_received', t_bid_offer_received])

                    event_id = str(web3.toText(event['args']['_id']))
                    
                    # Choosing provider

                    # service id, service id, index of the bid
                    # print(service_id, web3.toText(event['args']['_id']), event['args']['max_bid_index'])
                    # logger.info("Bid offer received")
                    bid_index = int(event['args']['max_bid_index'])

                    # Received bids
                    if bid_index >= providers:
                        # ------ #
                        t_bid_offer_received = time.time() - process_start_time
                        data.append(['bid_offer_received', t_bid_offer_received])
                        # ------ #
                        logger.info(f"{bid_index} bid offers received")
                        bidderArrived = True 
                        break
            # Use GetBidCount to ensure we have the correct number of bids
            total_bids = bid_index
            logger.info(f"Total bids received from contract: {total_bids}")

            if total_bids < providers:
                logger.error(f"Not enough bids received: {total_bids} < {providers}")
                raise HTTPException(status_code=500, detail=f"Not enough bids received: {total_bids} < {providers}")

                
            # Received bids
            best_bid_index = None

            # Loop through all bid indices and print their information
            retry_attempts = 10
            retry_delay = 2  # seconds
            
            # Loop through all bid indices and print their information
            for i in range(total_bids):
                attempts = 0
                while attempts < retry_attempts:
                    try:
                        bid_info = GetBidInfo(i)
                        logger.info(f"Bid {i}: {bid_info}")
                        if bid_info is None:
                            logger.warning(f"Bid info for index {i} is None, retrying...")
                            time.sleep(retry_delay)
                            attempts += 1
                            continue

                        bid_price = int(bid_info[1]) 
                        if bid_price == matching_price:
                            best_bid_index = int(bid_info[2])
                            logger.info(f"Found bid with specific price {matching_price}: {bid_info}")
                            break
                        else:
                            break
                    except Exception as e:
                        logger.error(f"Error processing bid at index {i}: {str(e)}, attempt {attempts + 1}/{retry_attempts}")
                        time.sleep(retry_delay)
                        attempts += 1
                if best_bid_index is not None:
                    break    

            if best_bid_index is None:
                logger.error(f"No bid matched the specific price {matching_price}")
                raise HTTPException(status_code=500, detail=f"No bid matched the specific price {matching_price}")
                        
            # Winner choosen 
            t_winner_choosen = time.time() - process_start_time
            data.append(['winner_choosen', t_winner_choosen])
            
            ChooseProvider(best_bid_index)
            logger.info(f"Provider Choosen - Bid Index: {best_bid_index}")

            # Service closed (state 1)
            #DisplayServiceState(service_id)

            # Consumer AD wait for provider confirmation
            serviceDeployed = False 
            while serviceDeployed == False:
                serviceDeployed = True if GetServiceState(service_id) == 2 else False
            
            # Confirmation received
            t_confirm_deployment_received = time.time() - process_start_time
            data.append(['confirm_deployment_received', t_confirm_deployment_received])
            
            t_establish_vxlan_connection_with_provider_start = time.time() - process_start_time
            data.append(['establish_vxlan_connection_with_provider_start', t_establish_vxlan_connection_with_provider_start])

            # Service deployed info
            federated_host, service_endpoint_provider = GetDeployedInfo(service_id, domain)
        
            federated_host = federated_host.decode('utf-8')
            service_endpoint_provider = service_endpoint_provider.decode('utf-8')

            endpoint_ip, endpoint_vxlan_id, endpoint_vxlan_port, endpoint_docker_subnet = extract_service_endpoint(service_endpoint_provider)

            logger.info(f"Federated Service Info - Service Endpoint Provider: {service_endpoint_provider}, Federated Host: {federated_host}")

            # Sets up the federation docker network and the VXLAN network interface
            configure_docker_network_and_vxlan(ip_address, endpoint_ip, interface_name, '200', '4789', docker_subnet, docker_ip_range)
            # configure_docker_network_and_vxlan(ip_address, service_endpoint_provider, interface_name, vxlan_id, vxlan_port, docker_subnet, docker_ip_range)

            attach_container_to_network("mec-app_1", "federation-net")

            t_establish_vxlan_connection_with_provider_finished = time.time() - process_start_time
            data.append(['establish_vxlan_connection_with_provider_finished', t_establish_vxlan_connection_with_provider_finished])
           
            total_duration = time.time() - process_start_time

            logger.info(f"Federation process completed in {total_duration:.2f} seconds")

            federated_host_ip = extract_ip_from_url(federated_host)
            if federated_host_ip is None:
                logger.error(f"Could not extract IP from '{federated_host}'")

            logger.info(f"Monitoring connection with federated host ({federated_host_ip})")
            monitor_connection_command = f"ping -c 10 {federated_host_ip}"
            execute_command_in_container("mec-app_1", monitor_connection_command)

            if export_to_csv:
                # Export the data to a csv file only if export_to_csv is True
                create_csv_file(domain, header, data)
                logger.info(f"Data exported to CSV for {domain}.")
            else:
                logger.warning("CSV export not requested.")

            return {"message": f"Federation process completed in {total_duration:.2f} seconds"}
        else:
            error_message = "You must be consumer to run this code"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Error in start_experiments_consumer_v4: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))    

@app.post("/start_experiments_provider_v3")
def start_experiments_provider_v3(export_to_csv: bool = False, price: int = 10, offers: int = 1):
    try:
        header = ['step', 'timestamp']
        data = []
        
        if domain == 'provider':
            
            # Start time of the process
            process_start_time = time.time()

            global winnerChosen_event 
            service_id = ''
            newService_event = ServiceAnnouncementEvent()
            newService = False
            open_services = []

            # Provider AD wait for service announcements
            logger.info("Subscribed to federation events...")
            while newService == False:
                new_events = newService_event.get_all_entries()
                for event in new_events:
                    service_id = web3.toText(event['args']['id'])
                    # service_id = service_id.rstrip('\x00')
                    
                    requirements = web3.toText(event['args']['requirements'])

                    requested_service, requested_replicas = extract_service_requirements(requirements.rstrip('\x00'))
                    
                    if GetServiceState(service_id) == 0 and service_id not in open_services:
                        open_services.append(service_id)
                        # logger.info(f"Announcement Received - Open Services: {len(open_services)}")

                # print("OPEN =", len(open_services)) 
                if len(open_services) >= offers:
                    
                    # Announcement received
                    t_announce_received = time.time() - process_start_time
                    data.append(['announce_received', t_announce_received])
                    logger.info(f"{len(open_services)} offers received")
                    
                    # logger.info(f"Announcement Received - Service ID: {service_id}, Requested Service: {repr(requested_service)}, Requested Replicas: {repr(requested_replicas)}")
                    # print(new_events)
                    newService = True
                

            logger.info(f"Open Services: {open_services}")

            # Place a bid offer to the Federation SC
            t_bid_offer_sent = time.time() - process_start_time
            data.append(['bid_offer_sent', t_bid_offer_sent])
            winnerChosen_events = []
            for service_id in open_services:
                winnerChosen_events.append((service_id, PlaceBid(service_id, price)))
                logger.info(f"Bid Offer sent to the SC - Service ID: {service_id}, Price: {price} €")
            
            # Wait for winnerChosen events for all services
            services_with_winners = []
            while len(services_with_winners) < len(open_services):
                for service_id, winnerChosen_event in winnerChosen_events:
                    if service_id in services_with_winners:
                        continue
                    try:
                        new_events = winnerChosen_event.get_all_entries()
                        # logger.info(f"New events for service ID {service_id}: {new_events}")
                        for event in new_events:
                            event_serviceid = web3.toText(event['args']['_id'])
                            if event_serviceid == service_id:
                                # Winner chosen received
                                services_with_winners.append(service_id)
                                # logger.info(f"Winner chosen for service ID: {service_id}")
                                break
                    except Exception as e:
                        logger.error(f"Error processing winnerChosen events for service ID {service_id}: {str(e)}")

            t_winner_received = time.time() - process_start_time
            data.append(['winner_received', t_winner_received])
            
            am_i_winner = False
            no_winner_count = 0
            for service_id in open_services:
                # Provider AD asks if he is the winner
                if CheckWinner(service_id):
                    logger.info(f"I am the winner for {service_id}")
                    # Start deployment of the requested federated service
                    logger.info("Start deployment of the requested federated service...")
                    t_deployment_start = time.time() - process_start_time
                    data.append(['deployment_start', t_deployment_start])
                    am_i_winner = True

                    # Service deployed info
                    federated_host, service_endpoint_consumer = GetDeployedInfo(service_id, domain)

                    service_endpoint_consumer = service_endpoint_consumer.decode('utf-8')

                    endpoint_ip, endpoint_vxlan_id, endpoint_vxlan_port, endpoint_docker_subnet = extract_service_endpoint(service_endpoint_consumer)
                    net_range = create_smaller_subnet(endpoint_docker_subnet, dlt_node_id)

                    logger.info(f"Service Endpoint Consumer: {service_endpoint_consumer}")

                    # Sets up the federation docker network and the VXLAN network interface
                    configure_docker_network_and_vxlan(ip_address, endpoint_ip, interface_name, '200', '4789', endpoint_docker_subnet, net_range)
                    # configure_docker_network_and_vxlan(ip_address, service_endpoint_consumer, interface_name, vxlan_id, vxlan_port, docker_subnet, docker_ip_range)

                    container_port=5000
                    exposed_ports=5000

                    # Deploy docker service and wait to be ready and get an IP address
                    deploy_docker_containers(
                        image=requested_service,
                        name=f"federated-{requested_service}",
                        network="federation-net",
                        replicas=int(requested_replicas),
                        env_vars={"SERVICE_ID": f"{domain_name} MEC system"},
                        container_port=container_port,
                        start_host_port=exposed_ports
                    )          

                    container_ips = get_container_ips(requested_service)
                    if container_ips:
                        first_container_name = next(iter(container_ips))
                        federated_host = container_ips[first_container_name]
                                
                    # Deployment finished
                    t_deployment_finished = time.time() - process_start_time
                    data.append(['deployment_finished', t_deployment_finished])
                        
                    # Deployment confirmation sent
                    t_confirm_deployment_sent = time.time() - process_start_time
                    data.append(['confirm_deployment_sent', t_confirm_deployment_sent])
                    federated_host=f"http://{federated_host}:{exposed_ports}"
                    ServiceDeployed(service_id, federated_host)

                    total_duration = time.time() - process_start_time

                    logger.info(f"Service Deployed - Federated Host: {federated_host}")
     
                    DisplayServiceState(service_id)
                        
                    if export_to_csv:
                        # Export the data to a csv file only if export_to_csv is True
                        create_csv_file(domain, header, data)
                        logger.info(f"Data exported to CSV for {domain}.")
                    else:
                        logger.warning("CSV export not requested.")

                    return {"message": f"Federation process completed successfully - {domain}"}
                else:
                    # logger.info(f"I am not the winner for {service_id}")
                    no_winner_count += 1
                    if no_winner_count == offers:
                        t_other_provider_chosen = time.time() - process_start_time
                        data.append(['other_provider_chosen', t_other_provider_chosen])
                        logger.info(f"I am not the winner for any service_id")
                        if export_to_csv:
                            # Export the data to a csv file only if export_to_csv is True
                            create_csv_file(domain, header, data)
                            logger.info(f"Data exported to CSV for {domain}.")
                            return {"message": f"I am not the winner for any service_id"}
                        else:
                            logger.warning("CSV export not requested.")
                            return {"message": f"I am not the winner for any service_id"}

        else:
            error_message = "You must be provider to run this code"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  
# ------------------------------------------------------------------------------------------------------------------------------#
@app.post("/start_experiments_consumer_v4")
def start_experiments_consumer_v4(export_to_csv: bool = False, providers: int = 2, matching_price: int = 2):
    try:
        header = ['step', 'timestamp']
        data = []
        
        if domain == 'consumer':
            
            # Start time of the process
            process_start_time = time.time()
            
            global bids_event
            global service_id
            
            # Service Announcement Sent
            t_service_announced = time.time() - process_start_time
            data.append(['service_announced', t_service_announced])
            bids_event = AnnounceService()

            logger.info(f"Service Announcement sent to the SC - Service ID: {service_id}")

            # Consumer AD wait for provider bids
            bidderArrived = False

            logger.info("Waiting for bids...")
            while not bidderArrived:
                new_events = bids_event.get_all_entries()
                for event in new_events:
                    
                    # # Bid Offer Received
                    # t_bid_offer_received = time.time() - process_start_time
                    # data.append(['bid_offer_received', t_bid_offer_received])

                    event_id = str(web3.toText(event['args']['_id']))
                    
                    # Choosing provider

                    # service id, service id, index of the bid
                    # print(service_id, web3.toText(event['args']['_id']), event['args']['max_bid_index'])
                    # logger.info("Bid offer received")
                    bid_index = int(event['args']['max_bid_index'])

                    # Received bids
                    if bid_index >= providers:
                        # ------ #
                        t_bid_offer_received = time.time() - process_start_time
                        data.append(['bid_offer_received', t_bid_offer_received])
                        # ------ #
                        logger.info(f"{bid_index} bid offers received")
                        bidderArrived = True 
                        break
                time.sleep(2)
            # Use GetBidCount to ensure we have the correct number of bids
            total_bids = bid_index
            logger.info(f"Total bids received from contract: {total_bids}")

            if total_bids < providers:
                logger.error(f"Not enough bids received: {total_bids} < {providers}")
                raise HTTPException(status_code=500, detail=f"Not enough bids received: {total_bids} < {providers}")

                
            # Received bids
            best_bid_index = None
            
            # Loop through all bid indices and print their information
            retry_attempts = 15
            retry_delay = 2  # seconds
            
            # Loop through all bid indices and print their information
            for i in range(total_bids):
                attempts = 0
                while attempts < retry_attempts:
                    try:
                        bid_info = GetBidInfo(i)
                        logger.info(f"Bid {i}: {bid_info}")
                        if bid_info is None:
                            logger.warning(f"Bid info for index {i} is None, retrying...")
                            time.sleep(retry_delay)
                            attempts += 1
                            continue

                        bid_price = int(bid_info[1]) 
                        if bid_price == matching_price:
                            best_bid_index = int(bid_info[2])
                            logger.info(f"Found bid with specific price {matching_price}: {bid_info}")
                            break
                        else:
                            break
                    except Exception as e:
                        logger.error(f"Error processing bid at index {i}: {str(e)}, attempt {attempts + 1}/{retry_attempts}")
                        time.sleep(retry_delay)
                        attempts += 1
                if best_bid_index is not None:
                    break    

            if best_bid_index is None:
                logger.error(f"No bid matched the specific price {matching_price}")
                raise HTTPException(status_code=500, detail=f"No bid matched the specific price {matching_price}")
                        
            # Winner choosen 
            t_winner_choosen = time.time() - process_start_time
            data.append(['winner_choosen', t_winner_choosen])
            
            ChooseProvider(best_bid_index)
            logger.info(f"Provider Choosen - Bid Index: {best_bid_index}")

            # Service closed (state 1)
            #DisplayServiceState(service_id)

            # Consumer AD wait for provider confirmation
            serviceDeployed = False 
            while serviceDeployed == False:
                serviceDeployed = True if GetServiceState(service_id) == 2 else False
            
            # Confirmation received
            t_confirm_deployment_received = time.time() - process_start_time
            data.append(['confirm_deployment_received', t_confirm_deployment_received])
            
            t_establish_vxlan_connection_with_provider_start = time.time() - process_start_time
            data.append(['establish_vxlan_connection_with_provider_start', t_establish_vxlan_connection_with_provider_start])

            # Service deployed info
            federated_host, service_endpoint_provider = GetDeployedInfo(service_id, domain)
        
            federated_host = federated_host.decode('utf-8')
            service_endpoint_provider = service_endpoint_provider.decode('utf-8')

            endpoint_ip, endpoint_vxlan_id, endpoint_vxlan_port, endpoint_docker_subnet = extract_service_endpoint(service_endpoint_provider)

            logger.info(f"Federated Service Info - Service Endpoint Provider: {endpoint_ip}, Federated Host: {federated_host}")

            # Sets up the federation docker network and the VXLAN network interface
            configure_docker_network_and_vxlan(ip_address, endpoint_ip, interface_name, vxlan_id, vxlan_port, docker_subnet, docker_ip_range)

            attach_container_to_network("mec-app_1", "federation-net")

            t_establish_vxlan_connection_with_provider_finished = time.time() - process_start_time
            data.append(['establish_vxlan_connection_with_provider_finished', t_establish_vxlan_connection_with_provider_finished])
           
            total_duration = time.time() - process_start_time

            logger.info(f"Federation process completed in {total_duration:.2f} seconds")

            federated_host_ip = extract_ip_from_url(federated_host)
            if federated_host_ip is None:
                logger.error(f"Could not extract IP from '{federated_host}'")

            logger.info(f"Monitoring connection with federated host ({federated_host_ip})")
            monitor_connection_command = f"ping -c 10 {federated_host_ip}"
            execute_command_in_container("mec-app_1", monitor_connection_command)

            if export_to_csv:
                # Export the data to a csv file only if export_to_csv is True
                create_csv_file(domain, header, data)
                logger.info(f"Data exported to CSV for {domain}.")
            else:
                logger.warning("CSV export not requested.")

            return {"message": f"Federation process completed in {total_duration:.2f} seconds"}
        else:
            error_message = "You must be consumer to run this code"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Error in start_experiments_consumer_v4: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start_experiments_provider_v4")
def start_experiments_provider_v4(export_to_csv: bool = False, price: int = 10, offers: int = 1, deployments: int = 2):
    try:
        header = ['step', 'timestamp']
        data = []
        
        if domain == 'provider':
            
            # Start time of the process
            process_start_time = time.time()

            global winnerChosen_event 
            global dlt_node_id
            service_id = ''
            newService_event = ServiceAnnouncementEvent()
            newService = False
            open_services = []

            # Provider AD wait for service announcements
            logger.info("Subscribed to federation events...")
            while newService == False:
                new_events = newService_event.get_all_entries()
                for event in new_events:
                    service_id = web3.toText(event['args']['id'])
                    # service_id = service_id.rstrip('\x00')
                    
                    requirements = web3.toText(event['args']['requirements'])

                    requested_service, requested_replicas = extract_service_requirements(requirements.rstrip('\x00'))
                    
                    if GetServiceState(service_id) == 0 and service_id not in open_services:
                        open_services.append(service_id)
                        # logger.info(f"Announcement Received - Open Services: {len(open_services)}")

                # print("OPEN =", len(open_services)) 
                if len(open_services) >= offers:
                    
                    # Announcement received
                    t_announce_received = time.time() - process_start_time
                    data.append(['announce_received', t_announce_received])
                    logger.info(f"{len(open_services)} offers received")
                    
                    # logger.info(f"Announcement Received - Service ID: {service_id}, Requested Service: {repr(requested_service)}, Requested Replicas: {repr(requested_replicas)}")
                    # print(new_events)
                    newService = True
                

            logger.info(f"Open Services: {open_services}")

            # Place a bid offer to the Federation SC
            t_bid_offer_sent = time.time() - process_start_time
            data.append(['bid_offer_sent', t_bid_offer_sent])
            winnerChosen_events = []
            for service_id in open_services:
                winnerChosen_events.append((service_id, PlaceBid(service_id, price)))
                logger.info(f"Bid Offer sent to the SC - Service ID: {service_id}, Price: {price} €")
            
            # Wait for winnerChosen events for all services
            services_with_winners = []
            while len(services_with_winners) < len(open_services):
                for service_id, winnerChosen_event in winnerChosen_events:
                    if service_id in services_with_winners:
                        continue
                    try:
                        new_events = winnerChosen_event.get_all_entries()
                        # logger.info(f"New events for service ID {service_id}: {new_events}")
                        for event in new_events:
                            event_serviceid = web3.toText(event['args']['_id'])
                            if event_serviceid == service_id:
                                # Winner chosen received
                                services_with_winners.append(service_id)
                                # logger.info(f"Winner chosen for service ID: {service_id}")
                                break
                    except Exception as e:
                        logger.error(f"Error processing winnerChosen events for service ID {service_id}: {str(e)}")

            t_winner_received = time.time() - process_start_time
            data.append(['winner_received', t_winner_received])
            
            am_i_winner = False
            no_winner_count = 0
            deployed_federations = 0
            
            for service_id in open_services:
                logger.info(f"Processing service_id: {service_id}")

                while True:
                    try:
                        is_winner = CheckWinner(service_id)
                        break
                    except Exception as e:
                        logger.error(f"Error checking winner for service ID {service_id}: {str(e)}. Retrying...")
                        time.sleep(2)

                if is_winner:
                    logger.info(f"I am the winner for {service_id}")

                    t_deployment_start = time.time() - process_start_time
                    data.append([f'deployment_start_service_{deployed_federations}', t_deployment_start])
                    logger.info(f"Deployment start time recorded: {t_deployment_start}")
                    
                    am_i_winner = True

                    logger.debug("Fetching deployed info")
                    try:
                        federated_host, service_endpoint_consumer = GetDeployedInfo(service_id, domain)

                        service_endpoint_consumer = service_endpoint_consumer.decode('utf-8')

                        endpoint_ip, endpoint_vxlan_id, endpoint_vxlan_port, endpoint_docker_subnet = extract_service_endpoint(service_endpoint_consumer)

                        net_range = create_smaller_subnet(endpoint_docker_subnet, dlt_node_id)

                        logger.info(f"Service Endpoint Consumer: {service_endpoint_consumer}")
                        svc_name = f"federated-{requested_service}-{deployed_federations}"
                        net_name = f"federation-net-{deployed_federations}"

                        configure_docker_network_and_vxlan(ip_address, endpoint_ip, interface_name, endpoint_vxlan_id, endpoint_vxlan_port, endpoint_docker_subnet, net_range, 'netcom', net_name)
                        logger.info(f"Network configuration completed for {svc_name} on network {net_name}")
                    except Exception as e:
                        logger.error(f"Error during deployment info fetching and network configuration: {e}")
                        raise HTTPException(status_code=500, detail=f"Error during deployment info fetching and network configuration: {e}")

                    container_port = 5000
                    try:
                        exposed_ports = 5000 + int(dlt_node_id) + deployed_federations
                        logger.debug("Deploying docker container")
                        deploy_docker_containers(
                            image=requested_service,
                            name=svc_name,
                            network=net_name,
                            replicas=int(requested_replicas),
                            env_vars={"SERVICE_ID": f"{domain_name} MEC system"},
                            container_port=container_port,
                            start_host_port=exposed_ports
                        )
                        logger.info(f"Docker container {svc_name} deployed successfully on network {net_name}")
                    except Exception as e:
                        logger.error(f"Error during docker container deployment: {e}")
                        raise HTTPException(status_code=500, detail=f"Error during docker container deployment: {e}")

                    try:
                        logger.debug("Getting container IPs")
                        container_ips = get_container_ips(requested_service)
                        if container_ips:
                            first_container_name = next(iter(container_ips))
                            federated_host = container_ips[first_container_name]
                        logger.debug(f"Container IPs: {container_ips}, federated_host: {federated_host}")
                    except Exception as e:
                        logger.error(f"Error getting container IPs: {e}")
                        raise HTTPException(status_code=500, detail=f"Error getting container IPs: {e}")
                                
                    try:
                        t_deployment_finished = time.time() - process_start_time
                        data.append([f'deployment_finished_service_{deployed_federations}', t_deployment_finished])
                        logger.info(f"Deployment finished time recorded: {t_deployment_finished}")

                        t_confirm_deployment_sent = time.time() - process_start_time
                        data.append([f'confirm_deployment_sent_service_{deployed_federations}', t_confirm_deployment_sent])
                        logger.info(f"Confirmation deployment sent time recorded: {t_confirm_deployment_sent}")

                        federated_host = f"http://{federated_host}:{exposed_ports}"
                        ServiceDeployed(service_id, federated_host)
                        logger.info(f"Service Deployed - Federated Host: {federated_host}")

                        deployed_federations += 1
                        total_duration = time.time() - process_start_time
                        logger.info(f"Total duration for deployment: {total_duration}")

                        DisplayServiceState(service_id)
                    except Exception as e:
                        logger.error(f"Error during deployment finalization: {e}")
                        raise HTTPException(status_code=500, detail=f"Error during deployment finalization: {e}")
                    
                    if deployed_federations >= deployments:
                        if export_to_csv:
                            create_csv_file(domain, header, data)
                            logger.info(f"Data exported to CSV for {domain}.")
                        else:
                            logger.warning("CSV export not requested.")

                        return {"message": f"Federation process completed successfully - {domain}"}
                else:
                    no_winner_count += 1
                    logger.info(f"No winner for service_id {service_id}. Total no_winner_count: {no_winner_count}")
                    
                    if no_winner_count == offers:
                        t_other_provider_chosen = time.time() - process_start_time
                        data.append(['other_provider_chosen', t_other_provider_chosen])
                        logger.info(f"Other provider chosen time recorded: {t_other_provider_chosen}")
                        
                        if export_to_csv:
                            create_csv_file(domain, header, data)
                            logger.info(f"Data exported to CSV for {domain}.")
                            return {"message": f"I am not the winner for any service_id"}
                        else:
                            logger.warning("CSV export not requested.")
                            return {"message": f"I am not the winner for any service_id"}

            if deployed_federations == 0:
                logger.error("Could not deploy any federations")
                raise HTTPException(status_code=500, detail="Could not deploy any federations")

            if deployed_federations < deployments:
                logger.error(f"Could only deploy {deployed_federations} out of {deployments} federations")
                raise HTTPException(status_code=500, detail=f"Could only deploy {deployed_federations} out of {deployments} federations")

        else:
            error_message = "You must be provider to run this code"
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Error in start_experiments_provider_v4: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
# ------------------------------------------------------------------------------------------------------------------------------#
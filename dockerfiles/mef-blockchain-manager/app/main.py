import os
import time
import logging
import uuid
import httpx
from web3 import Web3
from fastapi import FastAPI, HTTPException, Query
from fastapi_utils.tasks import repeat_every
from prettytable import PrettyTable

from typing import List, Dict
from datetime import datetime
import sys
import threading
import signal

import utils
from blockchain_interface import BlockchainInterface, FederationEvents
from models import (
    SubscriptionRequest, 
    SubscriptionResponse,
    TransactionReceiptResponse,
    ServiceAnnouncementRequest,
    PlaceBidRequest,
    ChooseProviderRequest,
    ServiceDeployedRequest,
    DemoConsumerRequest,
    DemoProviderRequest
)

# In-memory subscription store: sub_id → {'request': SubscriptionRequest, 'filter': Filter}
subscriptions: Dict[str, Dict] = {}

tags_metadata = [
    {"name": "General federation functions", "description": "General functions."},
    {"name": "Consumer functions", "description": "Functions for consumer domains."},
    {"name": "Provider functions", "description": "Functions for provider domains."}
]

app = FastAPI(
    title="MEF - Blockchain Manager API",
    description="This API provides endpoints for interacting with the Federation Smart Contract",
    version="1.0.0",
    openapi_tags=tags_metadata
)

shutdown_event = threading.Event()

# Graceful shutdown handler
def handle_sigint(sig, frame):
    print("🔌 SIGINT received. Cleaning up...")
    shutdown_event.set()
    # Do custom cleanup here (close files, stop threads, etc.)
    sys.exit(0)

signal.signal(signal.SIGINT, handle_sigint)

# Load configuration from environment variables
domain           = os.getenv("DOMAIN_FUNCTION", "").strip().lower()
eth_address      = os.getenv("ETH_ADDRESS")
eth_private_key  = os.getenv("ETH_PRIVATE_KEY")
eth_node_url     = os.getenv("ETH_NODE_URL")
contract_addr_raw= os.getenv("CONTRACT_ADDRESS")
provider_flag = (domain == "provider")

# -- guard against missing configurations --
required = {
    "DOMAIN_FUNCTION": domain,
    "ETH_ADDRESS":      eth_address,
    "ETH_PRIVATE_KEY":  eth_private_key,
    "ETH_NODE_URL":     eth_node_url,
    "CONTRACT_ADDRESS": contract_addr_raw,
}
missing = [k for k,v in required.items() if not v]
if missing:
    raise RuntimeError(f"ERROR: missing environment variables: {', '.join(missing)}")

# -- validate & normalize the contract address --
try:
    contract_address = Web3.toChecksumAddress(contract_addr_raw)
except Exception:
    raise RuntimeError(f"ERROR: CONTRACT_ADDRESS '{contract_addr_raw}' is not a valid Ethereum address")

# -- validate domain --
if domain not in ("provider", "consumer"):
    raise RuntimeError(f"ERROR: DOMAIN_FUNCTION must be 'provider' or 'consumer', got '{domain}'")

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize blockchain interface
blockchain = BlockchainInterface(
    eth_address=eth_address,
    private_key=eth_private_key,
    eth_node_url=eth_node_url,
    abi_path="/smart-contracts/build/contracts/Federation.json",
    contract_address=contract_address
)

# Background notifier using repeat_every
@app.on_event("startup")
@repeat_every(seconds=1)
async def notifier_loop() -> None:
    async with httpx.AsyncClient() as client:
        for sub_id, info in list(subscriptions.items()):
            req = info["request"]
            flt = info["filter"]
            for entry in flt.get_new_entries():
                # Decode event arguments using Web3.toText for clean UTF-8 strings
                decoded_args: Dict[str, str] = {}
                for k, v in entry.get("args", {}).items():
                    try:
                        text = Web3.toText(v).rstrip('\x00')
                    except (TypeError, ValueError):
                        text = v  # fallback to raw
                    decoded_args[k] = text

                payload = {
                    "subscription_id": sub_id,
                    "event": entry.get("event"),
                    "tx_hash": entry.get("transactionHash").hex(),
                    "block_number": entry.get("blockNumber"),
                    "args": decoded_args
                }
                try:
                    await client.post(req.callback_url, json=payload, timeout=5.0)
                except httpx.HTTPError as e:
                    logger.error(f"Failed to notify {req.callback_url}: {e}")

# Subscription endpoints
@app.post("/subscriptions", response_model=SubscriptionResponse, status_code=201)
def create_subscription(req: SubscriptionRequest):
    try:
        # ensure valid event
        _ = BlockchainInterface  # for type access
        event_filter = blockchain.create_event_filter(req.event_name, last_n_blocks=req.last_n_blocks)
    except ValueError:
        raise HTTPException(400, f"Unknown event '{req.event_name}'")
    sub_id = uuid.uuid4().hex
    subscriptions[sub_id] = {"request": req, "filter": event_filter}
    return SubscriptionResponse(subscription_id=sub_id, **req.dict())

@app.get("/subscriptions", response_model=List[SubscriptionResponse])
def list_subscriptions():
    return [SubscriptionResponse(subscription_id=sub_id, **info["request"].dict())
            for sub_id, info in subscriptions.items()]

@app.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription(sub_id: str):
    subscriptions.pop(sub_id, None)
    return

@app.get("/web3_info", summary="Get Web3 info", tags=["General federation functions"])
def web3_info_endpoint():
    try:
        return {"ethereum_node_url": eth_node_url,
                "ethereum_address": eth_address,
                "contract_address": contract_address}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tx_receipt/{tx_hash}", summary="Get transaction receipt", tags=["General federation functions"], response_model=TransactionReceiptResponse)
def tx_receipt_endpoint(tx_hash: str):
    try:
        return blockchain.get_transaction_receipt(tx_hash)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/register_domain/{name}", summary="Register a new domain (operator)", tags=["General federation functions"])
def register_domain_endpoint(name: str):
    try:
        tx_hash = blockchain.register_domain(name)
        return {"tx_hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/unregister_domain", summary="Unregisters an existing domain (operator)", tags=["General federation functions"])
def unregister_domain_endpoint():
    try:
        tx_hash = blockchain.unregister_domain()
        return {"tx_hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_service_announcement",
          summary="Create a service announcement", 
          tags=["Consumer functions"],
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
         tags=["General federation functions"],
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
         tags=["General federation functions"],
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
         tags=["Provider functions"], 
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
          tags=["Provider functions"],
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
         tags=["Consumer functions"],
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
          tags=["Consumer functions"],
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
         tags=["Provider functions"],
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
         tags=["Provider functions"],
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
          tags=["Provider functions"],
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
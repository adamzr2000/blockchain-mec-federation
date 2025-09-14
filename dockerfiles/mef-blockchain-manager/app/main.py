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
import re
import utils
import random

from blockchain_interface import BlockchainInterface, FederationEvents
from models import (
    SubscriptionRequest, 
    SubscriptionResponse,
    TransactionReceiptResponse,
    ServiceAnnouncementRequest,
    PlaceBidRequest,
    ChooseProviderRequest,
    ServiceDeployedRequest,
    DemoRegistrationRequest,
    DemoConsumerRequest,
    DemoProviderRequest,
    DemoConsumerMultipleRequest,
    DemoProviderMultipleRequest
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
    "CONTRACT_ADDRESS": contract_addr_raw
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

truffle_abi_path = "/smart-contracts/build/contracts/Federation.json"
hardhat_abi_path = "/smart-contracts/artifacts/contracts/Federation.sol/Federation.json"

# Initialize blockchain interface
blockchain = BlockchainInterface(
    eth_address=eth_address,
    private_key=eth_private_key,
    eth_node_url=eth_node_url,
    abi_path=hardhat_abi_path,
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
        tx_hash = blockchain.register_domain(name, wait=False, timeout=30)
        return {"tx_hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/unregister_domain", summary="Unregisters an existing domain (operator)", tags=["General federation functions"])
def unregister_domain_endpoint():
    try:
        tx_hash = blockchain.unregister_domain(wait=True, timeout=30)
        return {"tx_hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/announce_service", summary="Create service federation announcement", tags=["Consumer functions"])
def announce_service_endpoint(request: ServiceAnnouncementRequest):
    try:
        tx_hash, service_id = blockchain.announce_service(
            request.requirements,
            request.endpoint
        ) 
        return {"tx_hash": tx_hash, "service_id": service_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/service_state/{service_id}", summary="Get service state", tags=["General federation functions"])
def check_service_state_endpoint(service_id: str): 
    try:
        current_service_state = blockchain.get_service_state(service_id)
        state_mapping = {0: "open", 1: "closed", 2: "deployed"}
        return {"service_state": state_mapping.get(current_service_state, "unknown")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/service_announcements", summary="Check service federation announcements", tags=["Provider functions"])
def check_service_announcements_endpoint():
    blocks_to_check = 20
    try:
        new_service_event = blockchain.create_event_filter(FederationEvents.SERVICE_ANNOUNCEMENT, last_n_blocks=blocks_to_check)
        new_events = new_service_event.get_all_entries()
        announcements_received = []

        for event in new_events:
            service_id = Web3.toText(event['args']['serviceId']).rstrip('\x00')
            requirements = event['args']['requirements']
            tx_hash = Web3.toHex(event['transactionHash'])
            block_number = event['blockNumber']

            # Fetch block to extract timestamp
            block = blockchain.web3.eth.get_block(block_number)
            timestamp = datetime.utcfromtimestamp(block['timestamp']).isoformat() + "Z"

            # Check if the service is still open
            if blockchain.get_service_state(service_id) == 0:
                req = blockchain.get_service_requirements(service_id)

                announcements_received.append({
                    "requirements": requirements,
                })

        if announcements_received:
            return {"announcements": announcements_received}
        else:
            raise HTTPException(status_code=404, detail=f"No new services announced in the last {blocks_to_check} blocks.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/place_bid", summary="Place a bid", tags=["Provider functions"])
def place_bid_endpoint(request: PlaceBidRequest):
    try:
        tx_hash = blockchain.place_bid(
            request.service_id, 
            request.price_wei_hour, 
            request.endpoint,
        )
        return {"tx_hash": tx_hash}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/bids/{service_id}", summary="Check bids", tags=["Consumer functions"])
def check_bids_endpoint(service_id: str):
    try:
        bid_count = blockchain.get_bid_count(service_id)
        bids_received = []

        for index in range(bid_count):
            provider_address, price_wei_hour, bider_index = blockchain.get_bid_info(service_id, index)

            bids_received.append({
                "bider_index": bider_index,
                "provider_address": provider_address,
                "price_wei_hour": price_wei_hour
            })

        if bids_received:
            return {"bids": bids_received}
        else:
            raise HTTPException(status_code=404, detail=f"No bids found for service ID {service_id}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/choose_provider", summary="Choose provider", tags=["Consumer functions"])
def choose_provider_endpoint(request: ChooseProviderRequest): 
    try:
        tx_hash = blockchain.choose_provider(request.service_id, request.bider_index)
        return {"tx_hash": tx_hash}    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/is_winner/{service_id}", summary="Check if the calling provider is the winner", tags=["Provider functions"])
def is_winner_endpoint(service_id: str):
    try:
        return {"is_winner": "yes" if blockchain.is_winner(service_id) else "no"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/service_deployed", summary="Confirm service deployment", tags=["Provider functions"])
def service_deployed_endpoint(request: ServiceDeployedRequest):
    try:
        if blockchain.is_winner(request.service_id):
            tx_hash = blockchain.service_deployed(request.service_id, request.info)
            return {"tx_hash": tx_hash}
        else:
            raise HTTPException(status_code=404, detail="You are not the winner.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))      


# ------------------------------------------------------------------------------------------------------------------------------#
@app.post("/start_experiments_registration", tags=["General federation functions"])
def register_domain_endpoint(request: DemoRegistrationRequest):
    try:
        response = run_experiments_registration(name=request.name, export_to_csv=request.export_to_csv, csv_path=request.csv_path)
        return response
    except Exception as e:
        logger.error(f"Registration process failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def run_experiments_registration(name, export_to_csv, csv_path):
    header = ['step', 'timestamp']
    data = []

    process_start_time = time.time()

    send_time = int((time.time() - process_start_time) * 1000)
    data.append(["send_registration_transaction", send_time])

    tx_hash = blockchain.register_domain(name, wait=True, timeout=30)
    
    confirm_time = int((time.time() - process_start_time) * 1000)
    data.append(["confirm_registration_transaction", confirm_time])

    total_duration = time.time() - process_start_time

    logger.info(f"✅ Registration process successfully completed in {total_duration:.2f} seconds.")

    if export_to_csv:
        utils.create_csv_file(csv_path, header, data)
    
    return {
        "status": "success",
        "duration_s": round(total_duration, 2)
    }

@app.post("/start_experiments_consumer", tags=["Consumer functions"])
def start_experiments_consumer(request: DemoConsumerRequest):
    try:
        if domain != 'consumer':
            raise HTTPException(status_code=403, detail="This function is restricted to consumer domains.")
        federation_net = f"192.{request.node_id}.0.0/16"
        vxlan_id = str(200+ int(request.node_id))
        vxlan_port = str(int(6000) + int(request.node_id))
        endpoint = f"ip_address={request.ip_address};vxlan_id={vxlan_id};vxlan_port={vxlan_port};federation_net={federation_net}"
        if not utils.validate_endpoint(endpoint):
            raise HTTPException(status_code=400, detail="Invalid endpoint format.")
        response = run_experiments_consumer(requirements=request.requirements, endpoint=endpoint, offers_to_wait=request.offers_to_wait, 
                                            meo_endpoint=request.meo_endpoint, vxlan_interface=request.vxlan_interface, node_id=request.node_id,
                                            export_to_csv=request.export_to_csv, csv_path=request.csv_path)
        return response

    except Exception as e:
        logger.error(f"Federation process failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start_experiments_provider", tags=["Provider functions"])
def start_experiments_provider(request: DemoProviderRequest):
    try:
        if domain != 'provider':
            raise HTTPException(status_code=403, detail="This function is restricted to provider domains.")
        endpoint = f"ip_address={request.ip_address};vxlan_id=None;vxlan_port=None;federation_net=None"        
        if not utils.validate_endpoint(endpoint):
            raise HTTPException(status_code=400, detail="Invalid endpoint format.")
        response = run_experiments_provider(price_wei_per_hour=request.price_wei_per_hour, endpoint=endpoint, 
                                            meo_endpoint=request.meo_endpoint, vxlan_interface=request.vxlan_interface, node_id=request.node_id, requirements_filter=request.requirements_filter,
                                            export_to_csv=request.export_to_csv, csv_path=request.csv_path)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def run_experiments_consumer(requirements, endpoint, offers_to_wait, meo_endpoint, vxlan_interface, node_id, export_to_csv, csv_path):
    header = ['step', 'timestamp']
    data = []
    process_start_time = time.time()
    WAIT_TIMEOUT = 60  # seconds

    try:
        local_ip, vxlan_id, vxlan_port, federation_net  = utils.extract_service_endpoint(endpoint)
        federation_subnet = utils.create_smaller_subnet(federation_net, node_id)
                    
        # --- Service announcement ---
        tx_hash, service_id = blockchain.announce_service(requirements, endpoint)
        t_service_announced = int((time.time() - process_start_time) * 1000)
        data.append(['service_announced', t_service_announced]) 
        logger.info(f"📢 Service announcement sent - Service ID: {service_id}")

        # --- Wait for provider bids (with max wait) ---
        bids_event = blockchain.create_event_filter(FederationEvents.NEW_BID)
        bidderArrived = False
        logger.info(f"⏳ Waiting for {offers_to_wait} bids...")
        wait_start = time.time()
        while not bidderArrived and (time.time() - wait_start < WAIT_TIMEOUT):
            new_events = bids_event.get_all_entries()
            for event in new_events:
                event_service_id = Web3.toText(event['args']['serviceId']).rstrip('\x00')
                received_bids = int(event['args']['biderIndex'])
                if event_service_id == service_id:
                    t_bid_received = int((time.time() - process_start_time) * 1000)
                    data.append([f'bid_received_{received_bids}', t_bid_received])
                    # If enough bids have arrived, mark threshold timestamp
                    if received_bids >= offers_to_wait:
                        t_required_bids_received = int((time.time() - process_start_time) * 1000)
                        data.append(['required_bids_received', t_required_bids_received])
                        logger.info(f"📨 {received_bids} bid(s) received:")
                        bidderArrived = True 
                        break
            time.sleep(0.2)

        if not bidderArrived:
            raise RuntimeError("Timeout: not enough bids received")
        
        # --- Process bids ---
        lowest_price, best_bid_index = None, None
        for i in range(received_bids):
            bid_info = blockchain.get_bid_info(service_id, i)
            provider_addr, bid_price, bid_index = bid_info[0], int(bid_info[1]), int(bid_info[2])
            logger.info(f"  └ Bid index: {bid_index}, Provider: {provider_addr}, Price: {bid_price} Wei/hour")
            if lowest_price is None or bid_price < lowest_price:
                lowest_price = bid_price
                best_bid_index = bid_index
                # logger.info(f"New lowest price: {lowest_price} with bid index: {best_bid_index}")
        if best_bid_index is None:
            raise RuntimeError("No valid bids to choose from")
        
        # --- Choose provider ---
        blockchain.choose_provider(service_id, best_bid_index)
        t_winner_choosen = int((time.time() - process_start_time) * 1000)
        data.append(['winner_choosen', t_winner_choosen])
        logger.info(f"🏆 Provider selected - Bid index: {best_bid_index}")

        # --- Wait for provider confirmation (with timeout) ---
        logger.info(f"⏳ Waiting for provider to complete deployment...")
        wait_start = time.time()

        while blockchain.get_service_state(service_id) != 2:
            if time.time() - wait_start > WAIT_TIMEOUT:
                raise RuntimeError("Timeout: provider did not confirm deployment")
            time.sleep(0.2)
                    
        t_confirm_deployment_received = int((time.time() - process_start_time) * 1000)
        data.append(['confirm_deployment_received', t_confirm_deployment_received])
        logger.info("✅ Deployment confirmation received.")

        # --- Establish VXLAN ---
        t_establish_vxlan_connection_with_provider_start = int((time.time() - process_start_time) * 1000)
        data.append(['establish_vxlan_connection_with_provider_start', t_establish_vxlan_connection_with_provider_start])
        
        # Federated service info
        provider_endpoint, deployed_mec_app_ip = blockchain.get_service_info(service_id, provider_flag)
        remote_ip, provider_endpoint_vxlan_id, provider_endpoint_vxlan_port, provider_endpoint_federation_net  = utils.extract_service_endpoint(provider_endpoint)
        logger.info(f"Provider VXLAN endpoint: {provider_endpoint}")
        logger.info(f"Provider MEC app deployed - IP: {deployed_mec_app_ip}")

        # Uncomment this during experiments
        print(utils.configure_vxlan(f"{meo_endpoint}/configure_vxlan", local_ip, remote_ip, vxlan_interface, vxlan_id, vxlan_port, federation_net, federation_subnet, "fed-net"))
        print(utils.attach_to_network(f"{meo_endpoint}/attach_to_network","mecapp_1","fed-net"))

        t_establish_vxlan_connection_with_provider_finished = int((time.time() - process_start_time) * 1000)
        data.append(['establish_vxlan_connection_with_provider_finished', t_establish_vxlan_connection_with_provider_finished])

        # Uncomment this during experiments
        logger.info(f"📡 Running connection test on mecapp_1 - Target IP: {deployed_mec_app_ip}")
        connection_test = utils.exec_cmd(f"{meo_endpoint}/exec","mecapp_1", f"ping -c 6 -i 0.2 {deployed_mec_app_ip}")
        stdout = connection_test["stdout"]
        logger.debug(f"🔍 Ping output:\n{stdout}")
        loss = float(re.search(r'(\d+(?:\.\d+)?)%\s*packet loss', stdout).group(1))
        status = "success" if loss < 100.0 else "failure"
        t_connection_test = int((time.time() - process_start_time) * 1000)
        if status == "success":
            logger.info(f"✅ Connection test SUCCESS ({100 - loss:.1f}% packets received)")
            data.append(['connection_test_success', t_connection_test])
        else:
            logger.warning(f"❌ Connection test FAILURE ({loss:.1f}% packet loss)")
            data.append(['connection_test_failure', t_connection_test])

        # --- Wrap up ---
        total_duration = time.time() - process_start_time
        logger.info(f"✅ Federation process successfully completed in {total_duration:.2f} seconds.")

        if export_to_csv:
            data.append(['service_id', service_id]) 
            utils.create_csv_file(csv_path, header, data)
        
        return {"status": "success", "duration_s": round(total_duration, 2)}

    except Exception as e:
        logger.error(f"run_experiments_consumer failed: {e}")
        # if export_to_csv:
        #     data.append(['error', str(e)])
        #     utils.create_csv_file(csv_path, header, data)
        raise

def run_experiments_provider(price_wei_per_hour, endpoint, meo_endpoint, vxlan_interface, node_id, requirements_filter, export_to_csv, csv_path):
    header = ['step', 'timestamp']
    data = []
    local_ip, vxlan_id, vxlan_port, federation_net  = utils.extract_service_endpoint(endpoint)

    process_start_time = time.time()
    open_services = []

    # Wait for service announcements
    new_service_event = blockchain.create_event_filter(FederationEvents.SERVICE_ANNOUNCEMENT)
    logger.info("⏳ Waiting for federation events...")

    newService = False
    while not newService:
        new_events = new_service_event.get_all_entries()
        for event in new_events:
            service_id = Web3.toText(event['args']['serviceId']).rstrip('\x00')
            requirements = event['args']['requirements']

            if blockchain.get_service_state(service_id) == 0 and (requirements_filter is None or requirements == requirements_filter):
                open_services.append(service_id)

        if len(open_services) > 0:
            # Announcement received
            t_announce_received = int((time.time() - process_start_time) * 1000)
            data.append(['announce_received', t_announce_received])
            logger.info(f"Offers received: {len(open_services)} - Service ID: {service_id} - Requirements: {requirements}")
            newService = True
        
    service_id = open_services[-1]  # Select the latest open service

    # Place bid
    blockchain.place_bid(service_id, price_wei_per_hour, endpoint)
    t_bid_offer_sent = int((time.time() - process_start_time) * 1000)
    data.append(['bid_offer_sent', t_bid_offer_sent])
    logger.info(f"💰 Bid offer sent - Service ID: {service_id}, Price: {price_wei_per_hour} Wei/hour")

    logger.info("⏳ Waiting for a winner to be selected...")
    winner_chosen_event = blockchain.create_event_filter(FederationEvents.SERVICE_ANNOUNCEMENT_CLOSED)
    winnerChosen = False
    while not winnerChosen:
        new_events = winner_chosen_event.get_all_entries()
        for event in new_events:
            event_service_id = Web3.toText(event['args']['serviceId']).rstrip('\x00')
            if event_service_id == service_id:    
                # Winner choosen received
                t_winner_received = int((time.time() - process_start_time) * 1000)
                data.append(['winner_received', t_winner_received])
                winnerChosen = True
                break
    
    # Check if this provider is the winner
    if blockchain.is_winner(service_id):
        logger.info(f"🏆 Selected as the winner for service ID: {service_id}.")
        t_deployment_start = int((time.time() - process_start_time) * 1000)
        data.append(['deployment_start', t_deployment_start])
    else:
        logger.info(f"❌ Not selected as the winner for service ID: {service_id}.")
        t_other_provider_choosen = int((time.time() - process_start_time) * 1000)
        data.append(['other_provider_choosen', t_other_provider_choosen])

        if export_to_csv:
            utils.create_csv_file(csv_path, header, data)

        return {"message": f"Another provider was chosen for service ID: {service_id}."}
            
    consumer_endpoint, deployed_mec_app_ip = blockchain.get_service_info(service_id, provider_flag)
    remote_ip, consumer_endpoint_vxlan_id, consumer_endpoint_vxlan_port, consumer_endpoint_federation_net = utils.extract_service_endpoint(consumer_endpoint)

    logger.info(f"Consumer VXLAN endpoint: {consumer_endpoint}")

    federation_subnet = utils.create_smaller_subnet(consumer_endpoint_federation_net, node_id)

    # Dummy
    deployed_mec_app_ip = "8.8.8.8"


    print(local_ip, remote_ip, vxlan_interface, consumer_endpoint_vxlan_id, consumer_endpoint_vxlan_port, consumer_endpoint_federation_net, federation_subnet)

    # Uncomment this during experiments
    print(utils.configure_vxlan(f"{meo_endpoint}/configure_vxlan", local_ip, remote_ip, vxlan_interface, consumer_endpoint_vxlan_id, consumer_endpoint_vxlan_port, consumer_endpoint_federation_net, federation_subnet, "fed-net"))
    deployed_service = utils.deploy_service(f"{meo_endpoint}/deploy_docker_service", "mec-app:latest", "mecapp", "fed-net", 1)
    deployed_mec_app_ip = next(iter(deployed_service["container_ips"].values()))

    t_deployment_finished = int((time.time() - process_start_time) * 1000)
    data.append(['deployment_finished', t_deployment_finished])
        
    logger.info(f"✅ MEC app deployed - IP: {deployed_mec_app_ip}")

    # Confirm service deployed    
    blockchain.service_deployed(service_id, deployed_mec_app_ip)
    t_confirm_deployment_sent = int((time.time() - process_start_time) * 1000)
    data.append(['confirm_deployment_sent', t_confirm_deployment_sent])

    total_duration = time.time() - process_start_time


    if export_to_csv:
        utils.create_csv_file(csv_path, header, data)

    return {
        "status": "success",
        "duration_s": round(total_duration, 2)
    }


@app.post("/start_experiments_provider_multiple_requests", tags=["Provider functions"])
def start_experiments_provider_multiple_requests(request: DemoProviderMultipleRequest):
    try:
        if domain != 'provider':
            raise HTTPException(status_code=403, detail="This function is restricted to provider domains.")
        endpoint = f"ip_address={request.ip_address};vxlan_id=None;vxlan_port=None;federation_net=None"        
        if not utils.validate_endpoint(endpoint):
            raise HTTPException(status_code=400, detail="Invalid endpoint format.")
        response = run_experiments_provider_multiple_requests(price_wei_per_hour=request.price_wei_per_hour, endpoint=endpoint, requests_to_wait=request.requests_to_wait,
                                            meo_endpoint=request.meo_endpoint, vxlan_interface=request.vxlan_interface, node_id=request.node_id, requirements_filter=request.requirements_filter,
                                            export_to_csv=request.export_to_csv, csv_path=request.csv_path)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_experiments_provider_multiple_requests(price_wei_per_hour, endpoint, requests_to_wait, meo_endpoint, vxlan_interface, node_id, requirements_filter, export_to_csv, csv_path):
    header = ['step', 'timestamp']
    data = []
    WAIT_TIMEOUT = 60.0      # seconds (tweak if needed, or pass as a function arg)
    POLL_INTERVAL = 0.2      # seconds
    LOOKBACK_BLOCKS = 10     # small safety window to catch recent closes before filter creation

    process_start_time = time.time()

    try:
        local_ip, vxlan_id, vxlan_port, federation_net  = utils.extract_service_endpoint(endpoint)
        open_services: list[str] = []

        # --- Wait for service announcements (with timeout) ---
        new_service_event = blockchain.create_event_filter(FederationEvents.SERVICE_ANNOUNCEMENT, LOOKBACK_BLOCKS)
        logger.info(f"⏳ Waiting for federation events... (batch size = {requests_to_wait})")
        wait_start = time.time()
        while len(open_services) < requests_to_wait and (time.time() - wait_start < WAIT_TIMEOUT):
            new_events = new_service_event.get_all_entries()
            for event in new_events:
                service_id = Web3.toText(event['args']['serviceId']).rstrip('\x00')
                requirements = event['args']['requirements']

                # Only open services; optional requirements filter; no duplicates
                if (
                    service_id not in open_services and
                    blockchain.get_service_state(service_id) == 0 and
                    (requirements_filter is None or requirements == requirements_filter)
                ):
                    open_services.append(service_id)
                    t_announce_received = int((time.time() - process_start_time) * 1000)
                    data.append([f'announce_received_{service_id}', t_announce_received])

                    logger.info(f"📨 Matched open service: {service_id} | requirements: {requirements} | total {len(open_services)}/{requests_to_wait}")

                    # Record only when the N-th (last) required request arrives
                    if len(open_services) == requests_to_wait:
                        # Announcement received
                        t_required_announces_received = int((time.time() - process_start_time) * 1000)
                        data.append(['required_announces_received', t_required_announces_received])
                        break
            time.sleep(POLL_INTERVAL)
        if len(open_services) < requests_to_wait:
            raise RuntimeError("Timeout: did not receive enough service announcements")
        
        # --- Place bids ---
        bid_targets = []
        for service_id in open_services:
            try:
                # defensive re-check to avoid 'Service: not open' revert
                if blockchain.get_service_state(service_id) != 0:
                    logger.info(f"⏭️  Skipping bid: service {service_id} no longer open")
                    data.append([f'service_not_open_{service_id}', int((time.time() - process_start_time) * 1000)])
                    continue

                blockchain.place_bid(service_id, price_wei_per_hour, endpoint)
                t_bid_offer_sent = int((time.time() - process_start_time) * 1000)
                data.append([f'bid_offer_sent_{service_id}', t_bid_offer_sent])
                logger.info(f"💰 Bid offer sent - Service ID: {service_id}, Price: {price_wei_per_hour} Wei/hour")
                bid_targets.append(service_id)

            except Exception as e:
                msg = str(e)
                if "Service: not open" in msg:
                    logger.info(f"⏭️ Skipping bid (now closed): {service_id}")
                    continue
                logger.error(f"Error placing bid for {service_id}: {msg}")
                raise

        # keep only the services we actually bid on, so the later winner-wait matches
        open_services = bid_targets

        t_all_bid_offers_sent = int((time.time() - process_start_time) * 1000)
        data.append(['all_bid_offers_sent', t_all_bid_offers_sent])

        services_with_winners: set[str] = set()

        # Look back a bit so we don't miss a just-emitted close
        winner_chosen_events = blockchain.create_event_filter(
            FederationEvents.SERVICE_ANNOUNCEMENT_CLOSED,
            last_n_blocks=LOOKBACK_BLOCKS
        )

        wait_start = time.time()
        while len(services_with_winners) < len(open_services) and (time.time() - wait_start < WAIT_TIMEOUT):
            # 1) Consume new close events (fast path)
            try:
                new_events = winner_chosen_events.get_new_entries()
            except Exception as e:
                logger.error(f"Winner-event filter error: {e}")
                new_events = []

            for event in new_events:
                try:
                    event_service_id = Web3.toText(event['args']['serviceId']).rstrip('\x00')
                except Exception as e:
                    logger.error(f"Malformed event log (skipping): {e}")
                    continue

                if event_service_id not in open_services or event_service_id in services_with_winners:
                    continue

                # Defensive: ensure chain reflects Closed/Deployed
                try:
                    if blockchain.get_service_state(event_service_id) >= 1:  # 0=Open, 1=Closed, 2=Deployed
                        t_winner_received = int((time.time() - process_start_time) * 1000)
                        data.append([f'winner_received_{event_service_id}', t_winner_received])
                        services_with_winners.add(event_service_id)
                except Exception as e:
                    logger.error(f"get_service_state failed for {event_service_id}: {e}")
                    # don't break the loop; try others

            # 2) Poll states for any remaining services (slow but reliable path)
            if len(services_with_winners) < len(open_services):
                for sid in open_services:
                    if sid in services_with_winners:
                        continue
                    try:
                        state = blockchain.get_service_state(sid)
                        if state >= 1:
                            t_winner_received = int((time.time() - process_start_time) * 1000)
                            data.append([f'winner_received_{sid}', t_winner_received])
                            services_with_winners.add(sid)
                    except Exception as e:
                        logger.error(f"Polling get_service_state failed for {sid}: {e}")
                        # keep polling others
                if len(services_with_winners) < len(open_services):
                    time.sleep(POLL_INTERVAL)

        if len(services_with_winners) < len(open_services):
            raise RuntimeError("Timeout: winners not received (or services not closed) for all targeted services")

        t_all_winners_received = int((time.time() - process_start_time) * 1000)
        data.append(['all_winners_received', t_all_winners_received])

        # --- Deployment or loser path ---
        no_winner_count = 0
        deployed_federations = 0
        for service_id in open_services:
            
            # Check if this provider is the winner
            if blockchain.is_winner(service_id):
                logger.info(f"🏆 Selected as the winner for service ID: {service_id}.")
                t_deployment_start = int((time.time() - process_start_time) * 1000)
                data.append([f'deployment_start_{service_id}', t_deployment_start])

                consumer_endpoint, deployed_mec_app_ip = blockchain.get_service_info(service_id, provider_flag)
                remote_ip, consumer_endpoint_vxlan_id, consumer_endpoint_vxlan_port, consumer_endpoint_federation_net = utils.extract_service_endpoint(consumer_endpoint)

                logger.info(f"Consumer VXLAN endpoint: {consumer_endpoint}")

                federation_subnet = utils.create_smaller_subnet(consumer_endpoint_federation_net, node_id)

                # Dummy
                deployed_mec_app_ip = "8.8.8.8"


                print(local_ip, remote_ip, vxlan_interface, consumer_endpoint_vxlan_id, consumer_endpoint_vxlan_port, consumer_endpoint_federation_net, federation_subnet)

                svc_name = f"mecapp-{deployed_federations}"
                net_name = f"fed-net-{deployed_federations}"
                svc_host_port = 5000 + deployed_federations

                # Uncomment this during experiments
                print(utils.configure_vxlan(f"{meo_endpoint}/configure_vxlan", local_ip, remote_ip, vxlan_interface, consumer_endpoint_vxlan_id, consumer_endpoint_vxlan_port, consumer_endpoint_federation_net, federation_subnet, net_name))
                deployed_service = utils.deploy_service(f"{meo_endpoint}/deploy_docker_service", "mec-app:latest", svc_name, net_name, 1, svc_host_port, 60, 2.0)
                deployed_mec_app_ip = next(iter(deployed_service["container_ips"].values()))

                t_deployment_finished = int((time.time() - process_start_time) * 1000)
                data.append([f'deployment_finished_{service_id}', t_deployment_finished])
                    
                logger.info(f"✅ MEC app deployed - IP: {deployed_mec_app_ip}")
                deployed_federations += 1

                # Confirm service deployed
                blockchain.service_deployed(service_id, deployed_mec_app_ip)
                t_confirm_deployment_sent = int((time.time() - process_start_time) * 1000)
                data.append([f'confirm_deployment_sent_{service_id}', t_confirm_deployment_sent])


            else:
                no_winner_count += 1
                logger.info(f"❌ Not selected as the winner for service ID: {service_id}.")
                t_other_provider_choosen = int((time.time() - process_start_time) * 1000)
                data.append([f'other_provider_choosen_{service_id}', t_other_provider_choosen])
                
                if no_winner_count == requests_to_wait:
                    t_no_wins = int((time.time() - process_start_time) * 1000)
                    data.append(['no_wins', t_no_wins])
                    logger.info(f"❌ Not selected as the winner for any service")

                    if export_to_csv:
                        utils.create_csv_file(csv_path, header, data)

                    return {"message": "This provider was not selected as the winner for any service."}
                    
        t_all_confirm_deployment_sent = int((time.time() - process_start_time) * 1000)
        data.append(['all_confirm_deployment_sent', t_all_confirm_deployment_sent])

        total_duration = time.time() - process_start_time
        

        if export_to_csv:
            utils.create_csv_file(csv_path, header, data)

        return {"status": "success", "duration_s": round(total_duration, 2)}

    except Exception as e:
        logger.error(f"run_experiments_provider_multiple_requests failed: {e}")
        if export_to_csv:
            data.append(['error', str(e)])
            utils.create_csv_file(csv_path, header, data)
        raise


# ------------------------------------------------------------------------------------------------------------------------------#
@app.post("/start_experiments_consumer_multiple_requests", tags=["Consumer functions"])
def start_experiments_consumer_multiple_requests(request: DemoConsumerMultipleRequest):
    try:
        if domain != 'consumer':
            raise HTTPException(status_code=403, detail="This function is restricted to consumer domains.")
        federation_net = f"192.{request.node_id}.0.0/16"
        vxlan_id = str(200+ int(request.node_id))
        vxlan_port = str(int(6000) + int(request.node_id))
        endpoint = f"ip_address={request.ip_address};vxlan_id={vxlan_id};vxlan_port={vxlan_port};federation_net={federation_net}"
        if not utils.validate_endpoint(endpoint):
            raise HTTPException(status_code=400, detail="Invalid endpoint format.")
        response = run_experiments_consumer_multiple_requests(requirements=request.requirements, endpoint=endpoint, offers_to_wait=request.offers_to_wait, price_threshold_wei_per_hour=request.price_threshold_wei_per_hour,
                                            meo_endpoint=request.meo_endpoint, vxlan_interface=request.vxlan_interface, node_id=request.node_id,
                                            export_to_csv=request.export_to_csv, csv_path=request.csv_path)
        return response

    except Exception as e:
        logger.error(f"Federation process failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def run_experiments_consumer_multiple_requests(requirements, endpoint, offers_to_wait, price_threshold_wei_per_hour, meo_endpoint, vxlan_interface, node_id, export_to_csv, csv_path):
    header = ['step', 'timestamp']
    data = []
    local_ip, vxlan_id, vxlan_port, federation_net  = utils.extract_service_endpoint(endpoint)
    federation_subnet = utils.create_smaller_subnet(federation_net, node_id)
    process_start_time = time.time()
                
    # Send service announcement (federation request)
    tx_hash, service_id = blockchain.announce_service(requirements, endpoint)
    t_service_announced = int((time.time() - process_start_time) * 1000)
    data.append(['service_announced', t_service_announced]) 
    logger.info(f"📢 Service announcement sent - Service ID: {service_id}")

    # Wait for provider bids
    bids_event = blockchain.create_event_filter(FederationEvents.NEW_BID)
    qualifying_bids = []
    logger.info(f"⏳ Waiting for {offers_to_wait} bids...")
    while len(qualifying_bids) < offers_to_wait:
        new_events = bids_event.get_all_entries()
        for event in new_events:
            event_service_id = Web3.toText(event['args']['serviceId']).rstrip('\x00')
            received_bids = int(event['args']['biderIndex'])
            
            bid_info = blockchain.get_bid_info(service_id, received_bids)
            provider_addr, bid_price, _ = bid_info[0], int(bid_info[1]), int(bid_info[2])

            if event_service_id == service_id and bid_price <= price_threshold_wei_per_hour:
                t_bid_received = int((time.time() - process_start_time) * 1000)
                data.append([f'bid_received_{received_bids}', t_bid_received])
                qualifying_bids.append((bid_index, provider_addr, bid_price))

                # If enough bids have arrived, mark threshold timestamp
                if len(qualifying_bids) >= offers_to_wait:
                    t_required_bids_received = int((time.time() - process_start_time) * 1000)
                    data.append(['required_bids_received', t_required_bids_received])
                    logger.info(f"📨 {len(qualifying_bids)} qualifying bid(s) received")
                    break
    
    # Process bids
    lowest_price = None
    best_bid_index = None

    # Loop through all bid indices and print their information
    for i in range(received_bids):
        bid_info = blockchain.get_bid_info(service_id, i)
        provider_addr = bid_info[0]
        bid_price = int(bid_info[1])
        bid_index = int(bid_info[2])
        logger.info(f"  └ Bid index: {bid_index}, Provider: {provider_addr}, Price: {bid_price} Wei/hour")

        if lowest_price is None or bid_price < lowest_price:
            lowest_price = bid_price
            best_bid_index = bid_index
            # logger.info(f"New lowest price: {lowest_price} with bid index: {best_bid_index}")
    # Choose winner provider
    tx_hash = blockchain.choose_provider(service_id, best_bid_index)
    t_winner_choosen = int((time.time() - process_start_time) * 1000)
    data.append(['winner_choosen', t_winner_choosen])
    logger.info(f"🏆 Provider selected - Bid index: {best_bid_index}")

    # Wait for provider confirmation
    logger.info(f"⏳ Waiting for provider to complete deployment...")
    while blockchain.get_service_state(service_id) != 2:
        time.sleep(0.1)
                
    t_confirm_deployment_received = int((time.time() - process_start_time) * 1000)
    data.append(['confirm_deployment_received', t_confirm_deployment_received])
    logger.info("✅ Deployment confirmation received.")

    # blockchain.display_service_state(service_id)

    t_establish_vxlan_connection_with_provider_start = int((time.time() - process_start_time) * 1000)
    data.append(['establish_vxlan_connection_with_provider_start', t_establish_vxlan_connection_with_provider_start])
    
    # Federated service info
    provider_endpoint, deployed_mec_app_ip = blockchain.get_service_info(service_id, provider_flag)
    remote_ip, provider_endpoint_vxlan_id, provider_endpoint_vxlan_port, provider_endpoint_federation_net  = utils.extract_service_endpoint(provider_endpoint)
    logger.info(f"Provider VXLAN endpoint: {provider_endpoint}")
    logger.info(f"Provider MEC app deployed - IP: {deployed_mec_app_ip}")

    # Uncomment this during experiments
    print(utils.configure_vxlan(f"{meo_endpoint}/configure_vxlan", local_ip, remote_ip, vxlan_interface, vxlan_id, vxlan_port, federation_net, federation_subnet, "fed-net"))
    print(utils.attach_to_network(f"{meo_endpoint}/attach_to_network","mecapp_1","fed-net"))

    t_establish_vxlan_connection_with_provider_finished = int((time.time() - process_start_time) * 1000)
    data.append(['establish_vxlan_connection_with_provider_finished', t_establish_vxlan_connection_with_provider_finished])

    # Uncomment this during experiments
    logger.info(f"📡 Running connection test on mecapp_1 - Target IP: {deployed_mec_app_ip}")
    connection_test = utils.exec_cmd(f"{meo_endpoint}/exec","mecapp_1", f"ping -c 6 -i 0.2 {deployed_mec_app_ip}")
    stdout = connection_test["stdout"]
    logger.debug(f"🔍 Ping output:\n{stdout}")
    loss = float(re.search(r'(\d+(?:\.\d+)?)%\s*packet loss', stdout).group(1))
    status = "success" if loss < 100.0 else "failure"
    t_connection_test = int((time.time() - process_start_time) * 1000)
    if status == "success":
        logger.info(f"✅ Connection test SUCCESS ({100 - loss:.1f}% packets received)")
        data.append(['connection_test_success', t_connection_test])
    else:
        logger.warning(f"❌ Connection test FAILURE ({loss:.1f}% packet loss)")
        data.append(['connection_test_failure', t_connection_test])

    total_duration = time.time() - process_start_time

    logger.info(f"✅ Federation process successfully completed in {total_duration:.2f} seconds.")

    if export_to_csv:
        data.append(['service_id', service_id]) 
        utils.create_csv_file(csv_path, header, data)
    
    return {
        "status": "success",
        "duration_s": round(total_duration, 2)
    }

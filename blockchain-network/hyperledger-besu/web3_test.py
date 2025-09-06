# blockchain_interface.py

import json
import time
import logging
import threading
import os

from enum import Enum
from web3 import Web3, WebsocketProvider, HTTPProvider
from web3.middleware import geth_poa_middleware


logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class BlockchainInterface:
    def __init__(self, eth_address, private_key, eth_node_url):
        if eth_node_url.startswith("ws://"):
            self.web3 = Web3(WebsocketProvider(eth_node_url))
        elif eth_node_url.startswith("http://"):
            self.web3 = Web3(HTTPProvider(eth_node_url))
        else:
            raise ValueError("eth_node_url must start with ws:// or http://")

        self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        if not self.web3.is_connected():
            raise ConnectionError(f"Cannot connect to Ethereum node at {eth_node_url}")

        # Always convert to checksum address
        self.eth_address = Web3.to_checksum_address(eth_address)
        self.private_key = private_key

        logger.info(f"Web3 initialized. Address: {self.eth_address}")
        logger.info(f"Connected to Ethereum node {eth_node_url} | Version: {self.web3.client_version}")

        # Initialize local nonce and lock
        self._nonce_lock = threading.Lock()
        self._local_nonce = self.web3.eth.get_transaction_count(self.eth_address)

    # 🔹 Get current balance
    def get_balance(self):
        balance_wei = self.web3.eth.get_balance(self.eth_address)
        return self.web3.from_wei(balance_wei, "ether")

    # 🔹 Get latest nonce
    def get_nonce(self):
        return self.web3.eth.get_transaction_count(self.eth_address)

    # 🔹 Get transaction count (mined txs only)
    def get_transaction_count(self):
        return self.web3.eth.get_transaction_count(self.eth_address, block_identifier="latest")

    # 🔹 Get chain/network ID
    def get_chain_id(self):
        return self.web3.eth.chain_id

    # 🔹 Get latest block number
    def get_latest_block(self):
        return self.web3.eth.block_number


def load_eth_credentials(node_path: str):
    """
    Load Ethereum private key and address from Besu node config directory.
    """
    private_key_path = os.path.join(node_path, "accountPrivateKey")
    keystore_path = os.path.join(node_path, "accountKeystore")

    # Read private key (raw hex string)
    with open(private_key_path, "r") as f:
        private_key = f.read().strip()

    # Read address from keystore JSON
    with open(keystore_path, "r") as f:
        keystore = json.load(f)
        address = "0x" + keystore["address"]

    return {"address": address, "private_key": private_key}

# Example usage
if __name__ == "__main__":
    creds = load_eth_credentials("quorum-test-network/config/nodes/validator1")
    eth_address = creds["address"]
    eth_private_key = creds["private_key"]
    # eth_node_url="http://127.0.0.1:21001" # validator1 RPC HTTP endpoint
    eth_node_url="http://10.5.99.1:8545"
    blockchain = BlockchainInterface(
        eth_address=eth_address,
        private_key=eth_private_key,
        eth_node_url=eth_node_url
    )

    print("Balance (ETH):", blockchain.get_balance())
    print("Nonce:", blockchain.get_nonce())
    print("Tx count:", blockchain.get_transaction_count())
    print("Chain ID:", blockchain.get_chain_id())
    print("Latest block:", blockchain.get_latest_block())
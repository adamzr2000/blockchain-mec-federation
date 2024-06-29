# DLT Service Federation using Docker

<div align="center">

[![Static Badge](https://img.shields.io/badge/Docker-v25.0.3-blue)](https://github.com/docker)

</div>

## Overview

Federation of services aims to provide orchestration of services across multiple administrative domains (ADs). This project showcases how different ADs can establish federation efficiently using distributed ledger technologies (DLT) as a mediatior in the process. More specifically, the federation procedures are stored and deployed on a Federation Smart Contract, which is running on top of a permissioned blockchain. Each AD sets up a blockchain node to gain access to the blockchain network and they interact with the Federation Smart Contract by sending transactions.

**Author:** Adam Zahir Rodriguez

## Experimental Setup

Here is a diagram that represents visually the experimental setup:

![Experimental Setup](images/experimental-setup.svg)

- Two or more VMs, each acting as a separate AD, containing [Docker](https://docs.docker.com/engine/install/ubuntu)
- All VMs are interconnected in bridge mode
- All VMs have access to a blockchain node

## Workflow

- VM1 and VM2 are instantiated
- VM1 registers as a consumer domain, and VM2 registers as a provider domain in the Federation Smart Contract.
- VM1 decides it needs service extension and requests federation through the DLT.
- The DLT broadcasts the request. VM2 accepts, bids, and reveals its endpoint.
- VM1 receives the bid offer, accepts it, and reveals its own endpoint.
- VM2 initializes a VXLAN interface to the provided VM1 endpoint and deploys dummy containers based on the Alpine Linux image. Once the containers are deployed in the overlay network, VM2 notifies VM1 confirming the successful deployment and the IP address of the deployed federated service.
- VM1 establishes a VXLAN connection with VM2, enabling inter-service communication.

![Workflow](images/workflow.svg)

## Installation

1. Clone the repository:
```bash
git clone git@github.com:adamzr2000/blockchain-mec-federation.git
```

2. Build Docker Images:
Navigate to the [docker-images](./docker-images) directory and proceed to build the required Docker images for the project by executing their respective `build.sh` scripts:

```bash
cd docker-images
cd dlt-node && ./build.sh && cd ../truffle && ./build.sh && cd ../eth-netstats && ./build.sh
```

- `dlt-node`: Based on [Go-Ethereum (Geth)](https://geth.ethereum.org/docs) software, serving as nodes within the peer-to-peer blockchain network

- `truffle`: Development framework for Ethereum-based blockchain applications. It provides a suite of tools that allows developers to write, test, and deploy smart contracts on the blockchain network

- `eth-netstats`: Dashboard for monitoring Geth nodes within the blockchain network

3. Install the necessary python dependencies:
```bash
pip3 install -r requirements.txt
```

## Blockchain Network Setup

Firstly, we will create a blockchain network using `dlt-node` container images.  Initially, the network will comprise two nodes, corresponding to VM1 and VM2, respectively. `VM1` will act as the bootnode, facilitating the association of both nodes with each other.

1. Initialize the network:

`VM1` Navigate to the [dlt-network-docker](./dlt-network-docker) directory and start the network setup:

> Note: Please make sure to modify the IP addresses in the [node1.env](./config/dlt/node1.env) and [node2.env](./config/dlt/node2.env) files according to your setup before executing the script. Replace `IP_NODE_1` with the IP address of your `VM1` and `IP_NODE_2` with the IP address of your `VM2`.

```bash
cd dlt-network-docker
./start_dlt_network.sh
```

2. Join the network from a second node

`VM2` Navigate to the [dlt-network-docker](./dlt-network-docker) directory and join the blockchain network from the second node:

```bash
cd dlt-network-docker
./join_dlt_network.sh node2
```

3. Verify node association

After starting the blockchain network, you can verify that the nodes have associated correctly by executing the following commands:

```bash
# VM1
 ./get_peers.sh node1

# VM2  
 ./get_peers.sh node2
```
Each command should report `1 peer`, indicating that the nodes have successfully connected to each other.

Access the `eth-netsats` web interface for additional information at `http://<vm1-ip>:3000`

4. Adding more nodes:

More nodes can be added using the [join_dlt_network.sh](./dlt-network-docker/join_dlt_network.sh) file. The private network uses the [Clique (Proof-of-authority)](https://github.com/ethereum/EIPs/issues/225) consensus mechanism, which maintains the block structure as in PoW Ethereum, but instead of mining nodes competing to solve a difficult puzzle. There are pre-elected authorized signer nodes that can generate new blocks at any time. Each new block is endorsed by the list of signers, and the last signer node is responsible for populating the new block with transactions. The transaction reward for each new block created is shared between all the signers.

To join the consensus, new nodes must be accepted as "sealers" by at least (NUMBER_OF_TOTAL_SIGNERS / 2) + 1 nodes. To propose new signer nodes, execute the [add_validator.sh](./dlt-network-docker/add_validator.sh) script.

For example, to add a third node to the current blockchain network and participate as a sealer node, run the following commands:

```bash
# VM3
 ./join_dlt_network.sh node3

# VM1
./add_validator.sh node1 node3

# VM2 
./add_validator.sh node2 node3
```

Finally, check if the new node has been accepted as a sealer node with:

```bash
# VM3
./get_validators node3 
```

5. Stop the network:

`VM1` When needed, use the following command to stop the network:

```bash
./stop_dlt_network.sh
```

## Usage

1. Deploy the Federation Smart Contract to the blockchain Network:

`VM1` or `VM2` Execute the following commands:
```bash
cd smart-contracts
./deploy.sh 
```

2. Launch the orchestrator's web server on every VM and define the federation's domain parameters in the [federation](./dlt-network-docker/) directory using (at least) [consumer1.env](./config/federation/consumer1.env) and [provider1.env](./config/federation/provider1.env)files. Ensure to modify `DOMAIN_FUNCTION` according to the role within the federation (`consumer` or `provider`), and adjust `INTERFACE_NAME` to match your VM's network interface name for VXLAN tunnel setup.

```bash
# VM1
./start_app.sh config/federation/consumer1.env

# VM2
./start_app.sh config/federation/provider1.env

# VM3
./start_app.sh config/federation/provider2.env
```

For detailed information about the federation functions, refer to the REST API documentation, which is based on Swagger UI, at: `http://<vm-ip>:8000/docs`

3. Register each AD in the Smart Contract to enable their participation in the federation:

```bash
# VM1 
curl -X POST 'http://192.168.56.104:8000/register_domain'

# VM2 
curl -X POST 'http://192.168.56.105:8000/register_domain'
```

```bash
# VM1 
curl -X POST 'http://192.168.56.104:8000/start_experiments_consumer_v2'

# VM2 
curl -X POST 'http://192.168.56.105/start_experiments_provider_v2?export_to_csv=false&price=20'

# VM3
curl -X POST 'http://192.168.56.106/start_experiments_provider_v2?export_to_csv=false&price=15'
```


## API Endpoints

### Web3 Info
Returns `web3-info` details, otherwise returns an error message.

```sh
curl -X GET 'http://localhost:8000/web3_info'
```

### Transaction Receipt
Returns `tx-receipt` details for a specified `tx-hash`, otherwise returns an error message.

```sh
curl -X GET 'http://localhost:8000/tx_receipt?tx_hash=<tx-hash>'
```

### Register Domain
Returns the `tx-hash`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/register_domain?name=<domain-name>'
```

### Create Service Announcement
Returns the `tx-hash` and `service-id` for federation, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/create_service_announcement?requirements=<service-requirements>&service_endpoint_consumer=<service-endpoint-consumer>'
```

Example:
```sh
curl -X POST 'http://localhost:8000/create_service_announcement?requirements=service=alpine;replicas=1&service_endpoint_consumer=192.168.56.104'
```

### Check Service State
Returns the `state` of the federated service, which can be `open`,`closed`, or `deployed`; otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_service_state'
```

### Check Deployed Info
Returns the `service-endpoint` of the provider and `federated-host` (IP of the deployed service); otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_deployed_info?service_id=<service-id>'
```

### Check Service Announcements
Returns `announcements` details, otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_service_announcements'
```

### Place Bid
Returns the `tx-hash`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/place_bid?service_id=<service-id>&service_price=<service-price>'
```

### Check Bids
Returns the `bids` details, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/check_bids?service_id=<service-id>'
```

### Choose Provider
Returns the `tx-hash`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/choose_provider?bid_index=<bid-index>&service_id=<service-id>'
```

### Check if I am Winner
Returns the `winner-chosen`, which can be `yes`, or `no`; otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_if_i_am_winner?service_id=<service-id>'
```

### Check Winner
Returns the `am-i-winner`, which can be `yes`, or `no`; otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_winner?service_id=<service-id>'
```

### Deploy Service
Returns the `service-name`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/deploy_service?service_id=<service-id>'
```

### Deploy Docker Service
Returns the `service-name`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/deploy_docker_service?image=alpine&name=<service-name>&network=<docker-network>&replicas=<number-of-replicas>'
```

### Delete Docker Service
Returns successful deleted debug message, otherwise returns an error message.
```sh
curl -X DELETE 'http://localhost:8000/delete_docker_service?name=<service-name>'
```

### Delete Resources (VXLAN configuration and federated Docker network)

```sh
curl -X DELETE 'http://localhost:8000/delete_vxlan'
```


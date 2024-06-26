# DLT Service Federation using Kubernetes

<div align="center">

[![Static Badge](https://img.shields.io/badge/MicroK8s-v1.28.7-orange)](https://github.com/canonical/microk8s/tree/1.28)

[![Static Badge](https://img.shields.io/badge/Docker-v25.0.3-blue)](https://github.com/docker)

</div>

## Overview

Federation of services aims to provide orchestration of services across multiple administrative domains (ADs). This project showcases how different ADs can establish federation efficiently using distributed ledger technologies (DLT) as a mediatior in the process. More specifically, the federation procedures are stored and deployed on a Federation Smart Contract, which is running on top of a permissioned blockchain. Each AD sets up a blockchain node to gain access to the blockchain network and they interact with the Federation Smart Contract by sending transactions.

Here is a diagram that represents visually the experimental setup:

![Experimental Setup](images/experimental-setup.svg)

- 2 VMs, each acting as a separate AD, containing [Docker](https://docs.docker.com/engine/install/ubuntu)
- Both interconnected in bridge mode within [KVM](https://help.ubuntu.com/community/KVM/Networking)
- Both VMs have access to a blockchain node

**Author:** Adam Zahir Rodriguez

## Installation

1. Clone the repository:
```bash
git clone git@github.com:adamzr2000/blockchain-mec-federation.git
```

2. Build Docker Images:
Navigate to the `docker-images` directory and proceed to build the required Docker images for the project by executing their respective `build.sh` scripts:

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

Firstly, we will create a blockchain network using `dlt-node` container images. The network will consist of two nodes, corresponding to VM1 and VM2, respectively. **VM1** will act as the bootnode, facilitating the association of both nodes with each other.

1. Initialize the network:

**(VM1)** Navigate to the `dlt-network-docker` directory and start the network setup:

> Note: Please make sure to modify the IP addresses in the `.env` file according to your setup before executing the script. Replace `IP_NODE_1` with the IP address of your **VM1** and `IP_NODE_2` with the IP address of your **VM2**.

```bash
cd dlt-network-docker
./start_dlt_network.sh
```

2. Join the network from a second node

**(VM2)** Navigate to the `dlt-network-docker` directory and execute:

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

4. Stop the network:

**(VM1)** When needed, use the following command to stop the network:

```bash
./stop_dlt_network.sh
```

## Usage

1. Deploy the Federation Smart Contract to the blockchain Network:

**(VM1 or VM2)** Execute the following commands:
```bash
cd smart-contracts
./deploy.sh 
```

2. Start the orchestrator's web server on each VM and specify the domain role for the federation (e.g., VM1 as consumer and VM2 as provider)

```bash
./start_app.sh config/federation/consumer1.env
```

For detailed information about the federation functions, refer to the REST API documentation, which is based on Swagger UI, at: `http://<vm-ip>:8000/docs`

3. Register each AD in the Smart Contract to enable their participation in the federation:

```bash
# VM1 
curl -X POST http://<vm1-ip>:8000/register_domain

# VM2 
curl -X POST http://<vm2-ip>:8000/register_domain
```


# Blockchain-Driven Federation for Distributed Edge Systems

This project contains the code repositoy, measurements and analysis tools used in the paper entitled `Blockchain-Driven Federation for Distributed Edge Systems: Design and Experimental Validation`

**Author:** Adam Zahir Rodriguez

---

## 🚀 Deployment guide

### Build Docker Images:
```bash
docker compose build
```

### Deploy the blockchain network (distributed)

1. Initialize the network on `domain1`:

> Note: Please make sure to modify the IP addresses in the [node1.env](./config/dlt/node1.env) and [node2.env](./config/dlt/node2.env) files according to your setup before executing the script.

```bash
cd blockchain-network/geth-poa
./start.sh --validators 2
```

2. Join the network on `domain2`:

```bash
cd blockchain-network/geth-poa
./join.sh --id 2 --validators 2
```

## Usage

1. Deploy the Federation Smart Contract to the blockchain Network:

```bash
./deploy_smart_contract.sh --network-id 1234 --node-ip 127.0.0.1 --port 3334 --protocol ws
```

2. Launch the MEO/MEF server on every VM and define the federation's domain parameters in the [federation](./blockchain-network/) directory using (at least) [consumer1.env](./config/federation/consumer1.env) and [provider1.env](./config/federation/provider1.env) files. Ensure to modify `DOMAIN_FUNCTION` according to the role within the federation (`consumer` or `provider`), and adjust `INTERFACE_NAME` to match your VM's network interface name for VXLAN tunnel setup.

```bash
# VM1
./start_app.sh config/federation/consumer1.env

# VM2
./start_app.sh config/federation/provider1.env

# VM3
./start_app.sh config/federation/provider2.env
```

For detailed information about the federation functions, refer to the FastAPI documentation, which is based on Swagger UI, at: `http://<vm-ip>:8000/docs`

3. Register each AD in the Smart Contract to enable their participation in the federation:

```bash
# VM1 
curl -X POST 'http://10.5.99.1:8000/register_domain' 

# VM2 
curl -X POST 'http://10.5.99.2:8000/register_domain' 

# VM3
curl -X POST 'http://10.5.99.3:8000/register_domain' 
```

```bash
# VM1 
curl -X POST 'http://10.5.99.1:8000/start_experiments_consumer?export_to_csv=false&providers=2'

# VM2 
curl -X POST 'http://10.5.99.2:8000/start_experiments_provider?export_to_csv=false&price=20'

# VM3
curl -X POST 'http://10.5.99.3:8000/start_experiments_provider?export_to_csv=false&price=15'
```


## API Endpoints

### Web3 Info
Returns `web3-info` details, otherwise returns an error message.

```sh
curl -X GET 'http://localhost:8000/web3_info' | jq
```

### Transaction Receipt
Returns `tx-receipt` details for a specified `tx-hash`, otherwise returns an error message.

```sh
curl -X GET 'http://localhost:8000/tx_receipt?tx_hash=<tx-hash>' | jq
```

### Register Domain
Returns the `tx-hash`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/register_domain?name=<domain-name>' | jq
```

### Create Service Announcement
Returns the `tx-hash` and `service-id` for federation, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/create_service_announcement?requirements=<service-requirements>&service_endpoint_consumer=<service-endpoint-consumer>' | jq
```

Example:
```sh
curl -X POST 'http://localhost:8000/create_service_announcement?requirements=service=alpine;replicas=1&service_endpoint_consumer=192.168.56.104' | jq
```

### Check Service Announcements
Returns `announcements` details, otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_service_announcements' | jq
```

### Place Bid
Returns the `tx-hash`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/place_bid?service_id=<service-id>&service_price=<service-price>' | jq
```

### Check Bids
Returns the `bids` details, otherwise returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_bids?service_id=<service-id>' | jq
```

### Choose Provider
Returns the `tx-hash`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/choose_provider?bid_index=<bid-index>&service_id=<service-id>' | jq
``` 

### Check Winner
Returns the `am-i-winner`, which can be `yes`, or `no`; otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_winner?service_id=<service-id>' | jq
```

### Check if I am Winner
Returns the `winner-chosen`, which can be `yes`, or `no`; otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_if_i_am_winner?service_id=<service-id>' | jq
```

### Deploy Service
Returns the `service-name`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/deploy_service?service_id=<service-id>' | jq
```

### Deploy Docker Service
Returns the `service-name`, otherwise returns an error message.

```sh
curl -X POST 'http://localhost:8000/deploy_docker_service?image=alpine&name=<service-name>&network=<docker-network>&replicas=<number-of-replicas>' | jq
```

### Check Service State
Returns the `state` of the federated service, which can be `open`,`closed`, or `deployed`; otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_service_state?service_id=<service-id>' | jq
```

### Check Deployed Info
Returns the `service-endpoint` of the provider and `federated-host` (IP of the deployed service); otherwise, returns an error message.

```sh
curl -X GET 'http://localhost:8000/check_deployed_info?service_id=<service-id>' | jq
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


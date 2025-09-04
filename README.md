# Blockchain-Driven Federation for Distributed Edge Systems

This project contains the code repositoy, measurements and analysis tools used in the paper entitled `Blockchain-Driven Federation for Distributed Edge Systems: Design and Experimental Validation`

**Author:** Adam Zahir Rodriguez

---

```bash
python3 utils/ssh_git_pull.py -n 3
```

## 🚀 Deployment guide

### Build Docker Images:
```bash
docker compose build
```

### Deploy the blockchain network (distributed)

```bash
python3 utils/ssh_blockchain_network.py --start -n 3
```

```bash
python3 utils/ssh_blockchain_network.py --stop -n 3
```

### Deploy the Federation Smart Contract

```bash
./deploy_smart_contract.sh --network-id 1234 --node-ip 10.5.99.1 --port 3334 --protocol ws
```

> Note: gas used: 2813598 (0x2aee9e)

### Deploy the MEO and the MEF (blockchain manager)

```bash
python3 utils/ssh_mef_meo.py --start -n 3 -c 1 --mef --meo
```
```bash
python3 utils/ssh_mef_meo.py --stop -n 3 --mef --meo
```

### Demo

```bash
python3 utils/register_federation_participants.py -n 3
```

```shell
curl -X POST "http:///10.5.99.1:6666/deploy_docker_service?image=mec-app:latest&name=mecapp&network=bridge&replicas=1" | jq
```

```bash
curl -X POST "http://10.5.99.1:8000/start_experiments_consumer" \
-H 'Content-Type: application/json' \
-d '{
   "requirements": "zero_packet_loss",
   "offers_to_wait": 2,
   "meo_endpoint": "http://10.5.99.1:6666",
   "ip_address": "10.5.99.1",
   "vxlan_interface": "ens3",
   "node_id": 1,
   "export_to_csv": false,
   "csv_path": "/experiments/test/consumer_run_1.csv"
}' | jq
```

```bash
curl -X POST "http://10.5.99.2:8000/start_experiments_provider" \
-H 'Content-Type: application/json' \
-d '{
   "price_wei_per_hour": 10,
   "meo_endpoint": "http://10.5.99.2:6666",
   "ip_address": "10.5.99.2",
   "vxlan_interface": "ens3",
   "node_id": 2,
   "export_to_csv": false,
   "csv_path": "/experiments/test/provider_2_run_1.csv"
}' | jq
```

```bash
curl -X POST "http://10.5.99.3:8000/start_experiments_provider" \
-H 'Content-Type: application/json' \
-d '{
   "price_wei_per_hour": 20,
   "meo_endpoint": "http://10.5.99.3:6666",
   "ip_address": "10.5.99.3",
   "vxlan_interface": "ens3",
   "node_id": 3,
   "export_to_csv": false,
   "csv_path": "/experiments/test/provider_2_run_1.csv"
}' | jq
```

```shell
curl -X DELETE "http://10.5.99.1:6666/delete_docker_service?name=mecapp" | jq
curl -X DELETE "http://10.5.99.1:6666/delete_vxlan?vxlan_id=201&docker_net_name=fed-net" | jq
```

```shell
curl -X DELETE "http://10.5.99.2:6666/delete_docker_service?name=mecapp" | jq
curl -X DELETE "http://10.5.99.2:6666/delete_vxlan?vxlan_id=201&docker_net_name=fed-net" | jq
```

---

## API Endpoints

### Web3 Info
Returns `web3-info` details, otherwise returns an error message.

```bash
curl -X 'GET' "http://localhost:8000/web3_info" | jq
```
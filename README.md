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

### Deploy the MEO

```bash
python3 utils/ssh_meo.py --start -n 3
```

```bash
python3 utils/ssh_meo.py --stop -n 3
```

### Deploy the MEF (blockchain manager)

```bash
python utils/ssh_mef.py --start -n 3 -c 1
```

```bash
python3 utils/ssh_mef.py --stop -n 3
```

### Demo
```bash
curl -X POST 'http://10.5.99.1:8000/register_domain/domain1' 
```
---
```bash
curl -X POST 'http://10.5.99.2:8000/register_domain/domain2' 
```
---
```bash
curl -X POST 'http://10.5.99.3:8000/register_domain/domain3' 
```

```bash
curl -X POST "http://10.5.99.1:8000/start_demo_provider" \
-H 'Content-Type: application/json' \
-d '{
   "endpoint": "k8s_deployment"
   "price_wei_per_hour": 10,
   "location": "Madrid, Spain",
   "export_to_csv": false,
   "csv_path": "federation_demo_provider.csv"
}' | jq
```

## API Endpoints

### Web3 Info
Returns `web3-info` details, otherwise returns an error message.

```bash
FED_API="localhost:8000"
curl -X 'GET' "http://$FED_API/web3_info" | jq
```
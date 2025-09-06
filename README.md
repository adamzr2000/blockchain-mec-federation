# Blockchain-Driven Federation for Distributed Edge Systems

This project contains the code repositoy, measurements and analysis tools used in the paper entitled `Blockchain-Driven Federation for Distributed Edge Systems: Design and Experimental Validation`

**Author:** Adam Zahir Rodriguez

---

## Build Docker Images:
```bash
docker compose build
```

## 🚀 Experiments

[README here](./utils)

<!-- ```bash
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
``` -->
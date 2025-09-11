## 🚀 Experimental scenario

<!-- ### Deploy the blockchain network (distributed) - Geth
```bash
PARTICIPANTS=3
python3 ssh_geth_poa_network.py --start -n $PARTICIPANTS
```
```bash
./deploy_smart_contract_truffle.sh --network-id 1234 --node-ip 10.5.99.1 --port 3334 --protocol ws
```

[eth netstats dashboard](http://10.5.99.1:3000/)

> Note: gas used: 2813598 (0x2aee9e)

--- -->
### Deploy the blockchain network (distributed) - Besu
```bash
PARTICIPANTS=3
python3 ssh_besu_network.py --start -n $PARTICIPANTS
```
```bash
./deploy_smart_contract_hardhat.sh --rpc_url http://10.5.99.1:8545 --chain_id 1337
```

[QUORUM EXPLORER](http://10.5.99.1:25000/explorer/nodes)

---
### Deploy the MEO and the MEF
```bash
python3 ssh_mef_meo.py --start -n $PARTICIPANTS -c 1 --mef --meo
```
---
### Register MECs in the smart contract
```bash
python3 register_federation_participants.py -n $PARTICIPANTS
```
---
### Run registration experiments
```bash
TESTS=5
python3 run_experiments_registration.py -n $PARTICIPANTS -t $TESTS
```
```bash
TESTS=5
python3 run_experiments_registration.py -n $PARTICIPANTS -t $TESTS --export-csv --csv-base /experiments/test
```
---
### Run experiments 1 consumer
```bash
TESTS=5
python3 run_experiments_one_offer.py -n $PARTICIPANTS -t $TESTS
```
```bash
TESTS=5
python3 run_experiments_one_offer.py -n $PARTICIPANTS -t $TESTS --export-csv --csv-base /experiments/test
```
---
### Run experiments multiple consumers
```bash
python3 run_experiments_multiple_offers.py -n 4 -c 3 -t 1
```
```bash
python3 run_experiments_multiple_offers.py -n 4 -c 3 -t 1 --export-csv --csv-base /experiments/multiple-offers/clique/4-mecs
```
---
### Push results to git
```bash
python3 ssh_git_sync_experiments.py -n $PARTICIPANTS
```
```bash
python3 ssh_git_pull.py -n $PARTICIPANTS
```
---
### Stop the MEO and the MEF
```bash
python3 ssh_mef_meo.py --stop -n $PARTICIPANTS --mef --meo
```
---
<!-- ### Stop the blockchain network (distributed) - Geth
```bash
python3 ssh_geth_poa_network.py --stop -n $PARTICIPANTS
```
--- -->
### Stop the blockchain network (distributed) - Besu
```bash
python3 ssh_besu_network.py --stop -n $PARTICIPANTS
```

---

### Time
```bash
sudo timedatectl set-timezone Europe/Madrid
timedatectl
date
```

### Web3 endpoints

## Clique
```shell
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"clique_getSigners",
    "params":["latest"],
    "id":1
  }'
```
## QBFT/IBFT
```shell
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"qbft_getValidatorsByBlockNumber",
    "params":["latest"],
    "id":1
  }'
```
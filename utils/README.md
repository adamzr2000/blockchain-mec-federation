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
# 4
python3 run_experiments_registration.py -n 4 -t 20 --export-csv --csv-base /experiments/registration/clique/4-mecs
# 10
python3 run_experiments_registration.py -n 10 -t 20 --export-csv --csv-base /experiments/registration/clique/10-mecs
# 20
python3 run_experiments_registration.py -n 20 -t 20 --export-csv --csv-base /experiments/registration/clique/20-mecs
# 30
python3 run_experiments_registration.py -n 30 -t 20 --export-csv --csv-base /experiments/registration/clique/30-mecs
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
# 4 (3c, 1p)
python3 run_experiments_multiple_offers.py -n 4 -c 3 -t 1
# 10 (8c, 2p)
python3 run_experiments_multiple_offers.py -n 10 -c 8 -t 1
# 20 (16c, 4p)
python3 run_experiments_multiple_offers.py -n 20 -c 16 -t 1
# 30 (24c, 6p)
python3 run_experiments_multiple_offers.py -n 30 -c 24 -t 1
```
```bash
# 4 (3c, 1p)
python3 run_experiments_multiple_offers.py -n 4 -c 3 -t 20 --export-csv --csv-base /experiments/multiple-offers/clique/4-mecs
# 10 (8c, 2p)
python3 run_experiments_multiple_offers.py -n 10 -c 8 -t 20 --export-csv --csv-base /experiments/multiple-offers/clique/10-mecs
# 20 (16c, 4p)
python3 run_experiments_multiple_offers.py -n 20 -c 16 -t 20 --export-csv --csv-base /experiments/multiple-offers/clique/20-mecs
# 30 (24c, 6p) 
python3 run_experiments_multiple_offers.py -n 30 -c 24 -t 20 --export-csv --csv-base /experiments/multiple-offers/clique/30-mecs
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

## SoA
``` shell
python3 register_federation_participants_soa.py -n 4 -c 3
python3 run_experiments_registration_soa.py -n 4 -c 3 -t 5
python3 run_experiments_multiple_offers_soa.py -n 4 -c 3 -t 1
python3 unregister_federation_participants_soa.py -n 4
```

```shell
#1
python3 ssh_mef_meo_soa.py --start -n 4 -c 3 --mef --meo

#2
python3 run_experiments_registration_soa.py -n 4 -c 3 -t 20 --export-csv --csv-base /experiments/registration/soa/4-mecs

#3
python3 register_federation_participants_soa.py -n 4 -c 3

#4
python3 run_experiments_multiple_offers_soa.py -n 4 -c 3 -t 20 --export-csv --csv-base /experiments/multiple-offers/soa/4-mecs
```

```shell
#1
python3 ssh_mef_meo_soa.py --start -n 10 -c 8 --mef --meo

#2
python3 run_experiments_registration_soa.py -n 10 -c 8 -t 20 --export-csv --csv-base /experiments/registration/soa/10-mecs

#3
python3 register_federation_participants_soa.py -n 10 -c 8

#4
python3 run_experiments_multiple_offers_soa.py -n 10 -c 8 -t 20 --export-csv --csv-base /experiments/multiple-offers/soa/10-mecs
```

```shell
#1
python3 ssh_mef_meo_soa.py --start -n 20 -c 16 --mef --meo

#2
python3 run_experiments_registration_soa.py 20 -c 16 -t 20 --export-csv --csv-base /experiments/registration/soa/20-mecs

#3
python3 register_federation_participants_soa.py 20 -c 16

#4
python3 run_experiments_multiple_offers_soa.py 20 -c 16 -t 20 --export-csv --csv-base /experiments/multiple-offers/soa/20-mecs
```

```shell
#1
python3 ssh_mef_meo_soa.py --start -n 30 -c 24 --mef --meo

#2
python3 run_experiments_registration_soa.py -n 30 -c 24 -t 20 --export-csv --csv-base /experiments/registration/soa/30-mecs

#3
python3 register_federation_participants_soa.py -n 30 -c 24

#4
python3 run_experiments_multiple_offers_soa.py -n 30 -c 24 -t 20 --export-csv --csv-base /experiments/multiple-offers/soa/30-mecs
```
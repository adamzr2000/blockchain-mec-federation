## 🚀 Demo

### Deploy the blockchain network (distributed) - Geth
```bash
PARTICIPANTS=3
python3 ssh_geth_poa_network.py --start -n $PARTICIPANTS
```
```bash
./deploy_smart_contract.sh --network-id 1234 --node-ip 10.5.99.1 --port 3334 --protocol ws
```
[eth netstats dashboard](http://10.5.99.1:3000/)
---
### Deploy the blockchain network (distributed) - Besu
```bash
PARTICIPANTS=3
python3 ssh_besu_network.py --start -n $PARTICIPANTS
```
```bash
./deploy_smart_contract.sh --network-id 1337 --node-ip 10.5.99.1 --port 8445 --protocol http
```
[quorum explorer dashboard](http://10.5.99.1:25000/explorer/nodes)
> Note: gas used: 2813598 (0x2aee9e)
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
### Run experiments 1 consumer
```bash
TESTS=5
python3 run_experiments_one_offer.py -n $PARTICIPANTS -t $TESTS
```
---
### Run experiments 1 consumer (and export results)
```bash
TESTS=5
python3 run_experiments_one_offer.py -n $PARTICIPANTS -t $TESTS --export-csv --csv-base /experiments/test
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
### Stop the blockchain network (distributed) - Geth
```bash
python3 ssh_geth_poa_network.py --stop -n $PARTICIPANTS
```
---
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
### Demo

```bash
python3 register_federation_participants.py -n 3
```
```bash
python3 run_experiments_one_offer.py -n 3 -t 3
```
---
```bash
PARTICIPANTS=3
python3 run_experiments_one_offer.py -n $PARTICIPANTS -t 5 --export-csv --csv-base /experiments/test
```
```bash
python3 ssh_git_sync_experiments.py -n $PARTICIPANTS
```
```bash
python3 utils/ssh_git_pull.py -n $PARTICIPANTS
```
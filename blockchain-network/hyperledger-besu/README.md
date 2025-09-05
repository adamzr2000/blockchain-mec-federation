# Cluster setup
```bash
docker swarm init --advertise-addr 10.5.99.1
```
```bash
docker swarm join-token worker
```
```bash
docker node ls
```
---
```bash
docker swarm join --token <token> 10.5.99.1:2377
``` 
```bash
docker network create --attachable --subnet 172.16.239.0/24 --driver overlay quorum-dev-quickstart
```
```bash
docker swarm leave --force
``` 
---
# Deploy blockchain network
```bash
./run.sh docker-compose-validator1.yml
./run.sh docker-compose-validator2.yml
./run.sh docker-compose-validator3.yml
./run.sh docker-compose-validator4.yml
```
---
```bash
./remove.sh docker-compose-validator1.yml
./remove.sh docker-compose-validator2.yml
./remove.sh docker-compose-validator3.yml
./remove.sh docker-compose-validator4.yml
```
```bash
docker network rm quorum-dev-quickstart
docker swarm leave --force
docker info | grep Swarm
```
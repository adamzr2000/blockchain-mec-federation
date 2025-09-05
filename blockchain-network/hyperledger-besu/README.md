# Cluster setup
```bash
docker swarm init --advertise-addr 10.5.99.1
```
```bash
docker node ls
```
---
```bash
docker swarm join --token <token> 10.5.99.1:2377
``` 
```bash
docker swarm leave --force
``` 
---
# Deploy blockchain network
```bash
docker network create --attachable --subnet 172.16.239.0/24 --driver overlay quorum-dev-quickstart
```
```bash
./run.sh docker-compose-validator1.yml
./run.sh docker-compose-validator2.yml
```
---

---
```bash
./remove.sh docker-compose-validator1.yml
./remove.sh docker-compose-validator2.yml
```
```bash
docker network rm quorum-dev-quickstart
docker swarm leave --force
docker info | grep Swarm
```
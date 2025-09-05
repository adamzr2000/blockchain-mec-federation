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
# Test service
```bash
docker stack deploy -c docker-compose.yml demo
```
```bash
docker ps -a
docker service ls
docker service ps demo_alpine1
docker service ps demo_alpine2
docker service logs -f demo_alpine1
docker service logs -f demo_alpine2
```
```bash
docker stack rm demo
docker network rm demo_demo-net
docker swarm leave --force
docker info | grep Swarm
```
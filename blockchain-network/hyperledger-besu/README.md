# Master
```bash
docker swarm init --advertise-addr 10.5.99.1
```
```bash
docker node ls
```

# Workers
```bash
docker swarm join --token <token> 10.5.99.1:2377
``` 
```bash
docker swarm leave --force
``` 
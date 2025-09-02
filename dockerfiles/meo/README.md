```shell
curl -X POST "http://localhost:6666/deploy_docker_service?image=nginx:alpine&name=testsvc&network=bridge&replicas=1" | jq
```

```shell
docker network create testnet

curl -X POST "http://localhost:6666/attach_to_network?container_name=testsvc_1&network_name=testnet" | jq
```

```shell
curl -X POST "http://localhost:6666/exec?container_name=testsvc_1&cmd=ping%20-c%204%208.8.8.8"
```

```shell
curl -X DELETE "http://localhost:6666/delete_docker_service?name=testsvc" | jq

docker network rm testnet
```
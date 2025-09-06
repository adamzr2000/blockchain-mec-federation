```shell
curl -X POST "http://localhost:6666/deploy_docker_service?image=nginx:alpine&name=testsvc&network=bridge&replicas=1" | jq
```

```shell
curl -X GET "http://localhost:6666/service_ips?name=testsvc" | jq
```

```shell
docker network create testnet

curl -X POST "http://localhost:6666/attach_to_network?container_name=testsvc_1&network_name=testnet" | jq
```

```shell
curl -X POST "http://localhost:6666/exec?container_name=testsvc_1&cmd=ping%20-c%204%208.8.8.8" | jq
```

```shell
curl -X DELETE "http://localhost:6666/delete_docker_service?name=testsvc" | jq

docker network rm testnet
```

# VXLAN

```shell
# domain1
curl -X POST "http://localhost:6666/configure_vxlan?local_ip=10.5.99.1&remote_ip=10.5.99.2&interface_name=ens3&vxlan_id=200&dst_port=4789&subnet=10.0.0.0/16&ip_range=10.0.1.0/24&docker_net_name=fed-net" | jq

curl -X POST "http://localhost:6666/deploy_docker_service?image=nginx:alpine&name=testsvc&network=fed-net&replicas=1" | jq

curl -X POST "http://localhost:6666/exec?container_name=testsvc_1&cmd=ping%20-c%205%2010.0.2.1" | jq

# domain2
curl -X POST "http://localhost:6666/configure_vxlan?local_ip=10.5.99.2&remote_ip=10.5.99.1&interface_name=ens3&vxlan_id=200&dst_port=4789&subnet=10.0.0.0/16&ip_range=10.0.2.0/24&docker_net_name=fed-net" | jq

curl -X POST "http://localhost:6666/deploy_docker_service?image=nginx:alpine&name=testsvc&network=fed-net&replicas=1" | jq

curl -X POST "http://localhost:6666/exec?container_name=testsvc_1&cmd=ping%20-c%205%2010.0.1.1" | jq
```

```shell
curl -X DELETE "http://localhost:6666/delete_docker_service?name=testsvc" | jq

curl -X DELETE "http://localhost:6666/delete_vxlan?vxlan_id=200&docker_net_name=fed-net" | jq
```

# Monitoring

```shell
curl -X POST "http://localhost:6666/monitor/start?container=validator1&interval=1.0&stdout=true" | jq

curl -X POST "http://localhost:6666/monitor/start?container=validator1&interval=1.0&csv_path=%2Fexperiments%2Ftest%2Fvalidator1.csv&stdout=true" | jq

curl -X POST "http://localhost:6666/monitor/stop" | jq
```





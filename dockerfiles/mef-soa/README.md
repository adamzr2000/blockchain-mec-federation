```shell
./start_mef_soa.sh \
  --domain-function consumer \
  --container-name mef-soa-c \
  --meo-url http://127.0.0.1:6666 \
  --port 9000 \
  --local-domain-id consumer_1 \
  --node-id 1 \
  --vxlan-interface ens3
```

```shell
./start_mef_soa.sh \
  --domain-function provider \
  --container-name mef-soa-p \
  --meo-url http://172.19.209.157:6666 \
  --port 9001 \
  --local-domain-id provider_1 \
  --node-id 2 \
  --vxlan-interface ens3
```

```shell
curl -sS -X POST http://localhost:9000/federators/autoRegister \
  -H "Content-Type: application/json" \
  -d '{
        "providers": ["http://172.19.209.157:9001"],
        "self_url": "http://localhost:9000",
        "export_to_csv": false
      }' | jq
```
```shell
curl -sS http://localhost:9000/federators | jq
curl -X DELETE http://localhost:9000/federators | jq
```

```shell
# grab the token the consumer stored for provider_1
TOKEN=$(curl -s http://localhost:9000/federators | jq -r '.provider_1.token')

# call provider's admissionCheck with the token
curl -sS -X POST http://172.19.209.157:9001/admissionCheck \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service_id":"svc-test-123","requirements":"zero_packet_loss"}' | jq
```
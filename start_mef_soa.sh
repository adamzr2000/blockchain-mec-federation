#!/usr/bin/env bash
set -euo pipefail

# Defaults
port="8000"
container_name="mef-soa"
domain_function=""
image="mef-soa:latest"
meo_url="http://127.0.0.1:6666"
node_id="1"
vxlan_interface="ens3"
local_domain_id="mef-1"          # NEW
jwt_secret="super-secret-demo-key" # optional; keep defaults aligned with code

usage() {
  cat <<EOF
Usage: $0 --domain-function <provider|consumer>
          [--port <port>]
          [--container-name <name>]
          [--image <image>]
          [--meo-url <url>]
          [--node-id <int>]
          [--vxlan-interface <iface>]
          [--local-domain-id <id>]
          [--jwt-secret <secret>]

Examples:
  $0 --domain-function provider --port 9001 --node-id 7 --vxlan-interface ens4 --local-domain-id mef-p1
  $0 --domain-function consumer --port 9000 --meo-url http://10.5.99.1:6666 --node-id 3 --local-domain-id mef-c1
EOF
  exit 1
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain-function) domain_function="$(echo "${2:-}" | tr '[:upper:]' '[:lower:]')"; shift 2 ;;
    --container-name)  container_name="${2:-}"; shift 2 ;;
    --image)           image="${2:-}"; shift 2 ;;
    --port)            port="${2:-}"; shift 2 ;;
    --meo-url)         meo_url="${2:-}"; shift 2 ;;
    --node-id)         node_id="${2:-}"; shift 2 ;;
    --vxlan-interface) vxlan_interface="${2:-}"; shift 2 ;;
    --local-domain-id) local_domain_id="${2:-}"; shift 2 ;;   # NEW
    --jwt-secret)      jwt_secret="${2:-}"; shift 2 ;;         # NEW
    -*|--*)            echo "Unknown option: $1"; usage ;;
    *)                 break ;;
  esac
done

# Validate
[[ -n "$domain_function" ]] || { echo "ERROR: --domain-function is required."; usage; }
[[ "$domain_function" == "provider" || "$domain_function" == "consumer" ]] || {
  echo "ERROR: --domain-function must be provider|consumer"; exit 1;
}
if ! [[ "$node_id" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --node-id must be an integer"; exit 1;
fi

cat <<INFO
Launching '$container_name':
  Domain function   : $domain_function
  Host port         : $port
  Image             : $image
  MEO URL           : $meo_url
  NODE_ID           : $node_id
  VXLAN_INTERFACE   : $vxlan_interface
  LOCAL_DOMAIN_ID   : $local_domain_id
INFO

# Run container
docker run \
  --rm -d \
  --name "$container_name" \
  --hostname "$container_name" \
  -p "${port}:8000" \
  --env "DOMAIN_FUNCTION=$domain_function" \
  --env "MEO_URL=$meo_url" \
  --env "NODE_ID=$node_id" \
  --env "VXLAN_INTERFACE=$vxlan_interface" \
  --env "LOCAL_DOMAIN_ID=$local_domain_id" \
  --env "JWT_SECRET=$jwt_secret" \
  -v "$(pwd)/dockerfiles/mef-soa/app":/app \
  -v "$(pwd)/experiments":/experiments \
  "$image"

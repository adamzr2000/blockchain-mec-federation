#!/usr/bin/env bash
set -euo pipefail

# Defaults
port="8000"
container_name="blockchain-manager"
domain_function=""
image="mef-blockchain-manager:latest"
rpc_url=""
node_path=""
deployments_file="$(pwd)/smart-contracts/deployments/besu-Federation.json"

usage() {
  cat <<EOF
Usage: $0 --node-path <path/to/nodeX> --domain-function <provider|consumer> --rpc_url <http://ip:port> [--port <port>] [--container-name <name>] [--image <image>]

Examples:
  $0 --node-path blockchain-network/hyperledger-besu/quorum-test-network/config/nodes/validator1 --domain-function provider --rpc_url http://10.5.99.1:8545
EOF
  exit 1
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --node-path) node_path="$2"; shift 2 ;;
    --domain-function) domain_function="$(echo "$2" | tr '[:upper:]' '[:lower:]')"; shift 2 ;;
    --rpc_url) rpc_url="$2"; shift 2 ;;
    --port) port="$2"; shift 2 ;;
    --container-name) container_name="$2"; shift 2 ;;
    --image) image="$2"; shift 2 ;;
    -*|--*) echo "Unknown option: $1"; usage ;;
    *) break ;;
  esac
done

# Validate
[[ -n "$node_path" && -n "$domain_function" && -n "$rpc_url" ]] || { echo "ERROR: --node-path, --domain-function and --rpc_url are required."; usage; }
[[ "$domain_function" == "provider" || "$domain_function" == "consumer" ]] || { echo "ERROR: --domain-function must be provider|consumer"; exit 1; }
[[ -d "$node_path" ]] || { echo "ERROR: Node path '$node_path' not found."; exit 1; }

# Extract ETH values
privkey_file="$node_path/accountPrivateKey"
keystore_file="$node_path/accountKeystore"

[[ -f "$privkey_file" ]] || { echo "ERROR: Private key file not found at $privkey_file"; exit 1; }
[[ -f "$keystore_file" ]] || { echo "ERROR: Keystore file not found at $keystore_file"; exit 1; }

ETH_PRIVATE_KEY="$(<"$privkey_file")"

# Extract ETH address from keystore JSON
ETH_ADDRESS="$(grep -o '"address":[[:space:]]*"[^"]*"' "$keystore_file" | head -n1 | cut -d'"' -f4)"
ETH_ADDRESS="0x${ETH_ADDRESS}"

[[ -n "$ETH_ADDRESS" ]] || { echo "ERROR: Could not extract ETH address from $keystore_file"; exit 1; }

# Extract contract address from deployments JSON using grep/sed/awk
[[ -f "$deployments_file" ]] || { echo "ERROR: Deployments file not found: $deployments_file"; exit 1; }
CONTRACT_ADDRESS="$(grep -o '"address":[[:space:]]*"[^"]*"' "$deployments_file" | head -n1 | cut -d'"' -f4)"
[[ -n "$CONTRACT_ADDRESS" ]] || { echo "ERROR: Could not extract contract address."; exit 1; }

# Mask helper
mask() { local s="$1"; [[ ${#s} -le 8 ]] && printf '%s' "$s" || printf '%s…%s' "${s:0:6}" "${s: -4}"; }

cat <<INFO
Launching '$container_name':
  Domain function  : $domain_function
  ETH_ADDRESS      : $ETH_ADDRESS
  ETH_PRIVATE_KEY  : $(mask "$ETH_PRIVATE_KEY")
  RPC URL          : $rpc_url
  CONTRACT_ADDRESS : $CONTRACT_ADDRESS
  Host port        : $port
  Image            : $image
INFO

# Run container
docker run \
  --rm -d \
  --name "$container_name" \
  --hostname "$container_name" \
  -p "${port}:8000" \
  --env "ETH_ADDRESS=$ETH_ADDRESS" \
  --env "ETH_PRIVATE_KEY=$ETH_PRIVATE_KEY" \
  --env "ETH_NODE_URL=$rpc_url" \
  --env "CONTRACT_ADDRESS=$CONTRACT_ADDRESS" \
  --env "DOMAIN_FUNCTION=$domain_function" \
  -v "$(pwd)/smart-contracts":/smart-contracts \
  -v "$(pwd)/experiments":/experiments \
  -v "$(pwd)/dockerfiles/mef-blockchain-manager/app":/app \
  "$image"

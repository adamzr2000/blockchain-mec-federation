#!/usr/bin/env bash
set -euo pipefail

# Defaults
port="8000"
container_name="blockchain-manager"
config=""
domain_function=""
image="mef-blockchain-manager:latest"

usage() {
  cat <<EOF
Usage: $0 --config <path/to/nodeX.env> --domain-function <provider|consumer> [--port <port>] [--container-name <name>] [--image <image>]
EOF
  exit 1
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) config="$2"; shift 2 ;;
    --domain-function) domain_function="$(echo "$2" | tr '[:upper:]' '[:lower:]')"; shift 2 ;;
    --port) port="$2"; shift 2 ;;
    --container-name) container_name="$2"; shift 2 ;;
    --image) image="$2"; shift 2 ;;
    -*|--*) echo "Unknown option: $1"; usage ;;
    *) break ;;
  esac
done

# Validate
[[ -n "$config" && -n "$domain_function" ]] || { echo "ERROR: --config and --domain-function are required."; usage; }
[[ "$domain_function" == "provider" || "$domain_function" == "consumer" ]] || { echo "ERROR: --domain-function must be provider|consumer"; exit 1; }
[[ -f "$config" ]] || { echo "ERROR: Config file '$config' not found."; exit 1; }

# Infer node index X from filename ".../nodeX.env"
base="$(basename "$config")"
if [[ "$base" =~ ^[Nn]ode([0-9]+)\.env$ || "$base" =~ ^node([0-9]+)\.env$ || "$base" =~ ([0-9]+) ]]; then
  node_idx="${BASH_REMATCH[1]}"
else
  echo "ERROR: Could not infer node index from '$base' (expected something like node5.env)."
  exit 1
fi

# Safe getter: extract VAR=value from file without executing anything
get_var() {
  local var="$1" file="$2" line val
  line="$(grep -E "^[[:space:]]*${var}[[:space:]]*=" "$file" | tail -n1 || true)"
  [[ -n "$line" ]] || return 1
  val="${line#*=}"
  # trim
  val="${val#"${val%%[![:space:]]*}"}"
  val="${val%"${val##*[![:space:]]}"}"
  # strip surrounding quotes
  [[ "$val" =~ ^\".*\"$ ]] && val="${val:1:-1}"
  [[ "$val" =~ ^\'.*\'$ ]] && val="${val:1:-1}"
  printf '%s' "$val"
}

require() { local v="$1" ; [[ -n "$v" ]] || { echo "ERROR: missing required value: $2"; exit 1; }; }

# Read only what we need from nodeX.env
ETH_ADDRESS="$(get_var "ETHERBASE_NODE_${node_idx}" "$config")";  require "$ETH_ADDRESS"  "ETHERBASE_NODE_${node_idx}"
ETH_PRIVATE_KEY="$(get_var "PRIVATE_KEY_NODE_${node_idx}" "$config")"; require "$ETH_PRIVATE_KEY" "PRIVATE_KEY_NODE_${node_idx}"
NODE_IP="$(get_var "IP_NODE_${node_idx}" "$config")";               require "$NODE_IP"     "IP_NODE_${node_idx}"
WS_PORT="$(get_var "WS_PORT_NODE_${node_idx}" "$config")";          require "$WS_PORT"     "WS_PORT_NODE_${node_idx}"

ETH_NODE_URL="ws://${NODE_IP}:${WS_PORT}"

# Read CONTRACT_ADDRESS safely from smart-contracts/smart-contract.env
sc_env="$(pwd)/smart-contracts/smart-contract.env"
[[ -f "$sc_env" ]] || { echo "ERROR: smart-contract.env not found at $sc_env"; exit 1; }
CONTRACT_ADDRESS="$(get_var "CONTRACT_ADDRESS" "$sc_env")"; require "$CONTRACT_ADDRESS" "CONTRACT_ADDRESS"

mask() { local s="$1"; [[ ${#s} -le 8 ]] && printf '%s' "$s" || printf '%s…%s' "${s:0:6}" "${s: -4}"; }

cat <<INFO
Launching '$container_name' (node ${node_idx}):
  Domain function  : $domain_function
  ETH_ADDRESS      : $ETH_ADDRESS
  ETH_PRIVATE_KEY  : $(mask "$ETH_PRIVATE_KEY")
  ETH_NODE_URL     : $ETH_NODE_URL
  CONTRACT_ADDRESS : $CONTRACT_ADDRESS
  Host port        : $port
  Image            : $image
INFO

docker run \
  --rm -d \
  --name "$container_name" \
  --hostname "$container_name" \
  -p "${port}:8000" \
  --env "ETH_ADDRESS=$ETH_ADDRESS" \
  --env "ETH_PRIVATE_KEY=$ETH_PRIVATE_KEY" \
  --env "ETH_NODE_URL=$ETH_NODE_URL" \
  --env "CONTRACT_ADDRESS=$CONTRACT_ADDRESS" \
  --env "DOMAIN_FUNCTION=$domain_function" \
  -v "$(pwd)/smart-contracts":/smart-contracts \
  -v "$(pwd)/experiments":/experiments \
  -v "$(pwd)/dockerfiles/mef-blockchain-manager/app":/app \
  "$image"

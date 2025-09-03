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

  --config            Path to nodeX.env (required), e.g. blockchain-network/geth-poa/config/node5.env
  --domain-function   "provider" or "consumer" (required)
  --port              Host port to bind to container's 8000 (default: 8000)
  --container-name    Docker container name/hostname (default: blockchain-manager)
  --image             Docker image to run (default: mef-blockchain-manager:latest)
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

# Validate required flags
if [[ -z "$config" || -z "$domain_function" ]]; then
  echo "ERROR: --config and --domain-function are required."
  usage
fi
if [[ "$domain_function" != "provider" && "$domain_function" != "consumer" ]]; then
  echo "ERROR: --domain-function must be 'provider' or 'consumer'."
  exit 1
fi
if [[ ! -f "$config" ]]; then
  echo "ERROR: Config file '$config' not found."
  exit 1
fi

# Infer node index X from filename ".../nodeX.env"
base="$(basename "$config")"
if [[ "$base" =~ ^[Nn]ode([0-9]+)\.env$ || "$base" =~ ^node([0-9]+)\.env$ || "$base" =~ ([0-9]+) ]]; then
  node_idx="${BASH_REMATCH[1]}"
else
  echo "ERROR: Could not infer node index from '$base' (expected something like node5.env)."
  exit 1
fi

# Source the node env (may contain command substitutions)
set -o allexport
# shellcheck disable=SC1090
source "$config"
set +o allexport

# Load contract address
sc_env="$(pwd)/smart-contracts/smart-contract.env"
if [[ ! -f "$sc_env" ]]; then
  echo "ERROR: smart-contract.env not found at $sc_env"
  exit 1
fi
set -o allexport
# shellcheck disable=SC1090
source "$sc_env"
set +o allexport
: "${CONTRACT_ADDRESS:?Missing CONTRACT_ADDRESS in smart-contract.env}"

# Helper
require() { local v="$1"; if [[ -z "${!v:-}" ]]; then echo "ERROR: '$v' must be set in $config"; exit 1; fi; }

# Dynamic names for nodeX
ETHERBASE_VAR="ETHERBASE_NODE_${node_idx}"
PRIVATE_KEY_VAR="PRIVATE_KEY_NODE_${node_idx}"
IP_VAR="IP_NODE_${node_idx}"
WS_PORT_VAR="WS_PORT_NODE_${node_idx}"

# Pull values
ETH_ADDRESS="${!ETHERBASE_VAR:-}"
ETH_PRIVATE_KEY="${!PRIVATE_KEY_VAR:-}"
NODE_IP="${!IP_VAR:-}"
WS_PORT="${!WS_PORT_VAR:-}"

# Require essentials
require "$ETHERBASE_VAR"
require "$PRIVATE_KEY_VAR"

ETH_NODE_URL="ws://${NODE_IP}:${WS_PORT}"


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

# Docker args
docker_args=(
  --rm -d
  --name "$container_name"
  --hostname "$container_name"
  -p "${port}:8000"
  --env "ETH_ADDRESS=$ETH_ADDRESS"
  --env "ETH_PRIVATE_KEY=$ETH_PRIVATE_KEY"
  --env "ETH_NODE_URL=$ETH_NODE_URL"
  --env "CONTRACT_ADDRESS=$CONTRACT_ADDRESS"
  --env "DOMAIN_FUNCTION=$domain_function"
  -v "$(pwd)/smart-contracts":/smart-contracts
  -v "$(pwd)/experiments":/experiments
  -v "$(pwd)/dockerfiles/mef-blockchain-manager/app":/app
)

docker run "${docker_args[@]}" "$image"

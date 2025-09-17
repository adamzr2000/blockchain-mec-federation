#!/usr/bin/env bash
set -euo pipefail

# Defaults
port="8000"
container_name="mef-soa"
domain_function=""
image="mef-soa:latest"
meo_url="http://127.0.0.1:6666"

usage() {
  cat <<EOF
Usage: $0 --domain-function <provider|consumer> [--port <port>] [--container-name <name>] [--image <image>] [--meo-url <url>]

Examples:
  $0 --domain-function provider --port 9001
  $0 --domain-function consumer --port 9000
EOF
  exit 1
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain-function) domain_function="$(echo "$2" | tr '[:upper:]' '[:lower:]')"; shift 2 ;;
    --container-name) container_name="$2"; shift 2 ;;
    --image) image="$2"; shift 2 ;;
    --port) port="$2"; shift 2 ;;
    --meo-url) meo_url="$2"; shift 2 ;;
    -*|--*) echo "Unknown option: $1"; usage ;;
    *) break ;;
  esac
done

# Validate
[[ -n "$domain_function" ]] || { echo "ERROR: --domain-function is required."; usage; }
[[ "$domain_function" == "provider" || "$domain_function" == "consumer" ]] || { echo "ERROR: --domain-function must be provider|consumer"; exit 1; }

cat <<INFO
Launching '$container_name':
  Domain function  : $domain_function
  Host port        : $port
  Image            : $image
  MEO URL          : $meo_url
INFO

# Run container
docker run \
  --rm -it \
  --name "$container_name" \
  --hostname "$container_name" \
  -p "${port}:8000" \
  --env "DOMAIN_FUNCTION=$domain_function" \
  --env "MEO_URL=$meo_url" \
  -v "$(pwd)/dockerfiles/mef-soa/app":/app \
  "$image"

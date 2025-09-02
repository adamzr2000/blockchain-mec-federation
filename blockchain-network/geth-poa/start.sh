#!/bin/bash
set -euo pipefail

# Default
VALIDATORS=2

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --validators|-v)
      VALIDATORS="${2:-2}"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--validators N]"
      exit 1
      ;;
  esac
done

# This script lives next to docker-compose.yml
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Tell Compose which genesis to mount
export GENESIS_FILE="genesis_${VALIDATORS}_validators.json"

# Optional sanity check (keeps your current relative structure)
if [[ ! -f "../dockerfiles/geth-node-poa/scripts/${GENESIS_FILE}" ]]; then
  echo "Error: ../dockerfiles/geth-node-poa/scripts/${GENESIS_FILE} not found."
  exit 1
fi

echo "Starting DLT network with ${VALIDATORS} validators (mounting ${GENESIS_FILE})"
docker compose up -d

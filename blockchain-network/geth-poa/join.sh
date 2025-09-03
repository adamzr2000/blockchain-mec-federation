#!/bin/bash
set -euo pipefail

# Defaults
ID=""
VALIDATORS=2

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --id)
      if [[ "$2" =~ ^[0-9]+$ ]] && [ "$2" -ge 1 ]; then
        ID="$2"
      else
        echo "Invalid --id value: $2. Must be a positive number (1, 2, 3...)."
        exit 1
      fi
      shift 2
      ;;
    --validators|-v)
      if [[ "$2" =~ ^[0-9]+$ ]] && [ "$2" -ge 2 ]; then
        VALIDATORS="$2"
      else
        echo "Invalid --validators value: $2. Must be >= 2."
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "Usage: $0 --id <number> [--validators <N>]"
      echo "Example: $0 --id 2 --validators 3"
      exit 1
      ;;
  esac
done

if [[ -z "$ID" ]]; then
  echo "Error: --id is required."
  echo "Usage: $0 --id <number> [--validators <N>]"
  exit 1
fi

NODE_SELECTION="node${ID}"
GENESIS_FILE="genesis_${VALIDATORS}_validators.json"
START_CMD="./${NODE_SELECTION}_start.sh"

DOCKER_CMD="docker run -d --name $NODE_SELECTION --hostname $NODE_SELECTION --network host --rm \
-v $(pwd)/config/$NODE_SELECTION.env:/src/$NODE_SELECTION.env \
-v $(pwd)/../../dockerfiles/geth-node-poa/scripts/$GENESIS_FILE:/src/genesis.json \
-v $(pwd)/../../dockerfiles/geth-node-poa/scripts/password.txt:/src/password.txt \
-v $(pwd)/../../dockerfiles/geth-node-poa/scripts/${NODE_SELECTION}_start.sh:/src/${NODE_SELECTION}_start.sh \
geth-node-poa $START_CMD"

echo "Starting $NODE_SELECTION with $GENESIS_FILE and command $START_CMD..."
eval "$DOCKER_CMD"

echo "$NODE_SELECTION started successfully."

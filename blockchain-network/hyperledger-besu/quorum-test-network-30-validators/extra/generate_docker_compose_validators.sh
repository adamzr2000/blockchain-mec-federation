#!/bin/bash
set -e

# Usage: ./generate_local_compose.sh <NUM_VALIDATORS>
# Example: ./generate_local_compose.sh 10

NUM_VALIDATORS=$1
if [[ -z "$NUM_VALIDATORS" ]]; then
  echo "❌ Please provide number of validators."
  echo "   Example: ./generate_local_compose.sh 10"
  exit 1
fi

OUTFILE="../docker-compose-${NUM_VALIDATORS}-validators.local.yml"

echo ">>> Generating $OUTFILE with $NUM_VALIDATORS validators..."

cat > "$OUTFILE" <<'EOF'
---
version: '3.6'

x-besu-def:
  &besu-def
  restart: "on-failure"
  image: hyperledger/besu:${BESU_VERSION:-latest}
  env_file:
    - ./config/besu/.env
  entrypoint:
    - /bin/bash
    - -c
    - |

      cp "/config/${BESU_CONS_ALGO:-QBFT}genesis.json" /config/genesis.json

      /opt/besu/bin/besu \
      --config-file=/config/config.toml \
      --p2p-host=$$(hostname -i) \
      --rpc-http-api=EEA,WEB3,ETH,NET,TRACE,DEBUG,ADMIN,TXPOOL,PERM,${BESU_CONS_ALGO:-QBFT} \
      --rpc-ws-api=EEA,WEB3,ETH,NET,TRACE,DEBUG,ADMIN,TXPOOL,PERM,${BESU_CONS_ALGO:-QBFT} ;

services:
EOF

# Generate validator services
for i in $(seq 1 $NUM_VALIDATORS); do
  PORT=$((21000 + i))

  echo "  validator$i:" >> "$OUTFILE"
  echo "    << : *besu-def" >> "$OUTFILE"
  echo "    container_name: validator$i" >> "$OUTFILE"
  echo "    ports:" >> "$OUTFILE"
  echo "      - ${PORT}:8545/tcp" >> "$OUTFILE"
  echo "      - 30303" >> "$OUTFILE"
  echo "      - 9545" >> "$OUTFILE"
  echo "    environment:" >> "$OUTFILE"
  echo "      - OTEL_RESOURCE_ATTRIBUTES=service.name=validator$i,service.version=\${BESU_VERSION:-latest}" >> "$OUTFILE"
  echo "    labels:" >> "$OUTFILE"
  echo "      - \"consensus=besu\"" >> "$OUTFILE"
  echo "    volumes:" >> "$OUTFILE"
  echo "      - ./config/besu/:/config" >> "$OUTFILE"
  echo "      - ./config/nodes/validator$i:/opt/besu/keys" >> "$OUTFILE"
  echo "      #- ./logs/besu:/tmp/besu" >> "$OUTFILE"

  if [[ $i -gt 1 ]]; then
    echo "    depends_on:" >> "$OUTFILE"
    echo "      - validator1" >> "$OUTFILE"
  fi

  echo "    networks:" >> "$OUTFILE"
  echo "      quorum-dev-quickstart:" >> "$OUTFILE"
  echo "" >> "$OUTFILE"
done

# Add explorer at the end
cat >> "$OUTFILE" <<'EOF'
  explorer:
    container_name: explorer
    image: consensys/quorum-explorer:${QUORUM_EXPLORER_VERSION:-latest}
    volumes:
      - ./quorum-explorer/config.json:/app/config.json
      - ./quorum-explorer/env:/app/.env.production
    depends_on:
      - validator1
    ports:
      - 25000:25000/tcp
    networks:
      quorum-dev-quickstart:

volumes:
  public-keys:

networks:
  quorum-dev-quickstart:
    name: quorum-dev-quickstart
    driver: bridge
    ipam:
      config:
        - subnet: 172.16.239.0/24
EOF

echo "✅ Done. Local docker-compose file created at $OUTFILE"

#!/bin/bash -u

NO_LOCK_REQUIRED=true

. ./.env
. ./.common.sh

# create log folders with the user permissions so it won't conflict with container permissions
mkdir -p logs/besu logs/quorum logs/tessera

COMPOSE_FILE=${1:-docker-compose.yml}

echo "$COMPOSE_FILE" > ${LOCK_FILE}

echo "${bold}*************************************"
echo "Quorum Dev Quickstart"
echo "*************************************${normal}"
echo "Start network"
echo "--------------------"

if [ -f "docker-compose-deps.yml" ]; then
    echo "Starting dependencies..."
    docker compose -f docker-compose-deps.yml up --detach
    sleep 60
fi

echo "Starting network with $COMPOSE_FILE ..."
docker compose -f $COMPOSE_FILE build --pull
docker compose -f $COMPOSE_FILE up --detach

# list services and endpoints
./list.sh

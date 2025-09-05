#!/bin/bash -u

NO_LOCK_REQUIRED=false

. ./.env
. ./.common.sh

COMPOSE_FILE=${1:-docker-compose.yml}

removeDockerImage(){
  if [[ -n $(docker ps -a | grep "$1") ]]; then
    docker image rm "$1"
  fi
}

echo "${bold}*************************************"
echo "Quorum Dev Quickstart "
echo "*************************************${normal}"
echo "Stop and remove network..."

# Stop and remove the stack defined in the chosen compose file
docker compose -f "${COMPOSE_FILE}" down -v
docker compose -f "${COMPOSE_FILE}" rm -sfv

# Dependencies (if defined)
if [ -f "docker-compose-deps.yml" ]; then
    echo "Stopping dependencies..."
    docker compose -f docker-compose-deps.yml down -v
    docker compose -f docker-compose-deps.yml rm -sfv
fi

# Pet shop dapp cleanup
if [[ -n $(docker ps -a | grep quorum-dev-quickstart_pet_shop) ]]; then
  docker stop quorum-dev-quickstart_pet_shop
  docker rm quorum-dev-quickstart_pet_shop
  removeDockerImage quorum-dev-quickstart_pet_shop
fi

# Remove ELK stack images if present in the selected compose file
if grep -q 'kibana:' "${COMPOSE_FILE}" 2>/dev/null ; then
  docker image rm quorum-test-network_elasticsearch || true
  docker image rm quorum-test-network_logstash || true
  docker image rm quorum-test-network_filebeat || true
  docker image rm quorum-test-network_metricbeat || true
fi

# Remove lock file
rm -f "${LOCK_FILE}"
echo "Lock file ${LOCK_FILE} removed"

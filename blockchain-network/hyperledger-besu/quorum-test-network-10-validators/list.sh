#!/bin/bash -eu

NO_LOCK_REQUIRED=false

. ./.env
. ./.common.sh

COMPOSE_FILE=${1:-docker-compose.yml}
HOST=${DOCKER_PORT_2375_TCP_ADDR:-"localhost"}
dots=""
maxRetryCount=50

echo "${bold}*************************************"
echo "Quorum Dev Quickstart "
echo "*************************************${normal}"

elk_setup=true
if [ -z "$(docker compose -f $COMPOSE_FILE ps -q kibana 2>/dev/null)" ] ; then
  elk_setup=false
fi

if [ "$elk_setup" == true ]; then
    while [ "$(curl -m 10 -s -o /dev/null -w ''%{http_code}'' http://${HOST}:5601/api/status)" != "200" ] && [ ${#dots} -le ${maxRetryCount} ]; do
      dots=$dots"."
      printf "Kibana is starting, please wait $dots\\r"
      sleep 10
    done
    echo "Setting up the index patterns in kibana ..."
    if [ -z "$(docker ps -q --filter 'label=consensus=goquorum' 2>/dev/null)" ] ; then
      curl --silent --output /dev/null -X POST "http://${HOST}:5601/api/saved_objects/index-pattern/besu" -H 'kbn-xsrf: true' -H 'Content-Type: application/json' -d '{"attributes": {"title": "besu-*","timeFieldName": "@timestamp"}}'
    else
      curl --silent --output /dev/null -X POST "http://${HOST}:5601/api/saved_objects/index-pattern/quorum" -H 'kbn-xsrf: true' -H 'Content-Type: application/json' -d '{"attributes": {"title": "quorum-*","timeFieldName": "@timestamp"}}'
    fi
    curl --silent --output /dev/null -X POST "http://${HOST}:5601/api/saved_objects/index-pattern/tessera" -H 'kbn-xsrf: true' -H 'Content-Type: application/json' -d '{"attributes": {"title": "tessera-*","timeFieldName": "@timestamp"}}'
fi

splunk_setup=true
if [ -z "$(docker compose -f $COMPOSE_FILE ps -q splunk 2>/dev/null)" ] ; then
  splunk_setup=false
fi
if [ "$splunk_setup" == true ]; then
    while [ "$(docker inspect --format='{{json .State.Health.Status}}' splunk)" != "\"healthy\"" ] && [ ${#dots} -le ${maxRetryCount} ]; do
      dots=$dots"."
      printf "Splunk is starting, please wait $dots\\r"
      sleep 10
    done
fi

echo "----------------------------------"
echo "List endpoints and services"
echo "----------------------------------"

echo "JSON-RPC HTTP service endpoint                 : http://${HOST}:8545"
echo "JSON-RPC WebSocket service endpoint            : ws://${HOST}:8546"
echo "Web block explorer address                     : http://${HOST}:25000/explorer/nodes"
if [ -n "$(docker compose -f $COMPOSE_FILE ps -q chainlensapi 2>/dev/null)" ]; then
  echo "Chainlens address                              : http://${HOST}:8081/"
fi
if [ -n "$(docker compose -f $COMPOSE_FILE ps -q blockscout 2>/dev/null)" ]; then
  echo "Blockscout address                             : http://${HOST}:26000/"
fi
if [ -n "$(docker compose -f $COMPOSE_FILE ps -q prometheus 2>/dev/null)" ]; then
  echo "Prometheus address                             : http://${HOST}:9090/graph"
fi

grafana_url="http://${HOST}:3000/d/a1lVy7ycin9Yv/goquorum-overview?orgId=1&refresh=10s"
if [[ -n "$(docker ps -q --filter 'label=consensus=besu' 2>/dev/null)" ]]; then
  grafana_url="http://${HOST}:3000/d/XE4V0WGZz/besu-overview?orgId=1&refresh=10s"
fi
if [ -n "$(docker compose -f $COMPOSE_FILE ps -q grafana 2>/dev/null)" ]; then
  echo "Grafana address                                : $grafana_url"
fi

if [ "$elk_setup" == true ]; then
  echo "Collated logs using Kibana endpoint            : http://${HOST}:5601/app/kibana#/discover"
fi
if [ "$splunk_setup" == true ]; then
  echo "Logs, traces and metrics using Splunk endpoint : http://${HOST}:8000/"
fi

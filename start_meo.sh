#!/bin/bash

docker run --rm \
  -d \
  --network=host \
  --cap-add=NET_ADMIN \
  --cap-add=NET_RAW \
  --pid=host \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
  -v "$(pwd)/dockerfiles/meo/app":/app \
  -v "$(pwd)/experiments":/experiments \
  --name meo \
  meo:latest
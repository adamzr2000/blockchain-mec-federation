#!/bin/bash

docker run --rm \
  -d \
  --network=host \
  --cap-add=NET_ADMIN \
  --cap-add=NET_RAW \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)/dockerfiles/meo/app":/app \
  --name meo \
  meo:latest
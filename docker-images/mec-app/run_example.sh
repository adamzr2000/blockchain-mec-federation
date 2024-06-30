#!/bin/bash

docker run -d --rm -p 5000:5000 --name mec-service --env SERVER_ID="Provider MEC system" mec-app

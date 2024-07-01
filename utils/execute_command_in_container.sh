#!/bin/bash

# Check if container name and command arguments are provided
if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <container_name> <command>"
  exit 1
fi

CONTAINER_NAME=$1
shift
COMMAND=$@

# Execute the command in the specified container
sudo docker exec -it $CONTAINER_NAME sh -c "$COMMAND"

# Check if the operation was successful
if [ $? -eq 0 ]; then
  echo "Successfully executed command '$COMMAND' in container '$CONTAINER_NAME'."
else
  echo "Failed to execute command '$COMMAND' in container '$CONTAINER_NAME'."
fi


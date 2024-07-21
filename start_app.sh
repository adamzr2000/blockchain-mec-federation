#!/bin/bash

# Check if the environment file parameter is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <path_to_env_file>"
  exit 1
fi

# Load environment variables from the specified file
FEDERATION_ENV_FILE=$1
source $FEDERATION_ENV_FILE

# Define a screen session name
SCREEN_SESSION_NAME="dlt-federation-api"

# Start a new screen session and run the command
screen -dmS $SCREEN_SESSION_NAME bash -c "FEDERATION_ENV_FILE=$FEDERATION_ENV_FILE python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 --env-file $FEDERATION_ENV_FILE"

echo "Server started in screen session: $SCREEN_SESSION_NAME"
echo "You can attach to it using: screen -r $SCREEN_SESSION_NAME"
echo "You can kill it using: screen -XS $SCREEN_SESSION_NAME quit"

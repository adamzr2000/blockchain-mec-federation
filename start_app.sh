#!/bin/bash

# Check if the environment file parameter is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <path_to_env_file>"
  exit 1
fi

# Load environment variables from the specified file
export FEDERATION_ENV_FILE=$1

# Define a screen session name
SCREEN_SESSION_NAME="dlt_federation_api"

# Start a new screen session and run the command
screen -dmS $SCREEN_SESSION_NAME bash -c "python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 --env-file $FEDERATION_ENV_FILE"

echo "Server started in screen session: $SCREEN_SESSION_NAME"echo "Server started in screen session: $SCREEN_SESSION_NAME"
echo "You can attach to it using: screen -r $SCREEN_SESSION_NAME"
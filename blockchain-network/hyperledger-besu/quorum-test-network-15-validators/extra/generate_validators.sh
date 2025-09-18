#!/bin/bash
set -e

# Location of nodes config
BASE_DIR="../config/nodes"

# Password for accounts (you can change if needed)
PASSWORD="password"

# Loop from validator5 to validator30
for i in $(seq 5 30); do
    NODE_DIR="$BASE_DIR/validator$i"

    echo ">>> Creating $NODE_DIR"

    # Make directory if it does not exist
    mkdir -p "$NODE_DIR"

    # Go into the validator directory
    pushd "$NODE_DIR" > /dev/null

    # Clean up any old files to avoid overwrites
    rm -f accountKeystore accountPassword accountPrivateKey address nodekey nodekey.pub

    # Generate keys and account
    node ../../../extra/generate_node_details.js --password "$PASSWORD"

    popd > /dev/null
done

echo "✅ Finished creating validator5 through validator30"

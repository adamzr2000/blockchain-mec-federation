#!/bin/bash

# Execute the geth init command to initialize the data directory with genesis.json
output=$(geth init --datadir node23 genesis.json)
echo "$output"

# Read environment variables from node specific .env file
source node23.env

# Define the command
command="geth --identity 'node23' --syncmode 'full' --ws --ws.addr $IP_NODE_23  --ws.port $WS_PORT_NODE_23 --datadir node23 --port $ETH_PORT_NODE_23 --bootnodes $BOOTNODE_URL --ws.api 'eth,net,web3,personal,miner,admin,clique' --networkid $NETWORK_ID --nat 'any' --allow-insecure-unlock --authrpc.port $RPC_PORT_NODE_23 --ipcdisable --unlock $ETHERBASE_NODE_23 --password password.txt --mine --snapshot=false --miner.etherbase $ETHERBASE_NODE_23 --ethstats node23:$WS_SECRET@$ETH_NETSATS_IP:$ETH_NETSATS_PORT" 

# Add verbosity option to the command if logs need to be saved
if [ "$SAVE_LOGS" == "y" ] || [ "$SAVE_LOGS" == "Y" ]; then
  command="$command --verbosity 3 >> ./logs/node23.log 2>&1"
else
  command="$command"
fi

# Execute the command
eval $command
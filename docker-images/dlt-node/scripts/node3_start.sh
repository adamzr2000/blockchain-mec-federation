#!/bin/bash

# Execute the geth init command to initialize the data directory with genesis.json
output=$(geth init --datadir node3 genesis.json)
echo "$output"

# Read environment variables from .env file
source node3.env

# Define the command
command="geth --identity "node3" --syncmode "full" --ws --ws.addr $IP_NODE_3 --ws.port $WS_PORT_NODE_3 --datadir node3 --port $ETH_PORT_NODE_3 --bootnodes $BOOTNODE_URL --ws.api "eth,net,web3,personal,miner,admin,clique" --networkid 1234 --nat "any" --allow-insecure-unlock --authrpc.port $RPC_PORT_NODE_3 --ipcdisable --unlock $ETHERBASE_NODE_3 --password password.txt --mine --snapshot=false --miner.etherbase $ETHERBASE_NODE_3 --ethstats node3:$WS_SECRET@$ETH_NETSATS_IP:$ETH_NETSATS_PORT" 

# Execute the command
eval $command


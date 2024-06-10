#!/bin/bash

# This script cleans up the Docker network and VXLAN interfaces created by the setup script.

echo -e "\nRemoving Docker network 'federation-net'..."
sudo docker network rm federation-net

echo -e "\nRemoving VXLAN network interface 'vxlan200'..."
sudo ip link set vxlan200 down
sudo ip link del vxlan200

echo -e "\nCleanup completed successfully."

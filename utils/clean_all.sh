#!/bin/bash

# This script cleans up the Docker network and VXLAN interfaces created by the previous setup script.

# Step 1: Delete the Docker network named 'federation-net'.
# We use the network name directly to remove it.
echo -e "\nRemoving Docker network 'federation-net'..."
sudo docker network rm federation-net

# Step 2: Delete the VXLAN network interface named 'vxlan200'.
# This command disables and then removes the interface.
echo -e "\nRemoving VXLAN network interface 'vxlan200'..."
sudo ip link set vxlan200 down
sudo ip link del vxlan200

echo -e "\nCleanup completed successfully."


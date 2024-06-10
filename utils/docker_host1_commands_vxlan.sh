#!/bin/bash

# This script sets up a Docker network and a VXLAN network interface.

# Step 1: Create a Docker network.
# - Name: 'federation-net'
# - Subnet: 10.10.1.0/16
# - Network driver: default bridge
echo -e "\nCreating Docker network 'federation-net' with subnet 10.10.1.0/16..."
network_id=$(sudo docker network create --subnet 10.10.1.0/16 federation-net)

# Step 2: Verify the Docker network creation and extract the bridge name from brctl show.
echo -e "\nListing Docker networks to verify 'federation-net' is created..."
# Removed the echo of network inspect
sudo docker network inspect $network_id > /dev/null

# Extract the bridge name associated with the created network
bridge_name=$(sudo brctl show | grep $(echo $network_id | cut -c 1-12) | awk '{print $1}')
if [ -z "$bridge_name" ]; then
    echo "Bridge name could not be retrieved."
else
    echo "Bridge name: $bridge_name"
fi

# Step 3: Create a VXLAN network interface.
# - Name: 'vxlan200'
# - Type: VXLAN
# - VNI (Virtual Network Identifier): 200
# - Source IP: 192.168.56.104 (Host-2 IP)
# - Destination IP: 192.168.56.105 (Assuming remote host IP)
# - Destination Port: 4789 (standard UDP port for VXLAN)
# - Parent interface: 'enp0s3'
echo -e "\nCreating VXLAN network interface 'vxlan200'..."
sudo ip link add vxlan200 type vxlan id 200 local 192.168.56.104 remote 192.168.56.105 dstport 4789 dev enp0s3

# Step 4: Enable the VXLAN network interface.
echo -e "\nEnabling the VXLAN interface 'vxlan200'..."
sudo ip link set vxlan200 up

# Step 5: Verify that the VXLAN interface is correctly configured.
echo -e "\nChecking the list of interfaces for 'vxlan200'..."
ip a | grep vxlan

# Step 6: Display the Docker bridge names and check the connectivity.
echo -e "\nDisplaying bridge connections..."
sudo brctl show

# Step 7: Attach the newly created VXLAN interface to the docker bridge.
sudo brctl addif $bridge_name vxlan200

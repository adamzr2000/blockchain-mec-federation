#!/bin/bash

# Function to display usage information
usage() {
    echo "Usage: $0 -l <local_ip> -r <remote_ip> -i <interface_name>"
    echo "  -l <local_ip>        Local IP address"
    echo "  -r <remote_ip>       Remote IP address"
    echo "  -i <interface_name>  Interface name (e.g., enp0s3)"
    exit 1
}

# Function to validate IP address format
validate_ip() {
    local ip=$1
    local valid_ip_regex="^([0-9]{1,3}\.){3}[0-9]{1,3}$"
    if [[ $ip =~ $valid_ip_regex ]]; then
        IFS='.' read -r -a octets <<< "$ip"
        for octet in "${octets[@]}"; do
            if (( octet < 0 || octet > 255 )); then
                return 1
            fi
        done
        return 0
    else
        return 1
    fi
}

# Parse input arguments
while getopts "l:r:i:" opt; do
    case ${opt} in
        l ) local_ip=$OPTARG ;;
        r ) remote_ip=$OPTARG ;;
        i ) dev_interface=$OPTARG ;;
        * ) usage ;;
    esac
done

# Check if all required arguments are provided
if [ -z "$local_ip" ] || [ -z "$remote_ip" ] || [ -z "$dev_interface" ]; then
    usage
fi

# Validate IP address format
if ! validate_ip $local_ip; then
    echo "Invalid local IP address format: $local_ip"
    exit 1
fi

if ! validate_ip $remote_ip; then
    echo "Invalid remote IP address format: $remote_ip"
    exit 1
fi

# This script sets up a Docker network and a VXLAN network interface.

# Step 1: Create a Docker network.
echo -e "\nCreating Docker network 'federation-net' with subnet 10.10.1.0/16..."
network_id=$(sudo docker network create --subnet 10.10.1.0/16 federation-net)

# Step 2: Verify the Docker network creation and extract the bridge name from brctl show.
echo -e "\nListing Docker networks to verify 'federation-net' is created..."
sudo docker network inspect $network_id > /dev/null

# Extract the bridge name associated with the created network
bridge_name=$(sudo brctl show | grep $(echo $network_id | cut -c 1-12) | awk '{print $1}')
if [ -z "$bridge_name" ]; then
    echo "Bridge name could not be retrieved."
else
    echo "Bridge name: $bridge_name"
fi

# Step 3: Create a VXLAN network interface.
echo -e "\nCreating VXLAN network interface 'vxlan200'..."
sudo ip link add vxlan200 type vxlan id 200 local $local_ip remote $remote_ip dstport 4789 dev $dev_interface

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
echo -e "\nAttaching VXLAN interface 'vxlan200' to the Docker bridge '$bridge_name'..."
sudo brctl addif $bridge_name vxlan200

echo -e "\nSetup completed successfully."

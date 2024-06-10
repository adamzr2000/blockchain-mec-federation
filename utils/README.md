# Docker Network and VXLAN Setup Script

## Prerequisites

- Docker installed
- `brctl` command available (`sudo apt-get install bridge-utils`)

## Execute the Script

Run the script with the required parameters:

```sh
chmod +x docker_host_setup_vxlan.sh
```

Example:

```sh
./docker_host_setup_vxlan.sh -l 192.168.56.104 -r 192.168.56.105 -i enp0s3
```

```sh
./docker_host_setup_vxlan.sh -l 192.168.56.105 -r 192.168.56.104 -i enp0s3
```

```sh
sudo docker run --name alpine1 -it --rm --network federation-net --ip 10.10.0.2 alpine
```

```sh
sudo docker run --name alpine2 -it --rm --network federation-net --ip 10.10.0.3 alpine
```
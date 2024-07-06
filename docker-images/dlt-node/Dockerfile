# Use a base image with Ubuntu 
FROM ubuntu:20.04

LABEL maintainer="azahir@pa.uc3m.es"

# Set environment variables to avoid user interaction during the installation
ENV DEBIAN_FRONTEND=noninteractive

# Install the required software-properties-common package
RUN apt-get update && \
    apt-get install -y software-properties-common \
    wget \
    iputils-ping \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*
 

# Download and install specific version of Geth (1.13)
RUN wget https://gethstore.blob.core.windows.net/builds/geth-linux-amd64-1.13.15-c5ba367e.tar.gz && \
    tar -xvf geth-linux-amd64-1.13.15-c5ba367e.tar.gz && \
    mv geth-linux-amd64-1.13.15-c5ba367e/geth /usr/local/bin/ && \
    rm -rf geth-linux-amd64-1.13.15-c5ba367e geth-linux-amd64-1.13.15-c5ba367e.tar.gz


# Add Ethereum PPA repository
RUN add-apt-repository -y ppa:ethereum/ethereum

# Update package list
RUN apt-get update

# Install Ethereum package (bootnode)
RUN apt-get install -y bootnode

# Set the working directory inside the container
WORKDIR /dlt-network

# # Copy the entire directories and their contents into the container
COPY bootnode ./bootnode

COPY node1 ./node1
COPY node2 ./node2
COPY node3 ./node3
COPY node4 ./node4
COPY node5 ./node5
COPY node6 ./node6
COPY node7 ./node7
COPY node8 ./node8
COPY node9 ./node9
COPY node10 ./node10

RUN mkdir logs

# # Copy the shell scripts and other files
# COPY scripts/*_start.sh ./
# COPY scripts/password.txt ./ 
# COPY scripts/genesis.json ./

# # Make bash scripts executable
# RUN chmod +x scripts/*_start.sh

# Keep container running
#CMD tail -f /dev/null



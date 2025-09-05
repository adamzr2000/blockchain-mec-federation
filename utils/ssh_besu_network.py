#!/usr/bin/env python3
"""
Start/stop the Besu Docker Compose network over SSH using Fabric.

Usage:
  # Start validators 1..4
  python ssh_besu_network.py --start --nodes 4

  # Stop validators 1..4
  python ssh_besu_network.py --stop --nodes 4
"""

import sys
import time
import argparse
from fabric import Connection

# ------- environment defaults -------
REMOTE_USER = "netcom"
SUBNET_PREFIX = "10.5.99."
BASE_DIR = "/home/netcom/blockchain-mec-federation/blockchain-network/hyperledger-besu/quorum-test-network"
BASE_COMMAND = f"cd {BASE_DIR} &&"
# -----------------------------------

def execute_ssh_command(host: str, command: str) -> bool:
    """Run a command on a remote host over SSH, printing debug info."""
    print(f"Executing on {host}: {command}")
    try:
        with Connection(host=host, user=REMOTE_USER) as c:
            result = c.run(command, hide=False, warn=True)
            if result.ok:
                print(f"✅ Success: {host}")
                return True
            else:
                print(f"❌ Error: {host} (exit {result.exited})")
                return False
    except Exception as e:
        print(f"❌ Exception on {host}: {e}")
        return False

def start_besu_network(total_nodes: int) -> None:
    for i in range(1, total_nodes + 1):
        node_ip = f"{SUBNET_PREFIX}{i}"
        compose_file = f"docker-compose-validator{i}.yml"
        execute_ssh_command(node_ip, f"{BASE_COMMAND} ./run.sh {compose_file}")
        time.sleep(3)  # small delay to avoid race conditions

def stop_besu_network(total_nodes: int) -> None:
    for i in range(1, total_nodes + 1):
        node_ip = f"{SUBNET_PREFIX}{i}"
        compose_file = f"docker-compose-validator{i}.yml"
        execute_ssh_command(node_ip, f"{BASE_COMMAND} ./remove.sh {compose_file}")
        time.sleep(2)

def parse_args():
    parser = argparse.ArgumentParser(description="Start/stop Besu network via SSH using Fabric.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--start", action="store_true", help="Start the Besu network")
    action.add_argument("--stop", action="store_true", help="Stop the Besu network")
    parser.add_argument(
        "--nodes", "-n",
        type=int,
        required=True,
        help="Number of validator nodes (e.g. 4)"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    if args.start:
        start_besu_network(args.nodes)
    elif args.stop:
        stop_besu_network(args.nodes)
    else:
        print("Choose either --start or --stop.")
        sys.exit(1)

if __name__ == "__main__":
    main()

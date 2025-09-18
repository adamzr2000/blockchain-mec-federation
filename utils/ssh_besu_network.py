#!/usr/bin/env python3
"""
Start/stop the Besu Docker Compose network over SSH using Fabric.

Usage:
  # Start validators 1..4
  python ssh_besu_network.py --start --nodes 4

  # Stop validators 1..10
  python ssh_besu_network.py --stop --nodes 10
"""

import sys
import time
import argparse
from fabric import Connection

# ------- environment defaults -------
REMOTE_USER = "netcom"
SUBNET_PREFIX = "10.5.99."
BASE_PATH = "/home/netcom/blockchain-mec-federation/blockchain-network/hyperledger-besu"
# -----------------------------------


def get_base_dir(total_nodes: int) -> str:
    """Return the correct quorum-test-network directory based on validator count."""
    valid_options = [4, 10, 15, 20, 25, 30]
    if total_nodes not in valid_options:
        raise ValueError(f"Unsupported validator count: {total_nodes}. "
                         f"Choose one of {valid_options}")
    return f"{BASE_PATH}/quorum-test-network-{total_nodes}-validators"

def execute_ssh_command(host: str, command: str) -> bool:
    """Run a command on a remote host over SSH, printing debug info."""
    print(f"Executing on {host}: {command}")
    try:
        with Connection(host=host, user=REMOTE_USER) as c:
            result = c.run(command, hide=False, warn=True, pty=True)
            # tput often fails when TERM is not set, ignore exit 2
            if result.ok or result.exited == 2:
                print(f"✅ Success (ignoring tput noise): {host}")
                return True
            else:
                print(f"❌ Error: {host} (exit {result.exited})")
                return False
    except Exception as e:
        print(f"❌ Exception on {host}: {e}")
        return False


def start_besu_network(total_nodes: int) -> None:
    base_dir = get_base_dir(total_nodes)
    base_command = f"cd {base_dir} &&"
    for i in range(1, total_nodes + 1):
        node_ip = f"{SUBNET_PREFIX}{i}"
        compose_file = f"docker-compose-validator{i}.yml"
        execute_ssh_command(node_ip, f"{base_command} ./run.sh {compose_file}")
        time.sleep(2)  # small delay to avoid race conditions


def stop_besu_network(total_nodes: int) -> None:
    base_dir = get_base_dir(total_nodes)
    base_command = f"cd {base_dir} &&"
    for i in range(1, total_nodes + 1):
        node_ip = f"{SUBNET_PREFIX}{i}"
        compose_file = f"docker-compose-validator{i}.yml"
        execute_ssh_command(node_ip, f"{base_command} ./remove.sh {compose_file}")


def parse_args():
    parser = argparse.ArgumentParser(description="Start/stop Besu network via SSH using Fabric.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--start", action="store_true", help="Start the Besu network")
    action.add_argument("--stop", action="store_true", help="Stop the Besu network")
    parser.add_argument(
        "--nodes", "-n",
        type=int,
        required=True,
        help="Number of validator nodes (4, 10, 20, or 30)"
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

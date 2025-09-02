#!/usr/bin/env python3
"""
Start/stop the DLT network over SSH using Fabric.

Usage:
  # Start network on nodes 1..5
  python ssh_blockchain_network.py --start --nodes 5

  # Stop network, killing node2..node30 containers and stopping node1
  python ssh_blockchain_network.py --stop --nodes 30
"""

import sys
import time
import argparse
from fabric import Connection

# ------- environment defaults (from your setup) -------
REMOTE_USER = "netcom"
SUBNET_PREFIX = "10.5.99."
BASE_DIR = "/home/netcom/blockchain-mec-federation/blockchain-network/geth-poa"
BASE_COMMAND = f"cd {BASE_DIR} &&"
# ------------------------------------------------------

def execute_ssh_command(host: str, command: str) -> bool:
    """
    Run a command on a remote host over SSH, printing debug info.
    Returns True on success, False on failure.
    """
    print(f"Executing on {host}: {command}")
    try:
        with Connection(host=host, user=REMOTE_USER) as c:
            # warn=True -> don't raise on non-zero exit; we handle messaging
            result = c.run(command, hide=False, warn=True)
            if result.ok:
                print(f"Success: Command executed on {host}")
                return True
            else:
                print(f"Error: Command failed on {host} (exit {result.exited})")
                return False
    except Exception as e:
        print(f"Error: Exception on {host}: {e}")
        return False

def start_dlt_network(total_nodes: int) -> None:
    if total_nodes < 2:
        print("Error: --nodes must be at least 2 when starting.")
        sys.exit(1)

    # Start on node1
    node1 = SUBNET_PREFIX + "1"
    execute_ssh_command(node1, f"{BASE_COMMAND} ./start_dlt_network.sh")

    # Wait 5 seconds as in your original script
    print("Waiting for 5 seconds...")
    time.sleep(5)

    # Join nodes 2..N
    for i in range(2, total_nodes + 1):
        node_ip = f"{SUBNET_PREFIX}{i}"
        node_name = f"node{i}"
        execute_ssh_command(
            node_ip,
            f"{BASE_COMMAND} ./join_dlt_network.sh {node_name} {total_nodes}"
        )
        time.sleep(3)

def stop_dlt_network(max_node: int) -> None:
    # Kill docker containers node2..node{max_node}, but don't fail if not running
    for i in range(2, max_node + 1):
        node_ip = f"{SUBNET_PREFIX}{i}"
        node_name = f"node{i}"
        # Make it resilient: if kill fails, emit a note and continue
        kill_cmd = (
            f"docker kill {node_name} "
            f"|| echo 'Note: container {node_name} was not running on this host.'"
        )
        execute_ssh_command(node_ip, kill_cmd)

    # Stop DLT on node1
    node1 = SUBNET_PREFIX + "1"
    execute_ssh_command(node1, f"{BASE_COMMAND} ./stop_dlt_network.sh")

def parse_args():
    parser = argparse.ArgumentParser(description="Start/stop DLT network via SSH using Fabric.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--start", action="store_true", help="Start the DLT network")
    action.add_argument("--stop", action="store_true", help="Stop the DLT network")
    parser.add_argument(
        "--nodes", "-n",
        type=int,
        required=True,
        help="Number of nodes (>=2 to start; for stop, the highest node index to kill)"
    )
    return parser.parse_args()

def main():
    args = parse_args()

    if args.start:
        start_dlt_network(args.nodes)
    elif args.stop:
        stop_dlt_network(args.nodes)
    else:
        print("Choose either --start or --stop.")
        sys.exit(1)

if __name__ == "__main__":
    main()

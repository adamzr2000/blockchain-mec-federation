#!/usr/bin/env python3
import argparse
from fabric import Connection

REMOTE_USER = "netcom"
SUBNET_PREFIX = "10.5.99."
REMOTE_DIR = "/home/netcom/blockchain-mec-federation"

STOP_CMD = "docker kill blockchain-manager >/dev/null 2>&1 || true"

def exec_on_host(host: str, cmd: str) -> bool:
    print(f"[{host}] $ {cmd}")
    try:
        with Connection(host=host, user=REMOTE_USER) as c:
            res = c.run(cmd, hide=False, warn=True)
            if res.ok:
                print(f"[{host}] ✓ success")
                return True
            print(f"[{host}] ✗ exit {res.exited}")
            return False
    except Exception as e:
        print(f"[{host}] ✗ exception: {e}")
        return False

def start_mef(nodes: int, consumers: int) -> None:
    if consumers < 0: consumers = 0
    if consumers > nodes: consumers = nodes
    for i in range(1, nodes + 1):
        role = "consumer" if i <= consumers else "provider"
        cfg = f"blockchain-network/geth-poa/config/node{i}.env"
        cmd = (
            f"cd {REMOTE_DIR} && "
            f"./start_blockchain_manager.sh --config {cfg} --domain-function {role}"
        )
        host = f"{SUBNET_PREFIX}{i}"
        print(f"-> node{i} ({host}) -> {role}")
        exec_on_host(host, cmd)

def stop_mef(nodes: int) -> None:
    for i in range(1, nodes + 1):
        exec_on_host(f"{SUBNET_PREFIX}{i}", STOP_CMD)

def parse_args():
    p = argparse.ArgumentParser(description="Start/stop MEF via SSH with consumer split.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--start", action="store_true")
    g.add_argument("--stop", action="store_true")
    p.add_argument("-n", "--nodes", type=int, required=True, help="Highest node index N (1..N)")
    p.add_argument("-c", "--consumers", type=int, default=1, help="How many consumers (from node1 upward)")
    return p.parse_args()

def main():
    args = parse_args()
    if args.start:
        start_mef(args.nodes, args.consumers)
    else:
        stop_mef(args.nodes)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
from fabric import Connection

REMOTE_USER = "netcom"
SUBNET_PREFIX = "10.5.99."
REMOTE_DIR = "/home/netcom/blockchain-mec-federation"

# Commands
STOP_MEF_CMD = "docker kill blockchain-manager >/dev/null 2>&1 || true"
STOP_MEO_CMD = "docker kill meo >/dev/null 2>&1 || true"
START_MEO_CMD = f"cd {REMOTE_DIR} && ./start_meo.sh"

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

def get_base_dir(total_nodes: int) -> str:
    valid_options = [4, 10, 20, 30]
    if total_nodes not in valid_options:
        raise ValueError(f"Unsupported validator count: {total_nodes}. "
                         f"Choose one of {valid_options}")
    return f"blockchain-network/hyperledger-besu/quorum-test-network-{total_nodes}-validators"

# --- MEF part (adapted for Besu setup) ---
def start_mef(nodes: int, consumers: int) -> None:
    if consumers < 0:
        consumers = 0
    if consumers > nodes:
        consumers = nodes

    base_dir = get_base_dir(nodes)

    for i in range(1, nodes + 1):
        role = "consumer" if i <= consumers else "provider"
        node_path = f"{base_dir}/config/nodes/validator{i}"
        host = f"{SUBNET_PREFIX}{i}"
        rpc_url = f"http://{host}:8545"
        
        cmd = (
            f"cd {REMOTE_DIR} && "
            f"./start_blockchain_manager.sh --node-path {node_path} --domain-function {role} --rpc_url {rpc_url}"
        )
        print(f"-> validator{i} on {host} -> {role}")
        exec_on_host(host, cmd)

def stop_mef(nodes: int) -> None:
    for i in range(1, nodes + 1):
        exec_on_host(f"{SUBNET_PREFIX}{i}", STOP_MEF_CMD)

# --- MEO part (unchanged) ---
def start_meo(nodes: int) -> None:
    for i in range(1, nodes + 1):
        exec_on_host(f"{SUBNET_PREFIX}{i}", START_MEO_CMD)

def stop_meo(nodes: int) -> None:
    for i in range(1, nodes + 1):
        exec_on_host(f"{SUBNET_PREFIX}{i}", STOP_MEO_CMD)

def parse_args():
    p = argparse.ArgumentParser(description="Start/stop MEF and/or MEO via SSH.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--start", action="store_true", help="Start components")
    g.add_argument("--stop", action="store_true", help="Stop components")

    p.add_argument("-n", "--nodes", type=int, required=True, help="Highest node index N (1..N)")
    p.add_argument("-c", "--consumers", type=int, default=1, help="How many consumers (from node1 upward)")
    p.add_argument("--mef", action="store_true", help="Include MEF managers")
    p.add_argument("--meo", action="store_true", help="Include MEO containers")

    return p.parse_args()

def main():
    args = parse_args()

    if not (args.mef or args.meo):
        print("⚠ You must specify at least one of --mef or --meo")
        return

    if args.start:
        if args.mef:
            start_mef(args.nodes, args.consumers)
        if args.meo:
            start_meo(args.nodes)
    else:
        if args.mef:
            stop_mef(args.nodes)
        if args.meo:
            stop_meo(args.nodes)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
from fabric import Connection

REMOTE_USER = "netcom"
SUBNET_PREFIX = "10.5.99."
REMOTE_DIR = "/home/netcom/blockchain-mec-federation"

START_CMD = f"cd {REMOTE_DIR} && ./start_meo.sh"
# Silence both success output ("meo") and errors ("No such container"),
# and force a zero exit so we print ✓ without noise.
STOP_CMD = "docker kill meo >/dev/null 2>&1 || true"

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

def start_all(n: int) -> None:
    for i in range(1, n + 1):
        exec_on_host(f"{SUBNET_PREFIX}{i}", START_CMD)

def stop_all(n: int) -> None:
    for i in range(1, n + 1):
        exec_on_host(f"{SUBNET_PREFIX}{i}", STOP_CMD)

def parse_args():
    p = argparse.ArgumentParser(description="Start/stop MEO via SSH (simple).")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--start", action="store_true")
    g.add_argument("--stop", action="store_true")
    p.add_argument("-n", "--nodes", type=int, required=True, help="Highest host index N (1..N)")
    return p.parse_args()

def main():
    args = parse_args()
    if args.start:
        start_all(args.nodes)
    else:
        stop_all(args.nodes)

if __name__ == "__main__":
    main()

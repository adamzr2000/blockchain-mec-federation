#!/usr/bin/env python3
import argparse
from fabric import Connection
from typing import Any, Dict, List

REMOTE_USER = "netcom"
SUBNET_PREFIX = "10.5.99."
REMOTE_DIR = "/home/netcom/blockchain-mec-federation"

# Docker control commands
STOP_MEF_CMD = "docker kill mef-soa >/dev/null 2>&1 || true"
STOP_MEO_CMD = "docker kill meo >/dev/null 2>&1 || true"
START_MEO_CMD = f"cd {REMOTE_DIR} && ./start_meo.sh"

# Host inventory (vxlan iface + node_id per host)
HOSTS: List[Dict[str, Any]] = [
    {"node_id": 1,  "ip": "10.5.99.1",  "iface": "ens3"},
    {"node_id": 2,  "ip": "10.5.99.2",  "iface": "ens3"},
    {"node_id": 3,  "ip": "10.5.99.3",  "iface": "ens3"},
    {"node_id": 4,  "ip": "10.5.99.4",  "iface": "ens3"},
    {"node_id": 5,  "ip": "10.5.99.5",  "iface": "ens3"},
    {"node_id": 6,  "ip": "10.5.99.6",  "iface": "ens3"},
    {"node_id": 7,  "ip": "10.5.99.7",  "iface": "ens3"},
    {"node_id": 8,  "ip": "10.5.99.8",  "iface": "ens3"},
    {"node_id": 9,  "ip": "10.5.99.9",  "iface": "ens3"},
    {"node_id": 10, "ip": "10.5.99.10", "iface": "ens3"},
    {"node_id": 11, "ip": "10.5.99.11", "iface": "eno1"},
    {"node_id": 12, "ip": "10.5.99.12", "iface": "ens3"},
    {"node_id": 13, "ip": "10.5.99.13", "iface": "enp0s3"},
    {"node_id": 14, "ip": "10.5.99.14", "iface": "enp0s3"},
    {"node_id": 15, "ip": "10.5.99.15", "iface": "enp0s3"},
    {"node_id": 16, "ip": "10.5.99.16", "iface": "ens3"},
    {"node_id": 17, "ip": "10.5.99.17", "iface": "ens3"},
    {"node_id": 18, "ip": "10.5.99.18", "iface": "ens3"},
    {"node_id": 19, "ip": "10.5.99.19", "iface": "ens3"},
    {"node_id": 20, "ip": "10.5.99.20", "iface": "ens3"},
    {"node_id": 21, "ip": "10.5.99.21", "iface": "eth0"},
    {"node_id": 22, "ip": "10.5.99.22", "iface": "eth0"},
    {"node_id": 23, "ip": "10.5.99.23", "iface": "eth0"},
    {"node_id": 24, "ip": "10.5.99.24", "iface": "eth0"},
    {"node_id": 25, "ip": "10.5.99.25", "iface": "eth0"},
    {"node_id": 26, "ip": "10.5.99.26", "iface": "eth0"},
    {"node_id": 27, "ip": "10.5.99.27", "iface": "eth0"},
    {"node_id": 28, "ip": "10.5.99.28", "iface": "eth0"},
    {"node_id": 29, "ip": "10.5.99.29", "iface": "eth0"},
    {"node_id": 30, "ip": "10.5.99.30", "iface": "eth0"},
]

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

    if consumers < 0:
        consumers = 0
    if consumers > nodes:
        consumers = nodes

    provider_idx = 0
    consumer_idx = 0

    for i in range(nodes):
        entry = HOSTS[i]
        host_ip = entry["ip"]
        node_id = entry["node_id"]
        iface = entry["iface"]
        meo_url = f"http://{host_ip}:6666"

        is_consumer = (i < consumers)
        if is_consumer:
            consumer_idx += 1
            role = "consumer"
            local_domain_id = f"consumer_{consumer_idx}"
        else:
            provider_idx += 1
            role = "provider"
            local_domain_id = f"provider_{provider_idx}"

        cmd = (
            f"cd {REMOTE_DIR} && "
            f"./start_mef_soa.sh "
            f"--domain-function {role} "
            f"--meo-url {meo_url} "
            f"--node-id {node_id} "
            f"--vxlan-interface {iface} "
            f"--local-domain-id {local_domain_id}"
        )

        print(f"-> node{i+1} ({host_ip}) → role={role}, local_domain_id={local_domain_id}, iface={iface}, node_id={node_id}")
        exec_on_host(host_ip, cmd)

def stop_mef(nodes: int) -> None:
    for i in range(nodes):
        host_ip = HOSTS[i]["ip"]
        exec_on_host(host_ip, STOP_MEF_CMD)

def start_meo(nodes: int) -> None:
    for i in range(nodes):
        host_ip = HOSTS[i]["ip"]
        exec_on_host(host_ip, START_MEO_CMD)

def stop_meo(nodes: int) -> None:
    for i in range(nodes):
        host_ip = HOSTS[i]["ip"]
        exec_on_host(host_ip, STOP_MEO_CMD)

def parse_args():
    p = argparse.ArgumentParser(description="Start/stop MEF and/or MEO via SSH.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--start", action="store_true", help="Start components")
    g.add_argument("--stop", action="store_true", help="Stop components")

    p.add_argument("-n", "--nodes", type=int, required=True, help="Highest node index N (use first N entries from HOSTS)")
    p.add_argument("-c", "--consumers", type=int, default=1, help="How many consumers (from node1 upward)")
    p.add_argument("--mef", action="store_true", help="Include MEF managers")
    p.add_argument("--meo", action="store_true", help="Include MEO containers")

    return p.parse_args()

def main():
    args = parse_args()

    if not (args.mef or args.meo):
        print("⚠ You must specify at least one of --mef or --meo")
        return

    if args.nodes < 1 or args.nodes > len(HOSTS):
        print(f"⚠ --nodes must be between 1 and {len(HOSTS)}")
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

#!/usr/bin/env python3
"""
SoA multiple-offers runner (consumers trigger /start_experiments_consumer; providers just listen).

- First -c nodes are consumers; the rest are providers.
- Pre-run: deploy 'mecapp' on each consumer's MEO (http://<ip>:6666).
- Consumers call their local MEF /start_experiments_consumer with offers_to_wait:
    * 2 if participants >= 10, else 1.
- Post-run cleanup:
    * Consumers: delete 'mecapp', delete VXLAN id (200 + node_id) on net 'fed-net'.
    * Providers: /cleanup (containers/networks/vxlan by prefix) via their MEO.

Examples:
  python run_experiments_multiple_offers_soa.py -n 10 -c 8 -t 3 --export-csv --csv-base /experiments/test --timeout 20
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple
import requests

# ------------- Static inventory -------------
HOSTS: List[Dict[str, Any]] = [
    {"node_id": i, "ip": f"10.5.99.{i}"} for i in range(1, 31)
]

# ------------- Defaults -------------
MEF_PORT = 8000
MEO_PORT = 6666
BETWEEN_RUNS = 3.0

CONSUMER_APP_IMAGE = "mec-app:latest"
APP_NAME = "mecapp"
CONSUMER_APP_NETWORK = "bridge"
CONSUMER_APP_REPLICAS = 1
VXLAN_NETNAME = "fed-net"   # consumer-side fixed name in your MEF-SoA

# Globals set from CLI
EXPORT_TO_CSV = False
CSV_BASE = "/experiments/test"
TIMEOUT = 10.0  # seconds

# ------------- HTTP helpers -------------
def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text

def post_json(url: str, payload: Dict[str, Any]) -> Tuple[int, Any]:
    try:
        r = requests.post(url, json=payload, timeout=TIMEOUT)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url, "payload": payload}

def post_params(url: str, params: Dict[str, Any]) -> Tuple[int, Any]:
    try:
        r = requests.post(url, params=params, timeout=TIMEOUT)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url, "params": params}

def delete_params(url: str, params: Dict[str, Any]) -> Tuple[int, Any]:
    try:
        r = requests.delete(url, params=params, timeout=TIMEOUT)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url, "params": params}

def is_error(status: int, body: Any) -> bool:
    if status >= 400:
        return True
    if isinstance(body, dict) and body.get("success") is False:
        return True
    return False

# ------------- MEO helpers -------------
def meo_deploy_consumer_app(consumer_ip: str) -> None:
    url = f"http://{consumer_ip}:{MEO_PORT}/deploy_docker_service"
    params = {
        "image": CONSUMER_APP_IMAGE,
        "name": APP_NAME,
        "network": CONSUMER_APP_NETWORK,
        "replicas": CONSUMER_APP_REPLICAS,
    }
    print(f"[consumer {consumer_ip}] deploy app → POST {url} params={params}")
    sc, resp = post_params(url, params)
    if is_error(sc, resp):
        print(f"[consumer {consumer_ip}] deploy app ERROR: {sc} {resp}")
    time.sleep(0.5)

def meo_delete_service(host_ip: str, service_name: str, tag: str) -> None:
    url = f"http://{host_ip}:{MEO_PORT}/delete_docker_service"
    params = {"name": service_name}
    print(f"[{tag}] delete service '{service_name}' → DELETE {url} params={params}")
    sc, resp = delete_params(url, params)
    if is_error(sc, resp):
        print(f"[{tag}] delete service ERROR: {sc} {resp}")

def meo_delete_vxlan(host_ip: str, vxlan_id: int, netname: str, tag: str) -> None:
    url = f"http://{host_ip}:{MEO_PORT}/delete_vxlan"
    params = {"vxlan_id": vxlan_id, "docker_net_name": netname}
    print(f"[{tag}] delete VXLAN id={vxlan_id} net={netname} → DELETE {url} params={params}")
    sc, resp = delete_params(url, params)
    if is_error(sc, resp):
        print(f"[{tag}] delete VXLAN ERROR: {sc} {resp}")

def meo_cleanup_provider(host_ip: str, tag: str) -> None:
    url = f"http://{host_ip}:{MEO_PORT}/cleanup"
    params = {"container_prefix": "mecapp-", "network_prefix": "fed-net-", "vxlan_prefix": "vxlan"}
    print(f"[{tag}] provider cleanup → DELETE {url} params={params}")
    sc, resp = delete_params(url, params)
    if is_error(sc, resp):
        print(f"[{tag}] provider cleanup ERROR: {sc} {resp}")

# ------------- Experiment calls -------------
def start_consumer(consumer: Dict[str, Any], consumer_idx: int, offers_to_wait: int, run_idx: int) -> Dict[str, Any]:
    ip = consumer["ip"]
    url = f"http://{ip}:{MEF_PORT}/start_experiments_consumer"
    payload = {
        "requirements": "zero_packet_loss",
        "offers_to_wait": int(offers_to_wait),
        "export_to_csv": EXPORT_TO_CSV,
        "csv_path": f"{CSV_BASE}/consumer_{consumer_idx}_run_{run_idx}.csv",
    }
    print(f"[consumer{consumer_idx} node{consumer['node_id']}] → POST {url} offers_to_wait={offers_to_wait}")
    sc, resp = post_json(url, payload)
    if is_error(sc, resp):
        print(f"[consumer{consumer_idx} node{consumer['node_id']}] ERROR: {sc} {resp}")
    return {"status": sc}

# ------------- Orchestration -------------
def run_one(total_nodes: int, num_consumers: int, run_idx: int) -> None:
    assert 2 <= total_nodes <= len(HOSTS)
    assert 1 <= num_consumers < total_nodes, "-c must be >=1 and < total nodes"

    hosts = HOSTS[:total_nodes]
    consumers = hosts[:num_consumers]
    providers = hosts[num_consumers:]
    participants = total_nodes

    print(f"[plan] consumers={len(consumers)} providers={len(providers)} participants={participants}")
    print("[plan] consumer nodes:", [h["node_id"] for h in consumers])
    print("[plan] provider nodes:", [h["node_id"] for h in providers])

    offers_to_wait = 2 if participants >= 10 else 1

    # 1) Pre-run: deploy consumer app on each consumer host
    for cons in consumers:
        meo_deploy_consumer_app(cons["ip"])

    time.sleep(3)
    # 2) Trigger consumers in parallel
    with ThreadPoolExecutor(max_workers=min(32, len(consumers))) as pool:
        futs = [
            pool.submit(start_consumer, cons, idx, offers_to_wait, run_idx)
            for idx, cons in enumerate(consumers, start=1)
        ]
        results = [f.result() for f in as_completed(futs)]

    ok_cons = sum(1 for r in results if r["status"] < 400)
    print(f"[run {run_idx}] consumers ok: {ok_cons}/{len(consumers)}")

    # 3) Cleanup
    # Consumers: delete app + VXLAN (id = 200 + node_id), net = "fed-net"
    for cidx, cons in enumerate(consumers, start=1):
        meo_delete_service(cons["ip"], APP_NAME, tag=f"consumer{cidx}_node{cons['node_id']}")
        vxlan_id = 200 + int(cons["node_id"])
        meo_delete_vxlan(cons["ip"], vxlan_id, VXLAN_NETNAME, tag=f"consumer{cidx}_node{cons['node_id']}")

    # Providers: cleanup via MEO
    for pidx, prov in enumerate(providers, start=1):
        meo_cleanup_provider(prov["ip"], tag=f"provider{pidx}_node{prov['node_id']}")

# ------------- CLI -------------
def parse_args():
    ap = argparse.ArgumentParser(description="SoA multi-offers runner (consumers trigger SoA; providers already listening).")
    ap.add_argument("-n", "--nodes", type=int, required=True, help="Total participants (consumers + providers)")
    ap.add_argument("-c", "--consumers", type=int, required=True, help="Number of consumers (first -c hosts)")
    ap.add_argument("-t", "--tests", type=int, required=True, help="Number of runs")
    ap.add_argument("--export-csv", action="store_true", default=False, help="Ask consumers to export CSVs")
    ap.add_argument("--csv-base", default="/experiments/test", help="Remote base path for CSVs")
    ap.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    return ap.parse_args()

def main() -> int:
    global EXPORT_TO_CSV, CSV_BASE, TIMEOUT
    args = parse_args()

    if args.nodes < 2:
        print("Error: -n/--nodes must be >= 2"); return 2
    if args.consumers < 1 or args.consumers >= args.nodes:
        print("Error: -c/--consumers must be >= 1 and < nodes"); return 2
    if args.tests < 1:
        print("Error: -t/--tests must be >= 1"); return 2

    EXPORT_TO_CSV = bool(args.export_csv)
    CSV_BASE = args.csv_base
    TIMEOUT = float(args.timeout)

    print(f"CSV base: {CSV_BASE} | export_csv={EXPORT_TO_CSV} | timeout={TIMEOUT}s")

    for i in range(1, args.tests + 1):
        print(f"\n=== Run {i}/{args.tests} | nodes={args.nodes} | consumers={args.consumers} ===")
        run_one(args.nodes, args.consumers, i)
        if i < args.tests and BETWEEN_RUNS > 0:
            print(f"Waiting {BETWEEN_RUNS}s before next run...")
            time.sleep(BETWEEN_RUNS)

    print("\nAll experiments completed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

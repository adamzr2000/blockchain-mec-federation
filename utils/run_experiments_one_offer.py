#!/usr/bin/env python3
"""
Minimal runner with static host inventory.
- Pre-run: deploy consumer app via MEO (mec-app:latest -> mecapp on bridge)
- Run: start providers (parallel) then consumer
- Post-run: delete consumer app; delete provider1 app; delete VXLAN on consumer+provider1
- Monitor: start validator resource monitoring before run, stop after run (only if --export-csv)
- Writes files ONLY if something fails (HTTP >= 400 or {"success": false})

Usage:
  python run_experiments.py -n 3 -t 3
  python run_experiments.py -n 3 -t 3 --export-csv --csv-base /experiments/test
"""

import argparse
import json
import random
import time
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# =========================
# Static host inventory (edit iface/ip per host if needed)
# =========================
HOSTS: List[Dict[str, Any]] = [
    {"role": "consumer", "node_id": 1,  "ip": "10.5.99.1",  "iface": "ens3"},
    {"role": "provider", "node_id": 2,  "ip": "10.5.99.2",  "iface": "ens3"},
    {"role": "provider", "node_id": 3,  "ip": "10.5.99.3",  "iface": "ens3"},
    {"role": "provider", "node_id": 4,  "ip": "10.5.99.4",  "iface": "ens3"},
    {"role": "provider", "node_id": 5,  "ip": "10.5.99.5",  "iface": "ens3"},
    {"role": "provider", "node_id": 6,  "ip": "10.5.99.6",  "iface": "ens3"},
    {"role": "provider", "node_id": 7,  "ip": "10.5.99.7",  "iface": "ens3"},
    {"role": "provider", "node_id": 8,  "ip": "10.5.99.8",  "iface": "ens3"},
    {"role": "provider", "node_id": 9,  "ip": "10.5.99.9",  "iface": "ens3"},
    {"role": "provider", "node_id": 10, "ip": "10.5.99.10", "iface": "ens3"},
    {"role": "provider", "node_id": 11, "ip": "10.5.99.11", "iface": "ens3"},
    {"role": "provider", "node_id": 12, "ip": "10.5.99.12", "iface": "ens3"},
    {"role": "provider", "node_id": 13, "ip": "10.5.99.13", "iface": "ens3"},
    {"role": "provider", "node_id": 14, "ip": "10.5.99.14", "iface": "ens3"},
    {"role": "provider", "node_id": 15, "ip": "10.5.99.15", "iface": "ens3"},
    {"role": "provider", "node_id": 16, "ip": "10.5.99.16", "iface": "ens3"},
    {"role": "provider", "node_id": 17, "ip": "10.5.99.17", "iface": "ens3"},
    {"role": "provider", "node_id": 18, "ip": "10.5.99.18", "iface": "ens3"},
    {"role": "provider", "node_id": 19, "ip": "10.5.99.19", "iface": "ens3"},
    {"role": "provider", "node_id": 20, "ip": "10.5.99.20", "iface": "ens3"},
    {"role": "provider", "node_id": 21, "ip": "10.5.99.21", "iface": "ens3"},
    {"role": "provider", "node_id": 22, "ip": "10.5.99.22", "iface": "ens3"},
    {"role": "provider", "node_id": 23, "ip": "10.5.99.23", "iface": "ens3"},
    {"role": "provider", "node_id": 24, "ip": "10.5.99.24", "iface": "ens3"},
    {"role": "provider", "node_id": 25, "ip": "10.5.99.25", "iface": "ens3"},
    {"role": "provider", "node_id": 26, "ip": "10.5.99.26", "iface": "ens3"},
    {"role": "provider", "node_id": 27, "ip": "10.5.99.27", "iface": "ens3"},
    {"role": "provider", "node_id": 28, "ip": "10.5.99.28", "iface": "ens3"},
    {"role": "provider", "node_id": 29, "ip": "10.5.99.29", "iface": "ens3"},
    {"role": "provider", "node_id": 30, "ip": "10.5.99.30", "iface": "ens3"},
]

# --- Defaults ---
BM_PORT = 8000
MEO_PORT = 6666
REQ_TIMEOUT = 90
EXPORT_TO_CSV = False
CSV_BASE = "/experiments/test"
LOWEST_PRICE = 10
PRICE_MIN, PRICE_MAX = 11, 100
BETWEEN_RUNS = 3.0

CONSUMER_APP_IMAGE = "mec-app:latest"
APP_NAME = "mecapp"
CONSUMER_APP_NETWORK = "bridge"
CONSUMER_APP_REPLICAS = 1

VXLAN_ID_CLEANUP = 201
VXLAN_NETNAME = "fed-net"

# ---------- Error sink ----------
class ErrorSink:
    def __init__(self, base: Path):
        self.base = base
        self.session_dir: Optional[Path] = None 

    def _ensure_session(self):
        if self.session_dir is None:
            utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            self.session_dir = self.base / f"session_{utc}"
            self.session_dir.mkdir(parents=True, exist_ok=True)
            print(f"[errors] session dir: {self.session_dir}")

    def write(self, run_idx: int, filename: str, payload: Dict[str, Any]) -> None:
        self._ensure_session()
        run_dir = self.session_dir / f"run_{run_idx}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / filename).write_text(json.dumps(payload, indent=2, ensure_ascii=False))

ERRS: Optional[ErrorSink] = None

# ---------- HTTP helpers ----------
def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text

def is_error(status: int, body: Any) -> bool:
    if status >= 400:
        return True
    if isinstance(body, dict) and body.get("success") is False:
        return True
    return False

def post_json(url: str, payload: Dict[str, Any]) -> Tuple[int, Any]:
    try:
        r = requests.post(url, json=payload, timeout=REQ_TIMEOUT)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url, "payload": payload}

def post_params(url: str, params: Dict[str, Any]) -> Tuple[int, Any]:
    try:
        r = requests.post(url, params=params, timeout=REQ_TIMEOUT)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url, "params": params}

def delete_params(url: str, params: Dict[str, Any]) -> Tuple[int, Any]:
    try:
        r = requests.delete(url, params=params, timeout=REQ_TIMEOUT)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url, "params": params}

# ---------- Monitoring helpers ----------
def start_monitor(host_ip: str, validator_name: str, run_idx: int):
    url = f"http://{host_ip}:{MEO_PORT}/monitor/start"
    params = {
        "container": validator_name,
        "interval": 1.0,
        "stdout": "true",
    }
    if EXPORT_TO_CSV:
        params["csv_path"] = f"{CSV_BASE}/docker-logs/{validator_name}_run_{run_idx}.csv"

    print(f"[monitor] start {validator_name} on {host_ip} → POST {url} params={params}")
    sc, resp = post_params(url, params)
    if is_error(sc, resp) and ERRS:
        ERRS.write(run_idx, f"monitor_start_{validator_name}_run{run_idx}.json",
                   {"host": host_ip, "status": sc, "response": resp})

def stop_monitor(host_ip: str, validator_name: str, run_idx: int):
    url = f"http://{host_ip}:{MEO_PORT}/monitor/stop"
    print(f"[monitor] stop {validator_name} on {host_ip} → POST {url}")
    sc, resp = post_params(url, {})
    if is_error(sc, resp) and ERRS:
        ERRS.write(run_idx, f"monitor_stop_{validator_name}_run{run_idx}.json",
                   {"host": host_ip, "status": sc, "response": resp})

# ---------- Payload builders ----------
def provider_payload(host: Dict[str, Any], provider_index: int, run_idx: int) -> Dict[str, Any]:
    ip = host["ip"]
    return {
        "price_wei_per_hour": 0,
        "meo_endpoint": f"http://{ip}:{MEO_PORT}",
        "ip_address": ip,
        "vxlan_interface": host["iface"],
        "node_id": host["node_id"],
        "export_to_csv": EXPORT_TO_CSV,
        "csv_path": f"{CSV_BASE}/provider_{provider_index}_run_{run_idx}.csv",
    }

def consumer_payload(consumer: Dict[str, Any], num_providers: int, run_idx: int) -> Dict[str, Any]:
    offers_to_wait = num_providers
    ip = consumer["ip"]
    return {
        "requirements": "zero_packet_loss",
        "offers_to_wait": offers_to_wait,
        "meo_endpoint": f"http://{ip}:{MEO_PORT}",
        "ip_address": ip,
        "vxlan_interface": consumer["iface"],
        "node_id": consumer["node_id"],
        "export_to_csv": EXPORT_TO_CSV,
        "csv_path": f"{CSV_BASE}/consumer_run_{run_idx}.csv",
    }

# ---------- Pricing ----------
def generate_prices(num_providers: int) -> List[int]:
    prices: List[int] = []
    for i in range(1, num_providers + 1):
        prices.append(LOWEST_PRICE if i == 1 else random.randint(PRICE_MIN, PRICE_MAX))
    return prices

# ---------- MEO helpers ----------
def meo_deploy_consumer_app(consumer_ip: str, run_idx: int) -> None:
    url = f"http://{consumer_ip}:{MEO_PORT}/deploy_docker_service"
    params = {"image": CONSUMER_APP_IMAGE, "name": APP_NAME,
              "network": CONSUMER_APP_NETWORK, "replicas": CONSUMER_APP_REPLICAS}
    print(f"[consumer] deploy app → POST {url} params={params}")
    sc, resp = post_params(url, params)
    if is_error(sc, resp) and ERRS:
        ERRS.write(run_idx, f"consumer_deploy_error_run{run_idx}.json", {"status": sc, "response": resp})
    time.sleep(1.0)

def meo_delete_service(host_ip: str, service_name: str, run_idx: int, tag: str) -> None:
    url = f"http://{host_ip}:{MEO_PORT}/delete_docker_service"
    params = {"name": service_name}
    print(f"[{tag}] delete service '{service_name}' → DELETE {url} params={params}")
    sc, resp = delete_params(url, params)
    if is_error(sc, resp) and ERRS:
        ERRS.write(run_idx, f"{tag}_delete_service_error_run{run_idx}.json",
                   {"host": host_ip, "status": sc, "response": resp})

def meo_delete_vxlan(host_ip: str, vxlan_id: int, netname: str, run_idx: int, tag: str) -> None:
    url = f"http://{host_ip}:{MEO_PORT}/delete_vxlan"
    params = {"vxlan_id": vxlan_id, "docker_net_name": netname}
    print(f"[{tag}] delete VXLAN id={vxlan_id} net={netname} → DELETE {url} params={params}")
    sc, resp = delete_params(url, params)
    if is_error(sc, resp) and ERRS:
        ERRS.write(run_idx, f"{tag}_delete_vxlan_error_run{run_idx}.json",
                   {"host": host_ip, "status": sc, "response": resp})

# ---------- Experiment calls ----------
def start_provider(host: Dict[str, Any], provider_index: int, price: int, run_idx: int) -> Dict[str, Any]:
    ip = host["ip"]
    url = f"http://{ip}:{BM_PORT}/start_experiments_provider"
    payload = provider_payload(host, provider_index, run_idx)
    payload["price_wei_per_hour"] = int(price)

    print(f"[provider{provider_index} (node{host['node_id']})] → POST {url} price={price}")
    sc, resp = post_json(url, payload)
    if is_error(sc, resp) and ERRS:
        ERRS.write(run_idx, f"provider{provider_index}_node{host['node_id']}_error_run{run_idx}.json",
                   {"host": ip, "status": sc, "response": resp})
    return {"status": sc}

def start_consumer(consumer: Dict[str, Any], num_providers: int, run_idx: int) -> Dict[str, Any]:
    ip = consumer["ip"]
    url = f"http://{ip}:{BM_PORT}/start_experiments_consumer"
    payload = consumer_payload(consumer, num_providers, run_idx)

    print(f"[consumer node{consumer['node_id']}] → POST {url} offers_to_wait={payload['offers_to_wait']}")
    sc, resp = post_json(url, payload)
    if is_error(sc, resp) and ERRS:
        ERRS.write(run_idx, f"consumer_error_run{run_idx}.json",
                   {"host": ip, "status": sc, "response": resp})
    return {"status": sc}

# ---------- Orchestration ----------
def run_one(total_nodes: int, run_idx: int) -> None:
    assert 2 <= total_nodes <= len(HOSTS)

    consumer = HOSTS[0]
    providers = HOSTS[1:total_nodes]
    all_nodes = [consumer] + providers

    # 0) Start monitoring (validators)
    for node in all_nodes:
        validator_name = f"validator{node['node_id']}"
        start_monitor(node["ip"], validator_name, run_idx)

    # 1) Pre-run: deploy consumer app
    meo_deploy_consumer_app(consumer["ip"], run_idx)

    # 2) Kick off providers
    prices = generate_prices(len(providers))
    with ThreadPoolExecutor(max_workers=min(16, len(providers))) as pool:
        prov_futs = [pool.submit(start_provider, host, idx, price, run_idx)
                     for idx, (host, price) in enumerate(zip(providers, prices), start=1)]

        time.sleep(0.5)
        cons_result = start_consumer(consumer, len(providers), run_idx)

        prov_results = [f.result() for f in as_completed(prov_futs)]

    ok_prov = sum(1 for r in prov_results if r["status"] < 400)
    ok_cons = cons_result["status"] < 400
    print(f"[run {run_idx}] providers ok: {ok_prov}/{len(providers)} | consumer ok: {ok_cons}")

    # 3) Stop monitoring (validators)
    for node in all_nodes:
        validator_name = f"validator{node['node_id']}"
        stop_monitor(node["ip"], validator_name, run_idx)

    # 4) Cleanup
    meo_delete_service(consumer["ip"], APP_NAME, run_idx, tag="consumer")
    if providers:
        provider1 = providers[0]
        meo_delete_service(provider1["ip"], APP_NAME, run_idx, tag="provider1")
        meo_delete_vxlan(provider1["ip"], VXLAN_ID_CLEANUP, VXLAN_NETNAME, run_idx, tag="provider1")
    meo_delete_vxlan(consumer["ip"], VXLAN_ID_CLEANUP, VXLAN_NETNAME, run_idx, tag="consumer")

# ---------- CLI ----------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Minimal experiments runner (errors only logging)")
    ap.add_argument("-n", "--nodes", type=int, required=True)
    ap.add_argument("-t", "--tests", type=int, required=True)
    ap.add_argument("--export-csv", action="store_true", default=False)
    ap.add_argument("--csv-base", default="/experiments/test")
    return ap.parse_args()

def compute_local_logs_root(csv_base: str) -> Path:
    clean = csv_base.lstrip("/")
    return Path("..") / clean / "logs"

def main() -> int:
    global CSV_BASE, EXPORT_TO_CSV, ERRS
    args = parse_args()

    if args.nodes < 2:
        print("Error: -n/--nodes must be >= 2")
        return 2
    if args.tests < 1:
        print("Error: -t/--tests must be >= 1")
        return 2

    CSV_BASE = args.csv_base
    EXPORT_TO_CSV = bool(args.export_csv)
    ERRS = ErrorSink(compute_local_logs_root(CSV_BASE))

    print(f"Remote CSV base: {CSV_BASE}")
    print(f"Local error logs: {compute_local_logs_root(CSV_BASE)}")
    print("export_to_csv:", EXPORT_TO_CSV)

    for i in range(1, args.tests + 1):
        print(f"\n=== Run {i}/{args.tests} | nodes={args.nodes} ===")
        run_one(args.nodes, i)
        if i < args.tests and BETWEEN_RUNS > 0:
            print(f"Waiting {BETWEEN_RUNS}s before next run...")
            time.sleep(BETWEEN_RUNS)

    print("\nAll experiments completed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

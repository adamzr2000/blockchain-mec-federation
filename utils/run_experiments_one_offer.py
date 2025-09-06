#!/usr/bin/env python3
"""
Minimal runner with static host inventory.
- Pre-run: deploy consumer app via MEO (mec-app:latest -> mecapp on bridge)
- Run: start providers (parallel) then consumer
- Post-run: delete consumer app; delete provider1 app; delete VXLAN on consumer+provider1
- Writes files ONLY if something fails (HTTP >= 400 or {"success": false})

Usage:
  python run_experiments.py -n 3 -t 3
  python run_experiments.py -n 3 -t 3 --export-csv --csv-base /experiments/test
"""

import argparse
import json
import random
import time
import os
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

# --- Defaults (overridden by CLI) ---
BM_PORT = 8000
MEO_PORT = 6666
REQ_TIMEOUT = 90  # seconds
EXPORT_TO_CSV = False
CSV_BASE = "/experiments/test"  # remote CSV base (overridable via --csv-base)
LOWEST_PRICE = 10              # provider1
PRICE_MIN, PRICE_MAX = 11, 100 # provider2..K
BETWEEN_RUNS = 3.0  # seconds; set e.g. 5.0 to wait 5s between runs

# Consumer & Provider1 app (same name per your note)
CONSUMER_APP_IMAGE = "mec-app:latest"
APP_NAME = "mecapp"               # used on consumer AND provider1
CONSUMER_APP_NETWORK = "bridge"
CONSUMER_APP_REPLICAS = 1

# VXLAN cleanup (both consumer and provider1)
VXLAN_ID_CLEANUP = 201
VXLAN_NETNAME = "fed-net"
# ---------------------------------------


# ---------- Error sink (lazy; only writes on error) ----------

class ErrorSink:
    def __init__(self, base: Path):
        self.base = base
        self.session_dir: Optional[Path] = None 

    def _ensure_session(self):
        if self.session_dir is None:
            utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            host = socket.gethostname()
            pid = os.getpid()
            rid = uuid.uuid4().hex[:6]
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


# ---------- Payload builders ----------

def provider_payload(host: Dict[str, Any], provider_index: int, run_idx: int) -> Dict[str, Any]:
    ip = host["ip"]
    return {
        "price_wei_per_hour": 0,  # set by caller
        "meo_endpoint": f"http://{ip}:{MEO_PORT}",
        "ip_address": ip,
        "vxlan_interface": host["iface"],
        "node_id": host["node_id"],
        "export_to_csv": EXPORT_TO_CSV,
        "csv_path": f"{CSV_BASE}/provider_{provider_index}_run_{run_idx}.csv",
    }

def consumer_payload(consumer: Dict[str, Any], num_providers: int, run_idx: int) -> Dict[str, Any]:
    # offers_to_wait = min(2, num_providers) if num_providers > 0 else 0
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


# ---------- MEO helpers (deploy/cleanup) ----------

def meo_deploy_consumer_app(consumer_ip: str, run_idx: int) -> None:
    url = f"http://{consumer_ip}:{MEO_PORT}/deploy_docker_service"
    params = {
        "image": CONSUMER_APP_IMAGE,
        "name": APP_NAME,
        "network": CONSUMER_APP_NETWORK,
        "replicas": CONSUMER_APP_REPLICAS,
    }
    print(f"[consumer] deploy app → POST {url} params={params}")
    sc, resp = post_params(url, params)
    if is_error(sc, resp) and ERRS:
        ERRS.write(run_idx, f"consumer_deploy_error_run{run_idx}.json", {"status": sc, "response": resp})
    time.sleep(1.0)  # brief settle

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
    assert 2 <= total_nodes <= len(HOSTS), f"nodes must be between 2 and {len(HOSTS)}"

    consumer = HOSTS[0]
    providers = HOSTS[1:total_nodes]
    num_providers = len(providers)

    # 0) Pre-run: deploy consumer app
    meo_deploy_consumer_app(consumer["ip"], run_idx)

    # 1) Kick off providers in parallel (do NOT wait yet)
    prices = generate_prices(num_providers)
    with ThreadPoolExecutor(max_workers=min(16, num_providers)) as pool:
        prov_futs = []
        for provider_index, host in enumerate(providers, start=1):
            price = prices[provider_index - 1]
            prov_futs.append(pool.submit(start_provider, host, provider_index, price, run_idx))

        # 2) Small grace period, then start consumer on the main thread
        time.sleep(0.5)
        cons_result = start_consumer(consumer, num_providers, run_idx)

        # 3) Now wait for all providers to finish
        prov_results = []
        for f in as_completed(prov_futs):
            prov_results.append(f.result())

    ok_prov = sum(1 for r in prov_results if r["status"] < 400)
    ok_cons = cons_result["status"] < 400
    print(f"[run {run_idx}] providers ok: {ok_prov}/{num_providers} | consumer ok: {ok_cons}")

    # 4) Post-run cleanup
    # 4a) delete consumer app on consumer
    meo_delete_service(consumer["ip"], APP_NAME, run_idx, tag="consumer")

    # 4b) delete provider1 app on provider1 (winner) — uses SAME name as consumer
    if providers:
        provider1 = providers[0]  # logical provider1 (lowest price)
        meo_delete_service(provider1["ip"], APP_NAME, run_idx, tag="provider1")
        # 4c) delete VXLAN on provider1
        meo_delete_vxlan(provider1["ip"], VXLAN_ID_CLEANUP, VXLAN_NETNAME, run_idx, tag="provider1")

    # 4d) delete VXLAN on consumer
    meo_delete_vxlan(consumer["ip"], VXLAN_ID_CLEANUP, VXLAN_NETNAME, run_idx, tag="consumer")


# ---------- CLI ----------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Minimal experiments runner (errors only logging)")
    ap.add_argument("-n", "--nodes", type=int, required=True, help="Total nodes (consumer=1, providers=2..N)")
    ap.add_argument("-t", "--tests", type=int, required=True, help="Number of repetitions")
    ap.add_argument("--export-csv", action="store_true", default=False,
                    help="Set export_to_csv=true in requests (default: False)")
    ap.add_argument("--csv-base", default="/experiments/test",
                    help="Remote base path for CSVs; local error logs go to ../<csv-base>/logs (default: /experiments/test)")
    return ap.parse_args()

def compute_local_logs_root(csv_base: str) -> Path:
    clean = csv_base.lstrip("/")  # drop leading slash if absolute
    return Path("..") / clean / "logs"

def main() -> int:
    global CSV_BASE, EXPORT_TO_CSV, ERRS

    args = parse_args()
    if args.nodes < 2:
        print("Error: -n/--nodes must be >= 2 (1 consumer + 1 provider)")
        return 2
    if args.tests < 1:
        print("Error: -t/--tests must be >= 1")
        return 2

    # Apply CLI overrides
    CSV_BASE = args.csv_base
    EXPORT_TO_CSV = bool(args.export_csv)

    # Init error sink at ../<csv-base>/logs
    log_root = compute_local_logs_root(CSV_BASE)
    ERRS = ErrorSink(log_root)

    print(f"Remote CSV base: {CSV_BASE}")
    print(f"Local error logs: {log_root} (only written if something fails)")
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

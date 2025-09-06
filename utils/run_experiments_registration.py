#!/usr/bin/env python3
"""
Run registration experiments in parallel across N MEC hosts.
Each host runs /start_experiments_registration simultaneously,
waits until all are done, then cleans up with /unregister_domain.

Usage:
  python run_experiments_registration.py -n 3 -t 5 --export-csv --csv-base /experiments/test
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple
import requests

# =========================
# Static host inventory
# =========================
HOSTS: List[Dict[str, Any]] = [
    {"node_id": i, "ip": f"10.5.99.{i}"} for i in range(1, 31)
]

BM_PORT = 8000
REQ_TIMEOUT = 90  # seconds
EXPORT_TO_CSV = False
CSV_BASE = "/experiments/test"
BETWEEN_RUNS = 3.0  # seconds pause between runs


# ---------- HTTP helpers ----------
def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text

def post_json(url: str, payload: Dict[str, Any]) -> Tuple[int, Any]:
    try:
        r = requests.post(url, json=payload, timeout=REQ_TIMEOUT)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url}

def delete_json(url: str) -> Tuple[int, Any]:
    try:
        r = requests.delete(url, timeout=REQ_TIMEOUT)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url}


# ---------- Experiment calls ----------
def start_registration(host: Dict[str, Any], run_idx: int) -> Dict[str, Any]:
    ip = host["ip"]
    url = f"http://{ip}:{BM_PORT}/start_experiments_registration"
    csv_file_name = f"mec_{host['node_id']}_run_{run_idx}"
    name = f"mec_{host['node_id']}"
    payload = {
        "name": name,
        "export_to_csv": EXPORT_TO_CSV,
        "csv_path": f"{CSV_BASE}/{csv_file_name}.csv",
    }
    print(f"[node{host['node_id']}] → POST {url} name={name}")
    sc, resp = post_json(url, payload)
    return {"status": sc, "response": resp}

def cleanup_registration(host: Dict[str, Any], run_idx: int) -> Dict[str, Any]:
    ip = host["ip"]
    url = f"http://{ip}:{BM_PORT}/unregister_domain"
    print(f"[node{host['node_id']}] → DELETE {url}")
    sc, resp = delete_json(url)
    return {"status": sc, "response": resp}


# ---------- Orchestration ----------
def run_one(total_nodes: int, run_idx: int) -> None:
    hosts = HOSTS[:total_nodes]

    # Phase 1: parallel registration
    results = []
    with ThreadPoolExecutor(max_workers=total_nodes) as pool:
        futs = {pool.submit(start_registration, h, run_idx): h for h in hosts}
        for f in as_completed(futs):
            host = futs[f]
            try:
                results.append((host, f.result()))
            except Exception as e:
                results.append((host, {"status": 599, "error": str(e)}))

    ok = sum(1 for _, r in results if r.get("status", 500) < 400)
    print(f"[run {run_idx}] registrations ok: {ok}/{total_nodes}")

    # Phase 2: cleanup for all
    with ThreadPoolExecutor(max_workers=total_nodes) as pool:
        futs = {pool.submit(cleanup_registration, h, run_idx): h for h in hosts}
        for f in as_completed(futs):
            f.result()

    print(f"[run {run_idx}] cleanup completed.")


# ---------- CLI ----------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Registration experiments runner")
    ap.add_argument("-n", "--nodes", type=int, required=True,
                    help="Total MEC nodes to include (1..N)")
    ap.add_argument("-t", "--tests", type=int, required=True,
                    help="Number of repetitions")
    ap.add_argument("--export-csv", action="store_true", default=False,
                    help="Export per-host CSVs (default: False)")
    ap.add_argument("--csv-base", default="/experiments/test",
                    help="Remote base path for CSVs (default: /experiments/test)")
    return ap.parse_args()


def main() -> int:
    global CSV_BASE, EXPORT_TO_CSV
    args = parse_args()
    if args.nodes < 1:
        print("Error: -n/--nodes must be >= 1")
        return 2
    if args.tests < 1:
        print("Error: -t/--tests must be >= 1")
        return 2

    CSV_BASE = args.csv_base
    EXPORT_TO_CSV = args.export_csv

    print(f"CSV base: {CSV_BASE} | export_csv={EXPORT_TO_CSV}")

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

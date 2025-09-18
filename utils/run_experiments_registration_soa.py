#!/usr/bin/env python3
"""
Run SoA "registration experiments" across multiple hosts.

- First C nodes are consumers; the rest are providers (all share the same port).
- Phase 1: in parallel, each consumer calls POST /federators/autoRegister
           with the list of provider base URLs.
- Phase 2: delete all local peer registries via DELETE /federators on every node.

Example:
  python soa_run_registration.py -n 30 -c 24 -t 5 \
    --subnet 10.5.99. --port 8000 --export-csv --csv-base /experiments/test
"""

import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple
import requests

DEFAULT_SUBNET = "10.5.99."
DEFAULT_PORT = 8000
DEFAULT_SCHEME = "http"
DEFAULT_TIMEOUT = 8.0
PAUSE_BETWEEN_RUNS = 2.0

def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text

def post_json(url: str, payload: Dict[str, Any], timeout: float) -> Tuple[int, Any]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url}

def delete_json(url: str, timeout: float) -> Tuple[int, Any]:
    try:
        r = requests.delete(url, timeout=timeout)
        return r.status_code, _safe_json(r)
    except Exception as e:
        return 599, {"error": str(e), "url": url}

# ---------------- Phase 1: auto-register (consumers) ----------------
def auto_register_on_consumer(consumer_url: str,
                              providers: List[str],
                              timeout_s: float,
                              export_to_csv: bool,
                              csv_path: str) -> Dict[str, Any]:
    url = f"{consumer_url}/federators/autoRegister"
    payload = {
        "providers": providers,
        "self_url": consumer_url,
        "timeout_s": timeout_s,
        "export_to_csv": export_to_csv,
        "csv_path": csv_path,
    }
    sc, body = post_json(url, payload, timeout_s + 2)
    ok = (sc < 400) and isinstance(body, dict) and (body.get("registered", 0) == body.get("total", 0))
    return {"status": sc, "ok": ok, "body": body}

# ---------------- Phase 2: cleanup (all nodes) ----------------
def clear_registry(node_url: str, timeout_s: float) -> Dict[str, Any]:
    url = f"{node_url}/federators"
    sc, body = delete_json(url, timeout_s)
    ok = (sc < 400) and isinstance(body, dict) and (body.get("status") == "ok")
    return {"status": sc, "ok": ok, "body": body}

# ---------------- Orchestration ----------------
def run_once(nodes: int, consumers: int, scheme: str, subnet: str, port: int,
             timeout_s: float, export_csv: bool, csv_base: str, run_idx: int) -> None:
    assert 1 <= nodes
    assert 0 <= consumers <= nodes

    # Build URLs
    urls = [f"{scheme}://{subnet}{i}:{port}" for i in range(1, nodes + 1)]
    consumer_urls = urls[:consumers]
    provider_urls = urls[consumers:]

    print(f"[plan] consumers={len(consumer_urls)} providers={len(provider_urls)}")
    if not provider_urls:
        print("⚠ No providers. Skipping Phase 1 (autoRegister).")

    # Phase 1: consumers call autoRegister in parallel
    auto_ok = 0
    if provider_urls:
        with ThreadPoolExecutor(max_workers=max(1, len(consumer_urls))) as pool:
            futs = {}
            for idx, c_url in enumerate(consumer_urls, start=1):
                csv_path = f"{csv_base}/auto_register_consumer_{idx}_run_{run_idx}.csv"
                fut = pool.submit(auto_register_on_consumer, c_url, provider_urls, timeout_s, export_csv, csv_path)
                futs[fut] = c_url

            for fut in as_completed(futs):
                c_url = futs[fut]
                try:
                    res = fut.result()
                    ok = res.get("ok", False)
                    auto_ok += int(ok)
                    body = res.get("body", {})
                    reg = body.get("registered", "?")
                    tot = body.get("total", "?")
                    print(f"[autoRegister] {c_url} → {'✓' if ok else '✗'} (registered {reg}/{tot})")
                except Exception as e:
                    print(f"[autoRegister] {c_url} → ✗ exception: {e}")

        print(f"[run {run_idx}] autoRegister ok: {auto_ok}/{len(consumer_urls)}")

    time.sleep(2)
    
    # Phase 2: cleanup on all nodes
    clr_ok = 0
    with ThreadPoolExecutor(max_workers=max(1, len(urls))) as pool:
        futs = {pool.submit(clear_registry, u, timeout_s): u for u in urls}
        for fut in as_completed(futs):
            u = futs[fut]
            try:
                res = fut.result()
                ok = res.get("ok", False)
                clr_ok += int(ok)
                body = res.get("body", {})
                cleared = body.get("cleared", "?")
                print(f"[cleanup] {u}/federators → {'✓' if ok else '✗'} (cleared={cleared})")
            except Exception as e:
                print(f"[cleanup] {u} → ✗ exception: {e}")

    print(f"[run {run_idx}] cleanup ok: {clr_ok}/{len(urls)}")

# ---------------- CLI ----------------
def parse_args():
    p = argparse.ArgumentParser(description="SoA registration experiments runner (autoRegister + cleanup).")
    p.add_argument("-n", "--nodes", type=int, required=True, help="Total participants (1..N)")
    p.add_argument("-c", "--consumers", type=int, required=True, help="Number of consumers (first -c nodes)")
    p.add_argument("-t", "--tests", type=int, required=True, help="Number of repetitions")
    p.add_argument("--scheme", default=DEFAULT_SCHEME, choices=["http", "https"], help="URL scheme (default http)")
    p.add_argument("--subnet", default=DEFAULT_SUBNET, help=f"IP prefix (default {DEFAULT_SUBNET})")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Shared MEF port (default {DEFAULT_PORT})")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help=f"HTTP timeout seconds (default {DEFAULT_TIMEOUT})")
    p.add_argument("--export-csv", action="store_true", default=False, help="Ask MEFs to export CSVs")
    p.add_argument("--csv-base", default="/experiments/test", help="Remote CSV base path")
    return p.parse_args()

def main():
    args = parse_args()
    if args.nodes < 1:
        print("Error: --nodes must be >= 1"); return 2
    if args.consumers < 0 or args.consumers > args.nodes:
        print("Error: --consumers must be between 0 and --nodes"); return 2
    if args.tests < 1:
        print("Error: --tests must be >= 1"); return 2

    print(f"CSV base: {args.csv_base} | export_csv={args.export_csv}")

    for i in range(1, args.tests + 1):
        print(f"\n=== Run {i}/{args.tests} | nodes={args.nodes} | consumers={args.consumers} ===")
        run_once(args.nodes, args.consumers, args.scheme, args.subnet, args.port,
                 args.timeout, args.export_csv, args.csv_base, i)
        if i < args.tests and PAUSE_BETWEEN_RUNS > 0:
            print(f"Waiting {PAUSE_BETWEEN_RUNS}s before next run...")
            time.sleep(PAUSE_BETWEEN_RUNS)

    print("\nAll experiments completed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

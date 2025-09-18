#!/usr/bin/env python3
import argparse
import requests
from typing import List, Tuple

DEFAULT_SUBNET = "10.5.99."
DEFAULT_SCHEME = "http"
DEFAULT_PORT = 8000

def auto_register(consumer_url: str,
                  providers: List[str],
                  timeout_s: float,
                  export_to_csv: bool,
                  csv_path: str) -> Tuple[bool, str]:
    url = f"{consumer_url}/federators/autoRegister"
    payload = {
        "providers": providers,
        "self_url": consumer_url,
        "timeout_s": timeout_s,
        "export_to_csv": export_to_csv,
        "csv_path": csv_path,
    }
    try:
        r = requests.post(url, json=payload, timeout=timeout_s + 2)
        r.raise_for_status()
        body = r.json()
        reg = body.get("registered", 0)
        total = body.get("total", 0)
        return True, f"registered {reg}/{total}"
    except Exception as e:
        return False, f"error: {e}"

def main():
    p = argparse.ArgumentParser(
        description="Register federation participants using /federators/autoRegister (single shared port)."
    )
    p.add_argument("-n", "--nodes", type=int, required=True,
                   help="Total participants (consumers + providers)")
    p.add_argument("-c", "--consumers", type=int, required=True,
                   help="Number of consumers (first -c nodes are consumers)")
    p.add_argument("--subnet", default=DEFAULT_SUBNET,
                   help=f"IP prefix (default {DEFAULT_SUBNET})")
    p.add_argument("--scheme", default=DEFAULT_SCHEME, choices=["http", "https"],
                   help="URL scheme (default http)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"MEF port for ALL nodes (default {DEFAULT_PORT})")
    p.add_argument("--timeout", type=float, default=5.0,
                   help="Per-request timeout seconds (default 5.0)")
    p.add_argument("--export-csv", action="store_true", default=False,
                   help="Ask remote MEFs to export CSVs")
    p.add_argument("--csv-base", default="/experiments/test",
                   help="Base path for CSVs on remote hosts (default /experiments/test)")
    args = p.parse_args()

    if args.nodes < 1:
        print("✗ --nodes must be >= 1"); return
    if args.consumers < 0 or args.consumers > args.nodes:
        print("✗ --consumers must be between 0 and --nodes"); return

    # Build provider base URLs (after the first C nodes), same port for all.
    providers = []
    for i in range(args.consumers + 1, args.nodes + 1):
        host = f"{args.subnet}{i}"
        providers.append(f"{args.scheme}://{host}:{args.port}")

    if not providers:
        print("⚠ No providers to register against (consumers == nodes). Nothing to do.")
        return

    total_consumers = args.consumers
    ok_count = 0

    for i in range(1, total_consumers + 1):
        host = f"{args.subnet}{i}"
        consumer_url = f"{args.scheme}://{host}:{args.port}"
        consumer_id = f"consumer_{i}"
        csv_path = f"{args.csv_base}/auto_register_{consumer_id}.csv"

        print(f"[{consumer_id} @ {consumer_url}] → POST /federators/autoRegister "
              f"with {len(providers)} providers")
        ok, msg = auto_register(
            consumer_url=consumer_url,
            providers=providers,
            timeout_s=args.timeout,
            export_to_csv=args.export_csv,
            csv_path=csv_path,
        )
        print(("  ✓ " if ok else "  ✗ ") + msg)
        ok_count += int(ok)

    print(f"\nDone: {ok_count}/{total_consumers} consumers registered with providers.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import argparse
import requests

DEFAULT_SUBNET = "10.5.99."
DEFAULT_PORT = 8000

def unregister(host: str, port: int, timeout: float = 10.0):
    url = f"http://{host}:{port}/federators"
    try:
        r = requests.delete(url, timeout=timeout)
        # Best-effort JSON parse
        data = {}
        if r.headers.get("content-type", "").startswith("application/json"):
            try:
                data = r.json()
            except Exception:
                pass
        ok = r.ok and (data.get("status") == "ok")
        cleared = data.get("cleared", None)
        msg = f"cleared={cleared}" if cleared is not None else (r.text.strip() or "ok" if ok else "error")
        return ok, msg
    except Exception as e:
        return False, f"exception: {e}"

def main():
    p = argparse.ArgumentParser(description="Unregister peers on hosts 1..N via DELETE /federators.")
    p.add_argument("-n", "--nodes", type=int, required=True, help="Number of hosts (1..N)")
    p.add_argument("--subnet", default=DEFAULT_SUBNET, help=f"IP prefix (default {DEFAULT_SUBNET})")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"MEF port (default {DEFAULT_PORT})")
    p.add_argument("--timeout", type=float, default=8.0, help="HTTP timeout seconds per host")
    args = p.parse_args()

    ok_count = 0
    for i in range(1, args.nodes + 1):
        host = f"{args.subnet}{i}"
        print(f"[{host}] DELETE /federators")
        ok, msg = unregister(host, args.port, args.timeout)
        print(("  ✓ " if ok else "  ✗ ") + msg)
        ok_count += int(ok)

    print(f"Done: {ok_count}/{args.nodes} unregistered.")

if __name__ == "__main__":
    main()

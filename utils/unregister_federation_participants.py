#!/usr/bin/env python3
import argparse, requests

SUBNET_PREFIX = "10.5.99."
PORT = 8000

def unregister(host, port, timeout=10):
    url = f"http://{host}:{port}/unregister_domain"
    try:
        r = requests.delete(url, timeout=timeout)
        data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
        ok = r.ok and data.get("success", True)
        msg = data.get("message", r.text.strip())
        return ok, msg
    except Exception as e:
        return False, str(e)

def main():
    p = argparse.ArgumentParser(description="Unregister domains on hosts 1..N")
    p.add_argument("-n","--nodes", type=int, required=True)
    args = p.parse_args()

    ok_count = 0
    for i in range(1, args.nodes + 1):
        host = f"{SUBNET_PREFIX}{i}"
        print(f"[{host}] DELETE /unregister_domain")
        ok, msg = unregister(host, PORT)
        print(("  ✓ " if ok else "  ✗ ") + (msg or ""))
        ok_count += int(ok)
    print(f"Done: {ok_count}/{args.nodes} unregistered.")

if __name__ == "__main__":
    main()

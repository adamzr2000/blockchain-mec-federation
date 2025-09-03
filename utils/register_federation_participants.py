#!/usr/bin/env python3
import argparse, requests

SUBNET_PREFIX = "10.5.99."
PORT = 8000
DOMAIN_PREFIX = "domain"

def register(host, port, name, timeout=10):
    url = f"http://{host}:{port}/register_domain/{name}"
    try:
        r = requests.post(url, timeout=timeout)
        data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
        ok = r.ok and (data.get("success", True))
        msg = data.get("message", r.text.strip())
        return ok, msg
    except Exception as e:
        return False, str(e)

def main():
    p = argparse.ArgumentParser(description="Register N participants via HTTP.")
    p.add_argument("-n", "--nodes", type=int, required=True, help="Number of participants (1..N)")
    p.add_argument("--subnet", default=SUBNET_PREFIX)
    p.add_argument("--port", type=int, default=PORT)
    p.add_argument("--prefix", default=DOMAIN_PREFIX)
    args = p.parse_args()

    success = 0
    for i in range(1, args.nodes + 1):
        host = f"{args.subnet}{i}"
        name = f"{args.prefix}{i}"
        print(f"[{host}] POST /register_domain/{name}")
        ok, msg = register(host, args.port, name)
        print(("  ✓ " if ok else "  ✗ ") + (msg or ""))
        success += int(ok)

    print(f"Done: {success}/{args.nodes} registered.")

if __name__ == "__main__":
    main()

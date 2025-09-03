#!/usr/bin/env python3
"""
Run 'git pull' over SSH on hosts 10.5.99.1..N (user 'netcom').

Usage:
  python ssh_git_pull.py -n 30
"""

from __future__ import annotations
import argparse
import concurrent.futures as cf
from dataclasses import dataclass
from fabric import Connection

# ---- simple constants (edit if needed) ----
USER = "netcom"
PREFIX = "10.5.99."
CMD = "cd /home/netcom/blockchain-mec-federation && git pull"
CONNECT_TIMEOUT = 20
MAX_WORKERS_DEFAULT = 10
# -------------------------------------------

@dataclass
class Result:
    host: str
    ok: bool
    exit_code: int | None
    err: str | None

def run_one(host: str) -> Result:
    print(f"[{host}] → {CMD}")
    try:
        with Connection(host=host, user=USER, connect_timeout=CONNECT_TIMEOUT) as c:
            r = c.run(CMD, hide=True, warn=True, pty=False)
            print(f"[{host}] ✓ exit {r.exited}" if r.ok else f"[{host}] ✗ exit {r.exited}")
            return Result(host, r.ok, r.exited, None if r.ok else "non-zero exit")
    except Exception as e:
        print(f"[{host}] exception: {e}")
        return Result(host, False, None, str(e))

def main() -> int:
    ap = argparse.ArgumentParser(description="SSH git pull on 10.5.99.1..N")
    ap.add_argument("-n", "--nodes", type=int, required=True, help="Number of nodes (1..254)")
    args = ap.parse_args()

    if not (1 <= args.nodes <= 254):
        print("Error: --nodes must be between 1 and 254")
        return 2

    hosts = [f"{PREFIX}{i}" for i in range(1, args.nodes + 1)]
    max_workers = min(MAX_WORKERS_DEFAULT, len(hosts))

    results: list[Result] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for res in cf.as_completed([pool.submit(run_one, h) for h in hosts]):
            results.append(res.result())

    ok = sum(1 for r in results if r.ok)
    fail = [r for r in results if not r.ok]

    print("\n=== Summary ===")
    print(f"Total: {len(results)} | OK: {ok} | Failed: {len(fail)}")
    for r in sorted(fail, key=lambda x: x.host):
        print(f"- {r.host}: {r.err or 'failed'} (exit={r.exit_code})")

    return 0 if not fail else 1

if __name__ == "__main__":
    raise SystemExit(main())

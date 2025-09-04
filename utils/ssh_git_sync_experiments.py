#!/usr/bin/env python3
"""
Sync ./experiments across hosts 10.5.99.1..N using git.
For each host:
  - cd /home/netcom/blockchain-mec-federation
  - ensure branch exists locally (fetch if missing)
  - checkout branch
  - fetch + pull --rebase --autostash (fail fast)
  - add ./experiments
  - commit if changed
  - push (retry with rebase on rejection)

Usage:
  python ssh_git_sync_experiments.py -n 30
"""

import argparse
import concurrent.futures as cf
from typing import NamedTuple, Optional
from fabric import Connection

# ------- constants (edit if needed) -------
USER = "netcom"
PREFIX = "10.5.99."
REPO_DIR = "/home/netcom/blockchain-mec-federation"
BRANCH = "main"
SUBPATH = "experiments"   # relative to REPO_DIR
CONNECT_TIMEOUT = 20
MAX_WORKERS_DEFAULT = 10
# ------------------------------------------

class Result(NamedTuple):
    host: str
    ok: bool
    exit_code: Optional[int]
    err: Optional[str]

REMOTE_SCRIPT = rf"""
set -euo pipefail
REPO="{REPO_DIR}"
BR="{BRANCH}"
SUB="{SUBPATH}"

cd "$REPO" || {{ echo "[sync] repo not found: $REPO"; exit 2; }}

# Ensure the branch exists locally; if not, fetch it explicitly
if ! git rev-parse --verify "$BR" >/dev/null 2>&1; then
  echo "[sync] local branch '$BR' missing, fetching from origin..."
  git fetch origin "$BR":"$BR" || {{ echo "[sync] fetch of '$BR' failed"; exit 3; }}
fi

# Checkout the branch
git checkout "$BR" || {{ echo "[sync] cannot checkout '$BR'"; exit 4; }}

# Update branch: fetch and rebase pull (fail fast)
git fetch origin "$BR" || {{ echo "[sync] fetch origin '$BR' failed"; exit 5; }}
git pull --rebase --autostash origin "$BR" || {{ echo "[sync] pull --rebase failed"; exit 6; }}

# Stage only the experiments dir if it exists
if [ -d "$SUB" ]; then
  git add -A "$SUB"
else
  echo "[sync] '$SUB' does not exist, nothing to add"
fi

# If nothing staged, exit cleanly
if git diff --cached --quiet; then
  echo "[sync] no changes under ./$SUB"
  exit 0
fi

STAMP="$(date -u +'%Y%m%dT%H%M%SZ')"
HOSTIP="$(hostname -I 2>/dev/null | awk '{{print $1}}')"
[ -z "$HOSTIP" ] && HOSTIP="$(hostname)"

git commit -m "experiments(${HOSTIP}): ${STAMP}" || {{ echo "[sync] commit failed"; exit 7; }}

# Push with bounded retry; on rejection, rebase on latest and retry
tries=0
while ! git push origin "$BR"; do
  tries=$((tries+1))
  if [ $tries -ge 5 ]; then
    echo "[sync] push failed after $tries attempts"
    exit 8
  fi
  echo "[sync] push rejected, rebasing and retrying ($tries)..."
  git pull --rebase --autostash origin "$BR" || {{ echo "[sync] rebase retry failed"; exit 9; }}
done

echo "[sync] push OK"
"""

def run_one(host: str) -> Result:
    print(f"[{host}] sync {REPO_DIR}/{SUBPATH} on {BRANCH}")
    try:
        with Connection(host=host, user=USER, connect_timeout=CONNECT_TIMEOUT) as c:
            r = c.run(REMOTE_SCRIPT, hide=True, warn=True, pty=False)
            last = r.stdout.strip().splitlines()[-1] if r.stdout else ""
            print(f"[{host}] {'✓' if r.ok else '✗'} exit={r.exited} {last}")
            return Result(host, r.ok, r.exited, None if r.ok else "non-zero exit")
    except Exception as e:
        print(f"[{host}] exception: {e}")
        return Result(host, False, None, str(e))

def main() -> int:
    ap = argparse.ArgumentParser(description="SSH git pull/add/commit/push on 10.5.99.1..N")
    ap.add_argument("-n", "--nodes", type=int, required=True, help="Number of nodes (1..254)")
    args = ap.parse_args()

    if not (1 <= args.nodes <= 254):
        print("Error: --nodes must be between 1 and 254")
        return 2

    hosts = [f"{PREFIX}{i}" for i in range(1, args.nodes + 1)]
    max_workers = min(MAX_WORKERS_DEFAULT, len(hosts))

    results = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
        for fut in cf.as_completed([pool.submit(run_one, h) for h in hosts]):
            results.append(fut.result())

    ok = sum(1 for r in results if r.ok)
    fail = [r for r in results if not r.ok]

    print("\n=== Summary ===")
    print(f"Total: {len(results)} | OK: {ok} | Failed: {len(fail)}")
    for r in sorted(fail, key=lambda x: x.host):
        print(f"- {r.host}: {r.err or 'failed'} (exit={r.exit_code})")

    return 0 if not fail else 1

if __name__ == "__main__":
    raise SystemExit(main())

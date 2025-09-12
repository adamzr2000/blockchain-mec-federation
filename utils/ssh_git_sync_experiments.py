#!/usr/bin/env python3
"""
Sequentially sync ./experiments on hosts 10.5.99.1..N.

For each host:
  - cd /home/netcom/blockchain-mec-federation
  - ensure branch exists locally (fetch if missing)
  - checkout branch
  - fetch + pull --rebase --autostash
  - git add -A ./experiments (if exists)
  - commit if there are staged changes
  - push
Then wait an optional delay and move to the next host.

Usage:
  python ssh_git_sync_experiments.py -n 10 --delay 0.5
"""

import argparse
import time
from typing import NamedTuple, Optional
from fabric import Connection

# ------- constants -------
USER = "netcom"
PREFIX = "10.5.99."
REPO_DIR = "/home/netcom/blockchain-mec-federation"
BRANCH = "main"
SUBPATH = "experiments"   # relative to REPO_DIR
CONNECT_TIMEOUT = 20
# -------------------------

class Result(NamedTuple):
    host: str
    ok: bool
    exit_code: Optional[int]
    err: Optional[str]

REMOTE_SCRIPT = f"""
set -euo pipefail

REPO="{REPO_DIR}"
BR="{BRANCH}"
SUB="{SUBPATH}"

cd "$REPO" || {{ echo "[sync] repo not found: $REPO"; exit 2; }}

# Make sure branch exists locally
if ! git rev-parse --verify "$BR" >/dev/null 2>&1; then
  echo "[sync] local branch '$BR' missing, fetching from origin..."
  git fetch origin "$BR":"$BR" || {{ echo "[sync] fetch of '$BR' failed"; exit 3; }}
fi

# Checkout + update branch
git checkout "$BR" || {{ echo "[sync] cannot checkout '$BR'"; exit 4; }}
git fetch origin "$BR" || {{ echo "[sync] fetch origin '$BR' failed"; exit 5; }}
git pull --rebase --autostash origin "$BR" || {{ echo "[sync] pull --rebase failed"; exit 6; }}

# Stage only experiments dir if present
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
HOSTIP="$(hostname -I 2>/dev/null | awk '{{print $1}}' || true)"
[ -z "$HOSTIP" ] && HOSTIP="$(hostname)"

# Note: double braces so Python doesn't eat them; shell sees ${{...}}
git commit -m "experiments(${{HOSTIP}}): ${{STAMP}}" || {{ echo "[sync] commit failed"; exit 7; }}
git push origin "$BR" || {{ echo "[sync] push failed"; exit 8; }}

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
    ap = argparse.ArgumentParser(description="Sequential SSH sync of experiments on 10.5.99.1..N")
    ap.add_argument("-n", "--nodes", type=int, required=True, help="Number of nodes (1..254)")
    ap.add_argument("--delay", type=float, default=2.0, help="Seconds to sleep between hosts")
    args = ap.parse_args()

    if not (1 <= args.nodes <= 254):
        print("Error: --nodes must be between 1 and 254")
        return 2

    results = []
    for i in range(1, args.nodes + 1):
        host = f"{PREFIX}{i}"
        results.append(run_one(host))
        if i < args.nodes and args.delay > 0:
            time.sleep(args.delay)

    ok = sum(1 for r in results if r.ok)
    fail = [r for r in results if not r.ok]

    print("\n=== Summary ===")
    print(f"Total: {len(results)} | OK: {ok} | Failed: {len(fail)}")
    for r in fail:
        print(f"- {r.host}: {r.err or 'failed'} (exit={r.exit_code})")

    return 0 if not fail else 1

if __name__ == "__main__":
    raise SystemExit(main())

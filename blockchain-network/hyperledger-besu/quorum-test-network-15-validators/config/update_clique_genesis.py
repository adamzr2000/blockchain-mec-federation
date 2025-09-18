#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
from typing import Optional, List  # 3.6–3.9 compatible

GENESIS_PATH = "besu/CLIQUEgenesis.json"
PREFUND_BALANCE = "1000000000000000000000000000"  # 1e27 wei

def build_extradata(validators_no0x: List[str]) -> str:
    # 32-byte vanity + concatenated signer addresses (no 0x) + 65-byte padding
    vanity = "0x" + "00" * 32
    signers = "".join(validators_no0x)
    padding = "00" * 65
    return vanity + signers + padding

def read_validator_address(vdir: Path) -> Optional[str]:
    """Address used in Clique extraData (from nodes/*/address). Returns hex without 0x."""
    p = vdir / "address"
    if not p.exists():
        print(f"⚠️  Missing {p}")
        return None
    raw = p.read_text().strip()
    h = raw[2:] if raw.startswith("0x") else raw
    h = h.lower()
    if len(h) != 40 or any(c not in "0123456789abcdef" for c in h):
        print(f"⚠️  Invalid validator address in {p}: {raw}")
        return None
    return h  # no 0x

def read_keystore_address(vdir: Path) -> Optional[str]:
    """EOA to prefund in alloc (from nodes/*/accountKeystore). Returns 0x-prefixed."""
    p = vdir / "accountKeystore"
    if not p.exists():
        print(f"⚠️  Missing {p}")
        return None
    try:
        data = json.loads(p.read_text())
        raw = str(data.get("address", "")).strip()
        h = raw[2:] if raw.startswith("0x") else raw
        h = h.lower()
        if len(h) != 40 or any(c not in "0123456789abcdef" for c in h):
            print(f"⚠️  Invalid keystore address in {p}: {raw}")
            return None
        return "0x" + h
    except Exception as e:
        print(f"⚠️  Failed to parse {p}: {e}")
        return None

def main():
    # Load current genesis
    if not os.path.exists(GENESIS_PATH):
        print(f"❌ Genesis file not found at {GENESIS_PATH}")
        sys.exit(1)
    with open(GENESIS_PATH, "r") as f:
        genesis = json.load(f)

    # Optional arg: limit number of validators (validator1..N)
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            print("❌ Usage: python3 update_clique_genesis.py [NUM_VALIDATORS]")
            sys.exit(1)

    base_dir = Path("nodes")
    vdirs = sorted(
        [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("validator")],
        key=lambda d: int(d.name.replace("validator", ""))
    )
    if limit:
        vdirs = vdirs[:limit]
    if not vdirs:
        print("❌ No validator directories found in ./nodes/")
        sys.exit(1)

    # Ensure alloc exists
    if "alloc" not in genesis or not isinstance(genesis["alloc"], dict):
        genesis["alloc"] = {}

    signer_addrs_no0x = []     # for extraData
    prefund_addrs_with0x = []  # for alloc

    for vd in vdirs:
        signer = read_validator_address(vd)    # no 0x
        eoa = read_keystore_address(vd)        # with 0x
        if signer:
            signer_addrs_no0x.append(signer)
        if eoa:
            prefund_addrs_with0x.append(eoa)
            if eoa not in genesis["alloc"]:
                genesis["alloc"][eoa] = {"balance": PREFUND_BALANCE}

    if not signer_addrs_no0x:
        print("❌ No valid signer addresses collected for extraData.")
        sys.exit(1)

    # Update extraData
    genesis["extraData"] = build_extradata(signer_addrs_no0x)

    # Save
    with open(GENESIS_PATH, "w") as f:
        json.dump(genesis, f, indent=2)

    # Report
    print(f"✅ Updated Clique genesis at {GENESIS_PATH}")
    print("Signers in extraData:")
    for s in signer_addrs_no0x:
        print(" ", "0x" + s)
    if prefund_addrs_with0x:
        print("Prefunded EOAs from accountKeystore:")
        for a in prefund_addrs_with0x:
            print(" ", a)

if __name__ == "__main__":
    main()

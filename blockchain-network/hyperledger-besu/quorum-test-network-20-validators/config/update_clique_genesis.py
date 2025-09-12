#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

GENESIS_PATH = "besu/CLIQUEgenesis.json"

def build_extradata(validators):
    vanity = "0x" + "00" * 32
    signers = "".join(validators)  # already 40-char hex without 0x
    padding = "00" * 65
    return vanity + signers + padding

def main():
    # Load existing genesis
    if not os.path.exists(GENESIS_PATH):
        print(f"❌ Genesis file not found at {GENESIS_PATH}")
        sys.exit(1)

    with open(GENESIS_PATH, "r") as f:
        genesis = json.load(f)

    # Optional argument: number of validators
    num_validators = None
    if len(sys.argv) > 1:
        try:
            num_validators = int(sys.argv[1])
        except ValueError:
            print("❌ Usage: python3 update_clique_genesis.py [NUM_VALIDATORS]")
            sys.exit(1)

    base_dir = Path("nodes")
    validator_dirs = sorted(
        [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("validator")],
        key=lambda d: int(d.name.replace("validator", ""))
    )

    if num_validators:
        validator_dirs = validator_dirs[:num_validators]

    if not validator_dirs:
        print("❌ No validator directories found in ./nodes/")
        sys.exit(1)

    validators_for_extradata = []
    validators_for_alloc = []

    for vd in validator_dirs:
        address_file = vd / "address"
        if not address_file.exists():
            continue
        addr_raw = address_file.read_text().strip()

        # normalize
        if addr_raw.startswith("0x"):
            addr_noprefix = addr_raw[2:].lower()
        else:
            addr_noprefix = addr_raw.lower()

        if len(addr_noprefix) != 40:
            print(f"⚠️ Skipping invalid address in {vd}: {addr_raw}")
            continue

        # for extradata (no 0x)
        validators_for_extradata.append(addr_noprefix)

        # for alloc (with 0x)
        addr_with_prefix = "0x" + addr_noprefix
        validators_for_alloc.append(addr_with_prefix)

        # ensure prefunded
        if addr_with_prefix not in genesis["alloc"]:
            genesis["alloc"][addr_with_prefix] = {
                "balance": "1000000000000000000000000000"  # 1e27 wei
            }

    # Update extradata
    genesis["extraData"] = build_extradata(validators_for_extradata)

    # Save back
    with open(GENESIS_PATH, "w") as f:
        json.dump(genesis, f, indent=2)

    print(f"✅ Updated Clique genesis at {GENESIS_PATH}")
    print("Included validators:")
    for v in validators_for_alloc:
        print(" ", v)

if __name__ == "__main__":
    main()

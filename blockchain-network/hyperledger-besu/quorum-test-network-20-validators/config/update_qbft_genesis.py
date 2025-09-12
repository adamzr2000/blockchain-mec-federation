#!/usr/bin/env python3
import json
import glob
import os
import re
import sys

GENESIS_PATH = "besu/QBFTgenesis.json"
VALIDATOR_GLOB = "nodes/validator*/address"
BALANCE_FOR_VALIDATORS = "1000000000000000000000000000"  # 1e24 (like your base genesis)

# ---------- Minimal RLP encoding ----------
def int_to_min_bytes(x: int) -> bytes:
    if x == 0:
        return b""
    s = []
    while x:
        s.append(x & 0xff)
        x >>= 8
    return bytes(reversed(s))

def rlp_encode(item):
    if isinstance(item, list):
        payload = b"".join(rlp_encode(x) for x in item)
        if len(payload) <= 55:
            return bytes([0xc0 + len(payload)]) + payload
        else:
            l = int_to_min_bytes(len(payload))
            return bytes([0xf7 + len(l)]) + l + payload
    elif isinstance(item, int):
        if item == 0:
            return b"\x80"  # RLP integer zero = empty string
        bts = int_to_min_bytes(item)
        return rlp_encode(bts)
    elif isinstance(item, (bytes, bytearray)):
        bts = bytes(item)
        if len(bts) == 1 and bts[0] < 0x80:
            return bts
        if len(bts) <= 55:
            return bytes([0x80 + len(bts)]) + bts
        l = int_to_min_bytes(len(bts))
        return bytes([0xb7 + len(l)]) + l + bts
    elif isinstance(item, str):
        # treat hex string as raw bytes if it looks like hex, else utf-8
        hs = item.lower()
        if hs.startswith("0x"):
            hs = hs[2:]
        if re.fullmatch(r"[0-9a-f]*", hs) and len(hs) % 2 == 0:
            return rlp_encode(bytes.fromhex(hs))
        return rlp_encode(item.encode("utf-8"))
    else:
        raise TypeError(f"Unsupported RLP type: {type(item)}")

# ---------- Helpers ----------
def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def normalize_hex_addr(s: str) -> str:
    s = s.strip()
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    s = s.lower()
    if len(s) != 40 or not re.fullmatch(r"[0-9a-f]{40}", s):
        raise ValueError(f"Invalid hex address (need 40 hex chars): {s}")
    return s

def find_validator_dirs_sorted():
    files = glob.glob(VALIDATOR_GLOB)
    pairs = []
    for f in files:
        m = re.search(r"validator(\d+)/address$", f.replace("\\", "/"))
        if not m:
            continue
        idx = int(m.group(1))
        pairs.append((idx, f))
    pairs.sort(key=lambda x: x[0])
    return [f for _, f in pairs]

def load_validator_node_addresses(n):
    addrs = []
    paths = find_validator_dirs_sorted()
    if n > len(paths):
        raise RuntimeError(f"Requested {n} validators but found only {len(paths)}.")
    for p in paths[:n]:
        raw = read_file(p).replace("\n", "").replace("\r", "")
        addrs.append(normalize_hex_addr(raw))
    return addrs

def load_validator_account_address(validator_dir):
    # Read V3 keystore and pick the "address" field
    keystore_path = os.path.join(validator_dir, "accountKeystore")
    with open(keystore_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    acc = data.get("address")
    if not acc:
        raise RuntimeError(f"No 'address' in {keystore_path}")
    return "0x" + normalize_hex_addr(acc)

def update_alloc_for_validators(genesis_obj, validator_count):
    alloc = genesis_obj.setdefault("alloc", {})
    # Map from address file to its validator dir
    paths = find_validator_dirs_sorted()[:validator_count]
    for addr_path in paths:
        vdir = os.path.dirname(addr_path)
        acc_addr = load_validator_account_address(vdir)
        if acc_addr not in alloc:
            alloc[acc_addr] = {"balance": BALANCE_FOR_VALIDATORS}
    return alloc

def build_qbft_extra_data(validator_addresses_hex_no0x):
    # vanity = 32 zero bytes
    vanity = b"\x00" * 32
    validators_bytes = [bytes.fromhex(a) for a in validator_addresses_hex_no0x]
    # Per QBFT genesis:
    # [ vanity(32), [validators...], votes(empty list), round(0), seals(empty list) ]
    rlp_obj = [vanity, validators_bytes, [], 0, []]
    return "0x" + rlp_encode(rlp_obj).hex()

def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print("Usage: python3 update_qbft_genesis.py <NUM_VALIDATORS>")
        sys.exit(1)
    n = int(sys.argv[1])
    if n <= 0:
        print("NUM_VALIDATORS must be > 0")
        sys.exit(1)

    # Load existing genesis (we keep everything else unchanged)
    with open(GENESIS_PATH, "r", encoding="utf-8") as f:
        genesis = json.load(f)

    # Collect validator list from nodes/validatorX/address
    validators = load_validator_node_addresses(n)

    # Build RLP extraData
    genesis["extraData"] = build_qbft_extra_data(validators)

    # Add validator account addresses to alloc (funding)
    update_alloc_for_validators(genesis, n)

    # Write back
    with open(GENESIS_PATH, "w", encoding="utf-8") as f:
        json.dump(genesis, f, indent=2)
        f.write("\n")

    print(f"✅ Updated QBFT genesis at {GENESIS_PATH}")
    print("Included validators:")
    for v in validators:
        print(f"  0x{v}")

if __name__ == "__main__":
    main()

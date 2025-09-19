#!/usr/bin/env python3
from __future__ import annotations
import csv
from pathlib import Path
from statistics import mean, median, stdev
from math import ceil
from typing import List, Dict, Tuple, Optional

ROOT = Path(".")
SOA_DIR = ROOT / "soa"
SUMMARY_DIR = ROOT / "_summary"
SUMMARY_OUT = SUMMARY_DIR / "summary_all.csv"

STEP_START = "auto_register_start"
STEP_DONE  = "auto_register_done"

def ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def parse_mec_count(dirname: str) -> Optional[int]:
    if dirname.endswith("-mecs"):
        try:
            return int(dirname.split("-mecs")[0])
        except ValueError:
            return None
    return None

def parse_consumer_run(filename: str) -> Optional[Tuple[int,int]]:
    # auto_register_consumer_3_run_14.csv
    name = filename.lower()
    if not (name.startswith("auto_register_consumer_") and "_run_" in name and name.endswith(".csv")):
        return None
    try:
        left = name.split("auto_register_consumer_", 1)[1]
        cid_str, run_part = left.split("_run_", 1)
        return int(cid_str), int(run_part[:-4])
    except Exception:
        return None

def percentile(values: List[float], q: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    k = max(1, ceil(q * len(xs)))
    return float(xs[k - 1])

def read_latency_ms(csv_path: Path) -> Optional[int]:
    start = None
    done = None
    try:
        with csv_path.open(newline="") as f:
            r = csv.reader(f)
            _ = next(r, None)  # header
            for row in r:
                if len(row) < 2: continue
                step, ts = row[0], row[1]
                if step == STEP_START:
                    try: start = int(ts)
                    except: pass
                elif step == STEP_DONE:
                    try: done = int(ts)
                    except: pass
                if start is not None and done is not None:
                    break
    except Exception:
        return None
    if done is None: return None
    if start is None: return done
    return max(0, done - start)

def collect_latencies_by_consumer() -> Dict[int, Dict[int, List[int]]]:
    """
    Returns: latencies[mec_count][consumer_id] = [ms, ...]
    """
    latencies: Dict[int, Dict[int, List[int]]] = {}
    if not SOA_DIR.is_dir():
        return latencies

    for mec_dir in sorted(p for p in SOA_DIR.iterdir() if p.is_dir()):
        mec_count = parse_mec_count(mec_dir.name)
        if mec_count is None:
            continue
        for csv_path in sorted(mec_dir.glob("*.csv")):
            ids = parse_consumer_run(csv_path.name)
            if ids is None:
                continue
            consumer_id, _run_id = ids
            ms = read_latency_ms(csv_path)
            if ms is None:
                continue
            latencies.setdefault(mec_count, {}).setdefault(consumer_id, []).append(ms)
    return latencies

def append_summary(latencies: Dict[int, Dict[int, List[int]]]) -> None:
    ensure_dir(SUMMARY_OUT)
    write_header = not SUMMARY_OUT.exists()
    with SUMMARY_OUT.open("a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "consensus","mec_count","n_samples","n_runs_total",
                "mean_ms","std_ms","min_ms","p50_ms","p95_ms","max_ms",
                "p25_ms","p75_ms","aggregation"
            ])
        for mec_count in sorted(latencies.keys()):
            per_cons = latencies[mec_count]
            if not per_cons:
                continue
            # per-consumer medians (equal weight per consumer)
            medians = [median(vals) for vals in per_cons.values() if vals]
            if not medians:
                continue
            n_samples = len(medians)
            n_runs_total = sum(len(v) for v in per_cons.values())
            mu = mean(medians)
            sd = stdev(medians) if n_samples > 1 else 0.0
            mn = min(medians); md = median(medians)
            p25 = percentile(medians, 0.25); p75 = percentile(medians, 0.75); p95 = percentile(medians, 0.95)
            mx = max(medians)
            w.writerow([
                "soa", mec_count, n_samples, n_runs_total,
                f"{mu:.2f}", f"{sd:.2f}",
                f"{mn:.2f}", f"{md:.2f}", f"{p95:.2f}", f"{mx:.2f}",
                f"{p25:.2f}", f"{p75:.2f}", "per_consumer_median"
            ])

def main() -> int:
    lat = collect_latencies_by_consumer()
    if not lat:
        print("No SOA CSVs found under soa/*-mecs/*.csv")
        return 1
    append_summary(lat)
    print(f"Appended SOA rows to {SUMMARY_OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

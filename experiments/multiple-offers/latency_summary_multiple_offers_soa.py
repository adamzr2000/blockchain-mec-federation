#!/usr/bin/env python3
"""
soa_latency_summary_simple.py
Run from: experiments/multiple-offers/

Scans:  ./soa/*-mecs/consumer_*_run_*.csv
Metric: total_ms = connection_test_success - service_announced

Writes ONE file (does not touch any existing summaries):
  ./_summary/soa_latency_summary.csv

Aggregation is per mec_count (e.g., 4-mecs, 10-mecs):
  consensus=soa, mec_count, n_samples, mean, std, median, p25, p75, p95, min, max
"""

from __future__ import annotations
import csv
from pathlib import Path
from statistics import mean, median, stdev
from math import ceil
from typing import Dict, List, Optional

ROOT = Path(".")
SOA_DIR = ROOT / "soa"
OUT_DIR = ROOT / "_summary"
OUT_FILE = OUT_DIR / "soa_latency_summary.csv"

STEP_START = "service_announced"
STEP_END   = "connection_test_success"

def ensure_out_dir() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

def parse_mec_count(dirname: str) -> Optional[int]:
    # "<N>-mecs" -> N
    if not dirname.endswith("-mecs"):
        return None
    try:
        return int(dirname.split("-mecs")[0])
    except ValueError:
        return None

def read_total_ms(path: Path) -> Optional[int]:
    """
    Return END - START in ms, or None if either is missing.
    """
    start = None
    end = None
    try:
        with path.open(newline="") as f:
            r = csv.reader(f)
            _ = next(r, None)  # header
            for row in r:
                if len(row) < 2:
                    continue
                step, ts = row[0], row[1]
                if step == STEP_START:
                    try: start = int(ts)
                    except: pass
                elif step == STEP_END:
                    try: end = int(ts)
                    except: pass
                if start is not None and end is not None:
                    break
    except Exception:
        return None

    if start is None or end is None:
        return None
    return max(0, end - start)

def percentile(values: List[float], q: float) -> float:
    xs = [float(v) for v in values]
    if not xs:
        return float("nan")
    xs.sort()
    k = max(1, ceil(q * len(xs)))
    return xs[k - 1]

def format_num(x: float) -> str:
    return "" if x != x else f"{x:.2f}"  # NaN check

def main() -> int:
    if not SOA_DIR.is_dir():
        print("No 'soa' directory found. Run from experiments/multiple-offers/.")
        return 1

    # Collect durations per mec_count
    by_mec: Dict[int, List[int]] = {}
    scanned = 0
    for mec_dir in sorted(p for p in SOA_DIR.iterdir() if p.is_dir()):
        mec_count = parse_mec_count(mec_dir.name)
        if mec_count is None:
            continue
        for csv_path in mec_dir.glob("consumer_*_run_*.csv"):
            scanned += 1
            ms = read_total_ms(csv_path)
            if ms is not None:
                by_mec.setdefault(mec_count, []).append(ms)

    if not by_mec:
        print("No valid consumer CSVs with both steps found.")
        return 1

    ensure_out_dir()
    with OUT_FILE.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "consensus","mec_count","n_samples",
            "mean_ms","std_ms","median_ms","p25_ms","p75_ms","p95_ms","min_ms","max_ms"
        ])

        for mec_count in sorted(by_mec.keys()):
            vals = by_mec[mec_count]
            n = len(vals)
            mu = mean(vals)
            sd = stdev(vals) if n > 1 else 0.0
            md = median(vals)
            p25 = percentile(vals, 0.25)
            p75 = percentile(vals, 0.75)
            p95 = percentile(vals, 0.95)
            mn = min(vals)
            mx = max(vals)

            w.writerow([
                "soa", mec_count, n,
                format_num(mu), format_num(sd), format_num(md),
                format_num(p25), format_num(p75), format_num(p95),
                format_num(mn), format_num(mx),
            ])

    print(f"Wrote {OUT_FILE} (scanned {scanned} files).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

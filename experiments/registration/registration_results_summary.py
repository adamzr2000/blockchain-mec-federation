#!/usr/bin/env python3
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, stdev
from math import ceil
from typing import List, Dict, Tuple, Optional

ROOT = Path(".")
CONSENSUS_DIRS = ("clique", "qbft")
SUMMARY_DIR = ROOT / "_summary"
RAW_OUT = SUMMARY_DIR / "raw_all.csv"
SUMMARY_OUT = SUMMARY_DIR / "summary_all.csv"
PER_MEC_OUT = SUMMARY_DIR / "per_mec_summary.csv"

STEP_SEND = "send_registration_transaction"
STEP_CONFIRM = "confirm_registration_transaction"

@dataclass
class Sample:
    consensus: str
    mec_count: int
    mec_id: int
    run_id: int
    ms: int
    file: str

def parse_mec_run(filename: str) -> Optional[Tuple[int,int]]:
    name = filename.lower()
    if not (name.startswith("mec_") and "_run_" in name and name.endswith(".csv")):
        return None
    try:
        left = name.split("mec_", 1)[1]
        mec_part, run_part = left.split("_run_", 1)
        mec_id = int(mec_part)
        run_id = int(run_part[:-4])  # strip .csv
        return mec_id, run_id
    except Exception:
        return None

def parse_mec_count(dirname: str) -> Optional[int]:
    try:
        if not dirname.endswith("-mecs"):
            return None
        return int(dirname.split("-mecs")[0])
    except Exception:
        return None

def percentile(values: List[float], q: float) -> float:
    if not values:
        return float("nan")
    xs = sorted(values)
    k = max(1, ceil(q * len(xs)))
    return float(xs[k - 1])

def read_latency_ms(csv_path: Path) -> Optional[int]:
    """
    Return confirm - send if both are present, else confirm, else None.
    """
    send = None
    confirm = None
    try:
        with csv_path.open(newline="") as f:
            reader = csv.reader(f)
            _ = next(reader, None)  # header
            for row in reader:
                if len(row) < 2:
                    continue
                step, ts = row[0], row[1]
                if step == STEP_SEND:
                    try:
                        send = int(ts)
                    except ValueError:
                        pass
                elif step == STEP_CONFIRM:
                    try:
                        confirm = int(ts)
                    except ValueError:
                        pass
                if send is not None and confirm is not None:
                    break
    except Exception:
        return None

    if confirm is None:
        return None
    if send is None:
        return confirm
    return max(0, confirm - send)

def collect_samples() -> List[Sample]:
    samples: List[Sample] = []
    skipped = 0

    for conc in CONSENSUS_DIRS:
        conc_dir = ROOT / conc
        if not conc_dir.is_dir():
            continue
        for mec_folder in sorted(p for p in conc_dir.iterdir() if p.is_dir() ):
            mec_count = parse_mec_count(mec_folder.name)
            if mec_count is None:
                continue
            for csv_path in sorted(mec_folder.glob("*.csv")):
                ids = parse_mec_run(csv_path.name)
                if ids is None:
                    continue
                mec_id, run_id = ids

                ms_val = read_latency_ms(csv_path)
                if ms_val is None:
                    skipped += 1
                    continue

                samples.append(Sample(
                    consensus=conc,
                    mec_count=mec_count,
                    mec_id=mec_id,
                    run_id=run_id,
                    ms=ms_val,
                    file=str(csv_path.relative_to(ROOT)),
                ))

    if skipped:
        print(f"Note: skipped {skipped} files with missing/invalid data.")
    return samples

def write_raw_csv(samples: List[Sample]) -> None:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    with RAW_OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["consensus","mec_count","mec_id","run_id","registration_time_ms","file"])
        for s in samples:
            w.writerow([s.consensus, s.mec_count, s.mec_id, s.run_id, s.ms, s.file])

def per_mec_groups(samples: List[Sample]) -> Dict[Tuple[str,int,int], List[int]]:
    """Group run-level latencies by (consensus, mec_count, mec_id)."""
    groups: Dict[Tuple[str,int,int], List[int]] = {}
    for s in samples:
        groups.setdefault((s.consensus, s.mec_count, s.mec_id), []).append(s.ms)
    return groups

def write_per_mec_summary(samples: List[Sample]) -> Dict[Tuple[str,int], Dict[int, Dict[str, float]]]:
    """
    Write one row per MEC with per-MEC stats; return a nested dict:
      per_mec[(consensus, mec_count)][mec_id] = {"n_runs": ..., "median": ..., ...}
    """
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    groups = per_mec_groups(samples)

    per_mec: Dict[Tuple[str,int], Dict[int, Dict[str, float]]] = {}

    with PER_MEC_OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "consensus","mec_count","mec_id","n_runs",
            "mean_ms","median_ms","std_ms","min_ms","p25_ms","p75_ms","p95_ms","max_ms"
        ])

        for (conc, count, mec_id), vals in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
            n = len(vals)
            mu = mean(vals) if n else float("nan")
            md = median(vals) if n else float("nan")
            sd = stdev(vals) if n > 1 else 0.0
            mn = min(vals) if n else float("nan")
            p25 = percentile(vals, 0.25) if n else float("nan")
            p75 = percentile(vals, 0.75) if n else float("nan")
            p95 = percentile(vals, 0.95) if n else float("nan")
            mx = max(vals) if n else float("nan")

            w.writerow([
                conc, count, mec_id, n,
                f"{mu:.2f}", f"{md:.2f}", f"{sd:.2f}", f"{mn:.2f}",
                f"{p25:.2f}", f"{p75:.2f}", f"{p95:.2f}", f"{mx:.2f}"
            ])

            per_mec.setdefault((conc, count), {})[mec_id] = {
                "n_runs": n,
                "median": md,
                "mean": mu,
                "std": sd,
                "min": mn,
                "p25": p25,
                "p75": p75,
                "p95": p95,
                "max": mx,
            }

    return per_mec

def write_summary_csv(samples: List[Sample]) -> None:
    """
    Paper-friendly aggregation:
      1) compute per-MEC medians (equal weight per MEC),
      2) summarize those per-MEC medians per (consensus, mec_count).
    """
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    per_mec = write_per_mec_summary(samples)  # also writes PER_MEC_OUT

    with SUMMARY_OUT.open("w", newline="") as f:
        w = csv.writer(f)
        # keep prior columns and add n_runs_total + aggregation
        w.writerow([
            "consensus","mec_count","n_samples","n_runs_total",
            "mean_ms","std_ms","min_ms","p50_ms","p95_ms","max_ms",
            "p25_ms","p75_ms","aggregation"
        ])

        # group by (consensus, mec_count) over per-MEC medians
        keys = sorted(set((conc, count) for (conc, count) in per_mec.keys()),
                      key=lambda x: (x[0], x[1]))
        for conc, count in keys:
            mec_stats = per_mec[(conc, count)]
            medians = [v["median"] for v in mec_stats.values()]
            n_mecs = len(medians)
            n_runs_total = sum(int(v["n_runs"]) for v in mec_stats.values())

            if n_mecs == 0:
                continue

            mu = mean(medians)
            sd = stdev(medians) if n_mecs > 1 else 0.0
            mn = min(medians)
            md = median(medians)
            p25 = percentile(medians, 0.25)
            p75 = percentile(medians, 0.75)
            p95 = percentile(medians, 0.95)
            mx = max(medians)

            w.writerow([
                conc, count, n_mecs, n_runs_total,
                f"{mu:.2f}", f"{sd:.2f}",
                f"{mn:.2f}", f"{md:.2f}", f"{p95:.2f}", f"{mx:.2f}",
                f"{p25:.2f}", f"{p75:.2f}", "per_mec_median"
            ])

def main() -> int:
    samples = collect_samples()
    if not samples:
        print("No samples found. Run from experiments/registration (or adjust ROOT).")
        return 1
    write_raw_csv(samples)
    write_summary_csv(samples)
    print(f"Wrote {RAW_OUT}, {PER_MEC_OUT} and {SUMMARY_OUT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
latency_summary_multiple_offers.py
Run from: experiments/multiple-offers/

Scans:
  ./clique/<N-mecs>/*.csv
  ./qbft/<N-mecs>/*.csv

Parses ONLY consumer/provider CSVs (ignores docker-logs/ and others).
Computes DURATIONS (ms) on each node's local clock.

Outputs to ./_summary/:

  1) consumer_per_service.csv  (one row per consumer service)
     consensus,mec_count,consumer_id,run_id,file,service_id,has_success,
     c_bid_collection_ms,c_winner_selection_ms,c_provider_deploy_ms,
     c_vxlan_setup_ms,c_postcheck_ms,c_total_ms

  2) consumer_summary.csv  (per consensus+mec_count; two aggregation variants)
     - rows with aggregation=per_service  : stats directly across all services
     - rows with aggregation=per_consumer_median: first median per consumer across runs, then stats across consumers
     Columns (per phase):
       <phase>_{n,mean_ms,std_ms,median_ms,p25_ms,p75_ms,p95_ms,min_ms,max_ms}
     phases: bid_collection, winner_selection, provider_deploy, vxlan_setup, postcheck, total

  3) provider_per_run.csv  (one row per provider run)
     consensus,mec_count,provider_id,run_id,file,won_any,
     p_announce_wait_ms,p_bid_sending_ms,p_winner_wait_ms,p_confirm_all_ms

  4) provider_summary.csv  (per consensus+mec_count; two aggregation variants)
     - rows with aggregation=per_run       : stats directly across runs
     - rows with aggregation=per_provider_median: first median per provider across runs, then stats across providers
     Columns (per phase):
       <phase>_{n,mean_ms,std_ms,median_ms,p25_ms,p75_ms,p95_ms,min_ms,max_ms}
     phases: announce_wait, bid_sending, winner_wait, confirm_all

  5) consumer_cdf.csv (tidy long-form for CDFs/boxplots)
     consensus,mec_count,consumer_id,run_id,service_id,phase,value_ms,has_success,aggregation
     (aggregation is always "per_service" here)

  6) provider_cdf.csv (tidy long-form for CDFs/boxplots)
     consensus,mec_count,provider_id,run_id,phase,value_ms,won_any,aggregation
     (aggregation is always "per_run" here)
"""

from __future__ import annotations
import csv
import re
from pathlib import Path
from statistics import mean, median, stdev
from math import ceil
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

ROOT = Path(".")
SUMMARY_DIR = ROOT / "_summary"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

CONSENSUS_DIRS = ("clique", "qbft")

# -------- parsing helpers --------

def parse_mec_count(dirname: str) -> Optional[int]:
    if not dirname.endswith("-mecs"):
        return None
    try:
        return int(dirname.split("-mecs")[0])
    except Exception:
        return None

re_consumer = re.compile(r"^(?:c)?consumer_(\d+)_run_(\d+)\.csv$", re.IGNORECASE)
re_provider = re.compile(r"^provider_(\d+)_run_(\d+)\.csv$", re.IGNORECASE)

def parse_consumer_ids(name: str) -> Optional[Tuple[int,int]]:
    m = re_consumer.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def parse_provider_ids(name: str) -> Optional[Tuple[int,int]]:
    m = re_provider.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))

def read_steps_csv(path: Path) -> Dict[str, int]:
    """Return step->timestamp_ms (int). Non-numeric rows are skipped."""
    steps: Dict[str, int] = {}
    try:
        with path.open(newline="") as f:
            rdr = csv.reader(f)
            _ = next(rdr, None)  # header
            for row in rdr:
                if len(row) < 2:
                    continue
                k, v = row[0], row[1]
                try:
                    ts = int(float(v))
                    steps[k] = ts
                except Exception:
                    pass  # e.g., service_id row
    except Exception:
        pass
    return steps

def read_service_id(path: Path) -> Optional[str]:
    try:
        with path.open(newline="") as f:
            rdr = csv.reader(f)
            _ = next(rdr, None)
            for row in rdr:
                if len(row) >= 2 and row[0] == "service_id":
                    return row[1]
    except Exception:
        pass
    return None

def delta(steps: Dict[str,int], a: str, b: str) -> Optional[int]:
    """Non-negative duration b-a in ms if both present, else None."""
    if a in steps and b in steps:
        return max(0, steps[b] - steps[a])
    return None

def percentile(values: List[int], q: float) -> Optional[float]:
    """Nearest-rank percentile (q in [0,1]) on a list of ints."""
    xs = [int(v) for v in values if isinstance(v, (int, float))]
    if not xs:
        return None
    xs.sort()
    k = max(1, ceil(q * len(xs)))
    return float(xs[k - 1])

# -------- provider announce wait helper (fix) --------

def provider_announce_wait_ms(steps: Dict[str,int]) -> Optional[int]:
    """First announce -> required_announces_received (non-negative)"""
    if "required_announces_received" not in steps:
        return None
    first_announce_ts = min(
        (ts for k, ts in steps.items() if k.startswith("announce_received_")),
        default=None
    )
    if first_announce_ts is None:
        return None
    return max(0, steps["required_announces_received"] - first_announce_ts)

# -------- collect consumers --------

CONSUMER_PHASES = [
    "c_bid_collection_ms",
    "c_winner_selection_ms",
    "c_provider_deploy_ms",
    "c_vxlan_setup_ms",
    "c_postcheck_ms",
    "c_total_ms",
]

def collect_consumers() -> List[Dict]:
    rows: List[Dict] = []
    for conc in CONSENSUS_DIRS:
        conc_dir = ROOT / conc
        if not conc_dir.exists():
            continue
        for mec_dir in sorted(p for p in conc_dir.iterdir() if p.is_dir()):
            mec_count = parse_mec_count(mec_dir.name)
            if mec_count is None:
                continue
            for p in sorted(mec_dir.glob("*.csv")):
                ids = parse_consumer_ids(p.name)
                if not ids:
                    continue
                cid, run_id = ids
                steps = read_steps_csv(p)
                if "service_announced" not in steps:
                    continue

                c_bid_collection   = delta(steps, "service_announced", "required_bids_received")
                c_winner_selection = delta(steps, "required_bids_received", "winner_choosen")
                c_provider_deploy  = delta(steps, "winner_choosen", "confirm_deployment_received")
                c_vxlan_setup      = delta(steps, "establish_vxlan_connection_with_provider_start",
                                           "establish_vxlan_connection_with_provider_finished")
                c_postcheck        = delta(steps, "establish_vxlan_connection_with_provider_finished",
                                           "connection_test_success")

                # total: announced -> last observed milestone (prefers success)
                last_key_order = [
                    "connection_test_success",
                    "establish_vxlan_connection_with_provider_finished",
                    "confirm_deployment_received",
                    "winner_choosen",
                ]
                last_ts = next((steps[k] for k in last_key_order if k in steps), None)
                c_total = (max(0, last_ts - steps["service_announced"]) if last_ts is not None else None)

                rows.append({
                    "consensus": conc,
                    "mec_count": mec_count,
                    "consumer_id": cid,
                    "run_id": run_id,
                    "file": str(p.relative_to(ROOT)),
                    "service_id": read_service_id(p) or "",
                    "has_success": 1 if "connection_test_success" in steps else 0,
                    "c_bid_collection_ms": c_bid_collection,
                    "c_winner_selection_ms": c_winner_selection,
                    "c_provider_deploy_ms": c_provider_deploy,
                    "c_vxlan_setup_ms": c_vxlan_setup,
                    "c_postcheck_ms": c_postcheck,
                    "c_total_ms": c_total,
                })
    return rows

# -------- collect providers --------

PROVIDER_PHASES = [
    "p_announce_wait_ms",
    "p_bid_sending_ms",
    "p_winner_wait_ms",
    "p_confirm_all_ms",
]

def collect_providers() -> List[Dict]:
    rows: List[Dict] = []
    for conc in CONSENSUS_DIRS:
        conc_dir = ROOT / conc
        if not conc_dir.exists():
            continue
        for mec_dir in sorted(p for p in conc_dir.iterdir() if p.is_dir()):
            mec_count = parse_mec_count(mec_dir.name)
            if mec_count is None:
                continue
            for p in sorted(mec_dir.glob("*.csv")):
                ids = parse_provider_ids(p.name)
                if not ids:
                    continue
                pid, run_id = ids
                steps = read_steps_csv(p)

                p_announce_wait = provider_announce_wait_ms(steps)  # FIXED: duration
                p_bid_sending   = delta(steps, "required_announces_received", "all_bid_offers_sent")
                p_winner_wait   = delta(steps, "all_bid_offers_sent", "all_winners_received")
                p_confirm_all   = delta(steps, "all_winners_received", "all_confirm_deployment_sent")

                won_any = 0 if ("no_wins" in steps) else 1

                rows.append({
                    "consensus": conc,
                    "mec_count": mec_count,
                    "provider_id": pid,
                    "run_id": run_id,
                    "file": str(p.relative_to(ROOT)),
                    "won_any": won_any,
                    "p_announce_wait_ms": p_announce_wait,
                    "p_bid_sending_ms": p_bid_sending,
                    "p_winner_wait_ms": p_winner_wait,
                    "p_confirm_all_ms": p_confirm_all,  # may be None if no wins
                })
    return rows

# -------- stats helpers --------

def summarize_list(xs: List[int]) -> Dict[str, object]:
    if not xs:
        return {"n": 0, "mean": "", "std": "", "median": "",
                "p25": "", "p75": "", "p95": "", "min": "", "max": ""}
    return {
        "n": len(xs),
        "mean": f"{mean(xs):.2f}",
        "std": f"{(stdev(xs) if len(xs) > 1 else 0.0):.2f}",
        "median": f"{median(xs):.2f}",
        "p25": f"{percentile(xs, 0.25):.2f}",
        "p75": f"{percentile(xs, 0.75):.2f}",
        "p95": f"{percentile(xs, 0.95):.2f}",
        "min": f"{min(xs):.2f}",
        "max": f"{max(xs):.2f}",
    }

def summarize_series(vals: List[Optional[int]]) -> Dict[str, object]:
    xs = [int(v) for v in vals if isinstance(v, (int, float))]
    return summarize_list(xs)

def write_csv(path: Path, header: List[str], rows: List[Dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})

# -------- long-form CDF writers --------

def write_consumer_cdf(consumer_rows: List[Dict]) -> None:
    out = SUMMARY_DIR / "consumer_cdf.csv"
    hdr = ["consensus","mec_count","consumer_id","run_id","service_id",
           "phase","value_ms","has_success","aggregation"]
    long_rows = []
    for r in consumer_rows:
        for ph in CONSUMER_PHASES:
            v = r.get(ph)
            if isinstance(v, (int, float)):
                long_rows.append({
                    "consensus": r["consensus"],
                    "mec_count": r["mec_count"],
                    "consumer_id": r["consumer_id"],
                    "run_id": r["run_id"],
                    "service_id": r.get("service_id",""),
                    "phase": ph.replace("c_","").replace("_ms",""),
                    "value_ms": int(v),
                    "has_success": r.get("has_success", 0),
                    "aggregation": "per_service",
                })
    write_csv(out, hdr, long_rows)

def write_provider_cdf(provider_rows: List[Dict]) -> None:
    out = SUMMARY_DIR / "provider_cdf.csv"
    hdr = ["consensus","mec_count","provider_id","run_id",
           "phase","value_ms","won_any","aggregation"]
    long_rows = []
    for r in provider_rows:
        for ph in PROVIDER_PHASES:
            v = r.get(ph)
            if isinstance(v, (int, float)):
                long_rows.append({
                    "consensus": r["consensus"],
                    "mec_count": r["mec_count"],
                    "provider_id": r["provider_id"],
                    "run_id": r["run_id"],
                    "phase": ph.replace("p_","").replace("_ms",""),
                    "value_ms": int(v),
                    "won_any": r.get("won_any", 0),
                    "aggregation": "per_run",
                })
    write_csv(out, hdr, long_rows)

# -------- outputs --------

def make_consumer_outputs(consumer_rows: List[Dict]) -> None:
    # per-service (raw rows for CDF/boxplots)
    per_service_hdr = [
        "consensus","mec_count","consumer_id","run_id","file","service_id","has_success",
        "c_bid_collection_ms","c_winner_selection_ms","c_provider_deploy_ms",
        "c_vxlan_setup_ms","c_postcheck_ms","c_total_ms",
    ]
    write_csv(SUMMARY_DIR / "consumer_per_service.csv", per_service_hdr, consumer_rows)
    write_consumer_cdf(consumer_rows)

    # --- aggregation A: per_service (legacy, direct across services)
    groups: Dict[Tuple[str,int], List[Dict]] = {}
    for r in consumer_rows:
        groups.setdefault((r["consensus"], r["mec_count"]), []).append(r)

    summary_rows = []
    for (conc, mec_count), rs in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
        row = {"consensus": conc, "mec_count": mec_count, "n_services": len(rs), "aggregation": "per_service"}
        phases = {
            "bid_collection":   [r["c_bid_collection_ms"] for r in rs],
            "winner_selection": [r["c_winner_selection_ms"] for r in rs],
            "provider_deploy":  [r["c_provider_deploy_ms"] for r in rs],
            "vxlan_setup":      [r["c_vxlan_setup_ms"] for r in rs],
            "postcheck":        [r["c_postcheck_ms"] for r in rs],
            "total":            [r["c_total_ms"] for r in rs],
        }
        for ph, vals in phases.items():
            st = summarize_series(vals)
            row.update({
                f"{ph}_n": st["n"],
                f"{ph}_mean_ms": st["mean"],
                f"{ph}_std_ms": st["std"],
                f"{ph}_median_ms": st["median"],
                f"{ph}_p25_ms": st["p25"],
                f"{ph}_p75_ms": st["p75"],
                f"{ph}_p95_ms": st["p95"],
                f"{ph}_min_ms": st["min"],
                f"{ph}_max_ms": st["max"],
            })
        summary_rows.append(row)

    # --- aggregation B: per_consumer_median (low-noise)
    by_consumer = defaultdict(lambda: defaultdict(list))
    for r in consumer_rows:
        key = (r["consensus"], r["mec_count"], r["consumer_id"])
        for col in CONSUMER_PHASES:
            v = r.get(col)
            if isinstance(v, (int, float)):
                by_consumer[key][col].append(int(v))

    per_consumer = []
    for (cons, mec, cid), cols in by_consumer.items():
        row = {"consensus": cons, "mec_count": mec, "consumer_id": cid}
        for col, xs in cols.items():
            xs_sorted = sorted(xs)
            if not xs_sorted:
                continue
            m = xs_sorted[len(xs_sorted)//2] if (len(xs_sorted) % 2 == 1) else \
                (xs_sorted[len(xs_sorted)//2 - 1] + xs_sorted[len(xs_sorted)//2]) / 2
            row[col] = m
        per_consumer.append(row)

    groups2: Dict[Tuple[str,int], List[Dict]] = {}
    for r in per_consumer:
        groups2.setdefault((r["consensus"], r["mec_count"]), []).append(r)

    for (conc, mec_count), rs in sorted(groups2.items(), key=lambda x: (x[0][0], x[0][1])):
        row = {"consensus": conc, "mec_count": mec_count, "n_services": len(rs), "aggregation": "per_consumer_median"}
        phases = {
            "bid_collection":   [r.get("c_bid_collection_ms") for r in rs],
            "winner_selection": [r.get("c_winner_selection_ms") for r in rs],
            "provider_deploy":  [r.get("c_provider_deploy_ms") for r in rs],
            "vxlan_setup":      [r.get("c_vxlan_setup_ms") for r in rs],
            "postcheck":        [r.get("c_postcheck_ms") for r in rs],
            "total":            [r.get("c_total_ms") for r in rs],
        }
        for ph, vals in phases.items():
            st = summarize_series(vals)
            row.update({
                f"{ph}_n": st["n"],  # here: number of consumers with a median for this phase
                f"{ph}_mean_ms": st["mean"],
                f"{ph}_std_ms": st["std"],
                f"{ph}_median_ms": st["median"],
                f"{ph}_p25_ms": st["p25"],
                f"{ph}_p75_ms": st["p75"],
                f"{ph}_p95_ms": st["p95"],
                f"{ph}_min_ms": st["min"],
                f"{ph}_max_ms": st["max"],
            })
        summary_rows.append(row)

    # write summary
    base_hdr = ["consensus","mec_count","n_services","aggregation"]
    ph_cols = []
    for ph in ("bid_collection","winner_selection","provider_deploy","vxlan_setup","postcheck","total"):
        ph_cols += [
            f"{ph}_n", f"{ph}_mean_ms", f"{ph}_std_ms", f"{ph}_median_ms",
            f"{ph}_p25_ms", f"{ph}_p75_ms", f"{ph}_p95_ms", f"{ph}_min_ms", f"{ph}_max_ms"
        ]
    write_csv(SUMMARY_DIR / "consumer_summary.csv", base_hdr + ph_cols, summary_rows)

def make_provider_outputs(provider_rows: List[Dict]) -> None:
    # per-run (raw rows for CDF/boxplots)
    per_run_hdr = [
        "consensus","mec_count","provider_id","run_id","file","won_any",
        "p_announce_wait_ms","p_bid_sending_ms","p_winner_wait_ms","p_confirm_all_ms",
    ]
    write_csv(SUMMARY_DIR / "provider_per_run.csv", per_run_hdr, provider_rows)
    write_provider_cdf(provider_rows)

    # --- aggregation A: per_run (legacy, direct across runs)
    groups: Dict[Tuple[str,int], List[Dict]] = {}
    for r in provider_rows:
        groups.setdefault((r["consensus"], r["mec_count"]), []).append(r)

    summary_rows = []
    for (conc, mec_count), rs in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
        row = {"consensus": conc, "mec_count": mec_count, "n_runs": len(rs), "aggregation": "per_run"}
        phases = {
            "announce_wait": [r["p_announce_wait_ms"] for r in rs],
            "bid_sending":   [r["p_bid_sending_ms"]   for r in rs],
            "winner_wait":   [r["p_winner_wait_ms"]   for r in rs],
            # confirm_all: exclude None (no wins)
            "confirm_all":   [r["p_confirm_all_ms"]   for r in rs if r.get("p_confirm_all_ms") is not None],
        }
        for ph, vals in phases.items():
            st = summarize_series(vals)
            row.update({
                f"{ph}_n": st["n"],
                f"{ph}_mean_ms": st["mean"],
                f"{ph}_std_ms": st["std"],
                f"{ph}_median_ms": st["median"],
                f"{ph}_p25_ms": st["p25"],
                f"{ph}_p75_ms": st["p75"],
                f"{ph}_p95_ms": st["p95"],
                f"{ph}_min_ms": st["min"],
                f"{ph}_max_ms": st["max"],
            })
        summary_rows.append(row)

    # --- aggregation B: per_provider_median (low-noise)
    by_provider = defaultdict(lambda: defaultdict(list))
    for r in provider_rows:
        key = (r["consensus"], r["mec_count"], r["provider_id"])
        for col in PROVIDER_PHASES:
            v = r.get(col)
            if isinstance(v, (int, float)):
                by_provider[key][col].append(int(v))

    per_provider = []
    for (cons, mec, pid), cols in by_provider.items():
        row = {"consensus": cons, "mec_count": mec, "provider_id": pid}
        for col, xs in cols.items():
            xs_sorted = sorted(xs)
            if not xs_sorted:
                continue
            m = xs_sorted[len(xs_sorted)//2] if (len(xs_sorted) % 2 == 1) else \
                (xs_sorted[len(xs_sorted)//2 - 1] + xs_sorted[len(xs_sorted)//2]) / 2
            row[col] = m
        per_provider.append(row)

    groups2: Dict[Tuple[str,int], List[Dict]] = {}
    for r in per_provider:
        groups2.setdefault((r["consensus"], r["mec_count"]), []).append(r)

    for (conc, mec_count), rs in sorted(groups2.items(), key=lambda x: (x[0][0], x[0][1])):
        row = {"consensus": conc, "mec_count": mec_count, "n_runs": len(rs), "aggregation": "per_provider_median"}
        phases = {
            "announce_wait": [r.get("p_announce_wait_ms") for r in rs],
            "bid_sending":   [r.get("p_bid_sending_ms")   for r in rs],
            "winner_wait":   [r.get("p_winner_wait_ms")   for r in rs],
            "confirm_all":   [r.get("p_confirm_all_ms")   for r in rs if r.get("p_confirm_all_ms") is not None],
        }
        for ph, vals in phases.items():
            st = summarize_series(vals)
            row.update({
                f"{ph}_n": st["n"],  # here: number of providers with a median for this phase
                f"{ph}_mean_ms": st["mean"],
                f"{ph}_std_ms": st["std"],
                f"{ph}_median_ms": st["median"],
                f"{ph}_p25_ms": st["p25"],
                f"{ph}_p75_ms": st["p75"],
                f"{ph}_p95_ms": st["p95"],
                f"{ph}_min_ms": st["min"],
                f"{ph}_max_ms": st["max"],
            })
        summary_rows.append(row)

    # write summary
    base_hdr = ["consensus","mec_count","n_runs","aggregation"]
    ph_cols = []
    for ph in ("announce_wait","bid_sending","winner_wait","confirm_all"):
        ph_cols += [
            f"{ph}_n", f"{ph}_mean_ms", f"{ph}_std_ms", f"{ph}_median_ms",
            f"{ph}_p25_ms", f"{ph}_p75_ms", f"{ph}_p95_ms", f"{ph}_min_ms", f"{ph}_max_ms"
        ]
    write_csv(SUMMARY_DIR / "provider_summary.csv", base_hdr + ph_cols, summary_rows)

def main() -> int:
    consumer_rows = collect_consumers()
    provider_rows = collect_providers()

    make_consumer_outputs(consumer_rows)
    make_provider_outputs(provider_rows)

    print(f"Wrote {SUMMARY_DIR/'consumer_per_service.csv'} ({len(consumer_rows)} rows)")
    print(f"Wrote {SUMMARY_DIR/'consumer_summary.csv'} (with per_service and per_consumer_median)")
    print(f"Wrote {SUMMARY_DIR/'consumer_cdf.csv'}")
    print(f"Wrote {SUMMARY_DIR/'provider_per_run.csv'} ({len(provider_rows)} rows)")
    print(f"Wrote {SUMMARY_DIR/'provider_summary.csv'} (with per_run and per_provider_median)")
    print(f"Wrote {SUMMARY_DIR/'provider_cdf.csv'}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

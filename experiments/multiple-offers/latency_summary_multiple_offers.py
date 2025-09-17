#!/usr/bin/env python3
"""
latency_summary_multiple_offers.py
Run from: experiments/multiple-offers/

Writes ONLY three low-noise timeline summaries to ./_summary:

  1) consumer_timeline_summary.csv
     - Consumer durations/offsets aggregated as mean/std/quantiles of per-consumer medians.
     - dur_total = connection_test_success − service_announced (strict; logs error if missing).

  2) provider_timeline_summary.csv
     - Provider durations/offsets aggregated as mean/std/quantiles of per-provider medians.
     - DURATIONS (modified):
         dur_winners_received = all_winners_received − all_bid_offers_sent
         dur_confirm_deployment = all_confirm_deployment_sent − first(deployment_start_service*)
           (skip if 'no_wins' present; otherwise log error if cannot compute)
         dur_total = all_confirm_deployment_sent − first(announce_received_service*)
           (skip if 'no_wins' present; otherwise log error if cannot compute)
     - OFFSETS (relative to required_announces_received):
         t_all_bid_offers_sent_*, t_all_winners_received_*,
         t_start_deployment_* (first), t_all_confirm_deployment_sent_*
       (t_finish_all_deployment_* REMOVED)

  3) federation_timeline_summary.csv
     - Mixed (cross-role) durations using per-service pairing by service_id within the same run.
     - Offsets (relative to consumer service_announced) RE-INDEXED:
         Provider: t2_required_announces_received, t3_all_bid_offers_sent,
                   t6_all_winners_received, t7_start_deployment (first),
                   t8_all_confirm_deployment_sent
         Consumer: t4_required_bids_received, t5_winner_choosen,
                   t9_confirm_deployment_received, t10_vxlan_start,
                   t11_vxlan_finished, t12_connection_test_success
       (t8_finish_all_deployment REMOVED)
     - Cross-clock durations use safe_delta (drop negatives).

Aggregation method (low-noise) for every scenario (consensus, mec_count):
  1) Build per-run/per-service values.
  2) Collapse to per-node medians (consumer_id or provider_id).
  3) Across nodes: mean, std, median, p25, p75, p95, min, max.

Units: milliseconds. Missing/invalid values -> blank cells.
"""

from __future__ import annotations
import csv
import re
from pathlib import Path
from statistics import mean, median, stdev
from math import ceil
from typing import Dict, List, Optional, Tuple

ROOT = Path(".")
SUMMARY_DIR = ROOT / "_summary"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

CONSENSUS_DIRS = ("clique", "qbft")

# ------------ logging helpers ------------
_ERRORS: List[str] = []

def log_err(msg: str) -> None:
    _ERRORS.append(msg)

# ------------ parsing helpers ------------
def normalize_service_id(key: str) -> str:
    """
    From provider keys like:
      'announce_received_service...', 'bid_offer_sent_service...',
      'deployment_start_service...', 'deployment_finished_service...',
      'confirm_deployment_sent_service...'
    return the canonical substring starting at 'service...'.
    """
    i = key.find("service")
    return key[i:] if i != -1 else key

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
    return (int(m.group(1)), int(m.group(2))) if m else None

def parse_provider_ids(name: str) -> Optional[Tuple[int,int]]:
    m = re_provider.match(name)
    return (int(m.group(1)), int(m.group(2))) if m else None

def read_steps_csv(path: Path) -> Dict[str, int]:
    """Return step->timestamp_ms (int). Non-numeric rows are skipped (e.g., service_id)."""
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
                    pass
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
    if a in steps and b in steps:
        return steps[b] - steps[a]
    return None

def safe_delta(a: Optional[int], b: Optional[int]) -> Optional[int]:
    if a is None or b is None:
        return None
    d = b - a
    return d if d >= 0 else None

def percentile(values: List[float], q: float) -> float:
    """Nearest-rank percentile on a list of numbers."""
    xs = [float(v) for v in values if isinstance(v, (int, float))]
    if not xs:
        return float("nan")
    xs.sort()
    k = max(1, ceil(q * len(xs)))
    return xs[k - 1]

# --- NEW: per-consumer dur_total samples for true ECDF plotting ---
def write_consumer_total_samples(consumer_rows: List[Dict]) -> None:
    """
    One sample per consumer: median of strict end-to-end totals across that consumer's successful services.
    dur_total = connection_test_success - service_announced
    """
    by_consumer: Dict[Tuple[str, int, int], List[int]] = {}
    for r in consumer_rows:
        conc, mcount, cid = r["consensus"], r["mec_count"], r["consumer_id"]
        s = r.get("steps", {})
        if "service_announced" in s and "connection_test_success" in s:
            tot = s["connection_test_success"] - s["service_announced"]
            if isinstance(tot, (int, float)) and tot >= 0:
                by_consumer.setdefault((conc, mcount, cid), []).append(int(tot))

    out_rows = []
    for (conc, mcount, cid), vals in sorted(by_consumer.items()):
        if not vals:
            continue
        xs = sorted(vals)
        med = xs[len(xs)//2] if len(xs) % 2 == 1 else int(median(xs))
        out_rows.append({
            "consensus": conc,
            "mec_count": mcount,
            "consumer_id": cid,
            "n_services": len(xs),
            "dur_total_ms_median": med,
        })

    header = ["consensus", "mec_count", "consumer_id", "n_services", "dur_total_ms_median"]
    write_csv(SUMMARY_DIR / "consumer_total_per_consumer.csv", header, out_rows)

# ------------ collectors ------------
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
                rows.append({
                    "consensus": conc,
                    "mec_count": mec_count,
                    "consumer_id": cid,
                    "run_id": run_id,
                    "file": str(p.relative_to(ROOT)),
                    "service_id": read_service_id(p) or "",
                    "steps": steps,
                })
    return rows

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

                service_bid_sent: Dict[str, int] = {}
                service_started: Dict[str, int] = {}
                service_finished: Dict[str, int] = {}
                service_confirm_sent: Dict[str, int] = {}
                for k, ts in steps.items():
                    if k.startswith("bid_offer_sent_service"):
                        service_bid_sent[normalize_service_id(k)] = ts
                    elif k.startswith("deployment_start_service"):
                        service_started[normalize_service_id(k)] = ts
                    elif k.startswith("deployment_finished_service"):
                        service_finished[normalize_service_id(k)] = ts
                    elif k.startswith("confirm_deployment_sent_service"):
                        service_confirm_sent[normalize_service_id(k)] = ts

                won_any = 1 if service_started else (0 if "no_wins" in steps else 0)

                rows.append({
                    "consensus": conc,
                    "mec_count": mec_count,
                    "provider_id": pid,
                    "run_id": run_id,
                    "file": str(p.relative_to(ROOT)),
                    "steps": steps,
                    "service_bid_sent": service_bid_sent,
                    "service_started": service_started,
                    "service_finished": service_finished,
                    "service_confirm_sent": service_confirm_sent,
                    "won_any": won_any,
                })
    return rows

# ------------ stats/format helpers ------------
def _safe_stats(values: List[Optional[int]]) -> Dict[str, float]:
    xs = [float(v) for v in values if isinstance(v, (int, float))]
    if not xs:
        return {"mean": float("nan"), "std": 0.0, "median": float("nan"),
                "p25": float("nan"), "p75": float("nan"), "p95": float("nan"),
                "min": float("nan"), "max": float("nan")}
    return {
        "mean":   mean(xs),
        "std":    (stdev(xs) if len(xs) > 1 else 0.0),
        "median": median(xs),
        "p25":    percentile(xs, 0.25),
        "p75":    percentile(xs, 0.75),
        "p95":    percentile(xs, 0.95),
        "min":    min(xs),
        "max":    max(xs),
    }

def _fmt_stats(prefix: str, stats: Dict[str, float], into: Dict[str, object]) -> None:
    into[f"{prefix}_mean_ms"]   = f"{stats['mean']:.2f}"   if stats["mean"] == stats["mean"] else ""
    into[f"{prefix}_std_ms"]    = f"{stats['std']:.2f}"
    into[f"{prefix}_median_ms"] = f"{stats['median']:.2f}" if stats["median"] == stats["median"] else ""
    into[f"{prefix}_p25_ms"]    = f"{stats['p25']:.2f}"    if stats["p25"] == stats["p25"] else ""
    into[f"{prefix}_p75_ms"]    = f"{stats['p75']:.2f}"    if stats["p75"] == stats["p75"] else ""
    into[f"{prefix}_p95_ms"]    = f"{stats['p95']:.2f}"    if stats["p95"] == stats["p95"] else ""
    into[f"{prefix}_min_ms"]    = f"{stats['min']:.2f}"    if stats["min"] == stats["min"] else ""
    into[f"{prefix}_max_ms"]    = f"{stats['max']:.2f}"    if stats["max"] == stats["max"] else ""

def write_csv(path: Path, header: List[str], rows: List[Dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})

def _offset(steps: Dict[str,int], ref: str, key: str) -> Optional[int]:
    if ref in steps and key in steps:
        return steps[key] - steps[ref]
    return None

# ------------ timeline builders ------------
def build_consumer_timeline(consumer_rows: List[Dict]) -> None:
    per_node: Dict[Tuple[str,int,int], Dict[str, List[Optional[int]]]] = {}
    for r in consumer_rows:
        key = (r["consensus"], r["mec_count"], r["consumer_id"])
        steps = r["steps"]
        ref = "service_announced"

        offs = {
            "t_required_bids_received": _offset(steps, ref, "required_bids_received"),
            "t_winner_choosen": _offset(steps, ref, "winner_choosen"),
            "t_confirm_deployment_received": _offset(steps, ref, "confirm_deployment_received"),
            "t_vxlan_start": _offset(steps, ref, "establish_vxlan_connection_with_provider_start"),
            "t_vxlan_finished": _offset(steps, ref, "establish_vxlan_connection_with_provider_finished"),
            "t_connection_test_success": _offset(steps, ref, "connection_test_success"),
        }
        dst = per_node.setdefault(key, {k: [] for k in offs.keys()})
        for k2, v in offs.items(): dst[k2].append(v)

        for nm, val in [
            ("dur_bid_collection",   delta(steps, "service_announced", "required_bids_received")),
            ("dur_winner_selection", delta(steps, "required_bids_received", "winner_choosen")),
            ("dur_provider_deploy_confirm", delta(steps, "winner_choosen", "confirm_deployment_received")),
            ("dur_vxlan_setup",      delta(steps, "establish_vxlan_connection_with_provider_start",
                                                 "establish_vxlan_connection_with_provider_finished")),
            ("dur_federation_completed", delta(steps, "establish_vxlan_connection_with_provider_finished",
                                                     "connection_test_success")),
        ]:
            if nm not in dst: dst[nm] = []
            dst[nm].append(val)

        t1 = steps.get("service_announced")
        t_end = steps.get("connection_test_success")
        if t1 is None or t_end is None:
            log_err(f"[consumer total] missing service_announced or connection_test_success in {r['file']}")
            dt = None
        else:
            dt = t_end - t1
        dst.setdefault("dur_total", []).append(dt)

    node_medians: Dict[Tuple[str,int], Dict[str, List[Optional[int]]]] = {}
    for (conc, mcount, cid), series in per_node.items():
        tgt = node_medians.setdefault((conc, mcount), {})
        for name, values in series.items():
            xs = [v for v in values if isinstance(v, (int, float))]
            mval = (xs[len(xs)//2] if len(xs)%2==1 else int(median(xs))) if xs else None
            tgt.setdefault(name, []).append(mval)

    out_rows = []
    for (conc, mcount), series in sorted(node_medians.items(), key=lambda x: (x[0][0], x[0][1])):
        row = {"consensus": conc, "mec_count": mcount, "aggregation": "per_consumer_median"}
        row["n_consumers"] = max(len(v) for v in series.values()) if series else 0
        row["n_services"]  = sum(1 for r in consumer_rows if r["consensus"]==conc and r["mec_count"]==mcount)

        for lbl in ("dur_bid_collection","dur_winner_selection","dur_provider_deploy_confirm",
                    "dur_vxlan_setup","dur_federation_completed","dur_total"):
            _fmt_stats(lbl, _safe_stats(series.get(lbl, [])), row)

        for tname in ("t_required_bids_received","t_winner_choosen","t_confirm_deployment_received",
                      "t_vxlan_start","t_vxlan_finished","t_connection_test_success"):
            stats = _safe_stats(series.get(tname, []))
            row[f"{tname}_median_ms"] = f"{stats['median']:.2f}" if stats["median"]==stats["median"] else ""
            row[f"{tname}_p25_ms"]    = f"{stats['p25']:.2f}" if stats["p25"]==stats["p25"] else ""
            row[f"{tname}_p75_ms"]    = f"{stats['p75']:.2f}" if stats["p75"]==stats["p75"] else ""

        out_rows.append(row)

    hdr = [
        "consensus","mec_count","aggregation","n_consumers","n_services",
        "dur_bid_collection_mean_ms","dur_bid_collection_std_ms","dur_bid_collection_median_ms","dur_bid_collection_p25_ms","dur_bid_collection_p75_ms","dur_bid_collection_p95_ms","dur_bid_collection_min_ms","dur_bid_collection_max_ms",
        "dur_winner_selection_mean_ms","dur_winner_selection_std_ms","dur_winner_selection_median_ms","dur_winner_selection_p25_ms","dur_winner_selection_p75_ms","dur_winner_selection_p95_ms","dur_winner_selection_min_ms","dur_winner_selection_max_ms",
        "dur_provider_deploy_confirm_mean_ms","dur_provider_deploy_confirm_std_ms","dur_provider_deploy_confirm_median_ms","dur_provider_deploy_confirm_p25_ms","dur_provider_deploy_confirm_p75_ms","dur_provider_deploy_confirm_p95_ms","dur_provider_deploy_confirm_min_ms","dur_provider_deploy_confirm_max_ms",
        "dur_vxlan_setup_mean_ms","dur_vxlan_setup_std_ms","dur_vxlan_setup_median_ms","dur_vxlan_setup_p25_ms","dur_vxlan_setup_p75_ms","dur_vxlan_setup_p95_ms","dur_vxlan_setup_min_ms","dur_vxlan_setup_max_ms",
        "dur_federation_completed_mean_ms","dur_federation_completed_std_ms","dur_federation_completed_median_ms","dur_federation_completed_p25_ms","dur_federation_completed_p75_ms","dur_federation_completed_p95_ms","dur_federation_completed_min_ms","dur_federation_completed_max_ms",
        "dur_total_mean_ms","dur_total_std_ms","dur_total_median_ms","dur_total_p25_ms","dur_total_p75_ms","dur_total_p95_ms","dur_total_min_ms","dur_total_max_ms",
        "t_required_bids_received_median_ms","t_required_bids_received_p25_ms","t_required_bids_received_p75_ms",
        "t_winner_choosen_median_ms","t_winner_choosen_p25_ms","t_winner_choosen_p75_ms",
        "t_confirm_deployment_received_median_ms","t_confirm_deployment_received_p25_ms","t_confirm_deployment_received_p75_ms",
        "t_vxlan_start_median_ms","t_vxlan_start_p25_ms","t_vxlan_start_p75_ms",
        "t_vxlan_finished_median_ms","t_vxlan_finished_p25_ms","t_vxlan_finished_p75_ms",
        "t_connection_test_success_median_ms","t_connection_test_success_p25_ms","t_connection_test_success_p75_ms",
    ]
    write_csv(SUMMARY_DIR / "consumer_timeline_summary.csv", hdr, out_rows)

def build_provider_timeline(provider_rows: List[Dict]) -> None:
    per_node: Dict[Tuple[str,int,int], Dict[str, List[Optional[int]]]] = {}
    for pr in provider_rows:
        key = (pr["consensus"], pr["mec_count"], pr["provider_id"])
        steps = pr["steps"]
        ref = "required_announces_received"

        offs = {
            "t_all_bid_offers_sent": _offset(steps, ref, "all_bid_offers_sent"),
            "t_all_winners_received": _offset(steps, ref, "all_winners_received"),
            "t_start_deployment": (min([ts for k, ts in steps.items() if k.startswith("deployment_start_service")]) - steps[ref])
                                  if (ref in steps and any(k.startswith("deployment_start_service") for k in steps)) else None,
            "t_all_confirm_deployment_sent": _offset(steps, ref, "all_confirm_deployment_sent"),
        }
        dst = per_node.setdefault(key, {k: [] for k in offs.keys()})
        for k2, v in offs.items(): dst[k2].append(v)

        d_win = delta(steps, "all_bid_offers_sent", "all_winners_received")
        dst.setdefault("dur_winners_received", []).append(d_win)

        starts = [ts for k, ts in steps.items() if k.startswith("deployment_start_service")]
        first_start = min(starts) if starts else None
        d_conf = safe_delta(first_start, steps.get("all_confirm_deployment_sent"))
        if d_conf is None and "no_wins" not in steps:
            log_err(f"[provider confirm] cannot compute confirm_deployment in {pr['file']}")
        dst.setdefault("dur_confirm_deployment", []).append(d_conf if "no_wins" not in steps else None)

        announces = [ts for k, ts in steps.items() if k.startswith("announce_received_service")]
        first_announce = min(announces) if announces else None
        d_total = safe_delta(first_announce, steps.get("all_confirm_deployment_sent"))
        if d_total is None and "no_wins" not in steps:
            log_err(f"[provider total] missing earliest announce or all_confirm_deployment_sent in {pr['file']}")
        dst.setdefault("dur_total", []).append(d_total if "no_wins" not in steps else None)

    node_medians: Dict[Tuple[str,int], Dict[str, List[Optional[int]]]] = {}
    for (conc, mcount, pid), series in per_node.items():
        tgt = node_medians.setdefault((conc, mcount), {})
        for name, values in series.items():
            xs = [v for v in values if isinstance(v, (int, float))]
            mval = (xs[len(xs)//2] if len(xs)%2==1 else int(median(xs))) if xs else None
            tgt.setdefault(name, []).append(mval)

    out_rows = []
    for (conc, mcount), series in sorted(node_medians.items(), key=lambda x: (x[0][0], x[0][1])):
        row = {"consensus": conc, "mec_count": mcount, "aggregation": "per_provider_median"}
        row["n_providers"] = max(len(v) for v in series.values()) if series else 0
        row["n_runs"] = sum(1 for r in provider_rows if r["consensus"]==conc and r["mec_count"]==mcount)

        for lbl in ("dur_winners_received","dur_confirm_deployment","dur_total"):
            _fmt_stats(lbl, _safe_stats(series.get(lbl, [])), row)

        for tname in ("t_all_bid_offers_sent","t_all_winners_received","t_start_deployment","t_all_confirm_deployment_sent"):
            stats = _safe_stats(series.get(tname, []))
            row[f"{tname}_median_ms"] = f"{stats['median']:.2f}" if stats["median"]==stats["median"] else ""
            row[f"{tname}_p25_ms"]    = f"{stats['p25']:.2f}" if stats["p25"]==stats["p25"] else ""
            row[f"{tname}_p75_ms"]    = f"{stats['p75']:.2f}" if stats["p75"]==stats["p75"] else ""

        out_rows.append(row)

    hdr = [
        "consensus","mec_count","aggregation","n_providers","n_runs",
        "dur_winners_received_mean_ms","dur_winners_received_std_ms","dur_winners_received_median_ms","dur_winners_received_p25_ms","dur_winners_received_p75_ms","dur_winners_received_p95_ms","dur_winners_received_min_ms","dur_winners_received_max_ms",
        "dur_confirm_deployment_mean_ms","dur_confirm_deployment_std_ms","dur_confirm_deployment_median_ms","dur_confirm_deployment_p25_ms","dur_confirm_deployment_p75_ms","dur_confirm_deployment_p95_ms","dur_confirm_deployment_min_ms","dur_confirm_deployment_max_ms",
        "dur_total_mean_ms","dur_total_std_ms","dur_total_median_ms","dur_total_p25_ms","dur_total_p75_ms","dur_total_p95_ms","dur_total_min_ms","dur_total_max_ms",
        "t_all_bid_offers_sent_median_ms","t_all_bid_offers_sent_p25_ms","t_all_bid_offers_sent_p75_ms",
        "t_all_winners_received_median_ms","t_all_winners_received_p25_ms","t_all_winners_received_p75_ms",
        "t_start_deployment_median_ms","t_start_deployment_p25_ms","t_start_deployment_p75_ms",
        "t_all_confirm_deployment_sent_median_ms","t_all_confirm_deployment_sent_p25_ms","t_all_confirm_deployment_sent_p75_ms",
    ]
    write_csv(SUMMARY_DIR / "provider_timeline_summary.csv", hdr, out_rows)

def build_federation_timeline(consumer_rows: List[Dict], provider_rows: List[Dict]) -> None:
    prov_by_run: Dict[Tuple[str,int,int], List[Dict]] = {}
    for pr in provider_rows:
        prov_by_run.setdefault((pr["consensus"], pr["mec_count"], pr["run_id"]), []).append(pr)

    mixed_per_consumer: Dict[Tuple[str,int,int], Dict[str, List[Optional[int]]]] = {}
    mixed_offsets_per_consumer: Dict[Tuple[str,int,int], Dict[str, List[Optional[int]]]] = {}

    for r in consumer_rows:
        conc, mcount, run_id, sid = r["consensus"], r["mec_count"], r["run_id"], r["service_id"]
        key = (conc, mcount, r["consumer_id"])
        steps_c = r["steps"]
        t1 = steps_c.get("service_announced")
        if t1 is None or not sid:
            continue

        winners = []
        for pr in prov_by_run.get((conc, mcount, run_id), []):
            if sid in pr.get("service_started", {}):
                winners.append(pr)
        if not winners:
            continue
        pr = min(winners, key=lambda x: x["service_started"][sid])
        steps_p = pr["steps"]
        svc_bid_map = pr.get("service_bid_sent", {})
        svc_confirm_map = pr.get("service_confirm_sent", {})

        req_fed = safe_delta(t1, steps_p.get("required_announces_received"))
        bid_offered = safe_delta(svc_bid_map.get(sid), steps_c.get("required_bids_received"))
        provider_chosen = safe_delta(steps_c.get("winner_choosen"), steps_p.get("all_winners_received"))
        service_deployed_running = safe_delta(svc_confirm_map.get(sid), steps_c.get("connection_test_success"))

        bucket = mixed_per_consumer.setdefault(key, {
            "dur_request_federation": [], "dur_bid_offered": [],
            "dur_provider_chosen": [], "dur_service_deployed_running": [],
        })
        bucket["dur_request_federation"].append(req_fed)
        bucket["dur_bid_offered"].append(bid_offered)
        bucket["dur_provider_chosen"].append(provider_chosen)
        bucket["dur_service_deployed_running"].append(service_deployed_running)

        offs = mixed_offsets_per_consumer.setdefault(key, {
            "t2_required_announces_received": [],
            "t3_all_bid_offers_sent": [],
            "t6_all_winners_received": [],
            "t7_start_deployment": [],
            "t8_all_confirm_deployment_sent": [],
            "t4_required_bids_received": [],
            "t5_winner_choosen": [],
            "t9_confirm_deployment_received": [],
            "t10_vxlan_start": [],
            "t11_vxlan_finished": [],
            "t12_connection_test_success": [],
        })
        def add_off(name: str, base: Dict[str,int], key: str, ref_ts: int):
            offs[name].append((base[key] - ref_ts) if key in base else None)

        add_off("t2_required_announces_received", steps_p, "required_announces_received", t1)
        add_off("t3_all_bid_offers_sent", steps_p, "all_bid_offers_sent", t1)
        add_off("t6_all_winners_received", steps_p, "all_winners_received", t1)
        starts = [ts for k, ts in steps_p.items() if k.startswith("deployment_start_service")]
        offs["t7_start_deployment"].append((min(starts) - t1) if starts else None)
        add_off("t8_all_confirm_deployment_sent", steps_p, "all_confirm_deployment_sent", t1)

        add_off("t4_required_bids_received", steps_c, "required_bids_received", t1)
        add_off("t5_winner_choosen", steps_c, "winner_choosen", t1)
        add_off("t9_confirm_deployment_received", steps_c, "confirm_deployment_received", t1)
        add_off("t10_vxlan_start", steps_c, "establish_vxlan_connection_with_provider_start", t1)
        add_off("t11_vxlan_finished", steps_c, "establish_vxlan_connection_with_provider_finished", t1)
        add_off("t12_connection_test_success", steps_c, "connection_test_success", t1)

    node_medians: Dict[Tuple[str,int], Dict[str, List[Optional[int]]]] = {}
    node_offs_medians: Dict[Tuple[str,int], Dict[str, List[Optional[int]]]] = {}
    for (conc, mcount, cid), durs in mixed_per_consumer.items():
        tgt = node_medians.setdefault((conc, mcount), {})
        for name, values in durs.items():
            xs = [v for v in values if isinstance(v, (int, float))]
            mval = (xs[len(xs)//2] if len(xs)%2==1 else int(median(xs))) if xs else None
            tgt.setdefault(name, []).append(mval)
    for (conc, mcount, cid), offs in mixed_offsets_per_consumer.items():
        tgt = node_offs_medians.setdefault((conc, mcount), {})
        for name, values in offs.items():
            xs = [v for v in values if isinstance(v, (int, float))]
            mval = (xs[len(xs)//2] if len(xs)%2==1 else int(median(xs))) if xs else None
            tgt.setdefault(name, []).append(mval)

    out_rows = []
    for (conc, mcount), series in sorted(node_medians.items(), key=lambda x: (x[0][0], x[0][1])):
        row = {"consensus": conc, "mec_count": mcount, "aggregation": "per_consumer_median"}
        row["n_consumers"] = max(len(v) for v in series.values()) if series else 0
        row["n_services"]  = sum(1 for r in consumer_rows if r["consensus"]==conc and r["mec_count"]==mcount)

        for lbl in ("dur_request_federation","dur_bid_offered","dur_provider_chosen","dur_service_deployed_running"):
            _fmt_stats(lbl, _safe_stats(series.get(lbl, [])), row)

        offs_series = node_offs_medians.get((conc, mcount), {})
        for tname in (
            "t2_required_announces_received","t3_all_bid_offers_sent",
            "t6_all_winners_received","t7_start_deployment","t8_all_confirm_deployment_sent",
            "t4_required_bids_received","t5_winner_choosen","t9_confirm_deployment_received",
            "t10_vxlan_start","t11_vxlan_finished","t12_connection_test_success"
        ):
            stats = _safe_stats(offs_series.get(tname, []))
            row[f"{tname}_median_ms"] = f"{stats['median']:.2f}" if stats["median"]==stats["median"] else ""
            row[f"{tname}_p25_ms"]    = f"{stats['p25']:.2f}" if stats["p25"]==stats["p25"] else ""
            row[f"{tname}_p75_ms"]    = f"{stats['p75']:.2f}" if stats["p75"]==stats["p75"] else ""

        out_rows.append(row)

    hdr = [
        "consensus","mec_count","aggregation","n_consumers","n_services",
        "dur_request_federation_mean_ms","dur_request_federation_std_ms","dur_request_federation_median_ms","dur_request_federation_p25_ms","dur_request_federation_p75_ms","dur_request_federation_p95_ms","dur_request_federation_min_ms","dur_request_federation_max_ms",
        "dur_bid_offered_mean_ms","dur_bid_offered_std_ms","dur_bid_offered_median_ms","dur_bid_offered_p25_ms","dur_bid_offered_p75_ms","dur_bid_offered_p95_ms","dur_bid_offered_min_ms","dur_bid_offered_max_ms",
        "dur_provider_chosen_mean_ms","dur_provider_chosen_std_ms","dur_provider_chosen_median_ms","dur_provider_chosen_p25_ms","dur_provider_chosen_p75_ms","dur_provider_chosen_p95_ms","dur_provider_chosen_min_ms","dur_provider_chosen_max_ms",
        "dur_service_deployed_running_mean_ms","dur_service_deployed_running_std_ms","dur_service_deployed_running_median_ms","dur_service_deployed_running_p25_ms","dur_service_deployed_running_p75_ms","dur_service_deployed_running_p95_ms","dur_service_deployed_running_min_ms","dur_service_deployed_running_max_ms",
        "t2_required_announces_received_median_ms","t2_required_announces_received_p25_ms","t2_required_announces_received_p75_ms",
        "t3_all_bid_offers_sent_median_ms","t3_all_bid_offers_sent_p25_ms","t3_all_bid_offers_sent_p75_ms",
        "t6_all_winners_received_median_ms","t6_all_winners_received_p25_ms","t6_all_winners_received_p75_ms",
        "t7_start_deployment_median_ms","t7_start_deployment_p25_ms","t7_start_deployment_p75_ms",
        "t8_all_confirm_deployment_sent_median_ms","t8_all_confirm_deployment_sent_p25_ms","t8_all_confirm_deployment_sent_p75_ms",
        "t4_required_bids_received_median_ms","t4_required_bids_received_p25_ms","t4_required_bids_received_p75_ms",
        "t5_winner_choosen_median_ms","t5_winner_choosen_p25_ms","t5_winner_choosen_p75_ms",
        "t9_confirm_deployment_received_median_ms","t9_confirm_deployment_received_p25_ms","t9_confirm_deployment_received_p75_ms",
        "t10_vxlan_start_median_ms","t10_vxlan_start_p25_ms","t10_vxlan_start_p75_ms",
        "t11_vxlan_finished_median_ms","t11_vxlan_finished_p25_ms","t11_vxlan_finished_p75_ms",
        "t12_connection_test_success_median_ms","t12_connection_test_success_p25_ms","t12_connection_test_success_p75_ms",
    ]
    write_csv(SUMMARY_DIR / "federation_timeline_summary.csv", hdr, out_rows)

# ------------ main ------------
def main() -> int:
    consumer_rows = collect_consumers()
    provider_rows = collect_providers()

    build_consumer_timeline(consumer_rows)
    build_provider_timeline(provider_rows)
    build_federation_timeline(consumer_rows, provider_rows)

    # Tiny export for the ECDF plot
    write_consumer_total_samples(consumer_rows)

    print(f"Wrote {SUMMARY_DIR/'consumer_timeline_summary.csv'}")
    print(f"Wrote {SUMMARY_DIR/'provider_timeline_summary.csv'}")
    print(f"Wrote {SUMMARY_DIR/'federation_timeline_summary.csv'}")
    print(f"Wrote {SUMMARY_DIR/'consumer_total_per_consumer.csv'}")

    if _ERRORS:
        print(f"[WARN] Completed with {len(_ERRORS)} issues. First 20:")
        for m in _ERRORS[:20]:
            print("  " + m)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

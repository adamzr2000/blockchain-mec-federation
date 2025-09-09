#!/usr/bin/env python3
"""
Modular Docker container resource monitor (window-aware, no throughput MB/s).

- Start/stop API + context manager
- CPU %, Mem MB, Mem limit MB, Mem %
- Disk R/W MB (cumulative) with fallback: Docker blkio -> cgroup v2 io.stat -> /proc/<pid>/io
- Net RX/TX MB (cumulative)
- Per-window totals via get_window_totals()
- Optional CSV, per-sample callback
"""
from __future__ import annotations

import csv
import logging
import threading
import time
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any

try:
    import docker
except Exception:
    docker = None

logger = logging.getLogger(__name__)

# ---------- helpers ----------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _safe_get(dct, path, default=0):
    cur = dct
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def _bytes_to_mb(b: int) -> float:
    return float(b) / (1024.0 * 1024.0)

def _compute_cpu_percent(stats) -> float:
    cpu_total = _safe_get(stats, ("cpu_stats","cpu_usage","total_usage"))
    pre_cpu_total = _safe_get(stats, ("precpu_stats","cpu_usage","total_usage"))
    system_cpu = _safe_get(stats, ("cpu_stats","system_cpu_usage"))
    pre_system_cpu = _safe_get(stats, ("precpu_stats","system_cpu_usage"))
    online_cpus = _safe_get(stats, ("cpu_stats","online_cpus"))
    if not online_cpus:
        per_cpu = _safe_get(stats, ("cpu_stats","cpu_usage","percpu_usage"), default=[])
        online_cpus = len(per_cpu) if isinstance(per_cpu, list) and per_cpu else 1
    cpu_delta = cpu_total - pre_cpu_total
    system_delta = system_cpu - pre_system_cpu
    if system_delta > 0 and cpu_delta >= 0:
        return (cpu_delta / float(system_delta)) * online_cpus * 100.0
    return 0.0

def _compute_mem_used_mb(stats) -> float:
    usage = _safe_get(stats, ("memory_stats","usage"))
    cache = _safe_get(stats, ("memory_stats","stats","cache"))
    used_no_cache = usage - cache if usage >= cache else usage
    return _bytes_to_mb(used_no_cache)

def _compute_mem_limit_mb(stats) -> Optional[float]:
    limit = _safe_get(stats, ("memory_stats","limit"))
    if not isinstance(limit, (int, float)) or limit <= 0:
        return None
    if limit > 1 << 50:  # treat huge as "unlimited"
        return None
    return _bytes_to_mb(limit)

def _compute_mem_percent(used_mb: float, limit_mb: Optional[float]) -> Optional[float]:
    if limit_mb and limit_mb > 0:
        return max(0.0, min(100.0, (used_mb / limit_mb) * 100.0))
    return None

# ---- Docker API blkio ----
def _docker_blkio_mb(stats):
    reads = 0
    writes = 0
    entries = _safe_get(stats, ("blkio_stats","io_service_bytes_recursive"), default=[])
    if isinstance(entries, list):
        for it in entries:
            op = it.get("op")
            val = int(it.get("value", 0))
            if op == "Read":
                reads += val
            elif op == "Write":
                writes += val
    return _bytes_to_mb(reads), _bytes_to_mb(writes)

# ---- cgroup v2 helpers ----
def _is_cgroup_v2(pid: int) -> bool:
    try:
        with open(f"/proc/{pid}/cgroup", "r") as f:
            lines = f.read().strip().splitlines()
        return any(line.startswith("0::/") for line in lines)
    except Exception:
        return False

def _cgroup_path_v2(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cgroup", "r") as f:
            for line in f:
                if line.startswith("0::/"):
                    return line.strip().split("0::", 1)[1]
    except Exception:
        pass
    return "/"

def _blkio_from_cgroup_v2(pid: int):
    cg = _cgroup_path_v2(pid)
    path = os.path.join("/sys/fs/cgroup", cg.lstrip("/"), "io.stat")
    rbytes = 0
    wbytes = 0
    try:
        with open(path, "r") as f:
            for line in f:
                for kv in line.strip().split():
                    if kv.startswith("rbytes="):
                        rbytes += int(kv.split("=", 1)[1])
                    elif kv.startswith("wbytes="):
                        wbytes += int(kv.split("=", 1)[1])
        return _bytes_to_mb(rbytes), _bytes_to_mb(wbytes)
    except Exception:
        return None

# ---- /proc/<pid>/io fallback ----
def _blkio_from_proc_io(pid: int):
    path = f"/proc/{pid}/io"
    read_bytes = 0
    write_bytes = 0
    try:
        with open(path, "r") as f:
            for line in f:
                if line.startswith("read_bytes:"):
                    read_bytes = int(line.split(":", 1)[1].strip())
                elif line.startswith("write_bytes:"):
                    write_bytes = int(line.split(":", 1)[1].strip())
        return _bytes_to_mb(read_bytes), _bytes_to_mb(write_bytes)
    except Exception:
        return None

# ---- network helper (this was missing in your file) ----
def _compute_net_mb(stats):
    rx = 0
    tx = 0
    networks = stats.get("networks", {})
    if isinstance(networks, dict):
        for _, vals in networks.items():
            rx += int(vals.get("rx_bytes", 0))
            tx += int(vals.get("tx_bytes", 0))
    return _bytes_to_mb(rx), _bytes_to_mb(tx)

# ---------- monitor ----------
@dataclass
class DockerContainerMonitor:
    container_ref: str
    interval: float = 1.0
    csv_path: Optional[str] = None
    write_header: bool = True
    stdout: bool = False
    on_sample: Optional[Callable[[dict], None]] = None

    _thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _csv_file: Optional[object] = field(default=None, init=False, repr=False)
    _csv_writer: Optional[csv.DictWriter] = field(default=None, init=False, repr=False)
    _baseline: Optional[Dict[str, float]] = field(default=None, init=False, repr=False)
    _last_sample: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)
    _container_pid: Optional[int] = field(default=None, init=False, repr=False)

    def start(self) -> None:
        if docker is None:
            raise RuntimeError("The 'docker' package is required. Install with: pip install docker")
        if self._thread and self._thread.is_alive():
            logger.warning("DockerContainerMonitor is already running.")
            return

        self._stop_event.clear()
        self._baseline = None
        self._last_sample = None

        if self.csv_path:
            self._csv_file = open(self.csv_path, "a", newline="")
            fieldnames = [
                "timestamp",
                "cpu_percent",
                "mem_mb",
                "mem_limit_mb",
                "mem_percent",
                "blk_read_mb", "blk_write_mb",
                "net_rx_mb", "net_tx_mb",
            ]
            self._csv_writer = csv.DictWriter(self._csv_file, fieldnames=fieldnames)
            if self.write_header:
                try:
                    self._csv_writer.writeheader()
                    self._csv_file.flush()
                except Exception as e:
                    logger.exception("Failed to write CSV header: %s", e)

        self._thread = threading.Thread(target=self._run, name="DockerContainerMonitor", daemon=True)
        self._thread.start()
        logger.info("DockerContainerMonitor started for container: %s", self.container_ref)

    def stop(self, timeout: Optional[float] = 5.0) -> None:
        self._take_final_snapshot()
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        if self._csv_file:
            try:
                self._csv_file.close()
            except Exception:
                pass
            finally:
                self._csv_file = None
                self._csv_writer = None
        logger.info("DockerContainerMonitor stopped for container: %s", self.container_ref)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()

    def _resolve_container(self, client):
        try:
            return client.containers.get(self.container_ref)
        except Exception:
            matches = [c for c in client.containers.list(all=True)
                       if c.id.startswith(self.container_ref) or c.name == self.container_ref or c.name.endswith(self.container_ref)]
            if not matches:
                raise
            if len(matches) > 1:
                logger.warning("Multiple containers match '%s'. Using the first: %s (%s)",
                               self.container_ref, matches[0].id[:12], matches[0].name)
            return matches[0]

    def _compute_blkio_mb_with_fallback(self, stats):
        r_mb, w_mb = _docker_blkio_mb(stats)
        if (r_mb > 0.0 or w_mb > 0.0) or not self._container_pid:
            return r_mb, w_mb
        try:
            if _is_cgroup_v2(self._container_pid):
                cg_vals = _blkio_from_cgroup_v2(self._container_pid)
                if cg_vals is not None:
                    return cg_vals
        except Exception:
            pass
        try:
            proc_vals = _blkio_from_proc_io(self._container_pid)
            if proc_vals is not None:
                return proc_vals
        except Exception:
            pass
        return r_mb, w_mb

    def _run(self) -> None:
        client = docker.from_env()
        try:
            container = self._resolve_container(client)
        except Exception as e:
            logger.exception("Failed to resolve container '%s': %s", self.container_ref, e)
            return

        try:
            try:
                self._container_pid = int(container.attrs.get("State", {}).get("Pid", 0)) or None
            except Exception:
                self._container_pid = None

            stream = container.stats(stream=True, decode=True)
            try:
                next(stream)  # prime for precpu fields
            except StopIteration:
                logger.error("No stats available from Docker. Is the container running?")
                return
        except Exception as e:
            logger.exception("Failed to open stats stream: %s", e)
            return

        last_emit = time.monotonic()
        interval = max(0.05, float(self.interval))

        while not self._stop_event.is_set():
            try:
                stats = next(stream)
            except StopIteration:
                logger.info("Stats stream ended.")
                break
            except Exception as e:
                logger.exception("Error reading stats: %s", e)
                break

            now_mono = time.monotonic()
            if now_mono - last_emit < interval:
                continue
            last_emit = now_mono

            mem_mb = round(_compute_mem_used_mb(stats), 2)
            mem_limit_mb = _compute_mem_limit_mb(stats)
            mem_percent = _compute_mem_percent(mem_mb, mem_limit_mb)

            sample = {
                "timestamp": int(time.time() * 1000),
                "cpu_percent": round(_compute_cpu_percent(stats), 2),
                "mem_mb": mem_mb,
                "mem_limit_mb": round(mem_limit_mb, 2) if mem_limit_mb is not None else None,
                "mem_percent": round(mem_percent, 2) if mem_percent is not None else None,
            }

            blk_read_mb, blk_write_mb = self._compute_blkio_mb_with_fallback(stats)
            net_rx_mb, net_tx_mb = _compute_net_mb(stats)
            sample.update({
                "blk_read_mb": round(blk_read_mb, 3),
                "blk_write_mb": round(blk_write_mb, 3),
                "net_rx_mb": round(net_rx_mb, 3),
                "net_tx_mb": round(net_tx_mb, 3),
            })

            if self._baseline is None:
                self._baseline = {
                    "blk_read_mb": sample["blk_read_mb"],
                    "blk_write_mb": sample["blk_write_mb"],
                    "net_rx_mb": sample["net_rx_mb"],
                    "net_tx_mb": sample["net_tx_mb"],
                }

            self._last_sample = dict(sample)

            if self._csv_writer:
                try:
                    self._csv_writer.writerow(sample)
                    self._csv_file.flush()
                except Exception as e:
                    logger.exception("Failed to write CSV row: %s", e)

            if self.stdout:
                mem_part = f"MEM {sample['mem_mb']:8.2f} MB"
                if sample["mem_percent"] is not None:
                    if sample["mem_limit_mb"] is not None:
                        mem_part += f" ({sample['mem_percent']:5.1f}% of {sample['mem_limit_mb']:.0f} MB)"
                    else:
                        mem_part += f" ({sample['mem_percent']:5.1f}%)"

                logger.info(
                    "CPU %6.2f%% | %s | DISK R %8.3f MB / W %8.3f MB | NET RX %8.3f MB / TX %8.3f MB",
                    sample["cpu_percent"],
                    mem_part,
                    sample["blk_read_mb"], sample["blk_write_mb"],
                    sample["net_rx_mb"], sample["net_tx_mb"],
                )
                # logger.info(f"timestamp: {sample['timestamp']}")

            if self.on_sample:
                try:
                    self.on_sample(dict(sample))
                except Exception as e:
                    logger.exception("on_sample callback error: %s", e)

    def _take_final_snapshot(self) -> None:
        try:
            if docker is None:
                return
            client = docker.from_env()
            container = self._resolve_container(client)
            stats = container.stats(stream=False, decode=True)

            mem_mb = round(_compute_mem_used_mb(stats), 2)
            mem_limit_mb = _compute_mem_limit_mb(stats)
            mem_percent = _compute_mem_percent(mem_mb, mem_limit_mb)

            sample = {
                "timestamp": int(time.time() * 1000),
                "cpu_percent": round(_compute_cpu_percent(stats), 2),  # may be 0.0 without precpu
                "mem_mb": mem_mb,
                "mem_limit_mb": round(mem_limit_mb, 2) if mem_limit_mb is not None else None,
                "mem_percent": round(mem_percent, 2) if mem_percent is not None else None,
            }
            br, bw = self._compute_blkio_mb_with_fallback(stats)
            rx, tx = _compute_net_mb(stats)
            sample.update({
                "blk_read_mb": round(br, 3),
                "blk_write_mb": round(bw, 3),
                "net_rx_mb": round(rx, 3),
                "net_tx_mb": round(tx, 3),
            })
            self._last_sample = sample
        except Exception:
            pass

    def get_window_totals(self) -> Optional[Dict[str, float]]:
        if not self._baseline or not self._last_sample:
            return None
        def delta(key):
            cur = float(self._last_sample.get(key, 0.0))
            base = float(self._baseline.get(key, 0.0))
            return max(0.0, round(cur - base, 3))
        return {
            "blk_read_mb_total": delta("blk_read_mb"),
            "blk_write_mb_total": delta("blk_write_mb"),
            "net_rx_mb_total": delta("net_rx_mb"),
            "net_tx_mb_total": delta("net_tx_mb"),
        }

    def get_last_sample(self) -> Optional[Dict[str, Any]]:
        return self._last_sample

# ---------- demo ----------
# if __name__ == "__main__":
#     import logging
#     logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
#     monitor = DockerContainerMonitor(container_ref="validator1", interval=1.0, csv_path="validator1_stats.csv", stdout=True)
#     try:
#         monitor.start()
#         time.sleep(10)
#     except KeyboardInterrupt:
#         pass
#     finally:
#         monitor.stop()
#         logger.info("Window totals: %s", monitor.get_window_totals())

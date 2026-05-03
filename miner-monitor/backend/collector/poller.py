"""
Background Poller
Uses friend's working approach: poll summary, then poll stats separately,
merge stats fields directly into the summary dict before extracting values.
This matches exactly what works in production with L3+ Hiveon firmware.
"""
import asyncio, logging
from datetime import datetime, timezone
from typing import Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("poller")
OFFLINE_THRESHOLD = 3

# Cumulative fields — always increasing, store delta instead of raw value
CUMULATIVE_FIELDS = {
    "Hardware Errors", "chain_hw1", "chain_hw2", "chain_hw3", "chain_hw4",
    "no_matching_work", "Accepted", "Rejected", "Discarded",
}

def _try_float(v):
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return float(v)
    if isinstance(v, str):
        try: return float(v.strip())
        except: return None
    return None


def _extract_numeric_from_merged(raw: dict) -> dict:
    """
    Extract all numeric fields from a merged cgminer response dict.
    Handles string-encoded numbers. Skips metadata and chip-status strings.
    """
    SKIP = {
        "id", "When", "Code", "Elapsed", "STATUS", "Description", "Msg",
        "CGMiner", "Miner", "CompileTime", "Type", "ID", "STATS",
        "chain_acs1", "chain_acs2", "chain_acs3", "chain_acs4",
        "chain_acs5", "chain_acs6",
        "Min", "Max", "Wait", "Calls", "fan_num", "temp_num",
    }
    result = {}

    def walk(obj, skip_section=False):
        if isinstance(obj, dict):
            for k, v in obj.items():
                s = skip_section or k in ("STATUS", "status")
                if not s and k not in SKIP:
                    fv = _try_float(v)
                    if fv is not None and k not in result:
                        result[k] = fv
                    elif isinstance(v, (dict, list)):
                        walk(v, s)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, skip_section)

    walk(raw)
    return result


def _apply_deltas(current: dict, previous: dict) -> dict:
    """Replace cumulative field values with delta since last reading."""
    result = {}
    for k, v in current.items():
        if k in CUMULATIVE_FIELDS and k in previous:
            result[k] = max(0.0, v - previous[k])
        else:
            result[k] = v
    return result


def extract_values_robust(preset_id: str, numeric: dict, registry, miner_id: str = "") -> dict:
    """
    Map numeric fields to preset labels.
    Falls back to returning all numeric fields if preset matches nothing.
    """
    preset = registry.get_preset(preset_id)
    if preset:
        result = {}
        for feat in preset.get("features", []):
            raw_key = feat.get("raw_key", "")
            label   = feat.get("label", raw_key)
            if raw_key and raw_key in numeric:
                result[label] = numeric[raw_key]
            elif label and label != raw_key and label in numeric:
                result[label] = numeric[label]
        if result:
            logger.debug(f"{miner_id}: preset matched {len(result)} fields")
            return result

    # Fallback — return everything
    if numeric:
        logger.info(f"{miner_id}: preset '{preset_id}' matched 0 — returning all {len(numeric)} fields")
        return numeric
    return {}


class MinerPoller:

    def __init__(self):
        self._scheduler   = AsyncIOScheduler()
        self._jobs: dict  = {}
        self._modes: dict = {}
        self._failures: dict = {}
        self._offline: set = set()
        self._prev_values: dict = {}   # for delta computation
        self._on_reading: list[Callable] = []

    def on_reading(self, cb): self._on_reading.append(cb)

    def start(self):
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Poller started")

    def stop(self):
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def is_offline(self, mid): return mid in self._offline

    def add_miner(self, miner_id, ip, port=4028, preset_id="antminer_l3", interval_seconds=30):
        if miner_id in self._jobs: self.remove_miner(miner_id)
        self._modes.pop(miner_id, None)
        self._failures[miner_id] = 0
        self._offline.discard(miner_id)
        self._prev_values.pop(miner_id, None)

        async def _poll():
            from backend.collector.socket_client import poll_miner_sync, _is_http_bridge, MinerOfflineError
            from backend.collector.preset_registry import registry as reg

            ts = datetime.now(timezone.utc)
            try:
                # Detect HTTP bridge vs direct TCP once, cache it
                if miner_id not in self._modes:
                    self._modes[miner_id] = _is_http_bridge(ip, port)
                    logger.info(
                        f"{miner_id}: mode={'bridge' if self._modes[miner_id] else 'tcp'} "
                        f"({ip}:{port})"
                    )
                use_http = self._modes[miner_id]

                # ── Step 1: poll summary ────────────────────────────────────
                raw = poll_miner_sync(ip, port, "summary", use_http)

                # ── Step 2: poll stats, merge fields into raw dict ──────────
                # This is the approach that works: merge stats fields directly
                # into the summary response dict so extract_values_robust sees
                # all fields (temp, fan, frequency, voltage, chain data) in one place.
                try:
                    raw_stats = poll_miner_sync(ip, port, "stats", use_http)
                    stats_section = raw_stats.get("STATS", [])
                    for item in stats_section:
                        if not isinstance(item, dict): continue
                        # Skip the firmware info item
                        if "CGMiner" in item or "CompileTime" in item: continue
                        for k, v in item.items():
                            # Only add if not already in raw (summary takes priority)
                            if k not in raw:
                                raw[k] = v
                    logger.debug(f"{miner_id}: stats merged successfully")
                except Exception as e:
                    logger.warning(f"{miner_id}: stats poll failed ({e}) — no temp/fan data")

                # ── Step 3: extract all numeric fields ─────────────────────
                numeric = _extract_numeric_from_merged(raw)

                # ── Step 4: map to preset labels ─────────────────────────
                # NO delta computation — trainer extracts only instantaneous
                # features (hashrate, temps, fans) and ignores cumulative counters
                values = extract_values_robust(preset_id, numeric, reg, miner_id)

                # ── Success ─────────────────────────────────────────────────
                self._failures[miner_id] = 0
                if miner_id in self._offline:
                    self._offline.discard(miner_id)
                    logger.info(f"{miner_id}: back online")

                if values:
                    for cb in self._on_reading:
                        try: await cb(miner_id, ts, values)
                        except Exception as e: logger.error(f"Callback {miner_id}: {e}")
                    logger.debug(f"{miner_id}: {len(values)} fields")
                else:
                    logger.warning(f"{miner_id}: 0 values — numeric keys: {list(numeric.keys())[:10]}")

            except MinerOfflineError as e:
                await self._handle_failure(miner_id, ts, str(e))
            except Exception as e:
                self._modes.pop(miner_id, None)  # reset so next poll re-detects mode
                await self._handle_failure(miner_id, ts, str(e))

        job = self._scheduler.add_job(
            _poll,
            trigger=IntervalTrigger(seconds=interval_seconds),
            id=f"poll_{miner_id}",
            replace_existing=True,
            next_run_time=datetime.now(timezone.utc),
        )
        self._jobs[miner_id] = job.id
        logger.info(f"Polling {miner_id} every {interval_seconds}s (summary + stats)")

    async def _handle_failure(self, miner_id, ts, reason):
        self._failures[miner_id] = self._failures.get(miner_id, 0) + 1
        count = self._failures[miner_id]
        logger.warning(f"{miner_id}: failure {count}/{OFFLINE_THRESHOLD} — {reason}")
        if count >= OFFLINE_THRESHOLD and miner_id not in self._offline:
            self._offline.add(miner_id)
            logger.warning(f"{miner_id}: MARKED OFFLINE")
            for cb in self._on_reading:
                try: await cb(miner_id, ts, {"_offline": 1.0})
                except: pass

    def remove_miner(self, miner_id):
        job_id = self._jobs.pop(miner_id, None)
        self._modes.pop(miner_id, None)
        self._failures.pop(miner_id, None)
        self._offline.discard(miner_id)
        self._prev_values.pop(miner_id, None)
        if job_id and self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

    def update_interval(self, miner_id, seconds):
        job_id = self._jobs.get(miner_id)
        if job_id:
            job = self._scheduler.get_job(job_id)
            if job: job.reschedule(trigger=IntervalTrigger(seconds=seconds))

    @property
    def active_miners(self): return list(self._jobs.keys())


poller = MinerPoller()

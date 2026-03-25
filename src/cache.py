"""
Shared in-process result cache for visa portal checks.

Previously duplicated between checker.py and worker_pool.py — now a
single source of truth imported by both.

TTL is configurable via CACHE_TTL_SECONDS env var (default: 180 s / 3 min).

Cleanup:
  A background daemon thread runs every CLEANUP_INTERVAL seconds and
  evicts expired entries so the dict doesn't grow unbounded.
"""

from __future__ import annotations
import hashlib
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_TTL        = int(os.getenv("CACHE_TTL_SECONDS", "180"))
CLEANUP_INTERVAL = 60   # seconds between cleanup sweeps


_cache: dict[str, tuple[dict, float]] = {}
_cache_lock = threading.Lock()
_cleanup_started = False


def cache_key(passport: str, name: str, dob: str) -> str:
    raw = f"{passport.upper()}|{name.upper()}|{dob}"
    return hashlib.md5(raw.encode()).hexdigest()


def cache_get(key: str) -> Optional[dict]:
    with _cache_lock:
        entry = _cache.get(key)
    if entry and (time.time() - entry[1]) < CACHE_TTL:
        return entry[0]
    return None


def cache_put(key: str, result: dict) -> None:
    """Cache a successful result. Errors and NOT_FOUND are never cached."""
    if result.get("status_en") in ("ERROR", "NOT_FOUND", None):
        return
    with _cache_lock:
        _cache[key] = (result, time.time())
    # Start cleanup thread on first put (lazy init)
    _ensure_cleanup_running()


def cache_clear() -> None:
    """Clear all cached results (e.g. for testing)."""
    with _cache_lock:
        _cache.clear()
    logger.debug("Result cache cleared")


def cache_stats() -> dict:
    """Return cache size and TTL for monitoring."""
    with _cache_lock:
        total = len(_cache)
        now = time.time()
        alive = sum(1 for _, ts in _cache.values() if now - ts < CACHE_TTL)
    return {"total_entries": total, "alive": alive, "expired": total - alive, "ttl": CACHE_TTL}


# ── Background cleanup ───────────────────────────────────────────────────────

def _evict_expired() -> int:
    """Remove expired entries from cache. Returns number of evicted entries."""
    now = time.time()
    with _cache_lock:
        expired_keys = [k for k, (_, ts) in _cache.items() if now - ts >= CACHE_TTL]
        for k in expired_keys:
            del _cache[k]
    if expired_keys:
        logger.debug("Cache cleanup: evicted %d expired entries, %d remain",
                      len(expired_keys), len(_cache))
    return len(expired_keys)


def _cleanup_loop() -> None:
    """Background loop that runs every CLEANUP_INTERVAL seconds."""
    while True:
        time.sleep(CLEANUP_INTERVAL)
        try:
            _evict_expired()
        except Exception as exc:
            logger.warning("Cache cleanup error: %s", exc)


def _ensure_cleanup_running() -> None:
    """Start the cleanup daemon thread (once)."""
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True
    t = threading.Thread(target=_cleanup_loop, daemon=True, name="cache-cleanup")
    t.start()
    logger.debug("Cache cleanup thread started (interval=%ds, ttl=%ds)",
                 CLEANUP_INTERVAL, CACHE_TTL)

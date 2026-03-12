"""
Shared in-process result cache for visa portal checks.

Previously duplicated between checker.py and worker_pool.py — now a
single source of truth imported by both.

TTL is configurable via CACHE_TTL_SECONDS env var (default: 300 s / 5 min).
"""

from __future__ import annotations
import hashlib
import logging
import os
import threading
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))

_cache: dict[str, tuple[dict, float]] = {}
_cache_lock = threading.Lock()


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


def cache_clear() -> None:
    """Clear all cached results (e.g. for testing)."""
    with _cache_lock:
        _cache.clear()
    logger.debug("Result cache cleared")

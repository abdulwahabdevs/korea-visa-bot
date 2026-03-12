"""
Per-user cooldown rate limiter.

Prevents a single user from spamming /mystatus or /check and queueing
many portal checks with different credentials.

Cooldown is configurable via USER_COOLDOWN_SECONDS env var (default: 30 s).
"""

from __future__ import annotations
import os
import threading
import time
from typing import Optional

USER_COOLDOWN = int(os.getenv("USER_COOLDOWN_SECONDS", "30"))

_last_check: dict[int, float] = {}
_lock = threading.Lock()


def check_rate_limit(user_id: int) -> Optional[int]:
    """
    Check if user is within cooldown.

    Returns:
      None      — user is allowed (not rate-limited)
      int > 0   — seconds remaining until they can check again
    """
    now = time.time()
    with _lock:
        last = _last_check.get(user_id, 0.0)
        elapsed = now - last
        if elapsed < USER_COOLDOWN:
            return int(USER_COOLDOWN - elapsed) + 1
        return None


def record_check(user_id: int) -> None:
    """Record that a user just performed a check (start their cooldown)."""
    with _lock:
        _last_check[user_id] = time.time()

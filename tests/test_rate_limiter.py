"""
Tests for src/rate_limiter.py — per-user cooldown.
"""

import time
import pytest
from src.rate_limiter import check_rate_limit, record_check, USER_COOLDOWN, _last_check, _lock


class TestRateLimiter:
    def setup_method(self):
        """Clear all rate-limit state between tests."""
        with _lock:
            _last_check.clear()

    def test_first_check_not_limited(self):
        """A user who has never checked should NOT be rate-limited."""
        assert check_rate_limit(999) is None

    def test_after_record_is_limited(self):
        """Immediately after a check, user should be rate-limited."""
        uid = 1001
        record_check(uid)
        wait = check_rate_limit(uid)
        assert wait is not None
        assert wait > 0
        assert wait <= USER_COOLDOWN + 1

    def test_cooldown_expires(self):
        """After USER_COOLDOWN seconds, user should be allowed again."""
        uid = 1002
        record_check(uid)
        # Fake the timestamp to be in the past
        with _lock:
            _last_check[uid] = time.time() - USER_COOLDOWN - 1
        assert check_rate_limit(uid) is None

    def test_different_users_independent(self):
        """Rate limit for user A should not affect user B."""
        record_check(2001)
        assert check_rate_limit(2001) is not None  # A is limited
        assert check_rate_limit(2002) is None       # B is free

    def test_wait_seconds_decrease(self):
        """Wait time should decrease as cooldown progresses."""
        uid = 3001
        record_check(uid)
        wait1 = check_rate_limit(uid)
        time.sleep(1)
        wait2 = check_rate_limit(uid)
        assert wait2 < wait1

    def test_record_resets_cooldown(self):
        """Recording a new check should reset the cooldown timer."""
        uid = 4001
        record_check(uid)
        # Fast-forward past cooldown
        with _lock:
            _last_check[uid] = time.time() - USER_COOLDOWN - 1
        assert check_rate_limit(uid) is None  # expired
        # Record again
        record_check(uid)
        assert check_rate_limit(uid) is not None  # limited again

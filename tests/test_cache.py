"""
Tests for src/cache.py — in-process result cache with TTL.
"""

import time
import pytest
from src.cache import (
    cache_key, cache_get, cache_put, cache_clear,
    cache_stats, _evict_expired, CACHE_TTL,
)


class TestCacheKey:
    def test_consistent(self):
        """Same inputs → same key."""
        k1 = cache_key("FA4166021", "SOMEONOV SOMEONE", "19981217")
        k2 = cache_key("FA4166021", "SOMEONOV SOMEONE", "19981217")
        assert k1 == k2

    def test_case_insensitive(self):
        """Passport/name casing shouldn't matter."""
        k1 = cache_key("fa4166021", "someonov someone", "19981217")
        k2 = cache_key("FA4166021", "SOMEONOV SOMEONE", "19981217")
        assert k1 == k2

    def test_different_inputs(self):
        k1 = cache_key("FA4166021", "SOMEONOV SOMEONE", "19981217")
        k2 = cache_key("AB1234567", "OTHEROV OTHER",    "20010315")
        assert k1 != k2


class TestCachePutGet:
    def setup_method(self):
        cache_clear()

    def test_put_then_get(self):
        """Cached result should be retrievable."""
        key = "test_key_1"
        data = {"status_en": "APPROVED", "status_ko": "허가"}
        cache_put(key, data)
        result = cache_get(key)
        assert result is not None
        assert result["status_en"] == "APPROVED"

    def test_error_not_cached(self):
        """ERROR results should never be cached."""
        key = "test_key_error"
        cache_put(key, {"status_en": "ERROR", "reason": "timeout"})
        assert cache_get(key) is None

    def test_not_found_not_cached(self):
        """NOT_FOUND results should never be cached."""
        key = "test_key_nf"
        cache_put(key, {"status_en": "NOT_FOUND"})
        assert cache_get(key) is None

    def test_none_status_not_cached(self):
        """None status should not be cached."""
        key = "test_key_none"
        cache_put(key, {"status_en": None})
        assert cache_get(key) is None

    def test_miss_returns_none(self):
        assert cache_get("nonexistent_key") is None

    def test_overwrite(self):
        """Putting a new value for the same key overwrites."""
        key = "test_key_overwrite"
        cache_put(key, {"status_en": "PENDING"})
        cache_put(key, {"status_en": "APPROVED"})
        result = cache_get(key)
        assert result["status_en"] == "APPROVED"


class TestCacheTTL:
    """CACHE_TTL_SECONDS is set to 5 in conftest.py for fast tests."""

    def setup_method(self):
        cache_clear()

    def test_expired_entry_not_returned(self):
        """After TTL, cache_get should return None."""
        key = "test_key_ttl"
        cache_put(key, {"status_en": "APPROVED"})
        assert cache_get(key) is not None

        # Wait for TTL to expire (conftest sets CACHE_TTL_SECONDS=5)
        time.sleep(CACHE_TTL + 1)
        assert cache_get(key) is None


class TestCacheClear:
    def test_clear_empties_cache(self):
        key = "test_key_clear"
        cache_put(key, {"status_en": "APPROVED"})
        assert cache_get(key) is not None
        cache_clear()
        assert cache_get(key) is None


class TestCacheStats:
    def setup_method(self):
        cache_clear()

    def test_empty_stats(self):
        stats = cache_stats()
        assert stats["total_entries"] == 0
        assert stats["alive"] == 0
        assert stats["expired"] == 0

    def test_stats_with_entries(self):
        cache_put("k1", {"status_en": "APPROVED"})
        cache_put("k2", {"status_en": "PENDING"})
        stats = cache_stats()
        assert stats["total_entries"] == 2
        assert stats["alive"] == 2


class TestCacheEviction:
    def setup_method(self):
        cache_clear()

    def test_evict_expired_removes_old_entries(self):
        cache_put("old_key", {"status_en": "APPROVED"})
        assert cache_stats()["total_entries"] == 1

        # Wait for TTL to expire (conftest sets CACHE_TTL_SECONDS=5)
        time.sleep(CACHE_TTL + 1)
        evicted = _evict_expired()
        assert evicted == 1
        assert cache_stats()["total_entries"] == 0

    def test_evict_keeps_fresh_entries(self):
        cache_put("fresh_key", {"status_en": "APPROVED"})
        evicted = _evict_expired()
        assert evicted == 0
        assert cache_stats()["total_entries"] == 1

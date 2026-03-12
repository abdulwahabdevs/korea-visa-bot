"""
Checker — orchestrator between the Telegram bot and the Selenium scraper.

Two public check methods:
  check_evisa(receipt, passport)           — E-Visa Individual (admin)
  check_diplomatic(passport, name, dob)    — Diplomatic Office (student)

Speed optimisations:
  OPT-E  Result cache: identical queries within CACHE_TTL seconds return
         the cached result instantly without hitting the portal at all.
         Cache lives in src/cache.py (shared with worker_pool).

  OPT-F  pre_warm(): loads the portal page in the background so the first
         real check skips the initial page load entirely (OPT-B in facade).
         Called from bot/app.py post_init hook in a background thread.
"""

from __future__ import annotations
import logging
import re
import threading
from datetime import datetime
from typing import Optional

from .scraper.driver_factory import build_driver
from .scraper.facade import (
    check_evisa as _check_evisa,
    check_diplomatic as _check_diplomatic,
    _load_portal,
)
from .scraper.status_parser import parse_portal_result
from .cache import cache_key, cache_get, cache_put, cache_clear  # shared cache

logger = logging.getLogger(__name__)

# Re-export cache_clear for callers that imported it from here
__all__ = [
    "cache_clear", "ValidationError",
    "validate_receipt", "validate_passport", "validate_name", "validate_dob",
    "VisaChecker", "get_checker", "close_checker",
]


# ── Input validation ──────────────────────────────────────────────────────────

class ValidationError(ValueError):
    pass


def validate_receipt(receipt: str) -> str:
    cleaned = re.sub(r"\s", "", receipt).strip()
    if not re.fullmatch(r"\d{10}", cleaned):
        raise ValidationError("receipt_format")
    return cleaned


def validate_passport(passport: str) -> str:
    cleaned = re.sub(r"\s", "", passport).strip().upper()
    if not re.fullmatch(r"[A-Z]{1,2}\d{7,8}", cleaned):
        raise ValidationError("passport_format")
    return cleaned


def validate_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name.strip()).upper()
    if len(cleaned) < 2:
        raise ValidationError("name_format")
    if not re.fullmatch(r"[A-Z\s\-']+", cleaned):
        raise ValidationError("name_format")
    return cleaned


def validate_dob(dob: str) -> str:
    """Accept YYYYMMDD, YYYY-MM-DD, YYYY.MM.DD → return YYYYMMDD."""
    cleaned = re.sub(r"[\s.\-/]", "", dob.strip())
    if not re.fullmatch(r"\d{8}", cleaned):
        raise ValidationError("dob_format")
    year  = int(cleaned[:4])
    month = int(cleaned[4:6])
    day   = int(cleaned[6:])
    if not (1900 <= year <= 2020 and 1 <= month <= 12 and 1 <= day <= 31):
        raise ValidationError("dob_format")
    return cleaned


# ── Checker class ─────────────────────────────────────────────────────────────

class VisaChecker:
    """
    Manages a single Chrome session.
    Restarts Chrome automatically after 3 consecutive errors.

    Extra capabilities:
      • pre_warm()         — loads portal in background thread at startup.
      • check_diplomatic() — uses shared OPT-E result cache.
    """
    _MAX_ERRORS = 3

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._driver   = None
        self._errors   = 0
        self._lock     = threading.Lock()   # one check at a time

    def _get_driver(self):
        if self._driver is None:
            logger.info("Starting Chrome WebDriver (headless=%s)", self._headless)
            self._driver = build_driver(headless=self._headless)
        return self._driver

    def _restart(self):
        logger.warning("Restarting Chrome WebDriver")
        try:
            self._driver and self._driver.quit()
        except Exception:
            pass
        self._driver = None
        self._errors = 0

    def _build_result(self, raw: dict, receipt: str = "") -> dict:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if raw.get("not_found"):
            self._errors = 0
            return {"status_en": "NOT_FOUND", "status_ko": "조회된 데이터가 없습니다",
                    "visa_type": "", "app_date": "", "reason": "",
                    "checked_at": now, "receipt": receipt}
        if raw.get("error"):
            self._errors += 1
            return {"status_en": "ERROR", "status_ko": "",
                    "visa_type": "", "app_date": "", "reason": raw["error"],
                    "checked_at": now, "receipt": receipt}
        self._errors = 0
        raw["receipt"] = receipt
        if raw.get("status_en") and raw["status_en"] not in ("", "UNKNOWN"):
            return {
                "status_en":  raw["status_en"],
                "status_ko":  raw.get("status_ko", ""),
                "visa_type":  raw.get("visa_type", ""),
                "app_date":   raw.get("app_date", ""),
                "reason":     raw.get("reason", ""),
                "checked_at": now,
                "receipt":    receipt,
            }
        parsed = parse_portal_result(raw)
        return {"status_en": parsed.status_en, "status_ko": parsed.status_ko,
                "visa_type": parsed.visa_type, "app_date": parsed.app_date,
                "reason": parsed.reason, "checked_at": now, "receipt": receipt}

    # ── OPT-F: Pre-warm ───────────────────────────────────────────────────

    def pre_warm(self) -> None:
        """
        OPT-F: Background pre-warm.
        Starts Chrome and loads the portal page so the first real check
        hits an already-loaded page (OPT-B skips driver.get() entirely).
        Called in a daemon thread from bot/app.py post_init.
        """
        def _warm():
            try:
                logger.info("Pre-warming Chrome + portal page …")
                with self._lock:
                    driver = self._get_driver()
                    _load_portal(driver)
                logger.info("✅ Chrome pre-warm complete — portal ready")
            except Exception as exc:
                logger.warning("Pre-warm failed (non-critical): %s", exc)

        t = threading.Thread(target=_warm, daemon=True, name="chrome-prewarm")
        t.start()

    # ── Public check methods ──────────────────────────────────────────────

    def check_evisa(self, receipt: str, passport: str,
                    name: str = "", dob: str = "") -> dict:
        """Check via E-Visa tab (admin use).

        Portal requires all 4 fields: receipt, passport, name, DOB.
        name: UPPERCASE Latin full name (e.g. "KODIROV MUKHAMMADSODIK")
        dob:  YYYYMMDD (e.g. "19981217")
        """
        if self._errors >= self._MAX_ERRORS:
            self._restart()
        with self._lock:
            try:
                driver = self._get_driver()
                raw = _check_evisa(driver, receipt, passport, name, dob)
            except Exception as exc:
                logger.error("Driver error (evisa): %s", exc)
                self._restart()
                return self._build_result({"error": str(exc)}, receipt)
        return self._build_result(raw, receipt)

    def check_diplomatic(self, passport: str, name: str, dob: str) -> dict:
        """
        Check via Diplomatic tab (student use: passport + name + DOB).
        OPT-E: returns cached result if queried within CACHE_TTL seconds.
        """
        # ── OPT-E: shared cache lookup ────────────────────────────────────
        key = cache_key(passport, name, dob)
        cached = cache_get(key)
        if cached:
            logger.info("Cache hit for passport=%s — skipping portal check", passport)
            cached = dict(cached)
            cached["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            cached["cached"] = True
            return cached

        if self._errors >= self._MAX_ERRORS:
            self._restart()

        with self._lock:
            try:
                driver = self._get_driver()
                raw = _check_diplomatic(driver, passport, name, dob)
            except Exception as exc:
                logger.error("Driver error (diplomatic): %s", exc)
                self._restart()
                return self._build_result({"error": str(exc)})

        result = self._build_result(raw)
        cache_put(key, result)
        return result

    def close(self):
        if self._driver:
            try: self._driver.quit()
            except Exception: pass
            self._driver = None

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


# ── Global singleton ──────────────────────────────────────────────────────────

_checker: Optional[VisaChecker] = None


def get_checker(headless: bool = True) -> VisaChecker:
    global _checker
    if _checker is None:
        _checker = VisaChecker(headless=headless)
    return _checker


def close_checker():
    global _checker
    if _checker:
        _checker.close()
        _checker = None

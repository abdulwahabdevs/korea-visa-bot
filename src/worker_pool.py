"""
Chrome Worker Pool — concurrent visa portal checks.

Architecture
────────────
Instead of one global Chrome instance protected by a single mutex
(which serialises EVERY check), we maintain a pool of N independent
Chrome workers.  Each worker owns its own WebDriver session and its
own threading.Lock.  The pool hands out the first idle worker; if all
workers are busy it queues the request and waits.

              ┌─────────────────────────────────┐
              │         WorkerPool               │
              │  ┌───────┐ ┌───────┐ ┌───────┐  │
  request ───►│  │ W-1   │ │ W-2   │ │ W-3   │  │
              │  │Chrome │ │Chrome │ │Chrome │  │
              │  └───────┘ └───────┘ └───────┘  │
              │      idle     busy    idle       │
              └─────────────────────────────────┘
                       ▲
              next free worker assigned

Key properties
──────────────
• Pool size   : configured via POOL_SIZE env-var (default 3).
• Thread-safe : a queue.Queue hands out worker tokens; get() blocks
                only when ALL workers are occupied.
• Isolation   : a crash / restart in W-2 has zero effect on W-1 & W-3.
• Bulk check  : each row in /checkall runs on a separate worker in
                parallel — a 30-row checkall completes in ~10 min
                instead of ~30 min.
• Pre-warm    : all workers load the portal at startup so the first
                real check on every worker hits a hot page.
• Result cache: shared 5-min in-process cache (OPT-E) — a student
                who just checked will get an instant reply even if
                another worker is busy.
"""

from __future__ import annotations
import logging
import os
import queue
import threading
import time
from datetime import datetime
from typing import Optional

from .scraper.driver_factory import build_driver
from selenium.common.exceptions import WebDriverException
from .scraper.facade import (
    check_evisa as _check_evisa,
    check_diplomatic as _check_diplomatic,
    download_approval_cert as _download_cert,
    _load_portal,
    CERT_DOWNLOAD_DIR,
)
from .scraper.status_parser import parse_portal_result
from .cache import cache_key as _cache_key, cache_get as _cache_get, cache_put as _cache_put, cache_clear  # shared cache

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
POOL_SIZE       = int(os.environ.get("CHROME_POOL_SIZE", "2"))
RESTART_BACKOFF = int(os.environ.get("WORKER_RESTART_BACKOFF", "5"))


# ── Single Worker ─────────────────────────────────────────────────────────────

class _Worker:
    """
    One Chrome session.  The pool keeps N of these.
    Each worker is single-threaded (one check at a time per session).
    """
    _MAX_ERRORS = 3

    def __init__(self, wid: int, headless: bool = True):
        self._id       = wid
        self._headless = headless
        self._driver   = None
        self._errors   = 0
        self._lock     = threading.Lock()   # guards this worker's driver

    # ── Internal helpers ──────────────────────────────────────────────────

    def _get_driver(self):
        if self._driver is None:
            logger.info("[W%d] Starting Chrome (headless=%s)", self._id, self._headless)
            self._driver = build_driver(headless=self._headless)
        return self._driver

    def _restart(self):
        logger.warning("[W%d] Restarting Chrome", self._id)
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

    # ── Public check methods ──────────────────────────────────────────────

    def check_evisa(self, receipt: str, passport: str,
                    name: str = "", dob: str = "") -> dict:
        """Run an e-visa check, with one automatic post-crash retry.

        Flow
        ────
        Attempt 1  ──►  success?  ──►  return result
                    └─►  WebDriverException?
                              ├─ _restart() (kills dead Chrome, spawns fresh)
                              ├─ sleep(RESTART_BACKOFF)
                              └─►  Attempt 2  ──►  success?  ──►  return result
                                               └─►  any error  ──►  return ERROR
        """
        if self._errors >= self._MAX_ERRORS:
            self._restart()
        with self._lock:
            for _attempt in range(1, 3):   # attempt 1, then 1 post-crash retry
                try:
                    driver = self._get_driver()
                    raw    = _check_evisa(driver, receipt, passport, name, dob)
                    return self._build_result(raw, receipt)   # ← success path

                except WebDriverException as exc:
                    err_str = str(exc)
                    is_crash = any(k in err_str for k in (
                        "ERR_CONNECTION", "renderer", "session deleted",
                        "no such session", "chrome not reachable"))
                    if is_crash:
                        logger.error(
                            "[W%d] Chrome crashed (attempt %d) — restarting in %ds: %s",
                            self._id, _attempt, RESTART_BACKOFF, err_str[:120])
                    else:
                        logger.error("[W%d] evisa WebDriver error (attempt %d): %s",
                                     self._id, _attempt, err_str[:120])
                    self._restart()
                    if _attempt < 2:
                        logger.info("[W%d] Waiting %ds before retry …",
                                    self._id, RESTART_BACKOFF)
                        time.sleep(RESTART_BACKOFF)
                        continue   # ← retry on fresh driver
                    return self._build_result({"error": err_str[:200]}, receipt)

                except Exception as exc:
                    logger.error("[W%d] evisa error (attempt %d): %s",
                                 self._id, _attempt, exc)
                    self._restart()
                    if _attempt < 2:
                        time.sleep(RESTART_BACKOFF)
                        continue
                    return self._build_result({"error": str(exc)}, receipt)
        # unreachable — loop always returns
        return self._build_result({"error": "check_evisa: unexpected loop exit"}, receipt)

    def check_diplomatic(self, passport: str, name: str, dob: str) -> dict:
        """Run a diplomatic/student visa check, with one automatic post-crash retry.

        Same retry flow as check_evisa: crash → restart → backoff → retry once.
        """
        if self._errors >= self._MAX_ERRORS:
            self._restart()
        with self._lock:
            for _attempt in range(1, 3):
                try:
                    driver = self._get_driver()
                    raw    = _check_diplomatic(driver, passport, name, dob)
                    return self._build_result(raw)   # ← success path

                except WebDriverException as exc:
                    err_str = str(exc)
                    is_crash = any(k in err_str for k in (
                        "ERR_CONNECTION", "renderer", "session deleted",
                        "no such session", "chrome not reachable"))
                    if is_crash:
                        logger.error(
                            "[W%d] Chrome crashed (attempt %d) — restarting in %ds: %s",
                            self._id, _attempt, RESTART_BACKOFF, err_str[:120])
                    else:
                        logger.error("[W%d] diplomatic WebDriver error (attempt %d): %s",
                                     self._id, _attempt, err_str[:120])
                    self._restart()
                    if _attempt < 2:
                        logger.info("[W%d] Waiting %ds before retry …",
                                    self._id, RESTART_BACKOFF)
                        time.sleep(RESTART_BACKOFF)
                        continue
                    return self._build_result({"error": err_str[:200]})

                except Exception as exc:
                    logger.error("[W%d] diplomatic error (attempt %d): %s",
                                 self._id, _attempt, exc)
                    self._restart()
                    if _attempt < 2:
                        time.sleep(RESTART_BACKOFF)
                        continue
                    return self._build_result({"error": str(exc)})
        return self._build_result({"error": "check_diplomatic: unexpected loop exit"})

    def pre_warm(self, stagger_seconds: float = 0.0) -> None:
        """Start portal pre-warm in background, optionally after a stagger delay.

        stagger_seconds lets the pool space out workers so they don't all
        hammer the portal simultaneously (rate-limiting prevention).
        """
        def _warm():
            if stagger_seconds > 0:
                logger.info("[W%d] Pre-warm staggered %.1f s …", self._id, stagger_seconds)
                time.sleep(stagger_seconds)
            try:
                logger.info("[W%d] Pre-warming portal …", self._id)
                with self._lock:
                    ok = _load_portal(self._get_driver())
                if ok:
                    logger.info("[W%d] ✅ Portal pre-warmed", self._id)
                else:
                    logger.warning("[W%d] ⚠️  Portal pre-warm incomplete (radio buttons not ready); "
                                   "workers will reload on first real check", self._id)
            except Exception as exc:
                logger.warning("[W%d] Pre-warm failed: %s", self._id, exc)
        threading.Thread(target=_warm, daemon=True,
                         name=f"prewarm-w{self._id}").start()

    def download_cert(self, passport: str, name: str, dob: str) -> dict:
        """Download approval cert on a fresh dedicated Chrome session.

        Does NOT reuse self._driver because the download driver needs
        Chrome prefs set to a specific download directory at launch time.
        The pool worker slot is held during the download to apply back-pressure.
        """
        import os as _os, tempfile as _tf
        _os.makedirs(CERT_DOWNLOAD_DIR, exist_ok=True)
        tmp_dir = _tf.mkdtemp(prefix=f"cert_w{self._id}_", dir=CERT_DOWNLOAD_DIR)
        logger.info("[W%d] cert download — tmp dir: %s", self._id, tmp_dir)
        tmp_driver = None
        try:
            tmp_driver = build_driver(headless=self._headless, download_dir=tmp_dir)
            result = _download_cert(tmp_driver, passport, name, dob)
        except Exception as exc:
            logger.error("[W%d] cert download error: %s", self._id, exc)
            result = {"error": str(exc)}
        finally:
            if tmp_driver:
                try:
                    tmp_driver.quit()
                except Exception:
                    pass
        return result

    def close(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def __repr__(self):
        return f"<Worker id={self._id} errors={self._errors}>"


# ── Worker Pool ───────────────────────────────────────────────────────────────

class WorkerPool:
    """
    Pool of N Chrome workers.

    Usage
    ─────
        pool = WorkerPool(size=3)
        pool.pre_warm()           # fire-and-forget background warm-up

        # Check (blocks only if ALL workers are busy)
        result = pool.check_diplomatic(passport, name, dob)
        result = pool.check_evisa(receipt, passport, name, dob)
    """

    def __init__(self, size: int = POOL_SIZE, headless: bool = True):
        self._workers = [_Worker(i + 1, headless) for i in range(size)]
        # queue acts as a semaphore + FIFO scheduler
        # each token is a worker index
        self._available: queue.Queue[int] = queue.Queue()
        for i in range(size):
            self._available.put(i)
        logger.info("WorkerPool created: %d Chrome workers", size)

    # ── Acquire / release ─────────────────────────────────────────────────

    def _acquire(self) -> tuple[int, _Worker]:
        """Block until a free worker is available, return (slot, worker)."""
        slot = self._available.get()   # blocks if all workers busy
        return slot, self._workers[slot]

    def _release(self, slot: int) -> None:
        self._available.put(slot)

    # ── Public check methods (with cache) ────────────────────────────────

    def check_diplomatic(self, passport: str, name: str, dob: str) -> dict:
        """
        Check student visa (gb03).
        Returns cached result instantly if queried within CACHE_TTL.
        Otherwise borrows an idle worker — queues if all are busy.
        """
        key    = _cache_key(passport, name, dob)
        cached = _cache_get(key)
        if cached:
            logger.info("[pool] Cache hit passport=%s", passport)
            c = dict(cached)
            c["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            c["cached"] = True
            return c

        slot, worker = self._acquire()
        try:
            result = worker.check_diplomatic(passport, name, dob)
        finally:
            self._release(slot)

        _cache_put(key, result)
        return result

    def check_evisa(self, receipt: str, passport: str,
                    name: str = "", dob: str = "") -> dict:
        """
        Check admin E-Visa (gb01).
        Borrows an idle worker — queues if all are busy.
        No cache (admin checks always fresh).
        """
        slot, worker = self._acquire()
        try:
            result = worker.check_evisa(receipt, passport, name, dob)
        finally:
            self._release(slot)
        return result

    def download_cert(self, passport: str, name: str, dob: str) -> dict:
        """Download the visa approval certificate for an approved student.

        Acquires a worker slot (for back-pressure), runs _Worker.download_cert
        which spawns a dedicated Chrome session internally.
        """
        slot, worker = self._acquire()
        try:
            result = worker.download_cert(passport, name, dob)
        finally:
            self._release(slot)
        return result

    # ── Pre-warm all workers ──────────────────────────────────────────────

    # ── Pre-warm stagger constant: seconds between each worker's portal load ──
    _PREWARM_STAGGER = 5  # s — keeps concurrent Chrome→portal connections ≤1

    def pre_warm(self) -> None:
        """Launch staggered background pre-warm threads for every worker.

        Worker-1 starts immediately; Worker-2 waits 5 s; Worker-3 waits 10 s …
        This prevents the portal from receiving N simultaneous GET requests and
        triggering rate-limiting or session blocks.
        """
        for idx, w in enumerate(self._workers):
            w.pre_warm(stagger_seconds=idx * self._PREWARM_STAGGER)

    # ── Stats ─────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return pool status for health monitoring."""
        idle = self._available.qsize()
        total = len(self._workers)
        return {
            "total":   total,
            "idle":    idle,
            "busy":    total - idle,
            "workers": [repr(w) for w in self._workers],
        }

    # ── Cleanup ───────────────────────────────────────────────────────────

    def close(self) -> None:
        for w in self._workers:
            w.close()
        logger.info("WorkerPool closed")

    def __enter__(self): return self
    def __exit__(self, *_): self.close()


# ── Global pool singleton ─────────────────────────────────────────────────────

_pool: Optional[WorkerPool] = None
_pool_lock = threading.Lock()


def get_pool(size: int = POOL_SIZE, headless: bool = True) -> WorkerPool:
    """Return the global WorkerPool, creating it on first call."""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = WorkerPool(size=size, headless=headless)
    return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool:
            _pool.close()
            _pool = None

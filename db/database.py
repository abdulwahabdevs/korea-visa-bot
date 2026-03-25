"""
Database layer — SQLite via the standard library.

Tables:
  users              — Telegram user registry
  student_bindings   — telegram_id → passport + name + dob  (diplomatic mode, no receipt)
  check_results      — audit log of every check
  admin_sessions     — per-session admin auth state (with TTL expiry)
"""

from __future__ import annotations
import os
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Admin sessions expire after this many hours (configurable via env)
SESSION_TTL_HOURS = int(os.getenv("ADMIN_SESSION_TTL_HOURS", "24"))

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "visa_bot.db"

# Override DB_PATH from env if provided
_env_db = os.getenv("DB_PATH", "")
if _env_db:
    DB_PATH = Path(_env_db)


from db.crypto import encrypt, decrypt


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id   INTEGER PRIMARY KEY,
                username      TEXT,
                full_name     TEXT,
                language      TEXT    NOT NULL DEFAULT 'uz',
                role          TEXT    NOT NULL DEFAULT 'student',
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                last_seen     TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS student_bindings (
                telegram_id   INTEGER PRIMARY KEY REFERENCES users(telegram_id),
                passport      TEXT    NOT NULL,
                full_name     TEXT    NOT NULL,
                dob           TEXT    NOT NULL,
                bound_at      TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS check_results (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id   INTEGER REFERENCES users(telegram_id),
                check_type    TEXT    NOT NULL DEFAULT 'diplomatic',
                receipt       TEXT,
                passport      TEXT,
                full_name     TEXT,
                dob           TEXT,
                status_en     TEXT,
                status_ko     TEXT,
                visa_type     TEXT,
                app_date      TEXT,
                reason        TEXT,
                checked_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS admin_sessions (
                telegram_id   INTEGER PRIMARY KEY REFERENCES users(telegram_id),
                authenticated INTEGER NOT NULL DEFAULT 0,
                auth_at       TEXT
            );

            -- Tracks the LATEST known status per passport (for change detection & /stats)
            CREATE TABLE IF NOT EXISTS status_history (
                passport      TEXT    PRIMARY KEY,
                full_name     TEXT,
                dob           TEXT,
                receipt       TEXT,
                check_type    TEXT    NOT NULL DEFAULT 'diplomatic',
                status_en     TEXT,
                status_ko     TEXT,
                visa_type     TEXT,
                app_date      TEXT,
                reason        TEXT,
                first_seen_at TEXT    NOT NULL DEFAULT (datetime('now')),
                last_checked  TEXT    NOT NULL DEFAULT (datetime('now')),
                status_changed_at TEXT
            );

            -- Stores completed bulk check rows for partial export & error retry
            CREATE TABLE IF NOT EXISTS bulk_sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key   TEXT    NOT NULL,
                row_index     INTEGER NOT NULL,
                receipt       TEXT,
                passport      TEXT,
                full_name     TEXT,
                dob           TEXT,
                check_type    TEXT    NOT NULL DEFAULT 'diplomatic',
                status_en     TEXT,
                status_ko     TEXT,
                visa_type     TEXT,
                app_date      TEXT,
                reason        TEXT,
                checked_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                UNIQUE(session_key, row_index)
            );
        """)
    logger.info("Database initialised at %s", DB_PATH)


# ── User helpers ──────────────────────────────────────────────────────────────

def upsert_user(telegram_id: int, username: str = "", full_name: str = "") -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT INTO users (telegram_id, username, full_name, last_seen)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(telegram_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name,
                last_seen = datetime('now')
        """, (telegram_id, username or "", full_name or ""))


def get_user_language(telegram_id: int) -> str:
    with get_db() as conn:
        row = conn.execute(
            "SELECT language FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    return row["language"] if row else "uz"


def set_user_language(telegram_id: int, lang: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET language = ? WHERE telegram_id = ?", (lang, telegram_id)
        )


# ── Student binding helpers ───────────────────────────────────────────────────

def get_student_binding(telegram_id: int) -> Optional[dict]:
    """Return {passport, full_name, dob} or None — values are decrypted."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT passport, full_name, dob FROM student_bindings WHERE telegram_id = ?",
            (telegram_id,)
        ).fetchone()
    if not row:
        return None
    return {
        "passport":  decrypt(row["passport"]),
        "full_name": decrypt(row["full_name"]),
        "dob":       decrypt(row["dob"]),
    }


def save_student_binding(telegram_id: int, passport: str, full_name: str, dob: str) -> None:
    """Save student PII — values are encrypted before storage."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO student_bindings (telegram_id, passport, full_name, dob)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                passport  = excluded.passport,
                full_name = excluded.full_name,
                dob       = excluded.dob,
                bound_at  = datetime('now')
        """, (telegram_id, encrypt(passport), encrypt(full_name), encrypt(dob)))


def clear_student_binding(telegram_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "DELETE FROM student_bindings WHERE telegram_id = ?", (telegram_id,)
        )


# ── Check result logging ──────────────────────────────────────────────────────

def log_check_result(
    telegram_id: int,
    check_type: str,
    result: dict,
    passport: str = "",
    receipt: str = "",
    full_name: str = "",
    dob: str = "",
) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT INTO check_results
              (telegram_id, check_type, receipt, passport, full_name, dob,
               status_en, status_ko, visa_type, app_date, reason, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            telegram_id, check_type, receipt or result.get("receipt", ""),
            passport, full_name, dob,
            result.get("status_en"), result.get("status_ko"),
            result.get("visa_type"), result.get("app_date"),
            result.get("reason"),
            result.get("checked_at", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ))


# ── Admin session helpers ─────────────────────────────────────────────────────

def is_admin_authenticated(telegram_id: int) -> bool:
    """Return True only if admin is authenticated AND session has not expired."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT authenticated, auth_at FROM admin_sessions WHERE telegram_id = ?",
            (telegram_id,)
        ).fetchone()
    if not row or not row["authenticated"]:
        return False
    try:
        auth_time = datetime.fromisoformat(row["auth_at"])
        if datetime.now() - auth_time > timedelta(hours=SESSION_TTL_HOURS):
            # Session expired — revoke it silently
            revoke_admin_session(telegram_id)
            return False
    except (TypeError, ValueError):
        return False
    return True


def set_admin_authenticated(telegram_id: int, authenticated: bool = True) -> None:
    with get_db() as conn:
        conn.execute("""
            INSERT INTO admin_sessions (telegram_id, authenticated, auth_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(telegram_id) DO UPDATE SET
                authenticated = excluded.authenticated,
                auth_at       = datetime('now')
        """, (telegram_id, 1 if authenticated else 0))


def revoke_admin_session(telegram_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "DELETE FROM admin_sessions WHERE telegram_id = ?", (telegram_id,)
        )


# ── Stats helpers ─────────────────────────────────────────────────────────────

def count_student_bindings() -> int:
    with get_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM student_bindings").fetchone()[0]


def get_all_check_results() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT cr.*, u.full_name as tg_name
            FROM check_results cr
            LEFT JOIN users u ON cr.telegram_id = u.telegram_id
            ORDER BY cr.checked_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ── Status history helpers ────────────────────────────────────────────────────

def upsert_status_history(
    passport: str,
    full_name: str,
    dob: str,
    status_en: str,
    status_ko: str,
    visa_type: str,
    app_date: str,
    reason: str,
    check_type: str = "diplomatic",
    receipt: str = "",
) -> bool:
    """
    Update the latest-known status for a passport.
    Returns True if the status CHANGED (useful for alerting).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_db() as conn:
        existing = conn.execute(
            "SELECT status_en FROM status_history WHERE passport = ?", (passport,)
        ).fetchone()

        status_changed = existing is None or existing["status_en"] != status_en
        changed_at = now if status_changed else None

        if existing is None:
            conn.execute("""
                INSERT INTO status_history
                  (passport, full_name, dob, receipt, check_type,
                   status_en, status_ko, visa_type, app_date, reason,
                   first_seen_at, last_checked, status_changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (passport, full_name, dob, receipt, check_type,
                  status_en, status_ko, visa_type, app_date, reason,
                  now, now, now))
        else:
            conn.execute("""
                UPDATE status_history SET
                    full_name  = ?, dob = ?, receipt = ?, check_type = ?,
                    status_en  = ?, status_ko = ?, visa_type = ?,
                    app_date   = ?, reason = ?,
                    last_checked = ?,
                    status_changed_at = CASE
                        WHEN status_en != ? THEN ?
                        ELSE status_changed_at
                    END
                WHERE passport = ?
            """, (full_name, dob, receipt, check_type,
                  status_en, status_ko, visa_type,
                  app_date, reason,
                  now,
                  status_en, changed_at,
                  passport))
    return status_changed


def get_status_stats() -> dict:
    """
    Return admin stats: counts per status_en bucket, total, last checked time.
    """
    with get_db() as conn:
        rows = conn.execute("""
            SELECT status_en, COUNT(*) as cnt
            FROM status_history
            GROUP BY status_en
        """).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM status_history").fetchone()[0]
        last = conn.execute(
            "SELECT MAX(last_checked) FROM status_history"
        ).fetchone()[0]
        recent_changes = conn.execute("""
            SELECT passport, full_name, status_en, status_ko, status_changed_at
            FROM status_history
            WHERE status_changed_at IS NOT NULL
            ORDER BY status_changed_at DESC
            LIMIT 10
        """).fetchall()

    buckets = {
        "APPROVED": 0, "ISSUED": 0, "USED": 0,
        "UNDER_REVIEW": 0, "RECEIVED": 0, "PENDING": 0,
        "SUPPLEMENT": 0, "SUPPLEMENT_DONE": 0,
        "REJECTED": 0, "RETURNED": 0,
        "WITHDRAWN": 0, "CANCELLED": 0,
        "NOT_FOUND": 0, "ERROR": 0, "UNKNOWN": 0,
    }
    for row in rows:
        key = row["status_en"] or "UNKNOWN"
        if key in buckets:
            buckets[key] += row["cnt"]
        else:
            buckets["UNKNOWN"] += row["cnt"]

    return {
        "total": total,
        "buckets": buckets,
        "last_checked": last,
        "recent_changes": [dict(r) for r in recent_changes],
    }


def get_all_status_history() -> list[dict]:
    """Return all rows from status_history for Excel export."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT passport, full_name, dob, receipt, check_type,
                   status_en, status_ko, visa_type, app_date, reason,
                   first_seen_at, last_checked, status_changed_at
            FROM status_history
            ORDER BY last_checked DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ── Bulk session helpers (partial export + error retry) ───────────────────────

def bulk_save_row(session_key: str, row_index: int, result: dict,
                  receipt: str = "", passport: str = "",
                  full_name: str = "", dob: str = "",
                  check_type: str = "diplomatic") -> None:
    """Persist a single completed bulk-check row immediately after it finishes."""
    with get_db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO bulk_sessions
              (session_key, row_index, receipt, passport, full_name, dob, check_type,
               status_en, status_ko, visa_type, app_date, reason, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_key, row_index,
            receipt, passport, full_name, dob, check_type,
            result.get("status_en", "ERROR"),
            result.get("status_ko", ""),
            result.get("visa_type", ""),
            result.get("app_date", ""),
            result.get("reason", ""),
            result.get("checked_at", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ))


def bulk_get_session(session_key: str) -> list[dict]:
    """Return all saved rows for a session, ordered by row_index."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM bulk_sessions
            WHERE session_key = ?
            ORDER BY row_index ASC
        """, (session_key,)).fetchall()
    return [dict(r) for r in rows]


def bulk_get_error_rows(session_key: str) -> list[dict]:
    """Return only ERROR rows from a session (for retry)."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM bulk_sessions
            WHERE session_key = ? AND status_en = 'ERROR'
            ORDER BY row_index ASC
        """, (session_key,)).fetchall()
    return [dict(r) for r in rows]


def bulk_clear_old_sessions(keep_latest: int = 5) -> None:
    """Keep only the N most recent session keys to avoid unbounded growth."""
    with get_db() as conn:
        old_keys = conn.execute("""
            SELECT session_key FROM (
                SELECT session_key, MAX(checked_at) as latest
                FROM bulk_sessions
                GROUP BY session_key
                ORDER BY latest DESC
                LIMIT -1 OFFSET ?
            )
        """, (keep_latest,)).fetchall()
        for row in old_keys:
            conn.execute(
                "DELETE FROM bulk_sessions WHERE session_key = ?", (row[0],)
            )

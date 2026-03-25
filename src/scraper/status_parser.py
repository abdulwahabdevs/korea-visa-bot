"""
Korean visa portal status parser.
Maps Korean status strings → English constants and metadata.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedStatus:
    status_en: str          # PENDING / APPROVED / REJECTED / NOT_FOUND / ERROR
    status_ko: str          # original Korean text
    reason: str             # supplement / rejection reason (if any)
    visa_type: str          # e.g. 석사유학(D-2-3)
    app_date: str           # YYYY-MM-DD
    receipt: str


# ── Korean → English mapping ──────────────────────────────────────────────────
# Each English constant corresponds to a distinct UI category with its own
# emoji, colour (bot message + Excel row fill) and progress-bar bucket.
#
# Category quick reference:
#   APPROVED / ISSUED      → 🟢 green     (visa granted)
#   USED                   → ✅ dark green (visa used, entered Korea)
#   RECEIVED               → 🟡 yellow    (application received, no review yet)
#   PENDING                → 🟡 yellow    (generic pending / preparing issuance)
#   UNDER_REVIEW           → 🔵 blue      (actively being reviewed)
#   SUPPLEMENT             → 📋 orange    (additional docs REQUESTED by officer)
#   SUPPLEMENT_DONE        → 📤 yellow    (docs submitted, back in review queue)
#   REJECTED               → 🔴 red       (denied)
#   RETURNED               → 🟠 coral     (sent back by consulate)
#   WITHDRAWN              → ⚪ grey      (applicant withdrew voluntarily)
#   CANCELLED              → ⚫ dark grey (application cancelled / 신청취소)
#   NOT_FOUND              → ⬜ light grey
#   ERROR                  → 🟣 purple

_STATUS_MAP: dict[str, str] = {
    # ── Pending / in-review states ────────────────────────────────────────
    "접수":       "RECEIVED",       # Received (application registered)
    "심사중":     "UNDER_REVIEW",   # Under review
    "심사":       "UNDER_REVIEW",   # Review (shorter form)
    "추가심사중": "UNDER_REVIEW",   # Additional review in progress
    "발급준비중": "PENDING",        # Preparing issuance
    "발급준비":   "PENDING",        # Preparing issuance (shorter)

    # ── Supplement states (split: requested vs submitted) ─────────────────
    "보완요청":   "SUPPLEMENT",      # Additional documents REQUESTED
    "보완중":     "SUPPLEMENT",      # Supplementing in progress (docs not yet submitted)
    "보완완료":   "SUPPLEMENT_DONE", # Documents submitted → back in review queue → pending

    # ── Approved / Used states ────────────────────────────────────────────
    "발급":       "APPROVED",   # Issued
    "발급완료":   "APPROVED",   # Issuance complete
    "사증발급":   "APPROVED",   # Visa issued
    "허가":       "APPROVED",   # Permitted / approved
    "사용완료":   "USED",       # Visa used — student entered Korea
    "여권교부":   "APPROVED",   # Passport handed over (visa centre)

    # ── Withdrawn / cancelled states ──────────────────────────────────────
    "접수철회":   "WITHDRAWN",  # Application withdrawn by applicant
    "철회":       "WITHDRAWN",  # Withdrawn
    "취하":       "WITHDRAWN",  # Withdrawn (formal term)
    "신청취소":   "CANCELLED",  # Application cancelled (NEW from portal)

    # ── Rejected / returned states ────────────────────────────────────────
    "불허":       "REJECTED",   # Rejected / denied
    "거부":       "REJECTED",   # Refused
    "불허가":     "REJECTED",   # Not permitted
    "반려":       "RETURNED",   # Returned by consulate (distinct from rejected)
}


# Pre-sorted by keyword length (longest first) for safe substring matching.
# "접수철회" must be checked before "접수", "보완완료" before "보완", etc.
_STATUS_MAP_BY_LENGTH = sorted(_STATUS_MAP.items(), key=lambda x: len(x[0]), reverse=True)


def parse_status(raw_ko: str) -> str:
    """Return the English status constant for a Korean status string."""
    raw_ko = (raw_ko or "").strip()
    # Direct match (O(1) dict lookup)
    if raw_ko in _STATUS_MAP:
        return _STATUS_MAP[raw_ko]
    # Partial / compound match — longest keywords first to prevent
    # false positives (e.g. "접수" inside "접수철회").
    for ko_key, en_val in _STATUS_MAP_BY_LENGTH:
        if ko_key in raw_ko:
            return en_val
    return "UNKNOWN"


def parse_portal_result(raw: dict) -> ParsedStatus:
    """
    Convert raw dict scraped from the portal into a clean ParsedStatus.

    Expected raw keys (all optional / may be empty):
        status_ko, reason, visa_type, app_date, receipt
    """
    status_ko = (raw.get("status_ko") or "").strip()
    status_en = parse_status(status_ko)

    return ParsedStatus(
        status_en=status_en,
        status_ko=status_ko,
        reason=(raw.get("reason") or "").strip(),
        visa_type=(raw.get("visa_type") or "").strip(),
        app_date=(raw.get("app_date") or "").strip(),
        receipt=(raw.get("receipt") or "").strip(),
    )

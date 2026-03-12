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
_STATUS_MAP: dict[str, str] = {
    # Pending / in-review states
    "접수":       "PENDING",    # Received
    "심사중":     "PENDING",    # Under review
    "보완요청":   "PENDING",    # Additional documents requested
    "보완완료":   "PENDING",    # Documents supplemented (still under review)
    "보완중":     "PENDING",    # Supplementing in progress
    "추가심사중": "PENDING",    # Additional review in progress
    "발급준비중": "PENDING",    # Preparing issuance
    # Approved / Used states (gb03 '사용완료' = used → means visa was granted AND used)
    "발급":       "APPROVED",   # Issued
    "발급완료":   "APPROVED",   # Issuance complete
    "사증발급":   "APPROVED",   # Visa issued
    "허가":       "APPROVED",   # Permitted
    "사용완료":   "APPROVED",   # Used/completed (visa was issued and the student entered Korea)
    "여권교부":   "APPROVED",   # Passport handed over
    # Rejected states
    "불허":       "REJECTED",   # Rejected
    "거부":       "REJECTED",   # Refused
    "불허가":     "REJECTED",   # Not permitted
}


def parse_status(raw_ko: str) -> str:
    """Return the English status constant for a Korean status string."""
    raw_ko = (raw_ko or "").strip()
    # Direct match
    if raw_ko in _STATUS_MAP:
        return _STATUS_MAP[raw_ko]
    # Partial match (handles compound strings)
    for ko_key, en_val in _STATUS_MAP.items():
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

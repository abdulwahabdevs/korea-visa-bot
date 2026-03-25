"""
Tests for src/scraper/status_parser.py — Korean → English status mapping.

Every portal status must map to the correct English constant.
This is the most critical mapping in the bot — a wrong mapping means
students see incorrect visa results.
"""

import pytest
from src.scraper.status_parser import parse_status, parse_portal_result


# ── Direct matches ──────────────────────────────────────────────────────────

class TestParseStatusDirect:
    """Test exact Korean strings → English constants."""

    @pytest.mark.parametrize("korean, expected", [
        # Approved family
        ("허가",       "APPROVED"),
        ("발급",       "APPROVED"),
        ("발급완료",   "APPROVED"),
        ("사증발급",   "APPROVED"),
        ("여권교부",   "APPROVED"),
        # Used
        ("사용완료",   "USED"),
        # Pending / review
        ("접수",       "RECEIVED"),
        ("심사중",     "UNDER_REVIEW"),
        ("심사",       "UNDER_REVIEW"),
        ("추가심사중", "UNDER_REVIEW"),
        ("발급준비중", "PENDING"),
        ("발급준비",   "PENDING"),
        # Supplement — requested vs submitted
        ("보완요청",   "SUPPLEMENT"),
        ("보완중",     "SUPPLEMENT"),
        ("보완완료",   "SUPPLEMENT_DONE"),
        # Rejected / returned
        ("불허",       "REJECTED"),
        ("거부",       "REJECTED"),
        ("불허가",     "REJECTED"),
        ("반려",       "RETURNED"),
        # Withdrawn / cancelled
        ("접수철회",   "WITHDRAWN"),
        ("철회",       "WITHDRAWN"),
        ("취하",       "WITHDRAWN"),
        ("신청취소",   "CANCELLED"),
    ])
    def test_direct_match(self, korean, expected):
        assert parse_status(korean) == expected


# ── Partial / compound matches ──────────────────────────────────────────────

class TestParseStatusPartial:
    """Portal sometimes returns compound strings like '유학.연수 — 허가'."""

    @pytest.mark.parametrize("korean, expected", [
        ("유학.연수 — 허가",         "APPROVED"),
        ("유학.연수 — 심사중",       "UNDER_REVIEW"),
        ("유학.연수 — 불허",         "REJECTED"),
        ("유학.연수 — 보완요청",     "SUPPLEMENT"),
        ("유학.연수 — 보완완료",     "SUPPLEMENT_DONE"),
        ("유학.연수 — 접수철회",     "WITHDRAWN"),
        ("유학.연수 — 신청취소",     "CANCELLED"),
        ("유학.연수 — 반려",         "RETURNED"),
        ("유학.연수 — 사용완료",     "USED"),
    ])
    def test_compound_match(self, korean, expected):
        assert parse_status(korean) == expected


# ── Ordering: more specific keywords must win ───────────────────────────────

class TestParseStatusOrdering:
    """보완완료 must NOT match 보완 (→ SUPPLEMENT). It must match SUPPLEMENT_DONE.
    접수철회 must NOT match 접수 (→ RECEIVED). It must match WITHDRAWN."""

    def test_supplement_done_not_supplement(self):
        assert parse_status("보완완료") == "SUPPLEMENT_DONE"
        assert parse_status("보완완료") != "SUPPLEMENT"

    def test_withdrawn_not_received(self):
        assert parse_status("접수철회") == "WITHDRAWN"
        assert parse_status("접수철회") != "RECEIVED"

    def test_cancelled_not_received(self):
        """신청취소 contains no 접수 substring, but verify it's CANCELLED."""
        assert parse_status("신청취소") == "CANCELLED"


# ── Edge cases ──────────────────────────────────────────────────────────────

class TestParseStatusEdgeCases:
    def test_empty_string(self):
        assert parse_status("") == "UNKNOWN"

    def test_none_input(self):
        assert parse_status(None) == "UNKNOWN"

    def test_whitespace(self):
        assert parse_status("  허가  ") == "APPROVED"

    def test_unknown_status(self):
        assert parse_status("알수없음") == "UNKNOWN"
        assert parse_status("random text") == "UNKNOWN"


# ── parse_portal_result ─────────────────────────────────────────────────────

class TestParsePortalResult:
    def test_approved_result(self):
        raw = {"status_ko": "허가", "visa_type": "D-2-3", "app_date": "2026-01-15", "reason": ""}
        result = parse_portal_result(raw)
        assert result.status_en == "APPROVED"
        assert result.status_ko == "허가"
        assert result.visa_type == "D-2-3"

    def test_supplement_result(self):
        raw = {"status_ko": "보완요청", "visa_type": "", "app_date": "", "reason": "서류 부족"}
        result = parse_portal_result(raw)
        assert result.status_en == "SUPPLEMENT"
        assert result.reason == "서류 부족"

    def test_empty_result(self):
        result = parse_portal_result({})
        assert result.status_en == "UNKNOWN"
        assert result.status_ko == ""

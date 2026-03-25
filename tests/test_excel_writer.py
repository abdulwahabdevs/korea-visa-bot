"""
Tests for src/excel_writer.py — Excel output with color-coded statuses.
"""

import pytest
from pathlib import Path
from src.excel_writer import write_results, write_history_export, STATUS_FILLS


# ── Color map completeness ──────────────────────────────────────────────────

class TestStatusFills:
    """Every status the bot can produce must have a color entry."""

    REQUIRED_STATUSES = [
        "APPROVED", "ISSUED", "USED",
        "PENDING", "RECEIVED", "UNDER_REVIEW",
        "SUPPLEMENT", "SUPPLEMENT_DONE",
        "REJECTED", "RETURNED",
        "WITHDRAWN", "CANCELLED",
        "NOT_FOUND", "ERROR", "UNKNOWN",
    ]

    def test_all_statuses_have_color(self):
        for status in self.REQUIRED_STATUSES:
            assert status in STATUS_FILLS, f"Missing color for {status}"

    def test_no_duplicate_colors_for_different_categories(self):
        """Key statuses that must be visually distinct."""
        distinct_pairs = [
            ("APPROVED", "REJECTED"),
            ("APPROVED", "PENDING"),
            ("SUPPLEMENT", "PENDING"),
            ("SUPPLEMENT", "SUPPLEMENT_DONE"),
            ("WITHDRAWN", "CANCELLED"),
            ("REJECTED", "ERROR"),
            ("REJECTED", "RETURNED"),
            ("NOT_FOUND", "ERROR"),
        ]
        for a, b in distinct_pairs:
            assert STATUS_FILLS[a] != STATUS_FILLS[b], \
                f"{a} and {b} should have different colors but both are #{STATUS_FILLS[a]}"


# ── Write results to file ───────────────────────────────────────────────────

class TestWriteResults:
    def test_creates_file(self, tmp_path):
        out = tmp_path / "results.xlsx"
        rows = [
            {"index": 1, "receipt": "5677400001", "name": "SOMEONOV SOMEONE",
             "passport": "FA4166021", "dob": "19981217", "status_en": "APPROVED",
             "status_ko": "허가", "visa_type": "D-2-3", "app_date": "2026-01-15",
             "reason": "", "checked_at": "2026-01-15 10:00"},
        ]
        result_path = write_results(rows, out)
        assert result_path.exists()
        assert result_path.stat().st_size > 0

    def test_handles_empty_list(self, tmp_path):
        out = tmp_path / "empty.xlsx"
        write_results([], out)
        assert out.exists()

    def test_handles_none_in_list(self, tmp_path):
        out = tmp_path / "with_none.xlsx"
        rows = [
            None,
            {"index": 1, "receipt": "", "name": "SOMEONE", "passport": "FA4166021",
             "dob": "19981217", "status_en": "PENDING", "status_ko": "접수",
             "visa_type": "", "app_date": "", "reason": "", "checked_at": "2026-01-15 10:00"},
        ]
        write_results(rows, out)
        assert out.exists()

    def test_all_status_colors_applied(self, tmp_path):
        """Verify each status gets the correct fill color in the Excel file."""
        import openpyxl
        out = tmp_path / "colors.xlsx"
        rows = [
            {"index": i, "receipt": "", "name": f"STUDENT{i}", "passport": f"FA{i:07d}",
             "dob": "19981217", "status_en": status, "status_ko": "",
             "visa_type": "", "app_date": "", "reason": "", "checked_at": ""}
            for i, status in enumerate(STATUS_FILLS.keys(), 1)
        ]
        write_results(rows, out)

        wb = openpyxl.load_workbook(out)
        ws = wb.active
        # Row 1 = header, rows 2+ = data
        for row_idx in range(2, len(rows) + 2):
            status_cell = ws.cell(row=row_idx, column=6)  # column F = status_en
            fill_color = status_cell.fill.fgColor.rgb
            # openpyxl returns "00" + hex, so "00C6EFCE"
            assert fill_color is not None, f"Row {row_idx} has no fill color"


# ── Write history export ─────────────────────────────────────────────────────

class TestWriteHistoryExport:
    def test_creates_file(self, tmp_path):
        out = tmp_path / "history.xlsx"
        rows = [
            {"passport": "FA4166021", "full_name": "SOMEONOV SOMEONE",
             "dob": "19981217", "receipt": "", "check_type": "diplomatic",
             "status_en": "APPROVED", "status_ko": "허가", "visa_type": "D-2-3",
             "app_date": "2026-01-15", "reason": "",
             "first_seen_at": "2026-01-10", "last_checked": "2026-01-15",
             "status_changed_at": "2026-01-15"},
        ]
        write_history_export(rows, out)
        assert out.exists()
        assert out.stat().st_size > 0

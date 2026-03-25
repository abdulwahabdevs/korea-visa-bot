"""
Tests for src/excel_reader.py — smart header detection, normalisation, validation.
"""

import pytest
from src.excel_reader import (
    read_students_validated,
    _normalise_dob,
    _normalise_passport,
    _normalise_name,
    _match_header,
)


# ── Header keyword detection ────────────────────────────────────────────────

class TestMatchHeader:
    @pytest.mark.parametrize("cell, expected", [
        ("여권번호",         "passport"),
        ("Passport",         "passport"),
        ("PASSPORT NO",      "passport"),
        ("pasport",          "passport"),     # typo in Uzbek
        ("성명",             "name"),
        ("Full Name",        "name"),
        ("피초청자",         "name"),
        ("ism",              "name"),         # Uzbek
        ("생년월일",         "dob"),
        ("Date of Birth",   "dob"),
        ("birthday",         "dob"),
        ("신청번호",         "receipt"),
        ("Receipt",          "receipt"),
        ("접수번호",         "receipt"),
        ("ariza",            "receipt"),      # Uzbek
        # Not a known header
        ("random column",    None),
        ("",                 None),
    ])
    def test_header_detection(self, cell, expected):
        assert _match_header(cell) == expected


# ── DOB normalisation ───────────────────────────────────────────────────────

class TestNormaliseDob:
    @pytest.mark.parametrize("raw, expected", [
        ("19981217",       "19981217"),       # already YYYYMMDD
        ("1998.12.17",     "19981217"),       # dots
        ("1998-12-17",     "19981217"),       # dashes
        ("1998/12/17",     "19981217"),       # slashes
        ("17/12/1998",     "19981217"),       # DD/MM/YYYY
        ("17.12.1998",     "19981217"),       # DD.MM.YYYY
        (None,             ""),               # None
        (36146,            "19981217"),       # Excel serial date (1998-12-17)
    ])
    def test_normalise(self, raw, expected):
        assert _normalise_dob(raw) == expected


# ── Passport normalisation ──────────────────────────────────────────────────

class TestNormalisePassport:
    def test_uppercase(self):
        assert _normalise_passport("fa4166021") == "FA4166021"

    def test_strip_spaces(self):
        assert _normalise_passport(" FA 4166021 ") == "FA4166021"


# ── Name normalisation ──────────────────────────────────────────────────────

class TestNormaliseName:
    def test_uppercase_and_collapse(self):
        assert _normalise_name("  someonov   someone  ") == "SOMEONOV SOMEONE"


# ── Full Excel read (integration) ───────────────────────────────────────────

class TestReadStudentsValidated:
    """Tests using real .xlsx files created via tmp_xlsx fixture."""

    def test_diplomatic_valid_rows(self, tmp_xlsx):
        """Diplomatic mode: passport + name + dob required, receipt optional."""
        path = tmp_xlsx([
            ["passport", "name", "dob"],
            ["FA4166021", "SOMEONOV SOMEONE UGLI", "19981217"],
            ["AB1234567", "OTHEROV OTHER QIZI",    "20010315"],
        ])
        result = read_students_validated(path, require_receipt=False)
        assert len(result.valid) == 2
        assert len(result.invalid) == 0
        assert result.valid[0].passport == "FA4166021"
        assert result.valid[1].dob == "20010315"

    def test_evisa_valid_rows(self, tmp_xlsx):
        """E-Visa mode: receipt column required."""
        path = tmp_xlsx([
            ["receipt", "passport", "name", "dob"],
            ["5677400001", "FA4166021", "SOMEONOV SOMEONE UGLI", "19981217"],
        ])
        result = read_students_validated(path, require_receipt=True)
        assert len(result.valid) == 1
        assert result.valid[0].receipt == "5677400001"

    def test_korean_headers(self, tmp_xlsx):
        """Korean column names should be detected."""
        path = tmp_xlsx([
            ["여권번호", "성명", "생년월일"],
            ["FA4166021", "SOMEONOV SOMEONE UGLI", "19981217"],
        ])
        result = read_students_validated(path, require_receipt=False)
        assert len(result.valid) == 1

    def test_invalid_passport_flagged(self, tmp_xlsx):
        """Invalid passport format should be in result.invalid."""
        path = tmp_xlsx([
            ["passport", "name", "dob"],
            ["INVALID!!!", "SOMEONOV SOMEONE UGLI", "19981217"],
        ])
        result = read_students_validated(path, require_receipt=False)
        assert len(result.valid) == 0
        assert len(result.invalid) == 1
        assert "Passport" in result.invalid[0].errors[0]

    def test_duplicate_passport_skipped(self, tmp_xlsx):
        """Duplicate passports should be flagged and skipped."""
        path = tmp_xlsx([
            ["passport", "name", "dob"],
            ["FA4166021", "SOMEONOV SOMEONE UGLI", "19981217"],
            ["FA4166021", "SOMEONOV SOMEONE UGLI", "19981217"],  # duplicate
        ])
        result = read_students_validated(path, require_receipt=False)
        assert len(result.valid) == 1
        assert len(result.invalid) == 1
        assert "Takroriy" in result.invalid[0].errors[0]

    def test_missing_receipt_column_evisa(self, tmp_xlsx):
        """E-Visa mode should raise ValueError if receipt column missing."""
        path = tmp_xlsx([
            ["passport", "name", "dob"],
            ["FA4166021", "SOMEONOV SOMEONE UGLI", "19981217"],
        ])
        with pytest.raises(ValueError, match="receipt"):
            read_students_validated(path, require_receipt=True)

    def test_blank_rows_skipped(self, tmp_xlsx):
        """Fully blank rows should be silently skipped."""
        path = tmp_xlsx([
            ["passport", "name", "dob"],
            ["FA4166021", "SOMEONOV SOMEONE UGLI", "19981217"],
            [None, None, None],  # blank
            ["AB1234567", "OTHEROV OTHER QIZI", "20010315"],
        ])
        result = read_students_validated(path, require_receipt=False)
        assert len(result.valid) == 2

    def test_dob_normalization_in_full_read(self, tmp_xlsx):
        """DOB formats should be normalised during read."""
        path = tmp_xlsx([
            ["passport", "name", "dob"],
            ["FA4166021", "SOMEONOV SOMEONE UGLI", "1998.12.17"],  # dots
        ])
        result = read_students_validated(path, require_receipt=False)
        assert result.valid[0].dob == "19981217"

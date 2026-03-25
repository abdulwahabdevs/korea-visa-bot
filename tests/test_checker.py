"""
Tests for src/checker.py — input validation functions.

These validators are the first line of defence: if bad data passes through,
the scraper sends garbage to the portal → wasted Chrome time + wrong results.
"""

import pytest
from src.checker import (
    validate_passport,
    validate_receipt,
    validate_name,
    validate_dob,
    ValidationError,
)


# ── Passport validation ─────────────────────────────────────────────────────

class TestValidatePassport:
    """Format: 1-2 uppercase letters + 7-8 digits."""

    @pytest.mark.parametrize("input_val, expected", [
        ("FA4166021",  "FA4166021"),
        ("AB1234567",  "AB1234567"),
        ("A12345678",  "A12345678"),    # 1 letter + 8 digits
        ("fa4166021",  "FA4166021"),    # lowercased → uppercased
        (" FA4166021", "FA4166021"),    # leading space
        ("FA4166021 ", "FA4166021"),    # trailing space
    ])
    def test_valid(self, input_val, expected):
        assert validate_passport(input_val) == expected

    @pytest.mark.parametrize("input_val", [
        "",             # empty
        "12345678",     # no letters
        "ABCDEFGHI",   # no digits
        "F1234567890",  # too many digits
        # NOTE: "FA 4166021" is NOT invalid — spaces are stripped → "FA4166021" (valid)
        "FAA1234567",   # 3 letters
        "F123456",      # too short (1 letter + 6 digits)
    ])
    def test_invalid(self, input_val):
        with pytest.raises(ValidationError):
            validate_passport(input_val)


# ── Receipt validation ───────────────────────────────────────────────────────

class TestValidateReceipt:
    """Format: exactly 10 digits."""

    @pytest.mark.parametrize("input_val, expected", [
        ("5677400001", "5677400001"),
        ("0000000000", "0000000000"),
        (" 5677400001 ", "5677400001"),  # whitespace stripped
    ])
    def test_valid(self, input_val, expected):
        assert validate_receipt(input_val) == expected

    @pytest.mark.parametrize("input_val", [
        "",
        "123456789",    # 9 digits
        "12345678901",  # 11 digits
        "56774ABCDE",   # letters mixed in
    ])
    def test_invalid(self, input_val):
        with pytest.raises(ValidationError):
            validate_receipt(input_val)


# ── Name validation ──────────────────────────────────────────────────────────

class TestValidateName:
    """Format: uppercase Latin letters + spaces, min 2 chars."""

    @pytest.mark.parametrize("input_val, expected", [
        ("SOMEONOV SOMEONE",                    "SOMEONOV SOMEONE"),
        ("SOMEONOV SOMEONE SOMEONES SON UGLI",  "SOMEONOV SOMEONE SOMEONES SON UGLI"),
        ("someonov someone",                    "SOMEONOV SOMEONE"),      # auto-uppercased
        ("  SOMEONOV   SOMEONE  ",              "SOMEONOV SOMEONE"),      # whitespace collapsed
        ("O'BRIAN JAMES",                       "O'BRIAN JAMES"),         # apostrophe allowed
        ("SMITH-JONES MARY",                    "SMITH-JONES MARY"),      # hyphen allowed
    ])
    def test_valid(self, input_val, expected):
        assert validate_name(input_val) == expected

    @pytest.mark.parametrize("input_val", [
        "",           # empty
        "A",          # too short
        "ИВАНОВ",     # Cyrillic
        "田中太郎",    # Japanese
        "NAME123",    # digits
    ])
    def test_invalid(self, input_val):
        with pytest.raises(ValidationError):
            validate_name(input_val)


# ── DOB validation ───────────────────────────────────────────────────────────

class TestValidateDob:
    """Format: YYYYMMDD, also accepts YYYY-MM-DD and YYYY.MM.DD."""

    @pytest.mark.parametrize("input_val, expected", [
        ("19981217",     "19981217"),
        ("20010315",     "20010315"),
        ("1998-12-17",   "19981217"),     # dashes stripped
        ("1998.12.17",   "19981217"),     # dots stripped
        ("1998/12/17",   "19981217"),     # slashes stripped
        (" 19981217 ",   "19981217"),     # whitespace stripped
    ])
    def test_valid(self, input_val, expected):
        assert validate_dob(input_val) == expected

    @pytest.mark.parametrize("input_val", [
        "",             # empty
        "1234",         # too short
        "123456789",    # too long
        "18991217",     # year < 1900
        "20211217",     # year > 2020
        "19981317",     # month 13
        "19981232",     # day 32
        "abcdefgh",     # not digits
    ])
    def test_invalid(self, input_val):
        with pytest.raises(ValidationError):
            validate_dob(input_val)

    def test_boundary_years(self):
        assert validate_dob("19000101") == "19000101"  # min year
        assert validate_dob("20200101") == "20200101"  # max year

    def test_boundary_months(self):
        assert validate_dob("19980101") == "19980101"  # month 01
        assert validate_dob("19981201") == "19981201"  # month 12

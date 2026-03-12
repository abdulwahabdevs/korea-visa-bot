# src/scraper/__init__.py
from .facade import check_evisa, check_diplomatic
from .status_parser import parse_portal_result, ParsedStatus

__all__ = ["check_evisa", "check_diplomatic", "parse_portal_result", "ParsedStatus"]

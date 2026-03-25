"""
Shared fixtures and setup for the test suite.

Stubs out selenium so tests can import project modules without
needing Chrome/ChromeDriver installed.
"""

import os
import sys
import types
import pytest
from pathlib import Path

# ── Project root on sys.path ─────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Minimal env vars ─────────────────────────────────────────────────────────
os.environ.setdefault("BOT_TOKEN", "test:fake_token")
os.environ.setdefault("ADMIN_CHAT_IDS", "111111111")
os.environ.setdefault("ADMIN_PASSWORD", "testpass")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests")
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("CACHE_TTL_SECONDS", "5")

# ── Stub selenium (tests don't need a real Chrome driver) ────────────────────
if "selenium" not in sys.modules:
    _sel = types.ModuleType("selenium")
    _wd  = types.ModuleType("selenium.webdriver")
    _submodules = {
        "selenium":                                          _sel,
        "selenium.webdriver":                                _wd,
        "selenium.webdriver.chrome":                         types.ModuleType("selenium.webdriver.chrome"),
        "selenium.webdriver.chrome.options":                 types.ModuleType("selenium.webdriver.chrome.options"),
        "selenium.webdriver.chrome.service":                 types.ModuleType("selenium.webdriver.chrome.service"),
        "selenium.webdriver.common":                         types.ModuleType("selenium.webdriver.common"),
        "selenium.webdriver.common.by":                      types.ModuleType("selenium.webdriver.common.by"),
        "selenium.webdriver.support":                        types.ModuleType("selenium.webdriver.support"),
        "selenium.webdriver.support.ui":                     types.ModuleType("selenium.webdriver.support.ui"),
        "selenium.webdriver.support.expected_conditions":    types.ModuleType("selenium.webdriver.support.expected_conditions"),
        "selenium.common":                                   types.ModuleType("selenium.common"),
        "selenium.common.exceptions":                        types.ModuleType("selenium.common.exceptions"),
    }
    # Register stubs
    for name, mod in _submodules.items():
        sys.modules[name] = mod

    # Exception classes needed by facade.py / worker_pool.py
    _exc = sys.modules["selenium.common.exceptions"]
    for exc_name in ("TimeoutException", "NoAlertPresentException",
                     "UnexpectedAlertPresentException", "WebDriverException"):
        setattr(_exc, exc_name, type(exc_name, (Exception,), {}))

    # Minimal class stubs
    sys.modules["selenium.webdriver.support.ui"].WebDriverWait = type("WebDriverWait", (), {})
    sys.modules["selenium.webdriver.support.ui"].Select = type("Select", (), {})
    sys.modules["selenium.webdriver.common.by"].By = type("By", (), {"CSS_SELECTOR": "css", "ID": "id"})
    sys.modules["selenium.webdriver.support.expected_conditions"].presence_of_element_located = lambda x: x
    sys.modules["selenium.webdriver.support.expected_conditions"].visibility_of_element_located = lambda x: x
    sys.modules["selenium.webdriver.chrome.options"].Options = type("Options", (), {})
    sys.modules["selenium.webdriver.chrome.service"].Service = type("Service", (), {})
    sys.modules["selenium.webdriver"].Chrome = type("Chrome", (), {})


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_xlsx(tmp_path):
    """Factory that creates a temp .xlsx file from a list of rows."""
    import openpyxl

    def _make(rows: list[list], filename: str = "test.xlsx") -> Path:
        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        path = tmp_path / filename
        wb.save(path)
        return path

    return _make

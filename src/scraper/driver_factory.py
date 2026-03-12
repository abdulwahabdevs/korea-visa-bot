"""
Chrome WebDriver factory.
Builds a Selenium WebDriver with anti-detection flags and speed optimisations
suitable for automating the Korea visa portal.

IMPORTANT — flags that must NOT be added on Windows headless:
  ✗ --disable-software-rasterizer   kills the only rendering fallback in headless
  ✗ --disable-d3d11                 kills Direct3D 11 rendering backend
  ✗ --disable-d3d12                 kills Direct3D 12 rendering backend
  ✗ --blink-settings=imagesEnabled=0  can break rendering path in --headless=new

  Removing all three of the above caused the renderer crash:
  "Timed out receiving message from renderer: 57.777"
  → Chrome had ZERO rendering backends → renderer process froze → crash.

Safe flags for Windows headless:
  ✓ --disable-gpu         disables hardware GPU (standard headless practice)
  ✓ --disable-gpu-sandbox improves headless stability without killing rendering
  ✓ --headless=new        Chrome 112+ headless mode (stable when rendering is intact)

Speed optimisations applied here (OPT-D):
  • CDP Network.setBlockedURLs — blocks only analytics/tracking scripts.
    CSS, JS, fonts and images are NOT blocked (portal needs them to render).
"""

from __future__ import annotations
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

logger = logging.getLogger(__name__)

# Only block tracking/analytics — DO NOT block images, fonts, CSS or JS.
# The portal's JS dynamically shows/hides form sections; blocking resources
# that look harmless can silently break that logic.
_BLOCKED_URLS = [
    "*google-analytics.com/*",
    "*googletagmanager.com/*",
    "*doubleclick.net/*",
    "*googlesyndication.com/*",
    "*facebook.net/*",
]


def build_driver(headless: bool = True, download_dir: str | None = None) -> webdriver.Chrome:
    """
    Create and return a configured Chrome WebDriver.

    Args:
        headless: Run Chrome without a visible window (default True).
                  Set False for local debugging.

    Returns:
        selenium.webdriver.Chrome instance, ready to use.

    Args (new):
        download_dir: If given, configure Chrome to silently download files
                      (PDFs, HWP) to this directory without showing a save dialog.
                      Used exclusively by the certificate-download worker.
    """
    options = Options()

    if headless:
        options.add_argument("--headless=new")   # stable on Chrome 112+

    # ── Anti-detection & stability ────────────────────────────────────────
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)

    # ── Window & rendering ────────────────────────────────────────────────
    # --disable-gpu   : disables hardware GPU acceleration (safe for headless)
    # --disable-gpu-sandbox : improves headless stability
    # NOTE: do NOT add --disable-software-rasterizer / --disable-d3d11/d3d12
    #       those flags kill ALL rendering backends and crash the renderer.
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-gpu-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    # ── Network / certificates ────────────────────────────────────────────
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-running-insecure-content")

    # ── Realistic user-agent ──────────────────────────────────────────────
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    # ── Download directory (certificate download workers only) ────────────
    if download_dir:
        import os as _os
        _os.makedirs(download_dir, exist_ok=True)
        prefs = {
            "download.default_directory":        download_dir,
            "download.prompt_for_download":      False,
            "download.directory_upgrade":        True,
            "plugins.always_open_pdf_externally": True,   # save PDF instead of preview
            "safebrowsing.enabled":              True,
        }
        options.add_experimental_option("prefs", prefs)
        logger.debug("Chrome download dir: %s", download_dir)

    # ── Page load strategy: eager (DOM ready, don't wait for all resources)
    options.page_load_strategy = "eager"

    # ── Suppress console/log noise ────────────────────────────────────────
    options.add_argument("--log-level=3")
    options.add_argument("--silent")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception:
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=options)

    # ── Explicit timeouts ─────────────────────────────────────────────────
    driver.set_page_load_timeout(45)   # HTTP page-load timeout
    driver.set_script_timeout(30)      # execute_script timeout

    # ── Remove navigator.webdriver fingerprint ────────────────────────────
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    # ── Enable CDP download for headless mode ─────────────────────────────
    # In headless=new Chrome downloads are blocked by default unless we call
    # Page.setDownloadBehavior explicitly.
    if download_dir:
        try:
            import os as _os
            abs_dl = _os.path.abspath(download_dir)
            driver.execute_cdp_cmd(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": abs_dl},
            )
            # Tag the driver so download_approval_cert can read the dir back
            # without relying on non-existent Browser.getDownloadDirectory CDP.
            driver._cert_download_dir = abs_dl
            logger.debug("CDP download behaviour set to 'allow' → %s", abs_dl)
        except Exception as _e:
            logger.debug("CDP setDownloadBehavior unavailable: %s", _e)

    # ── OPT-D: block analytics/tracking only (safe, saves minor bandwidth) ─
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": _BLOCKED_URLS})
        logger.debug("CDP analytics blocking enabled")
    except Exception as exc:
        logger.debug("CDP blocking unavailable: %s", exc)

    logger.debug("Chrome WebDriver initialised (headless=%s)", headless)
    return driver

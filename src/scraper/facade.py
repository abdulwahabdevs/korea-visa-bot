"""
Korea Visa Portal scraper facade.

Supports two search modes:
  ① check_evisa()       — E-Visa Individual (전자비자 개인)
                           gb01: receipt + passport. Used by admins.

  ② check_diplomatic()  — Overseas Diplomatic Mission (재외공관 — gb03)
                           BUSI_GB=PASS_NO + sBUSI_GBNO + sEK_NM + sFROMDATE
                           Used by students.

Portal URL: https://www.visa.go.kr/openPage.do?MENU_ID=10301

─────────────────────────────────────────────────────────────────────────
SPEED OPTIMIZATIONS (why checks are fast):

  OPT-A  _dismiss_alert() is instant (direct try/except, NO WebDriverWait).
          The portal uses HTML modals, not JS alerts.  Old code waited 2s
          each call × 18 calls = 36 wasted seconds.  Now: 0 s.

  OPT-B  Stay-on-portal: if the driver is already on visa.go.kr, skip
          driver.get() entirely.  Saves the full HTTP round-trip (~3-5 s)
          on every check after the first one.

  OPT-C  Single-JS field fill: all four gb03 form fields are filled with
          ONE execute_script() call instead of four separate Selenium
          find_element / send_keys round-trips.  Saves ~0.5 s per check.

  OPT-D  Resource blocking: images, fonts, analytics are blocked via CDP
          so page loads complete ~1-2 s faster (set up in driver_factory).
          facade.py does NOT re-enable Network interception; it is already
          enabled by build_driver().

  OPT-E  No time.sleep() between field fills — Selenium send_keys /
          execute_script are synchronous.  Only one 0.3 s sleep remains:
          after clicking the radio button (lets fn_changeDivHide() run).
─────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations
import logging
import os
import re
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoAlertPresentException,
    UnexpectedAlertPresentException,
)

logger = logging.getLogger(__name__)

PORTAL_URL   = "https://www.visa.go.kr/openPage.do?MENU_ID=10301"
PAGE_TIMEOUT = 30    # portal loads in <10 s normally; 30 s is a safe margin
RESULT_WAIT  = 20    # AJAX result arrives in 2-4 s normally; 20 s for slow/bulk responses

SCREENSHOT_DIR = "data/screenshots"   # saved next to the DB so they persist
CERT_DOWNLOAD_DIR = "data/certs"      # temp directory for approval certificate PDFs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_debug_screenshot(driver: webdriver.Chrome, label: str) -> None:
    """
    Save a screenshot and the page source when something goes wrong.
    Files land in SCREENSHOT_DIR/<label>_<timestamp>.png/.html.
    Only active when LOG_LEVEL=DEBUG or always (it's cheap and very useful).
    """
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.join(SCREENSHOT_DIR, f"{label}_{ts}")
        driver.save_screenshot(base + ".png")
        with open(base + ".html", "w", encoding="utf-8", errors="replace") as fh:
            fh.write(driver.page_source)
        logger.info("[debug screenshot] saved %s.png + .html", base)
    except Exception as exc:
        logger.debug("Screenshot failed: %s", exc)


def _dismiss_alert(driver: webdriver.Chrome) -> Optional[str]:
    """
    OPT-A: Instant alert check.
    Uses direct driver.switch_to.alert (NO WebDriverWait).
    Returns None immediately when no alert is present (which is always for
    this portal — it uses HTML dialogs, not JS alerts).
    """
    try:
        alert = driver.switch_to.alert
        text  = alert.text
        alert.dismiss()
        logger.debug("Alert dismissed: %s", text)
        return text
    except (NoAlertPresentException, Exception):
        return None


def _wait(driver: webdriver.Chrome, by: By, value: str, timeout: int = PAGE_TIMEOUT):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    except TimeoutException:
        return None


def _js_click(driver: webdriver.Chrome, element) -> None:
    driver.execute_script("arguments[0].click();", element)


def _is_portal_ready(driver: webdriver.Chrome) -> bool:
    """
    OPT-B: Return True ONLY when the portal is fully loaded AND the session
    is still alive.

    Checks (all must pass):
      1. URL contains visa.go.kr (not openSessionOut / error page)
      2. Radio buttons present in DOM
      3. The gb01 receipt input (sINVITEE_SEQ) exists AND is visible —
         this element is rendered by the active session; on an expired
         session the form section is hidden/absent even though radio
         buttons remain in the static HTML.
    """
    try:
        url = driver.current_url
        if "visa.go.kr" not in url:
            return False
        if "openSessionOut" in url or "error" in url.lower():
            return False
        driver.find_element(By.CSS_SELECTOR, "input[type='radio'][name='RADIOSEARCH']")
        # Confirm the form is truly active (session alive)
        # Use existence check (not offsetParent/visibility) because the
        # portal opens on the gb03 tab — the gb01 section (searchType1) is
        # display:none at that point, so sINVITEE_SEQ.offsetParent IS null
        # even in a healthy session.  Checking existence is correct:
        #   valid session  → sINVITEE_SEQ is in the DOM → True → OPT-B fires
        #   expired/error  → navigated to openSessionOut (caught above) or
        #                    DOM is empty → False → full reload
        result = driver.execute_script(
            "return !!(document.getElementById('sINVITEE_SEQ')"
            "       && document.getElementById('sFROMDATE')"
            "       && document.getElementById('frmCmmAuth'));"
        )
        return bool(result)
    except Exception:
        return False


def _load_portal(driver: webdriver.Chrome) -> bool:
    """
    Load the portal.  OPT-B: skip driver.get() if page is already loaded.
    Falls back to a full reload only when the page is not on visa.go.kr.
    """
    # ── OPT-B: already on portal — just dismiss any stray alerts ─────────
    if _is_portal_ready(driver):
        logger.debug("Portal already loaded — skipping page reload (OPT-B)")
        _dismiss_alert(driver)
        return True

    # ── Full load (first check or after a crash) ──────────────────────────
    try:
        logger.debug("Loading portal from scratch")
        driver.get(PORTAL_URL)
        _dismiss_alert(driver)
        el = _wait(driver, By.CSS_SELECTOR,
                   "input[type='radio'][name='RADIOSEARCH']",
                   timeout=PAGE_TIMEOUT)
        if el is None:
            logger.warning("Portal radio buttons not found after %ds", PAGE_TIMEOUT)
            return False
        _dismiss_alert(driver)
        return True
    except UnexpectedAlertPresentException:
        _dismiss_alert(driver)
        return False
    except Exception as exc:
        logger.error("Portal load error: %s", exc)
        return False


# ── Result parsers ────────────────────────────────────────────────────────────

def _parse_result_gb03(driver: webdriver.Chrome) -> dict:
    """
    Parse the gb03 (재외공관) result from DOM after form submission.

    Fields read:
      APPL_DTM        — application date
      ENTRY_PURPOSE   — entry purpose (유학.연수, etc.)
      PROC_STS_CDNM_1 — status (사용완료, 허가, 불허, 접수, 심사 …)
      VISA_KIND_CD    — visa type (단수/복수)
      SOJ_QUAL_NM     — residence qualification (D-2-1, etc.)
      VISA_EXPR_YMD   — entry expiry date
    """
    import re as _re

    _dismiss_alert(driver)

    # ── Wait for AJAX to actually deliver data ────────────────────────────
    # WAIT STRATEGY (post-fix):
    # 1. Step 0 in check_diplomatic() FORCES resultValue.style.display='none' so
    #    this wait starts from a clean known state.
    # 2. We wait for EITHER:
    #    A) APPL_DTM contains text → data arrived from AJAX
    #    B) resultValue becomes visible → AJAX callback showed the "no data" div
    # NOTE: We do NOT use page_source string search — "조회된 데이터가 없습니다"
    # exists in the static HTML, so page_source always contains it.
    # ── CRITICAL FIX — use DOM visibility, NOT page_source string search ─────
    # CONFIRMED BUG: "조회된 데이터가 없습니다" is present in the STATIC HTML inside
    # div#resultValue (display:none) on initial page load.  The page's jQuery
    # ready() block runs:  if ("0" == 0) { $("#resultValue").show(); }
    # which makes resultValue VISIBLE immediately.  Any page_source check for
    # this phrase therefore fires at once — before AJAX has even started.
    #
    # The portal's AJAX callback controls visibility:
    #   • AJAX returns 0 results → $("#resultValue").show()   (no-data state)
    #   • AJAX returns >0 results → $("#result0_1").show()    (data state)
    #
    # We reset resultValue.style.display = 'none' in Step 0 (before fn_search),
    # then wait here for visibility to change as the definitive AJAX signal.
    try:
        WebDriverWait(driver, RESULT_WAIT).until(
            lambda d: (
                # Case A: real data arrived — APPL_DTM has content
                bool(
                    d.find_elements(By.ID, "APPL_DTM")
                    and d.find_element(By.ID, "APPL_DTM").text.strip()
                )
            ) or (
                # Case B: AJAX callback set resultValue visible (genuine no-data)
                bool(d.execute_script(
                    "var el=document.getElementById('resultValue');"
                    "return !!(el && window.getComputedStyle(el).display!=='none');"
                ))
            )
        )
    except TimeoutException:
        # RESULT_WAIT elapsed — check whether portal session expired
        cur_url = driver.current_url
        if "visa.go.kr" not in cur_url or "openSessionOut" in cur_url:
            logger.warning("[gb03] portal session expired (timeout) — at %s", cur_url)
            _save_debug_screenshot(driver, "gb03_session_expired")
            return {"error": "session_expired"}   # triggers retry + full reload
        logger.warning("AJAX result not confirmed after %ds — reading page_source anyway", RESULT_WAIT)
    except Exception:
        pass

    _dismiss_alert(driver)
    # Guard: page may have navigated after session expiry
    cur_url = driver.current_url
    if "visa.go.kr" not in cur_url or "openSessionOut" in cur_url:
        logger.warning("[gb03] session expired (post-wait) — at %s", cur_url)
        _save_debug_screenshot(driver, "gb03_session_expired")
        return {"error": "session_expired"}
    page = driver.page_source

    # ── No-data check (via DOM visibility, NOT page_source string) ──────────
    # The phrase "조회된 데이터가 없습니다" is always in the static HTML, so we
    # cannot rely on its presence in page_source.  We check whether the portal's
    # AJAX callback made div#resultValue visible (the definitive no-data signal).
    no_data_visible = driver.execute_script(
        "var el=document.getElementById('resultValue');"
        "return !!(el && window.getComputedStyle(el).display!=='none');"
    )
    if no_data_visible:
        logger.info("[gb03] resultValue visible → genuine no-data from AJAX")
        _save_debug_screenshot(driver, "gb03_not_found")
        return {"not_found": True}

    # ── Read DOM fields ───────────────────────────────────────────────────
    def _get(div_id: str) -> str:
        try:
            return _re.sub(r"\s+", " ",
                           driver.find_element(By.ID, div_id).text.strip())
        except Exception:
            return ""

    appl_date     = _get("APPL_DTM")
    entry_purpose = _get("ENTRY_PURPOSE")
    visa_kind     = _get("VISA_KIND_CD")
    soj_qual      = _get("SOJ_QUAL_NM")
    visa_expiry   = _get("VISA_EXPR_YMD")

    status_ko = ""
    try:
        els = driver.find_elements(By.ID, "PROC_STS_CDNM_1")
        if els:
            status_ko = _re.sub(r"\s+", " ", els[0].text.strip())
    except Exception:
        pass

    # Rejection reason
    reason = ""
    try:
        m = _re.search(
            r"귀하의 비자신청에 대한 불허사유[^<]*(?:</[^>]+>)*\s*<td[^>]*>(.*?)</td>",
            page, _re.DOTALL
        )
        if m:
            reason = _re.sub(r"\s+", " ",
                             _re.sub(r"<[^>]+>", " ", m.group(1))).strip()
    except Exception:
        pass

    # ── Status mapping ────────────────────────────────────────────────────
    status_map = {
        "사용완료": "USED",
        "허가":     "APPROVED",
        "발급":     "ISSUED",
        "불허":     "REJECTED",
        "접수":     "RECEIVED",
        "심사":     "UNDER_REVIEW",
        "취하":     "WITHDRAWN",
        "반려":     "RETURNED",
    }
    status_en = "UNKNOWN"
    for ko_kw, en_kw in status_map.items():
        if ko_kw in status_ko:
            status_en = en_kw
            break

    if not status_ko:                           # fallback: scan raw HTML
        for ko_kw, en_kw in status_map.items():
            if ko_kw in page:
                status_en = en_kw
                status_ko = ko_kw
                break

    visa_type = soj_qual + (f" ({visa_kind})" if visa_kind else "") if soj_qual else visa_kind

    if entry_purpose and entry_purpose not in status_ko:
        status_ko = f"{entry_purpose} — {status_ko}" if status_ko else entry_purpose

    if visa_expiry and status_en in ("USED", "APPROVED", "ISSUED"):
        # HTML confirmed: VISA_EXPR_YMD is stored as "(2026.04.22.)" with outer parens.
        # Strip them before appending so we don't get double-parens like "(만료: (2026.04.22.))"
        expiry_clean = visa_expiry.strip().strip("()")
        if expiry_clean and expiry_clean not in status_ko:
            status_ko += f" (입국만료: {expiry_clean})"

    if not status_ko and not appl_date and not visa_type:
        # One final check: maybe resultValue is now visible (late AJAX delivery)
        try:
            rv_vis = driver.execute_script(
                "var el=document.getElementById('resultValue');"
                "return !!(el && window.getComputedStyle(el).display!=='none');"
            )
        except Exception:
            rv_vis = False
        if rv_vis:
            logger.info("[gb03] resultValue visible on empty-DOM fallback → not_found")
            _save_debug_screenshot(driver, "gb03_not_found")
            return {"not_found": True}
        logger.warning("[gb03] no status/date/type fields found in DOM after AJAX")
        _save_debug_screenshot(driver, "gb03_empty_dom")
        return {"not_found": True}

    # ── Extract REPORTSE onclick args (cert available when approved) ──────
    cert_fn_args = ""
    try:
        rse = driver.find_elements(By.ID, "REPORTSE")
        if rse:
            href = rse[0].get_attribute("href") or ""
            m_args = re.search(r"fn_reportByCsvMap\d+\(([^)]+)\)", href)
            if m_args:
                cert_fn_args = m_args.group(1)
    except Exception:
        pass

    return {
        "status_ko":    status_ko.strip(),
        "status_en":    status_en,
        "visa_type":    visa_type.strip(),
        "app_date":     appl_date.strip(),
        "reason":       reason.strip(),
        "cert_fn_args": cert_fn_args,   # non-empty → cert download available
    }


def _parse_result_gb01(driver: webdriver.Chrome) -> dict:
    """
    Parse gb01 E-Visa Individual result.

    Strategy (ID-first, heuristic fallback):
      1. Wait up to 20 s for EITHER:
           – #resultValue visible     → genuine AJAX no-data response
           – #result0_1 / #result1_1 has non-empty <td>  → data arrived
      2. PRIMARY: read result by confirmed DOM IDs from portal HTML:
           PROC_STS_CDNM  (진행상태 / status)
           APPL_YMD       (신청일자 / application date)
           SOJ_QUAL_NM    (체류자격 / visa type)
      3. FALLBACK: heuristic scan of all <td> texts (backward-compatible).
    """
    import re as _re

    _dismiss_alert(driver)

    # ── Visibility-based AJAX wait (up to 20 s) ──────────────────────────
    deadline = time.time() + 20
    data_arrived = False
    while time.time() < deadline:
        try:
            state = driver.execute_script(
                "var rv = document.getElementById('resultValue');"
                "var rvVis = !!(rv && window.getComputedStyle(rv).display !== 'none');"
                "var cells = document.querySelectorAll('#result0_1 td, #result1_1 td');"
                "var hasText = false;"
                "for(var i=0;i<cells.length;i++){if(cells[i].innerText.trim()){hasText=true;break;}}"
                "return {rvVis: rvVis, hasText: hasText};"
            )
            if state["rvVis"] or state["hasText"]:
                data_arrived = state["hasText"]
                break
        except Exception:
            pass
        time.sleep(0.5)

    _dismiss_alert(driver)

    # ── Check resultValue visibility ──────────────────────────────────────
    try:
        rv_vis_01 = driver.execute_script(
            "var el=document.getElementById('resultValue');"
            "return !!(el && window.getComputedStyle(el).display!=='none');"
        )
    except Exception:
        rv_vis_01 = False

    if rv_vis_01 and not data_arrived:
        return {"not_found": True}

    # ── PRIMARY: DOM ID-based extraction (portal-confirmed IDs) ──────────
    # Portal HTML confirmed: PROC_STS_CDNM, APPL_YMD, SOJ_QUAL_NM
    def _id_text(eid: str) -> str:
        """Get text/value of element by ID (text first, then .value attr)."""
        try:
            els = driver.find_elements(By.ID, eid)
            if els:
                t = (els[0].text or "").strip()
                if not t:
                    t = (els[0].get_attribute("value") or "").strip()
                # Also try innerText via JS (handles hidden elements)
                if not t:
                    t = (driver.execute_script(
                        "var e=document.getElementById(arguments[0]);"
                        "return e ? (e.innerText||e.value||e.textContent||'').trim() : '';",
                        eid
                    ) or "").strip()
                return t
        except Exception:
            pass
        return ""

    status_ko = _id_text("PROC_STS_CDNM") or _id_text("PROC_STS_CDNM_1")
    app_date  = _id_text("APPL_YMD") or _id_text("APPL_DTM")
    visa_type = _id_text("SOJ_QUAL_NM")

    # ── Extract rejection reason from NONPERMRSNCD row ──────────────────
    # Portal HTML confirmed: <tr id="NONPERMRSNCD"> contains the reason
    # text in its <td colspan="3">, e.g.:
    #   "귀하의 비자신청에 대한 불허사유는 다음과 같습니다 :\n5. ...\n6. ..."
    reason = ""
    try:
        reason_rows = driver.find_elements(By.ID, "NONPERMRSNCD")
        if reason_rows:
            tds = reason_rows[0].find_elements(By.TAG_NAME, "td")
            if tds:
                raw_reason = tds[0].text.strip()
                reason = re.sub(r"\s+", " ", raw_reason)
    except Exception:
        pass

    # ── Extract e-visa number and expiry (for APPROVED / ISSUED status) ─
    ev_no      = _id_text("EV_NO")       # 전자비자번호
    ev_expiry  = _id_text("EV_EXPR_YMD") # 유효기간 expiry date
    visa_gbnm  = _id_text("APPL_VISA_GBNM")  # 비자종류 (1회/복수)
    judg_dt    = _id_text("JUDG_DTM")    # 심사일자 decision date

    # Enhance visa_type with entry type (single/multiple) if present
    if visa_gbnm and visa_gbnm not in visa_type:
        visa_type = f"{visa_type} / {visa_gbnm}" if visa_type else visa_gbnm

    # For approved visas, append e-visa number and expiry to status_ko
    if ev_no and status_ko:
        status_ko = f"{status_ko} (비자번호: {ev_no})"
    if ev_expiry and status_ko:
        expiry_clean = ev_expiry.strip().strip("()")
        if expiry_clean:
            status_ko = f"{status_ko} (만료: {expiry_clean})"

    if status_ko:
        logger.debug("[gb01] ID-based parse: status=%r visa=%r date=%r reason=%r",
                     status_ko, visa_type, app_date, reason[:40] if reason else "")
        return {"status_ko": status_ko, "visa_type": visa_type,
                "app_date": app_date, "reason": reason}

    # ── FALLBACK: heuristic text scan ────────────────────────────────────
    # Try result1_1 (data row) BEFORE result0_1 (header row) to avoid
    # picking up column-header text as status/date values.
    cells = driver.find_elements(
        By.CSS_SELECTOR, "#result1_1 td, #result0_1 td, .board_view02 td"
    )
    texts = [_re.sub(r"\s+", " ", c.text.strip()) for c in cells if c.text.strip()]
    if not texts:
        if rv_vis_01:
            return {"not_found": True}
        logger.warning("[gb01] empty DOM after wait — possible session timeout")
        return {"not_found": True}

    date_re   = _re.compile(r"\d{4}[-./]\d{2}[-./]\d{2}")
    visa_re   = _re.compile(r"[가-힣A-Z].*\([A-Z]-\d")
    status_kw = ["접수", "심사", "발급", "불허", "거부", "보완", "허가", "사용완료",
                 "발급준비", "추가심사", "여권교부"]

    status_ko = visa_type = app_date = reason = ""
    for txt in texts:
        if not status_ko and any(k in txt for k in status_kw):
            status_ko = txt
        if not visa_type and visa_re.search(txt):
            visa_type = txt
        if not app_date and date_re.search(txt):
            app_date = txt

    if len(texts) >= 5:
        last = texts[-1]
        if last not in (status_ko, visa_type, app_date) and not date_re.match(last):
            reason = last

    logger.debug("[gb01] heuristic parse: texts=%s → status=%r", texts[:6], status_ko)
    return {"status_ko": status_ko, "visa_type": visa_type,
            "app_date": app_date, "reason": reason}


# ── Public check functions ────────────────────────────────────────────────────

def check_evisa(driver: webdriver.Chrome, receipt: str, passport: str,
               name: str = "", dob: str = "") -> dict:
    """E-Visa Individual check (gb01 tab). Used by admins.

    Requires all 4 portal fields:
      sINVITEE_SEQ (receipt), sPASS_NO (passport),
      sEK_NM (name), sFROMDATE (YYYY-MM-DD DOB).
    name should be UPPERCASE Latin; dob as YYYYMMDD or YYYY-MM-DD.
    """
    MAX_TRIES = 3
    for attempt in range(1, MAX_TRIES + 1):
        logger.info("[E-Visa attempt %d] receipt=%s passport=%s", attempt, receipt, passport)

        if not _load_portal(driver):
            if attempt == MAX_TRIES:
                return {"error": "Portal failed to load"}
            time.sleep(3); continue

        try:
            # ── Step 0: Reset resultValue AND clear stale result cells ──────
            # CRITICAL: clear previous record's cell content so the AJAX-wait
            # loop doesn't fire immediately on stale text from the prior check.
            # Without this, records checked by the same worker after the first
            # one can receive the previous record's status.
            try:
                driver.execute_script(
                    # Hide resultValue so visibility-wait starts from clean state
                    "var rv=document.getElementById('resultValue');"
                    "if(rv) rv.style.display='none';"
                    # Clear all result cell content (confirmed IDs from portal HTML)
                    ";['PROC_STS_CDNM','APPL_YMD','SOJ_QUAL_NM','INVITEE_SEQ',"
                    " 'MEM_NM','EK_NM','APPL_VISA_GBNM','JUDG_DTM',"
                    " 'EV_NO','EV_EXPR_YMD','CCVI_NO']"
                    ".forEach(function(id){"
                    "  var el=document.getElementById(id);"
                    "  if(el) el.innerHTML='';"
                    "});"
                    # Hide rejection-reason row so it doesn't show stale text
                    "var nr=document.getElementById('NONPERMRSNCD');"
                    "if(nr) nr.style.display='none';"
                )
            except Exception:
                pass

            radio = _wait(driver, By.ID, "RADIOSEARCH01")
            if radio and not radio.is_selected():
                _js_click(driver, radio)
                time.sleep(0.3)
            _dismiss_alert(driver)
            driver.execute_script(
                "document.getElementById('searchType1').style.display='block';"
                "var sc=document.getElementById('searchType_common');"
                "if(sc) sc.style.display='block';"
            )

            # ── Step 1: Receipt (sINVITEE_SEQ) ──────────────────────────
            f_receipt = _wait(driver, By.ID, "sINVITEE_SEQ", timeout=8)
            if f_receipt is None:
                return {"error": "sINVITEE_SEQ field not found"}
            f_receipt.clear(); f_receipt.send_keys(receipt)

            # ── Step 2: Passport (sPASS_NO) ──────────────────────────────
            f_pass = _wait(driver, By.ID, "sPASS_NO", timeout=8)
            if f_pass is None:
                return {"error": "sPASS_NO field not found"}
            f_pass.clear(); f_pass.send_keys(passport.upper())
            _dismiss_alert(driver)

            # ── Step 3: Name (sEK_NM) — required by portal validation ────
            nm = name.strip().upper()
            f_name = _wait(driver, By.ID, "sEK_NM", timeout=5)
            if f_name is None:
                return {"error": "sEK_NM field not found"}
            f_name.clear()
            if nm:
                f_name.send_keys(nm)

            # ── Step 4+5: DOB + fn_search() atomically (same as gb03) ────
            # gfn_isValidDate1 strips dashes before checking → "2003-06-18"
            # passes because it becomes "20030618" (8 digits, valid range).
            # We set sFROMDATE WITH dashes so fn_search sends YYYY-MM-DD.
            raw_dob = re.sub(r"[\s.\-/]", "", dob)          # → YYYYMMDD
            dob_fmt = (f"{raw_dob[:4]}-{raw_dob[4:6]}-{raw_dob[6:]}"
                       if len(raw_dob) == 8 else dob)

            logger.info(
                "[gb01 pre-submit] receipt=%s passport=%s name=%s dob=%s",
                receipt, passport, nm, dob_fmt
            )

            # Single atomic JS: set sFROMDATE then call fn_search() so the
            # mask cannot interfere between the two operations.
            driver.execute_script(
                "document.getElementById('sFROMDATE').value = arguments[0];"
                "fn_search();",
                dob_fmt,
            )
            time.sleep(0.5)   # let portal validation JS run before polling
            _dismiss_alert(driver)

        except UnexpectedAlertPresentException:
            _dismiss_alert(driver)
            if attempt == MAX_TRIES:
                return {"error": "Unexpected alert during form fill"}
            time.sleep(2); continue
        except Exception as exc:
            if attempt == MAX_TRIES:
                return {"error": str(exc)}
            time.sleep(2); continue

        result = _parse_result_gb01(driver)
        if result.get("error") and attempt < MAX_TRIES:
            time.sleep(3); continue
        # Retry on not_found — likely a stale pre-warm session.
        # Navigate away so _is_portal_ready() returns False on next attempt,
        # forcing a full driver.get(PORTAL_URL) instead of reusing stale DOM.
        if result.get("not_found") and attempt < MAX_TRIES:
            logger.warning(
                "[gb01] not_found on attempt %d — navigating away to force fresh reload",
                attempt
            )
            try:
                driver.get("about:blank")   # invalidates OPT-B cache
            except Exception:
                pass
            time.sleep(3); continue
        return result

    return {"error": "Max retries exceeded"}



def download_approval_cert(
    driver: "webdriver.Chrome", passport: str, name: str, dob: str
) -> dict:
    """Download the 비자발급확인서 (Visa Approval Certificate) PDF.

    Requires a Chrome driver built with build_driver(download_dir=...).
    Returns:
      {"file_path": "/abs/path/to/file.pdf"}   on success
      {"error": "reason"}                        on failure
      {"not_approved": True, ...}                if status is not APPROVED/ISSUED
    """
    import glob as _glob
    import time as _time
    import os as _os

    MAX_TRIES = 2
    for attempt in range(1, MAX_TRIES + 1):
        logger.info("[cert dl attempt %d] passport=%s", attempt, passport)

        if not _load_portal(driver):
            if attempt == MAX_TRIES:
                return {"error": "Portal failed to load for cert download"}
            _time.sleep(3); continue

        try:
            # Select gb03 tab
            try:
                radio03 = _wait(driver, By.CSS_SELECTOR,
                                "input[type='radio'][value='gb03']", timeout=10)
            except Exception:
                radio03 = _wait(driver, By.ID, "RADIOSEARCH03", timeout=5)
            _js_click(driver, radio03)
            _time.sleep(0.5)
            _dismiss_alert(driver)

            # Format DOB
            dob_fmt = dob[:4] + "-" + dob[4:6] + "-" + dob[6:] if len(dob) == 8 else dob

            # Fill passport, name, DOB
            driver.execute_script(
                "document.getElementById('sBUSI_GBNO').value = arguments[0];"
                "document.getElementById('sEK_NM').value     = arguments[1];"
                "document.getElementById('sFROMDATE').value  = arguments[2];",
                passport, name.upper(), dob_fmt,
            )
            _dismiss_alert(driver)

            # Set dropdown to passport-number search
            try:
                from selenium.webdriver.support.ui import Select as _Select
                sel = _Select(driver.find_element(By.ID, "BUSI_GB"))
                sel.select_by_value("PASS_NO")
            except Exception:
                pass

            # Clear stale result cells
            driver.execute_script(
                "var rv=document.getElementById('resultValue');"
                "if(rv) rv.style.display='none';"
                ";['APPL_DTM','PROC_STS_CDNM_1','VISA_KIND_CD','VISA_EXPR_YMD']"
                ".forEach(function(id){"
                "  var el=document.getElementById(id);"
                "  if(el) el.innerHTML='';"
                "});"
            )

            # Submit
            driver.execute_script(
                "document.getElementById('sFROMDATE').value = arguments[0]; fn_search();",
                dob_fmt,
            )
            _time.sleep(0.5)
            _dismiss_alert(driver)

        except Exception as exc:
            if attempt == MAX_TRIES:
                return {"error": f"Form fill failed: {exc}"}
            _time.sleep(3); continue

        # Wait for AJAX result
        try:
            WebDriverWait(driver, RESULT_WAIT).until(
                lambda d: (
                    bool(d.find_elements(By.ID, "APPL_DTM")
                         and d.find_element(By.ID, "APPL_DTM").text.strip())
                ) or (
                    bool(d.execute_script(
                        "var el=document.getElementById('resultValue');"
                        "return !!(el && window.getComputedStyle(el).display!=='none');"
                    ))
                )
            )
        except TimeoutException:
            if attempt == MAX_TRIES:
                return {"error": "Portal AJAX timeout during cert download"}
            _time.sleep(3); continue
        except Exception:
            pass

        _dismiss_alert(driver)

        # Parse the result to confirm approval
        result = _parse_result_gb03(driver)
        if result.get("not_found"):
            return {"error": "Record not found on portal"}
        if result.get("error"):
            if attempt == MAX_TRIES:
                return {"error": result["error"]}
            _time.sleep(3); continue
        if result.get("status_en") not in ("APPROVED", "ISSUED", "USED"):
            return {"not_approved": True,
                    "status_en": result.get("status_en", "UNKNOWN"),
                    "status_ko": result.get("status_ko", "")}

        # Click #REPORTSE (비자발급확인서 button)
        try:
            rse_els = driver.find_elements(By.ID, "REPORTSE")
            if not rse_els:
                rse_els = driver.find_elements(By.PARTIAL_LINK_TEXT, "비자발급확인서")
            if not rse_els:
                return {"error": "Certificate button (#REPORTSE) not found on page"}
            rse = rse_els[0]
            if not rse.is_displayed():
                return {"error": "Certificate button is hidden — cert may not be ready"}
            logger.info("[cert dl] Clicking #REPORTSE …")
            _js_click(driver, rse)
        except Exception as exc:
            if attempt == MAX_TRIES:
                return {"error": f"Could not click cert button: {exc}"}
            _time.sleep(3); continue

        # Determine Chrome download dir (injected via CDP at driver build time)
        # Read the download directory that build_driver() tagged on the driver.
        # Browser.getDownloadDirectory is NOT a real CDP command — using the
        # custom attribute is the only reliable way to recover the per-request
        # temp directory from inside this function.
        dl_dir = getattr(driver, "_cert_download_dir", None)
        if not dl_dir:
            # Last resort: scan the base cert dir (catches manual test calls
            # where tmp_dir was passed to build_driver but attribute tagging
            # failed for some reason).
            dl_dir = _os.path.abspath(CERT_DOWNLOAD_DIR)
            logger.warning("[cert dl] _cert_download_dir not set on driver — "
                           "falling back to base cert dir %s", dl_dir)

        logger.info("[cert dl] Waiting for file in %s …", dl_dir)
        deadline = _time.time() + 45
        pdf_path = None
        while _time.time() < deadline:
            # Catch any completed download (pdf, hwp, xlsx — whatever the portal sends).
            # Exclude .crdownload (Chrome in-progress) and .tmp files.
            all_files = _glob.glob(dl_dir + "/*")
            complete = [
                p for p in all_files
                if _os.path.isfile(p)
                and not p.endswith((".crdownload", ".tmp", ".part"))
            ]
            if complete:
                pdf_path = max(complete, key=lambda p: _os.path.getmtime(p))
                logger.info("[cert dl] ✅ Downloaded: %s (%d bytes)",
                            _os.path.basename(pdf_path), _os.path.getsize(pdf_path))
                break
            _time.sleep(1.5)

        if pdf_path:
            return {"file_path": pdf_path}

        if attempt == MAX_TRIES:
            return {"error": "Download did not complete within 45 s — try again later"}
        _time.sleep(3)

    return {"error": "Max retries exceeded in download_approval_cert"}


def check_diplomatic(driver: webdriver.Chrome, passport: str, name: str, dob: str) -> dict:
    """
    Overseas Diplomatic Mission check (재외공관 — gb03 tab).
    Used by students who applied at an overseas Korean embassy (e.g. Tashkent).

    dob  : YYYYMMDD  (e.g. "20071014")
    name : UPPERCASE Latin  (e.g. "ORIPOV AKHADBEK AZIZBEK UGLI")
    """
    MAX_TRIES = 3
    for attempt in range(1, MAX_TRIES + 1):
        logger.info("[Diplomatic/gb03 attempt %d] passport=%s name=%s dob=%s",
                    attempt, passport, name, dob)

        if not _load_portal(driver):
            if attempt == MAX_TRIES:
                return {"error": "Portal failed to load"}
            time.sleep(3); continue

        try:
            # ── Step 0: Clear stale results from any previous search ──────
            # HTML inspection confirmed:
            #   • fn_changeDivHide('gb03') hides result3_2 but does NOT clear APPL_DTM text
            #   • On 2nd+ check, APPL_DTM still has old content → wait fires immediately
            #     with stale data.  We must wipe it before clicking Search.
            #   • Calling fn_changeDivHide also resets show/hide state correctly.
            driver.execute_script(
                "try { fn_changeDivHide('gb03'); } catch(e) {}"
                "var _a = document.getElementById('APPL_DTM');"
                "if (_a) _a.innerHTML = '';"
                "var _rv = document.getElementById('resultValue');"
                "if (_rv) _rv.style.display = 'none';"
            )
            _dismiss_alert(driver)

            # ── Step 1: Ensure gb03 radio is selected ─────────────────────
            # HTML confirmed: RADIOSEARCH03 is the FIRST radio and has checked='checked'
            # by default — the portal always opens on the gb03 tab.
            # We still check and click to guarantee the tab is active.
            radio03 = _wait(driver, By.CSS_SELECTOR,
                            "input[type='radio'][value='gb03']", timeout=10)
            if radio03 is None:
                radio03 = _wait(driver, By.ID, "RADIOSEARCH03", timeout=5)
            if radio03 is None:
                return {"error": "gb03 radio button not found"}

            if not radio03.is_selected():
                _js_click(driver, radio03)
                time.sleep(0.5)   # let fn_changeDivHide() fire
            _dismiss_alert(driver)

            # ── Step 2: Set BUSI_GB dropdown via Selenium Select ─────────
            # PASS_NO is the first (default) option but Select() fires onchange,
            # which the portal requires to bind the passport field correctly.
            try:
                busi_gb_el = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.ID, "BUSI_GB"))
                )
                Select(busi_gb_el).select_by_value("PASS_NO")
                time.sleep(0.2)
            except Exception as exc:
                logger.warning("BUSI_GB select failed: %s — JS fallback", exc)
                driver.execute_script(
                    "var gb=document.getElementById('BUSI_GB');"
                    "if(gb){gb.value='PASS_NO';"
                    "gb.dispatchEvent(new Event('change',{bubbles:true}));}"
                )
                time.sleep(0.2)
            _dismiss_alert(driver)

            # ── Step 3: Fill passport number ──────────────────────────────
            f_pass = WebDriverWait(driver, 8).until(
                EC.visibility_of_element_located((By.ID, "sBUSI_GBNO"))
            )
            f_pass.clear()
            f_pass.send_keys(passport.upper())

            # ── Step 4: Fill full name ────────────────────────────────────
            f_name = driver.find_element(By.ID, "sEK_NM")
            f_name.clear()
            f_name.send_keys(name.upper())

            # ── Step 5 + 6: Set DOB and call fn_search() atomically via JS ──
            #
            # ─────────────────────────────────────────────────────────────────
            # CONFIRMED ROOT CAUSE (traced through live portal JS):
            # ─────────────────────────────────────────────────────────────────
            # fn_search() for gb03 does:
            #   searchSubmit.addParam("sFROMDATE", $("#sFROMDATE").val());
            #
            # The raw jQuery .val() is passed to addParam — no stripping.
            # Under IBM mask (YYYY-MM-DD), .val() returns "2007-10-14" (dashes).
            # ComSubmit.addParam injects this as a hidden input into #frmCmmAuth.
            # ComSubmit.tran() serializes #frmCmmAuth → AJAX POST body contains:
            #   sFROMDATE=2007-10-14
            # The server therefore expects YYYY-MM-DD format.
            #
            # Previous code set input.value = "20071014" (raw YYYYMMDD),
            # making fn_search() send sFROMDATE=20071014 → server mismatch
            # → always NOT_FOUND.
            #
            # SOLUTION:
            #   1. Format dob as YYYY-MM-DD (matching the mask's native output).
            #   2. Set sFROMDATE AND call fn_search() in ONE JS execution so
            #      fn_search reads the value before any blur/mask event runs.
            #
            # NOTE: gfn_isValidDate1 internally strips dashes for validation,
            # so both "2007-10-14" and "20071014" pass — but only the
            # dashed format reaches the server correctly.
            # ── CRITICAL DATE FORMAT FIX ─────────────────────────────────────
            # Deep analysis of live portal JS (common.js, dateUtils.js) confirmed:
            #
            # fn_search() for gb03 sends:
            #   searchSubmit.addParam("sFROMDATE", $("#sFROMDATE").val());
            #
            # The raw .val() is passed — NO trimSpecialChar applied.
            # Under normal IBM mask operation (YYYY-MM-DD mask), the visible
            # sFROMDATE input stores "2007-10-14" WITH dashes.
            # So the server receives sFROMDATE = "2007-10-14".
            #
            # Our old code set input.value = "20071014" (raw YYYYMMDD),
            # so the server received "20071014" — a format mismatch → NOT_FOUND.
            #
            # FIX: inject YYYY-MM-DD so fn_search sends the same format
            # as a real browser user.
            dob_fmt = f"{dob[:4]}-{dob[4:6]}-{dob[6:]}"   # "20071014" → "2007-10-14"

            # Log what we're about to submit (for debugging)
            try:
                _v = driver.execute_script(
                    "return ["
                    "  document.getElementById('BUSI_GB')    ? document.getElementById('BUSI_GB').value    : 'N/A',"
                    "  document.getElementById('sBUSI_GBNO') ? document.getElementById('sBUSI_GBNO').value : 'N/A',"
                    "  document.getElementById('sEK_NM')     ? document.getElementById('sEK_NM').value     : 'N/A'"
                    "];"
                )
                logger.info(
                    "[gb03 pre-submit] BUSI_GB=%s | sBUSI_GBNO=%s | sEK_NM=%s | sFROMDATE=%s",
                    *_v, dob_fmt
                )
            except Exception:
                pass

            # Single atomic JS call: set sFROMDATE (YYYY-MM-DD) then call fn_search().
            # fn_search reads sFROMDATE BEFORE any blur event, so value is intact.
            # gfn_isValidDate1 strips dashes internally for validation → passes.
            # addParam then stores "2007-10-14" → server receives correct format.
            driver.execute_script(
                "document.getElementById('sFROMDATE').value = arguments[0]; "
                "fn_search();",
                dob_fmt
            )
            _dismiss_alert(driver)

            # ── Post-submit sanity log: verify fn_search actually ran ──────────
            # Read the hidden input that addParam injected into frmCmmAuth.
            # If sFROMDATE is present there, the fn_search() call succeeded.
            try:
                submitted_vals = driver.execute_script(
                    "var f = document.getElementById('frmCmmAuth');"
                    "if (!f) return 'frmCmmAuth not found';"
                    "var inp = f.querySelector('input[name=\"sFROMDATE\"]');"
                    "var inpBN = f.querySelector('input[name=\"sBUSI_GBNO\"]');"
                    "var inpNM = f.querySelector('input[name=\"sEK_NM\"]');"
                    "var inpGB = f.querySelector('input[name=\"sBUSI_GB\"]');"
                    "return ["
                    "  inp   ? inp.value   : 'MISSING',"
                    "  inpBN ? inpBN.value : 'MISSING',"
                    "  inpNM ? inpNM.value : 'MISSING',"
                    "  inpGB ? inpGB.value : 'MISSING'"
                    "];"
                )
                if isinstance(submitted_vals, list) and len(submitted_vals) == 4:
                    logger.info(
                        "[gb03 frmCmmAuth] sFROMDATE=%s sBUSI_GBNO=%s sEK_NM=%s sBUSI_GB=%s",
                        *submitted_vals
                    )
                else:
                    # String means frmCmmAuth missing → session likely expired
                    logger.warning("[gb03 frmCmmAuth] sanity check: %s", submitted_vals)
            except Exception as _e:
                logger.debug("frmCmmAuth sanity log failed: %s", _e)

            # ── Post-submit URL guard: detect instant session expiry ──────────
            # If fn_search AJAX got a session error response, the portal
            # navigates away immediately.  Detect it here so we can force
            # a full reload before the next attempt.
            time.sleep(0.8)   # let AJAX callback run
            _guard_url = driver.current_url
            if "visa.go.kr" not in _guard_url or "openSessionOut" in _guard_url:
                logger.warning("[gb03] session expired post-fn_search — reloading portal (%s)", _guard_url)
                _save_debug_screenshot(driver, "gb03_session_expired")
                try:
                    driver.get(PORTAL_URL)
                    _wait(driver, By.CSS_SELECTOR,
                          "input[type='radio'][name='RADIOSEARCH']",
                          timeout=PAGE_TIMEOUT)
                    logger.info("[gb03] portal reloaded after session expiry")
                except Exception:
                    pass
                # Fall through to parser — it will detect empty DOM and return error

        except UnexpectedAlertPresentException:
            _dismiss_alert(driver)
            if attempt == MAX_TRIES:
                return {"error": "Unexpected alert during form fill"}
            time.sleep(2); continue
        except Exception as exc:
            logger.error("Form fill error: %s", exc)
            if attempt == MAX_TRIES:
                return {"error": str(exc)}
            time.sleep(2); continue

        # ── Step 7: Parse result ──────────────────────────────────────────
        result = _parse_result_gb03(driver)
        # Retry on error (e.g. session_expired) OR not_found on attempt 1.
        # not_found on attempt 1 often means session expired mid-request,
        # not a genuine missing record.  Attempt 2 loads the portal fresh.
        if attempt < MAX_TRIES and (result.get("error") or result.get("not_found")):
            logger.info("[gb03] attempt %d → %s — retrying with fresh portal load",
                        attempt, result)
            time.sleep(3); continue
        return result

    return {"error": "Max retries exceeded"}

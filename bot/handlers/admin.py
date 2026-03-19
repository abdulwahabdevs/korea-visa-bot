"""
Admin handler.

Admins choose their visa type before every check:
  💻 E-Visa Individual  → receipt + passport  (searchType1 / gb01)
  🏛 Diplomatic Office  → passport + name + DOB  (searchType2 / gb02)

Commands:
  /login    — password authentication
  /logout   — close session
  /check    — single check (inline: selects type first)
  /checkall — bulk check via Excel (selects type first)
  /export   — download last Excel result
  /students — registered student count
"""

from __future__ import annotations
import asyncio
import random
import time
import logging
import os
from datetime import datetime
from pathlib import Path
from functools import partial

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.strings import t, format_result, STATUS_EMOJI
from bot.keyboards import cancel_keyboard, main_menu_keyboard, visa_type_keyboard
from db.database import (
    get_user_language, upsert_user,
    is_admin_authenticated, set_admin_authenticated, revoke_admin_session,
    log_check_result, count_student_bindings,
    upsert_status_history, get_status_stats, get_all_status_history,
    bulk_save_row, bulk_get_session, bulk_get_error_rows, bulk_clear_old_sessions,
)
from src.worker_pool import get_pool  # noqa
from src.checker import (
    validate_receipt, validate_passport, validate_name, validate_dob,
    ValidationError,
)
from src.excel_reader import read_students, read_students_validated, StudentRecord
from src.excel_writer import write_results, write_history_export

logger = logging.getLogger(__name__)

# ── ConversationHandler states ────────────────────────────────────────────────
(
    AWAIT_PASSWORD,         # /login
    AWAIT_VISA_TYPE_CHECK,  # /check  → type selection
    AWAIT_CHECK_INPUT,      # /check  → single check input
    AWAIT_VISA_TYPE_BULK,   # /checkall → type selection
    AWAIT_EXCEL,            # /checkall → Excel upload
) = range(5)

_CANCEL_TEXTS = {"❌ Bekor qilish", "❌ Cancel", "❌ Отмена", "/cancel"}
OUTPUT_DIR    = Path(__file__).parent.parent.parent / "data" / "output"

# bot_data keys
_KEY_LAST_EXPORT   = "last_export_path"
_KEY_LAST_SESSION  = "last_bulk_session_key"
_KEY_LAST_VTYPE    = "last_bulk_vtype"


def _lang(uid: int) -> str:
    return get_user_language(uid)


def _admin_ids() -> list[int]:
    """
    Parse ADMIN_CHAT_IDS from env. Handles:
      - spaces around commas:  7292007185, 6274342779
      - quoted values:         "7292007185,6274342779"
      - + prefix:              +7292007185
      - mixed:                 7292007185, +6274342779
    Result is cached on first call.
    """
    if not hasattr(_admin_ids, "_cache"):
        raw = os.getenv("ADMIN_CHAT_IDS", "").strip().strip('"').strip("'")
        ids = []
        for part in raw.split(","):
            part = part.strip().lstrip("+")
            if part.isdigit():
                ids.append(int(part))
            elif part:
                logger.warning("ADMIN_CHAT_IDS: skipping unrecognised entry %r", part)
        _admin_ids._cache = ids
        logger.info("Admin IDs loaded: %s", ids)
    return _admin_ids._cache


def _admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "")


def _is_admin_id(uid: int) -> bool:
    return uid in _admin_ids()


def _is_authed(uid: int) -> bool:
    return _is_admin_id(uid) and is_admin_authenticated(uid)


def _is_cancel(text: str) -> bool:
    return text.strip() in _CANCEL_TEXTS


# ── /login ────────────────────────────────────────────────────────────────────

async def login_cmd(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_admin_id(uid):
        user     = update.effective_user
        username = f"@{user.username}" if user.username else "—"
        support_username = os.getenv("SUPPORT_USERNAME", "gokorea_admin1").lstrip("@")
        # SUPPORT_CHAT_ID is the numeric ID of the support account (most reliable)
        # Falls back to @username if not set
        support_chat_id  = os.getenv("SUPPORT_CHAT_ID") or f"@{support_username}"

        # ── Tell the user they don't have access ─────────────────────────
        # Show inline button linking directly to the admin's Telegram profile
        await update.message.reply_html(
            t("admin_not_in_list", lang, uid=uid),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "👤 Admin bilan bog'lanish",
                    url=f"https://t.me/{support_username}",
                )
            ]]),
        )

        # ── Notify support account ────────────────────────────────────────
        # Send header text then forward the /login message.
        # Forwarding makes Telegram show the user's profile card with photo.
        notif = (
            f"🔔 <b>Kirish so'rovi</b>\n"
            f"👤 {user.full_name} ({username})\n"
            f"🆔 <code>{user.id}</code>\n\n"
            f"Bu foydalanuvchi /login buyrug'ini ishlatmoqchi.\n"
            f"Ruxsat berish uchun ID-ni <code>ADMIN_CHAT_IDS</code>ga qo'shing."
        )
        try:
            await ctx.bot.send_message(
                chat_id=support_chat_id,
                text=notif,
                parse_mode="HTML",
            )
            # Forward triggers Telegram's native profile card rendering
            await update.message.forward(chat_id=support_chat_id)
        except Exception as _e:
            logger.warning("Could not notify support %s of login attempt: %s", support_chat_id, _e)
        return ConversationHandler.END
    if _is_authed(uid):
        await update.message.reply_html(t("admin_already_logged_in", lang))
        return ConversationHandler.END
    await update.message.reply_html(t("admin_ask_password", lang), reply_markup=cancel_keyboard(lang))
    return AWAIT_PASSWORD


async def receive_password(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    text = (update.message.text or "").strip()
    if _is_cancel(text):
        await update.message.reply_html(t("cancelled", lang), reply_markup=main_menu_keyboard(lang))
        return ConversationHandler.END
    correct = _admin_password()
    if correct and text == correct:
        # Ensure the user row exists before touching admin_sessions (FK constraint).
        # Admins who never sent a regular message won't be in the users table yet.
        upsert_user(uid,
                    update.effective_user.username or "",
                    update.effective_user.full_name or "")
        set_admin_authenticated(uid, True)
        await update.message.reply_html(t("admin_login_ok", lang), reply_markup=main_menu_keyboard(lang))
        return ConversationHandler.END
    await update.message.reply_html(t("admin_login_fail", lang), reply_markup=cancel_keyboard(lang))
    return AWAIT_PASSWORD


async def cancel_conv(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    ctx.user_data.clear()
    await update.message.reply_html(t("cancelled", lang), reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END


# ── /logout ───────────────────────────────────────────────────────────────────

async def logout_cmd(update: Update, ctx: ContextTypes) -> None:
    uid  = update.effective_user.id
    lang = _lang(uid)
    revoke_admin_session(uid)
    await update.message.reply_html(t("admin_logged_out", lang))


# ── /check — single check (with type selection) ───────────────────────────────

async def check_cmd(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_authed(uid):
        await update.message.reply_html(t("admin_only", lang))
        return ConversationHandler.END
    await update.message.reply_html(
        t("choose_visa_type", lang),
        reply_markup=visa_type_keyboard(lang),
    )
    return AWAIT_VISA_TYPE_CHECK


async def check_type_selected(update: Update, ctx: ContextTypes) -> int:
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    lang  = _lang(uid)
    vtype = query.data  # "vtype_evisa" or "vtype_diplomatic"
    ctx.user_data["check_vtype"] = vtype

    if vtype == "vtype_evisa":
        await query.edit_message_text(t("admin_check_usage_evisa", lang), parse_mode="HTML")
    else:
        await query.edit_message_text(t("admin_check_usage_diplomatic", lang), parse_mode="HTML")

    return AWAIT_CHECK_INPUT


async def receive_check_input(update: Update, ctx: ContextTypes) -> int:
    uid   = update.effective_user.id
    lang  = _lang(uid)
    text  = (update.message.text or "").strip()
    vtype = ctx.user_data.get("check_vtype", "vtype_evisa")

    if _is_cancel(text):
        ctx.user_data.clear()
        await update.message.reply_html(t("cancelled", lang), reply_markup=main_menu_keyboard(lang))
        return ConversationHandler.END

    if vtype == "vtype_evisa":
        # Format: RECEIPT PASSPORT FULLNAME DOB
        # FULLNAME may contain spaces → receipt=parts[0], passport=parts[1],
        # dob=parts[-1], name=everything in between
        parts = text.split()
        if len(parts) < 4:
            await update.message.reply_html(t("admin_check_usage_evisa", lang))
            return AWAIT_CHECK_INPUT
        try:
            receipt  = validate_receipt(parts[0])
            passport = validate_passport(parts[1])
            dob      = validate_dob(parts[-1])
            name     = validate_name(" ".join(parts[2:-1]).strip('"'))
        except ValidationError as e:
            err_key = {
                "receipt_format":  "err_receipt_format",
                "passport_format": "err_passport_format",
                "dob_format":      "err_dob_format",
                "name_format":     "err_name_format",
            }.get(str(e), "cancelled")
            await update.message.reply_html(t(err_key, lang))
            return AWAIT_CHECK_INPUT
        progress = await update.message.reply_html(t("checking", lang))
        # OPT-G: run blocking Selenium check in thread-pool so the event loop stays free
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, get_pool().check_evisa, receipt, passport, name, dob
        )
        log_check_result(uid, "evisa", result, passport=passport, receipt=receipt,
                         full_name=name, dob=dob)
        try: await progress.delete()
        except Exception: pass
        await update.message.reply_html(format_result(result, lang))

    else:  # diplomatic
        # Parse: PASSPORT "FULL NAME" YYYYMMDD  or  PASSPORT NAME1 NAME2... YYYYMMDD
        parts = text.split()
        if len(parts) < 3:
            await update.message.reply_html(t("admin_check_usage_diplomatic", lang))
            return AWAIT_CHECK_INPUT
        try:
            passport = validate_passport(parts[0])
            dob      = validate_dob(parts[-1])
            name     = validate_name(" ".join(parts[1:-1]).strip('"'))
        except ValidationError as e:
            err_key = {"passport_format": "err_passport_format",
                       "dob_format":      "err_dob_format",
                       "name_format":     "err_name_format"}.get(str(e), "cancelled")
            await update.message.reply_html(t(err_key, lang))
            return AWAIT_CHECK_INPUT
        progress = await update.message.reply_html(t("checking", lang))
        # OPT-G: run blocking Selenium check in thread-pool so the event loop stays free
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, get_pool().check_diplomatic, passport, name, dob
        )
        log_check_result(uid, "diplomatic", result, passport=passport, full_name=name, dob=dob)
        try: await progress.delete()
        except Exception: pass
        await update.message.reply_html(format_result(result, lang))

    ctx.user_data.clear()
    return ConversationHandler.END


# ── /checkall — bulk check ─────────────────────────────────────────────────────

async def checkall_cmd(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_authed(uid):
        await update.message.reply_html(t("admin_only", lang))
        return ConversationHandler.END
    await update.message.reply_html(
        t("choose_visa_type", lang),
        reply_markup=visa_type_keyboard(lang),
    )
    return AWAIT_VISA_TYPE_BULK


async def checkall_type_selected(update: Update, ctx: ContextTypes) -> int:
    query = update.callback_query
    await query.answer()
    uid   = query.from_user.id
    lang  = _lang(uid)
    vtype = query.data
    ctx.user_data["bulk_vtype"] = vtype
    upload_key = "checkall_upload_diplomatic" if vtype == "vtype_diplomatic" else "checkall_upload"
    await query.edit_message_text(t(upload_key, lang), parse_mode="HTML")
    return AWAIT_EXCEL


async def receive_excel(update: Update, ctx: ContextTypes) -> int:
    uid   = update.effective_user.id
    lang  = _lang(uid)
    vtype = ctx.user_data.get("bulk_vtype", "vtype_evisa")

    if update.message.text and _is_cancel(update.message.text):
        ctx.user_data.clear()
        await update.message.reply_html(t("cancelled", lang), reply_markup=main_menu_keyboard(lang))
        return ConversationHandler.END

    doc = update.message.document
    if not doc:
        await update.message.reply_html(t("checkall_upload", lang))
        return AWAIT_EXCEL
    if not doc.file_name.endswith((".xlsx", ".xls")):
        await update.message.reply_html("❌ Faqat <b>.xlsx</b> fayl qabul qilinadi.", parse_mode="HTML")
        return AWAIT_EXCEL

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_DIR / f"input_{uid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    # ── Immediate ack so the user sees something while we download/parse ──
    ack_msg = await update.message.reply_html(
        "📥 <b>Fayl qabul qilindi.</b> Talabalar ro'yxati yuklanmoqda…"
    )
    file_obj = await doc.get_file()
    await file_obj.download_to_drive(str(tmp))

    # Diplomatic mode does not require a receipt/application-number column
    _require_receipt = (vtype == "vtype_evisa")
    try:
        read_result = read_students_validated(tmp, require_receipt=_require_receipt)
    except (ValueError, FileNotFoundError) as e:
        try: await ack_msg.delete()
        except Exception: pass
        await update.message.reply_html(
            f"❌ <b>Excel fayl xatosi:</b>\n<code>{e}</code>",
            parse_mode="HTML"
        )
        tmp.unlink(missing_ok=True)
        return AWAIT_EXCEL

    students = read_result.valid
    invalid  = read_result.invalid
    warnings = read_result.warnings

    # ── Pre-flight validation report ─────────────────────────────────────────
    # If any rows are invalid, report them to admin BEFORE starting any scraping.
    if invalid or warnings:
        lines = []
        if invalid:
            lines.append(f"⚠️ <b>{len(invalid)} ta satr tekshiruvdan o'tmadi</b> (o'tkazib yuboriladi):\n")
            for row in invalid[:15]:   # cap at 15 to avoid message length limit
                errs = "; ".join(row.errors)
                ident = row.passport or row.receipt or f"satr {row.row_num}"
                lines.append(f"  • <b>Satr {row.row_num}</b> [{ident}]: {errs}")
            if len(invalid) > 15:
                lines.append(f"  … va yana {len(invalid) - 15} ta xato satr")
        if warnings:
            lines.append("")
            for w in warnings[:5]:
                lines.append(f"  ℹ️ {w}")
        if students:
            lines.append(f"\n✅ <b>{len(students)} ta to'g'ri satr tekshiriladi.</b>")
        else:
            lines.append("\n❌ <b>Barcha satrlar noto'g'ri — tekshiruv bekor qilindi.</b>")

        try: await ack_msg.delete()
        except Exception: pass
        await update.message.reply_html("\n".join(lines))

        if not students:
            tmp.unlink(missing_ok=True)
            return AWAIT_EXCEL
        # Re-send ack for the valid rows that will proceed
        ack_msg = await update.message.reply_html(
            f"📋 <b>{len(students)} ta talaba tekshirilmoqda…</b>"
        )

    if not students:
        try: await ack_msg.delete()
        except Exception: pass
        if not invalid:
            # Truly empty file — no rows at all
            if vtype == "vtype_diplomatic":
                await update.message.reply_html(
                    "❌ <b>Talaba topilmadi.</b>\n\n"
                    "Diplomatic tekshiruv uchun Excel fayl quyidagi ustunlarni o'z ichiga olishi kerak:\n"
                    "• <b>여권번호</b> yoki <b>passport</b> (majburiy)\n"
                    "• <b>성명</b> yoki <b>name</b> (majburiy)\n"
                    "• <b>생년월일</b> yoki <b>dob</b> (majburiy)\n\n"
                    "Ariza raqami (receipt) <i>shart emas</i>.",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_html("❌ Faylda talaba topilmadi.")
        # else: invalid-rows message was already sent above
        tmp.unlink(missing_ok=True)
        return AWAIT_EXCEL

    try: await ack_msg.delete()
    except Exception: pass

    total    = len(students)
    import os as _os_eta
    _ps  = int(_os_eta.environ.get("CHROME_POOL_SIZE", "3"))
    _bs  = max(1, _ps - 1)                      # bulk slots (reserve 1 for students)
    eta  = max(1, round(total * 15 / _bs / 60)) # parallel ETA
    prog_msg = await update.message.reply_html(t("checkall_start", lang, count=total, eta=eta))

    # ── Session key: unique ID for this bulk run (used for partial export + retry) ──
    session_key = f"{uid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ctx.bot_data[_KEY_LAST_SESSION] = session_key
    ctx.bot_data[_KEY_LAST_VTYPE]   = vtype

    results    = [None] * total   # pre-allocated, preserves row order
    counters   = {k: 0 for k in ("APPROVED", "PENDING", "REJECTED", "NOT_FOUND", "ERROR")}
    pool       = get_pool()
    loop       = asyncio.get_running_loop()
    start_time = time.time()

    # ── Rate-limit guard: Telegram allows ~1 edit/sec per message ────────────
    _last_edit      = 0.0
    _MIN_EDIT_GAP   = 1.2   # seconds between edits (safe margin)
    _edit_lock      = asyncio.Lock()

    # ── Concurrency semaphore: keep 1 worker free for live students ──────────
    import os as _os
    _pool_size  = int(_os.environ.get("CHROME_POOL_SIZE", "3"))
    _bulk_slots = max(1, _pool_size - 1)
    _sem        = asyncio.Semaphore(_bulk_slots)

    done_count = 0
    last_name  = ""
    last_status = ""

    def _build_bar(done: int, total: int, width: int = 10) -> str:
        """Build a Unicode progress bar  ████████░░ 80%"""
        filled = round(width * done / total) if total else 0
        pct    = round(100 * done / total)   if total else 0
        return "█" * filled + "░" * (width - filled) + f" {pct}%"

    async def _edit_progress() -> None:
        """Edit the progress message, respecting Telegram rate limits."""
        nonlocal _last_edit
        async with _edit_lock:
            now = time.time()
            if now - _last_edit < _MIN_EDIT_GAP:
                return   # skip — too soon since last edit
            _last_edit = now

            elapsed   = int(now - start_time)
            remaining = max(0, int((total - done_count) * elapsed / done_count))                         if done_count else 0
            bar = _build_bar(done_count, total)
            try:
                await prog_msg.edit_text(
                    t("checkall_progress", lang,
                      bar=bar,
                      done=done_count,      total=total,
                      approved=counters["APPROVED"],
                      pending=counters["PENDING"],
                      rejected=counters["REJECTED"],
                      not_found=counters["NOT_FOUND"],
                      error=counters["ERROR"],
                      elapsed=elapsed,      remaining=remaining,
                      last_name=last_name,  last_status=last_status),
                    parse_mode="HTML",
                )
            except Exception:
                pass   # edit failure is non-fatal (message deleted, flood etc.)

    async def _check_one(i: int, stu) -> None:
        nonlocal done_count, last_name, last_status
        # ── Stagger task starts to prevent concurrent portal reloads ─────
        if i <= _pool_size:
            await asyncio.sleep((i - 1) * 3.0)
        try:
            async with _sem:
                if vtype == "vtype_evisa":
                    result = await loop.run_in_executor(
                        None, pool.check_evisa,
                        stu.receipt, stu.passport, stu.name, stu.dob
                    )
                    log_check_result(uid, "evisa", result, passport=stu.passport,
                                     receipt=stu.receipt, full_name=stu.name, dob=stu.dob)
                else:
                    result = await loop.run_in_executor(
                        None, pool.check_diplomatic,
                        stu.passport, stu.name, stu.dob
                    )
                    log_check_result(uid, "diplomatic", result, passport=stu.passport,
                                     full_name=stu.name, dob=stu.dob)
        except Exception as _task_err:
            logger.error("[checkall] row %d (%s) crashed: %s", i,
                         stu.passport, _task_err, exc_info=True)
            result = {
                "status_en": "ERROR", "status_ko": "",
                "visa_type": "", "app_date": "",
                "reason": str(_task_err), "receipt": "",
                "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

        result.update({"index": i, "name": stu.name,
                        "passport": stu.passport, "dob": stu.dob})
        results[i - 1] = result

        # ── Persist row immediately for partial export + retry ────────────
        bulk_save_row(
            session_key=session_key, row_index=i, result=result,
            receipt=stu.receipt, passport=stu.passport,
            full_name=stu.name, dob=stu.dob,
            check_type="evisa" if vtype == "vtype_evisa" else "diplomatic",
        )

        # ── Update status history (tracks changes over time) ─────────────
        s_en = result.get("status_en", "ERROR")
        if s_en not in ("ERROR",):
            try:
                upsert_status_history(
                    passport=stu.passport, full_name=stu.name, dob=stu.dob,
                    status_en=s_en,
                    status_ko=result.get("status_ko", ""),
                    visa_type=result.get("visa_type", ""),
                    app_date=result.get("app_date", ""),
                    reason=result.get("reason", ""),
                    check_type="evisa" if vtype == "vtype_evisa" else "diplomatic",
                    receipt=stu.receipt,
                )
            except Exception as _hist_err:
                logger.warning("status_history upsert failed: %s", _hist_err)

        s = result.get("status_en", "ERROR")
        # Normalise exotic statuses into display buckets
        s_bucket = s if s in counters else (
            "APPROVED" if s in ("ISSUED", "USED") else
            "PENDING"  if s in ("UNDER_REVIEW", "RECEIVED", "WITHDRAWN",
                                 "RETURNED", "UNKNOWN") else
            "ERROR"
        )
        counters[s_bucket] = counters.get(s_bucket, 0) + 1
        done_count  += 1
        last_name    = (stu.name or stu.passport or "—")[:30]
        # Map raw status_en → friendly label for progress display
        _STATUS_LABEL = {
            "APPROVED": "Approved", "ISSUED": "Approved (Issued)",
            "USED": "Approved (Used)", "PENDING": "Pending",
            "RECEIVED": "Received", "UNDER_REVIEW": "Under Review",
            "REJECTED": "Rejected", "WITHDRAWN": "Withdrawn",
            "RETURNED": "Returned", "NOT_FOUND": "Not Found",
            "ERROR": "Error", "UNKNOWN": "Unknown",
        }
        last_status  = f"{STATUS_EMOJI.get(s, '?')}{_STATUS_LABEL.get(s, s)}"

        # Update progress after EVERY completion (rate-limit guard handles throttle)
        await _edit_progress()

    # ── Fire all rows in parallel ─────────────────────────────────────────────
    interrupted = False
    try:
        await asyncio.gather(*[_check_one(i, stu)
                               for i, stu in enumerate(students, start=1)])
    except Exception as _bulk_err:
        logger.error("Bulk gather error: %s", _bulk_err, exc_info=True)
        interrupted = True
        # ── Partial export: save whatever completed before the crash ──────
        completed = [r for r in results if r is not None]
        if completed:
            partial_path = OUTPUT_DIR / f"partial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            write_results(completed, partial_path)
            ctx.bot_data[_KEY_LAST_EXPORT] = str(partial_path)
            await update.message.reply_html(
                f"⚠️ <b>Tekshiruv to'xtatildi.</b> {len(completed)}/{total} natija saqlandi.\n"
                f"<code>{str(_bulk_err)[:200]}</code>\n\n"
                f"• /export — qisman natijalarni yuklab olish\n"
                f"• /retryerrors — xato qatorlarni qayta tekshirish",
                parse_mode="HTML"
            )
            with open(partial_path, "rb") as f:
                await update.message.reply_document(
                    document=f, filename=partial_path.name,
                    caption=f"⚠️ Qisman natijalar ({len(completed)}/{total})"
                )
        else:
            await update.message.reply_html(
                f"❌ <b>Tekshiruv xatosi:</b>\n<code>{_bulk_err}</code>",
                parse_mode="HTML"
            )
        tmp.unlink(missing_ok=True)
        ctx.user_data.clear()
        return ConversationHandler.END

    # ── Final progress edit (ensures 100% is always shown) ───────────────────
    _last_edit = 0.0   # reset so final edit is never skipped
    await _edit_progress()
    await asyncio.sleep(0.5)

    # ── Save results & notify ─────────────────────────────────────────────────
    out_path = OUTPUT_DIR / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    write_results([r for r in results if r is not None], out_path)
    ctx.bot_data[_KEY_LAST_EXPORT]  = str(out_path)

    # Clean up old bulk sessions (keep last 5)
    try:
        bulk_clear_old_sessions(keep_latest=5)
    except Exception:
        pass

    total_elapsed = int(time.time() - start_time)
    mins, secs    = divmod(total_elapsed, 60)
    elapsed_str   = f"{mins}m {secs}s" if mins else f"{secs}s"

    try: await prog_msg.delete()
    except Exception: pass

    await update.message.reply_html(
        t("checkall_done", lang, total=total,
          approved=counters["APPROVED"], pending=counters["PENDING"],
          rejected=counters["REJECTED"], not_found=counters["NOT_FOUND"],
          error=counters["ERROR"],       elapsed=elapsed_str),
        reply_markup=main_menu_keyboard(lang),
    )
    if counters["ERROR"] > 0:
        await update.message.reply_html(
            f"💡 <b>{counters['ERROR']} ta xato qator topildi.</b>\n"
            f"/retryerrors — faqat xato qatorlarni qayta tekshirish"
        )
    with open(out_path, "rb") as f:
        await update.message.reply_document(document=f, filename=out_path.name,
                                            caption=t("export_ready", lang))

    tmp.unlink(missing_ok=True)
    ctx.user_data.clear()
    return ConversationHandler.END


# ── /export ───────────────────────────────────────────────────────────────────

async def export_cmd(update: Update, ctx: ContextTypes) -> None:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_authed(uid):
        await update.message.reply_html(t("admin_only", lang)); return
    path = ctx.bot_data.get(_KEY_LAST_EXPORT)
    if not path or not Path(path).exists():
        await update.message.reply_html(t("export_empty", lang)); return
    with open(path, "rb") as f:
        await update.message.reply_document(document=f, filename=Path(path).name,
                                            caption=t("export_ready", lang))


# ── /students ─────────────────────────────────────────────────────────────────

async def students_cmd(update: Update, ctx: ContextTypes) -> None:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_authed(uid):
        await update.message.reply_html(t("admin_only", lang)); return
    await update.message.reply_html(t("students_info", lang, count=count_student_bindings()))


# ── /retryerrors — re-run only ERROR rows from the last bulk session ──────────

async def retryerrors_cmd(update: Update, ctx: ContextTypes) -> None:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_authed(uid):
        await update.message.reply_html(t("admin_only", lang)); return

    session_key = ctx.bot_data.get(_KEY_LAST_SESSION)
    vtype       = ctx.bot_data.get(_KEY_LAST_VTYPE, "vtype_diplomatic")

    if not session_key:
        await update.message.reply_html(
            "❌ Oldingi tekshiruv sessiyasi topilmadi. Avval /checkall bajaring."
        ); return

    error_rows = bulk_get_error_rows(session_key)
    if not error_rows:
        await update.message.reply_html(
            "✅ Oldingi sessiyada xato qatorlar yo'q — qayta tekshirishga hojat yo'q."
        ); return

    total = len(error_rows)
    await update.message.reply_html(
        f"🔄 <b>{total} ta xato qator qayta tekshirilmoqda…</b>\n"
        f"Sessiya: <code>{session_key}</code>",
        parse_mode="HTML"
    )

    pool = get_pool()
    loop = asyncio.get_running_loop()

    import os as _os_r
    _pool_size  = int(_os_r.environ.get("CHROME_POOL_SIZE", "3"))
    _bulk_slots = max(1, _pool_size - 1)
    _sem_r      = asyncio.Semaphore(_bulk_slots)

    retry_results = []
    success_count = 0
    still_error   = 0

    async def _retry_one(row: dict) -> None:
        nonlocal success_count, still_error
        passport   = row.get("passport", "")
        full_name  = row.get("full_name", "")
        dob        = row.get("dob", "")
        receipt    = row.get("receipt", "")
        row_index  = row.get("row_index", 0)
        check_type = row.get("check_type", "diplomatic")

        try:
            async with _sem_r:
                if check_type == "evisa":
                    result = await loop.run_in_executor(
                        None, pool.check_evisa, receipt, passport, full_name, dob
                    )
                else:
                    result = await loop.run_in_executor(
                        None, pool.check_diplomatic, passport, full_name, dob
                    )
        except Exception as exc:
            result = {"status_en": "ERROR", "status_ko": "", "visa_type": "",
                      "app_date": "", "reason": str(exc),
                      "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

        result.update({"index": row_index, "name": full_name,
                        "passport": passport, "dob": dob})

        # Overwrite the row in bulk_sessions
        bulk_save_row(
            session_key=session_key, row_index=row_index, result=result,
            receipt=receipt, passport=passport, full_name=full_name,
            dob=dob, check_type=check_type,
        )

        # Update status history
        s_en = result.get("status_en", "ERROR")
        if s_en != "ERROR":
            try:
                upsert_status_history(
                    passport=passport, full_name=full_name, dob=dob,
                    status_en=s_en, status_ko=result.get("status_ko", ""),
                    visa_type=result.get("visa_type", ""),
                    app_date=result.get("app_date", ""),
                    reason=result.get("reason", ""),
                    check_type=check_type, receipt=receipt,
                )
            except Exception as _he:
                logger.warning("status_history retry upsert: %s", _he)

        retry_results.append(result)
        if s_en != "ERROR":
            success_count += 1
        else:
            still_error += 1

    await asyncio.gather(*[_retry_one(r) for r in error_rows])

    # Rebuild full session results and re-export
    all_rows = bulk_get_session(session_key)
    formatted = [
        {
            "index":      r["row_index"],
            "receipt":    r.get("receipt", ""),
            "name":       r.get("full_name", ""),
            "passport":   r.get("passport", ""),
            "dob":        r.get("dob", ""),
            "status_en":  r.get("status_en", ""),
            "status_ko":  r.get("status_ko", ""),
            "visa_type":  r.get("visa_type", ""),
            "app_date":   r.get("app_date", ""),
            "reason":     r.get("reason", ""),
            "checked_at": r.get("checked_at", ""),
        }
        for r in all_rows
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"retry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    write_results(formatted, out_path)
    ctx.bot_data[_KEY_LAST_EXPORT] = str(out_path)

    summary = (
        f"✅ <b>Qayta tekshiruv tugadi.</b>\n\n"
        f"• Muvaffaqiyatli: <b>{success_count}</b>\n"
        f"• Hali xato: <b>{still_error}</b>\n\n"
        f"Yangilangan to'liq natijalar faylga yozildi."
    )
    await update.message.reply_html(summary)
    with open(out_path, "rb") as f:
        await update.message.reply_document(
            document=f, filename=out_path.name,
            caption="📊 Yangilangan natijalar (retry qo'shilgan)"
        )


# ── /stats — admin-only status breakdown + recent changes ─────────────────────

async def stats_cmd(update: Update, ctx: ContextTypes) -> None:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_authed(uid):
        await update.message.reply_html(t("admin_only", lang)); return

    stats = get_status_stats()
    if stats["total"] == 0:
        await update.message.reply_html(
            "📊 Hali hech qanday ma'lumot yo'q. Avval /checkall bajaring."
        ); return

    b = stats["buckets"]

    # Friendly display buckets
    approved  = b.get("APPROVED", 0) + b.get("ISSUED", 0) + b.get("USED", 0)
    reviewing = b.get("UNDER_REVIEW", 0) + b.get("RECEIVED", 0) + b.get("PENDING", 0)
    rejected  = b.get("REJECTED", 0)
    not_found = b.get("NOT_FOUND", 0)
    error     = b.get("ERROR", 0)
    unknown   = b.get("UNKNOWN", 0)
    total     = stats["total"]

    def _bar(count: int, total: int, width: int = 8) -> str:
        filled = round(width * count / total) if total else 0
        return "█" * filled + "░" * (width - filled)

    lines = [
        f"📊 <b>Visa holati statistikasi</b>",
        f"Jami kuzatilayotgan: <b>{total}</b> ta",
        f"Oxirgi tekshiruv: {stats['last_checked'] or '—'}",
        "",
        f"✅ Tasdiqlangan:  <b>{approved}</b>  {_bar(approved, total)}",
        f"⏳ Ko'rib chiqish: <b>{reviewing}</b>  {_bar(reviewing, total)}",
        f"❌ Rad etilgan:   <b>{rejected}</b>  {_bar(rejected, total)}",
        f"🔍 Topilmadi:    <b>{not_found}</b>  {_bar(not_found, total)}",
        f"⚠️ Xato:         <b>{error}</b>  {_bar(error, total)}",
    ]
    if unknown:
        lines.append(f"❓ Noma'lum:      <b>{unknown}</b>  {_bar(unknown, total)}")

    # Recent status changes
    recent = stats.get("recent_changes", [])
    if recent:
        lines += ["", "🔔 <b>So'nggi holat o'zgarishlari:</b>"]
        for ch in recent[:5]:
            name     = (ch.get("full_name") or ch.get("passport") or "—")[:22]
            s_en     = ch.get("status_en", "?")
            emoji    = STATUS_EMOJI.get(s_en, "❓")
            changed  = (ch.get("status_changed_at") or "")[:16]
            lines.append(f"  {emoji} {name} → <b>{s_en}</b> ({changed})")

    lines += ["", "📥 /exporthistory — tarix faylini yuklab olish"]

    await update.message.reply_html("\n".join(lines))


# ── /exporthistory — full status history with change-tracking columns ─────────

async def exporthistory_cmd(update: Update, ctx: ContextTypes) -> None:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_authed(uid):
        await update.message.reply_html(t("admin_only", lang)); return

    history = get_all_status_history()
    if not history:
        await update.message.reply_html(
            "📊 Hali tarix yo'q. Avval /checkall bajaring."
        ); return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    write_history_export(history, out_path)

    with open(out_path, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=out_path.name,
            caption=(
                f"📋 Visa holati tarixi — {len(history)} ta yozuv\n"
                f"Ustunlar: Passport, Ism, DOB, Status, Holat o'zgargan sana"
            )
        )


# ── /exportpartial — export whatever is saved from an interrupted session ─────

async def exportpartial_cmd(update: Update, ctx: ContextTypes) -> None:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if not _is_authed(uid):
        await update.message.reply_html(t("admin_only", lang)); return

    session_key = ctx.bot_data.get(_KEY_LAST_SESSION)
    if not session_key:
        await update.message.reply_html(
            "❌ Saqlangan sessiya topilmadi. Avval /checkall bajaring."
        ); return

    rows = bulk_get_session(session_key)
    if not rows:
        await update.message.reply_html("❌ Bu sessiyada saqlangan ma'lumot yo'q."); return

    formatted = [
        {
            "index":      r["row_index"],
            "receipt":    r.get("receipt", ""),
            "name":       r.get("full_name", ""),
            "passport":   r.get("passport", ""),
            "dob":        r.get("dob", ""),
            "status_en":  r.get("status_en", ""),
            "status_ko":  r.get("status_ko", ""),
            "visa_type":  r.get("visa_type", ""),
            "app_date":   r.get("app_date", ""),
            "reason":     r.get("reason", ""),
            "checked_at": r.get("checked_at", ""),
        }
        for r in rows
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"partial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    write_results(formatted, out_path)
    ctx.bot_data[_KEY_LAST_EXPORT] = str(out_path)

    with open(out_path, "rb") as f:
        await update.message.reply_document(
            document=f, filename=out_path.name,
            caption=f"📊 Qisman natijalar — {len(rows)} ta qator saqlangan"
        )


# ── Handler registration ──────────────────────────────────────────────────────

def register(app) -> None:
    # Login conversation
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("login", login_cmd)],
        states={AWAIT_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)]},
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        name="admin_login", persistent=False,
    ))

    # Single check conversation  (text + callback query states)
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("check", check_cmd)],
        states={
            AWAIT_VISA_TYPE_CHECK: [CallbackQueryHandler(check_type_selected, pattern=r"^vtype_")],
            AWAIT_CHECK_INPUT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_check_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        name="admin_check", persistent=False, per_message=False,
    ))

    # Bulk check conversation
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("checkall", checkall_cmd)],
        states={
            AWAIT_VISA_TYPE_BULK: [CallbackQueryHandler(checkall_type_selected, pattern=r"^vtype_")],
            AWAIT_EXCEL:          [
                MessageHandler(filters.Document.ALL, receive_excel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_excel),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        name="admin_checkall", persistent=False, per_message=False,
    ))

    app.add_handler(CommandHandler("logout",        logout_cmd))
    app.add_handler(CommandHandler("export",        export_cmd))
    app.add_handler(CommandHandler("exportpartial", exportpartial_cmd))
    app.add_handler(CommandHandler("exporthistory", exporthistory_cmd))
    app.add_handler(CommandHandler("students",      students_cmd))
    app.add_handler(CommandHandler("stats",         stats_cmd))
    app.add_handler(CommandHandler("retryerrors",   retryerrors_cmd))

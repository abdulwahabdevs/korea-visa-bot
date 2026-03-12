"""
Student handler — /mystatus and /forget.

Students ALWAYS use the Diplomatic Office check (외교공관 접수):
  Fields: passport number  →  full name  →  date of birth
  No application receipt number needed.

First-time flow:
  /mystatus → ask passport (+ send MRZ photo) → ask name → ask DOB → check → save

Returning student:
  /mystatus → auto-load saved credentials → check immediately
"""

from __future__ import annotations
import asyncio
import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.strings import t, format_result, MRZ_IMAGE_URL, MRZ_IMAGE_LOCAL
from bot.keyboards import cancel_keyboard, main_menu_keyboard, cert_download_keyboard
from db.database import (
    upsert_user, get_user_language,
    get_student_binding, save_student_binding, clear_student_binding,
    log_check_result,
)
from src.worker_pool import get_pool  # noqa
from src.checker import (
    validate_passport, validate_name, validate_dob,
    ValidationError,
)
from src.rate_limiter import check_rate_limit, record_check

logger = logging.getLogger(__name__)

# ConversationHandler states
ASK_PASSPORT, ASK_NAME, ASK_DOB = range(3)

_CANCEL_TEXTS = {"❌ Bekor qilish", "❌ Cancel", "❌ Отмена", "/cancel"}


def _lang(uid: int) -> str:
    return get_user_language(uid)


def _is_cancel(text: str) -> bool:
    return text.strip() in _CANCEL_TEXTS


# ── Entry point ───────────────────────────────────────────────────────────────

async def mystatus_start(update: Update, ctx: ContextTypes) -> int:
    user = update.effective_user
    upsert_user(user.id, user.username or "", user.full_name or "")
    lang = _lang(user.id)

    binding = get_student_binding(user.id)
    if binding:
        # Returning student — enforce cooldown before hitting portal again
        wait = check_rate_limit(user.id)
        if wait:
            cooldown_msg = {
                "uz": f"⏳ Iltimos, {wait} soniya kuting va qayta urinib ko'ring.",
                "en": f"⏳ Please wait {wait} seconds before checking again.",
                "ru": f"⏳ Подождите {wait} секунд перед повторной проверкой.",
            }.get(lang, f"⏳ Please wait {wait}s before checking again.")
            await update.message.reply_html(cooldown_msg)
            return ConversationHandler.END
        # Check immediately with saved credentials
        await _run_check(
            update, ctx, user.id,
            binding["passport"], binding["full_name"], binding["dob"],
            first_time=False,
        )
        return ConversationHandler.END

    # New student — start the input flow
    await _ask_passport(update, lang)
    return ASK_PASSPORT


async def _ask_passport(update: Update, lang: str) -> None:
    """Send the passport-number prompt with an inline MRZ guide image."""
    await update.message.reply_html(
        t("ask_passport", lang),
        reply_markup=cancel_keyboard(lang),
    )
    # Send MRZ guide image with caption
    try:
        # Send guide image — local file first, URL fallback
        import os as _os
        _caption = t("passport_image_caption", lang)
        if _os.path.exists(MRZ_IMAGE_LOCAL):
            with open(MRZ_IMAGE_LOCAL, "rb") as _f:
                await update.message.reply_photo(photo=_f, caption=_caption, parse_mode="HTML")
        else:
            await update.message.reply_photo(photo=MRZ_IMAGE_URL, caption=_caption, parse_mode="HTML")
    except Exception as exc:
        logger.warning("Could not send MRZ guide image: %s", exc)
        # Fallback: monospace text diagram
        await update.message.reply_html(
            "<code>P&lt;UZBSURNAME&lt;&lt;GIVENNAME&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;\n"
            "<b>FA4166021</b>3UZB9812171M2812170&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;&lt;8</code>\n\n"
            "☝️ " + {"uz": "Ikkinchi qatorning dastlabki 9 belgisi.",
                     "en": "First 9 characters of line 2.",
                     "ru": "Первые 9 символов второй строки."}.get(lang, "")
        )


# ── Step 1: Receive passport ──────────────────────────────────────────────────

async def get_passport(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    text = (update.message.text or "").strip()

    if _is_cancel(text):
        await update.message.reply_html(t("cancelled", lang), reply_markup=main_menu_keyboard(lang))
        return ConversationHandler.END

    try:
        passport = validate_passport(text)
    except ValidationError:
        await update.message.reply_html(t("err_passport_format", lang), reply_markup=cancel_keyboard(lang))
        return ASK_PASSPORT  # retry

    ctx.user_data["passport"] = passport
    await update.message.reply_html(t("ask_name", lang), reply_markup=cancel_keyboard(lang))
    return ASK_NAME


# ── Step 2: Receive name ──────────────────────────────────────────────────────

async def get_name(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    text = (update.message.text or "").strip()

    if _is_cancel(text):
        ctx.user_data.clear()
        await update.message.reply_html(t("cancelled", lang), reply_markup=main_menu_keyboard(lang))
        return ConversationHandler.END

    try:
        name = validate_name(text)
    except ValidationError:
        await update.message.reply_html(t("err_name_format", lang), reply_markup=cancel_keyboard(lang))
        return ASK_NAME  # retry

    ctx.user_data["full_name"] = name
    await update.message.reply_html(t("ask_dob", lang), reply_markup=cancel_keyboard(lang))
    return ASK_DOB


# ── Step 3: Receive DOB → check ───────────────────────────────────────────────

async def get_dob(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    text = (update.message.text or "").strip()

    if _is_cancel(text):
        ctx.user_data.clear()
        await update.message.reply_html(t("cancelled", lang), reply_markup=main_menu_keyboard(lang))
        return ConversationHandler.END

    try:
        dob = validate_dob(text)
    except ValidationError:
        await update.message.reply_html(t("err_dob_format", lang), reply_markup=cancel_keyboard(lang))
        return ASK_DOB  # retry

    passport  = ctx.user_data.pop("passport", None)
    full_name = ctx.user_data.pop("full_name", None)
    if not passport or not full_name:
        await update.message.reply_html(t("cancelled", lang))
        return ConversationHandler.END

    await _run_check(update, ctx, uid, passport, full_name, dob, first_time=True)
    return ConversationHandler.END


# ── Check runner ──────────────────────────────────────────────────────────────

async def _run_check(
    update: Update,
    ctx: ContextTypes,
    uid: int,
    passport: str,
    full_name: str,
    dob: str,
    first_time: bool = False,
) -> None:
    lang         = _lang(uid)
    progress_msg = await update.message.reply_html(t("checking", lang))

    try:
        # OPT-G+Pool: borrow an idle Chrome worker from the pool.
        # Other users run on different workers concurrently.
        pool = get_pool()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, pool.check_diplomatic, passport, full_name, dob
        )
    except Exception as exc:
        logger.error("Checker error: %s", exc)
        result = {
            "status_en": "ERROR", "status_ko": "", "visa_type": "",
            "app_date": "", "reason": str(exc), "checked_at": "", "receipt": "",
        }

    log_check_result(uid, "diplomatic", result, passport=passport, full_name=full_name, dob=dob)

    # Record this check for rate limiting (start cooldown)
    record_check(uid)

    if first_time:
        save_student_binding(uid, passport, full_name, dob)

    try:
        await progress_msg.delete()
    except Exception:
        pass

    status_en = result.get("status_en", "")
    await update.message.reply_html(
        format_result(result, lang),
        reply_markup=main_menu_keyboard(lang),
    )

    # ── Cert download button: ONLY shown for student single-check + APPROVED ─
    # Rules:
    #   APPROVED  → store fresh credentials in session + show the cert button.
    #   any other → clear any stale cert credentials from the previous check
    #               so old cert buttons in chat history cannot be replayed.
    if status_en == "APPROVED":
        # Persist credentials in this session so cert_dl_handler can use them.
        ctx.user_data["cert_passport"] = passport
        ctx.user_data["cert_name"]     = full_name
        ctx.user_data["cert_dob"]      = dob
        _cert_msg = {
            "uz": "🎉 <b>Vizangiz tasdiqlandi!</b> Rasmiy sertifikatni yuklab olish uchun quyidagi tugmani bosing.",
            "en": "🎉 <b>Your visa is approved!</b> Tap the button below to download your official certificate.",
            "ru": "🎉 <b>Ваша виза одобрена!</b> Нажмите кнопку ниже, чтобы скачать официальную справку.",
        }.get(lang, "🎉 Visa approved! Tap below to download your certificate.")
        await update.message.reply_html(_cert_msg, reply_markup=cert_download_keyboard(lang))
    else:
        # Clear stale cert session data — any previous APPROVED cert button
        # in chat history becomes a no-op if the student re-checks now.
        ctx.user_data.pop("cert_passport", None)
        ctx.user_data.pop("cert_name",     None)
        ctx.user_data.pop("cert_dob",      None)

    if first_time:
        await update.message.reply_html(t("credentials_saved", lang))


# ── /forget ───────────────────────────────────────────────────────────────────

async def forget_cmd(update: Update, ctx: ContextTypes) -> None:
    uid  = update.effective_user.id
    lang = _lang(uid)
    if get_student_binding(uid):
        clear_student_binding(uid)
        await update.message.reply_html(t("forget_done", lang), reply_markup=main_menu_keyboard(lang))
    else:
        await update.message.reply_html(t("forget_nothing", lang), reply_markup=main_menu_keyboard(lang))


async def cancel(update: Update, ctx: ContextTypes) -> int:
    uid  = update.effective_user.id
    lang = _lang(uid)
    ctx.user_data.clear()
    await update.message.reply_html(t("cancelled", lang), reply_markup=main_menu_keyboard(lang))
    return ConversationHandler.END


# ── Handler registration ──────────────────────────────────────────────────────


# ── Certificate download callback handler ─────────────────────────────────────

async def cert_dl_handler(update: Update, ctx: ContextTypes) -> None:
    """Handle the 📄 Download Visa Certificate inline-button press.

    Steps:
      1. Acknowledge the callback (removes loading spinner).
      2. Send a "downloading…" progress message.
      3. Run pool.download_cert() in a thread executor — this spawns a
         fresh headless Chrome with a temp download directory, navigates
         to the portal, replicates the student's search, and clicks
         the #REPORTSE (비자발급확인서) button.
      4. On success: send the PDF file via Telegram and delete the temp file.
      5. On failure: send a localized error message.
    """
    query = update.callback_query
    await query.answer()   # dismiss spinner on the inline button

    user = update.effective_user
    lang = _lang(user.id)

    # Cert button only appears after a live APPROVED result in this session.
    # We do NOT fall back to the DB binding here because the DB binding is
    # permanent and the current status may have changed since the last check
    # (e.g. visa was approved last week, now expired or re-reviewed).
    # If the session is empty (bot restarted), the student must run /mystatus
    # again — which will show a fresh status and, if still APPROVED, a new
    # cert button.
    passport  = ctx.user_data.get("cert_passport")
    full_name = ctx.user_data.get("cert_name")
    dob       = ctx.user_data.get("cert_dob")

    if not passport or not full_name or not dob:
        # Session cleared (bot restart) or cert context was wiped on last
        # non-APPROVED check — ask student to re-check their status first.
        await query.message.reply_html(
            {"uz": "⚠️ Sertifikat ma'lumotlari topilmadi. Iltimos, /mystatus orqali holatni qayta tekshiring.",
             "en": "⚠️ Session expired. Please run /mystatus again — if your visa is still approved, the download button will reappear.",
             "ru": "⚠️ Сессия истекла. Выполните /mystatus ещё раз — если виза по-прежнему одобрена, кнопка появится снова."
            }.get(lang, "⚠️ Please run /mystatus first to refresh your status.")
        )
        return

    prog = await query.message.reply_html(t("cert_downloading", lang))

    try:
        pool   = get_pool()
        loop   = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, pool.download_cert, passport, full_name, dob
        )
    except Exception as exc:
        logger.error("cert_dl_handler error: %s", exc)
        result = {"error": str(exc)}
    finally:
        try:
            await prog.delete()
        except Exception:
            pass

    if result.get("not_approved"):
        await query.message.reply_html(t("cert_not_approved", lang))
        return

    if result.get("error"):
        await query.message.reply_html(
            t("cert_error", lang, error=result["error"][:200])
        )
        return

    file_path = result.get("file_path")
    if not file_path:
        await query.message.reply_html(t("cert_error", lang, error="No file returned"))
        return

    try:
        import os as _os
        with open(file_path, "rb") as pdf_f:
            await query.message.reply_document(
                document=pdf_f,
                filename=_os.path.basename(file_path),
                caption=t("cert_caption", lang),
            )
        logger.info("Cert sent to uid=%d file=%s", user.id, _os.path.basename(file_path))
    except Exception as exc:
        logger.error("Failed to send cert PDF: %s", exc)
        await query.message.reply_html(t("cert_error", lang, error=str(exc)[:200]))
    finally:
        # Clean up temp file and temp directory
        try:
            import os as _os
            _os.remove(file_path)
            _os.rmdir(_os.path.dirname(file_path))
        except Exception:
            pass

def register(app) -> None:
    # Button label texts in all three languages — must match keyboards.py exactly
    _CHECK_LABELS = (
        "📋 Viza Holatimni Tekshirish",   # uz
        "📋 Check My Visa Status",         # en
        "📋 Проверить статус визы",        # ru
    )
    _CANCEL_LABELS = (
        "❌ Bekor qilish",  # uz
        "❌ Cancel",        # en
        "❌ Отмена",        # ru
    )

    # FIX 1: Also accept ReplyKeyboard button press as entry point
    #         (text_menu_handler in common.py calls mystatus_start directly
    #          which bypasses the ConversationHandler state machine)
    check_filter  = filters.Regex("^(" + "|".join(_CHECK_LABELS)  + ")$")
    cancel_filter = filters.Regex("^(" + "|".join(_CANCEL_LABELS) + ")$")

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("mystatus", mystatus_start),
            MessageHandler(filters.TEXT & check_filter, mystatus_start),  # FIX 1
        ],
        states={
            ASK_PASSPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_passport)],
            ASK_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASK_DOB:      [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dob)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.TEXT & cancel_filter, cancel),  # FIX 2: ❌ button
        ],
        allow_reentry=True,
        name="student_mystatus",
        persistent=False,
        per_message=False,
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("forget", forget_cmd))
    # Cert download button (works outside the ConversationHandler)
    app.add_handler(CallbackQueryHandler(cert_dl_handler, pattern=r"^cert_dl$"))

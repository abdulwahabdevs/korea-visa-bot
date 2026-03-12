"""
Common handlers: /start, /help, /language, /guide, text menu buttons.
"""

from __future__ import annotations
import logging
import os

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from bot.strings import t, MRZ_IMAGE_URL
from bot.keyboards import main_menu_keyboard, language_keyboard
from db.database import upsert_user, get_user_language, set_user_language

logger = logging.getLogger(__name__)


def _lang(update: Update) -> str:
    return get_user_language(update.effective_user.id)


async def start(update: Update, ctx: ContextTypes) -> None:
    user = update.effective_user
    upsert_user(user.id, user.username or "", user.full_name or "")
    lang = get_user_language(user.id)
    await update.message.reply_html(
        t("welcome", lang),
        reply_markup=main_menu_keyboard(lang),
    )


async def help_cmd(update: Update, ctx: ContextTypes) -> None:
    uid       = update.effective_user.id
    lang      = _lang(update)
    admin_ids = [int(x) for x in os.getenv("ADMIN_CHAT_IDS", "").split(",") if x.strip().isdigit()]
    key       = "help_admin" if uid in admin_ids else "help_student"
    await update.message.reply_html(t(key, lang))


async def language_cmd(update: Update, ctx: ContextTypes) -> None:
    lang = _lang(update)
    await update.message.reply_html(t("choose_language", lang), reply_markup=language_keyboard())


async def language_callback(update: Update, ctx: ContextTypes) -> None:
    query     = update.callback_query
    await query.answer()
    lang_code = query.data.replace("lang_", "")
    if lang_code not in ("uz", "en", "ru"):
        return
    uid = query.from_user.id
    set_user_language(uid, lang_code)
    await query.edit_message_text(t("language_set", lang_code), parse_mode="HTML")
    await ctx.bot.send_message(
        chat_id=uid,
        text=t("welcome", lang_code),
        reply_markup=main_menu_keyboard(lang_code),
        parse_mode="HTML",
    )


async def guide_cmd(update: Update, ctx: ContextTypes) -> None:
    """Send simple inline text guide + MRZ image."""
    lang = _lang(update)
    await update.message.reply_html(t("guide", lang))
    try:
        await update.message.reply_photo(
            photo=MRZ_IMAGE_URL,
            caption=t("passport_image_caption", lang),
        )
    except Exception as exc:
        logger.warning("Could not send MRZ guide image: %s", exc)


async def text_menu_handler(update: Update, ctx: ContextTypes) -> None:
    """Route ReplyKeyboard button presses to the right command handler.

    NOTE: The '📋 Check' button is intentionally NOT handled here.
    It is handled as an entry_point inside the ConversationHandler in student.py.
    Calling mystatus_start() directly here would bypass the state machine.
    """
    text = (update.message.text or "").strip()

    # '📋 Check' button → handled by ConversationHandler entry_point in student.py
    guide_labels = {"📖 Qo'llanma", "📖 Guide", "📖 Инструкция"}
    help_labels  = {"ℹ️ Yordam",    "ℹ️ Help",   "ℹ️ Помощь"}

    if text in guide_labels:
        await guide_cmd(update, ctx)
    elif text in help_labels:
        await help_cmd(update, ctx)


# ── Handler registration ──────────────────────────────────────────────────────

def register(app) -> None:
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("help",     help_cmd))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("guide",    guide_cmd))
    app.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang_"))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_menu_handler),
        group=10,
    )

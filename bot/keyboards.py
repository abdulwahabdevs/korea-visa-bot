"""
All keyboard builders in one place.
"""

from __future__ import annotations
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def main_menu_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    labels = {
        "uz": ["📋 Viza Holatimni Tekshirish", "📖 Qo'llanma", "ℹ️ Yordam"],
        "en": ["📋 Check My Visa Status",       "📖 Guide",     "ℹ️ Help"],
        "ru": ["📋 Проверить статус визы",       "📖 Инструкция","ℹ️ Помощь"],
    }
    btns = labels.get(lang, labels["uz"])
    return ReplyKeyboardMarkup(
        [[btns[0]], [btns[1], btns[2]]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton("🇬🇧 English",   callback_data="lang_en"),
        InlineKeyboardButton("🇷🇺 Русский",   callback_data="lang_ru"),
    ]])


def visa_type_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Admin: choose between E-Visa and Diplomatic."""
    labels = {
        "uz": ("💻 E-Viza (Individual)",        "🏛 Diplomatik ofis"),
        "en": ("💻 E-Visa (Individual)",         "🏛 Diplomatic Office"),
        "ru": ("💻 Э-виза (Индивидуальная)",    "🏛 Дипломатический офис"),
    }
    ev, dip = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(ev,  callback_data="vtype_evisa"),
        InlineKeyboardButton(dip, callback_data="vtype_diplomatic"),
    ]])


def cancel_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    labels = {"uz": "❌ Bekor qilish", "en": "❌ Cancel", "ru": "❌ Отмена"}
    return ReplyKeyboardMarkup(
        [[labels.get(lang, labels["uz"])]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def cert_download_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """Inline button shown under an APPROVED result."""
    labels = {
        "uz": "📄 Viza sertifikatini yuklab olish",
        "en": "📄 Download Visa Certificate",
        "ru": "📄 Скачать справку о визе",
    }
    label = labels.get(lang, labels["uz"])
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(label, callback_data="cert_dl"),
    ]])


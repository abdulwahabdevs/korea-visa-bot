"""
All user-facing strings — Uzbek (uz), English (en), Russian (ru).

Usage:
    from bot.strings import t, format_result
    msg = t("welcome", "uz")
"""

from __future__ import annotations
from typing import Any

# MRZ guide image (verified working, ~97 KB)
MRZ_IMAGE_URL = (
    # Trilingual (UZ/EN/RU) Uzbekistan passport MRZ guide
    # This image is bundled as data/passport_guide.png
    # Bot sends it as InputFile from local path; fallback to URL below
    "https://www.genspark.ai/api/files/s/cHqpT428"
)
MRZ_IMAGE_LOCAL = "assets/passport_guide.png"  # local path for InputFile (tracked by git)

STRINGS: dict[str, dict[str, str]] = {

    # ── /start ────────────────────────────────────────────────────────────
    "welcome": {
        "uz": (
            "🇰🇷 <b>Koreya Viza Botiga</b> xush kelibsiz!\n\n"
            "• /mystatus — Viza holatimni tekshirish\n"
            "• /guide — Qo'llanma\n"
            "• /language — Til (uz / en / ru)\n"
            "• /help — Yordam"
        ),
        "en": (
            "🇰🇷 Welcome to the <b>Korea Visa Bot</b>!\n\n"
            "• /mystatus — Check my visa status\n"
            "• /guide — How-to guide\n"
            "• /language — Language (uz / en / ru)\n"
            "• /help — Help"
        ),
        "ru": (
            "🇰🇷 Добро пожаловать в <b>Korea Visa Bot</b>!\n\n"
            "• /mystatus — Проверить статус визы\n"
            "• /guide — Инструкция\n"
            "• /language — Язык (uz / en / ru)\n"
            "• /help — Помощь"
        ),
    },

    # ── /help (student) ───────────────────────────────────────────────────
    "help_student": {
        "uz": (
            "ℹ️ <b>Buyruqlar</b>\n\n"
            "/mystatus — Viza holatini tekshirish\n"
            "/forget — Saqlangan ma'lumotni o'chirish\n"
            "/guide — Qo'llanma\n"
            "/language — Tilni o'zgartirish"
        ),
        "en": (
            "ℹ️ <b>Commands</b>\n\n"
            "/mystatus — Check visa status\n"
            "/forget — Clear saved credentials\n"
            "/guide — How-to guide\n"
            "/language — Change language"
        ),
        "ru": (
            "ℹ️ <b>Команды</b>\n\n"
            "/mystatus — Проверить статус визы\n"
            "/forget — Удалить сохранённые данные\n"
            "/guide — Инструкция\n"
            "/language — Изменить язык"
        ),
    },

    # ── /help (admin) ─────────────────────────────────────────────────────
    "help_admin": {
        "uz": (
            "ℹ️ <b>Admin buyruqlari</b>\n\n"
            "/login — Parol bilan kirish\n"
            "/logout — Chiqish\n"
            "/check — Bitta tekshirish\n"
            "/checkall — Excel orqali ommaviy tekshirish\n"
            "/export — Natijalarni yuklab olish\n"
            "/students — Talabalar soni\n\n"
            "<b>Talaba buyruqlari ham:</b> /mystatus /forget /language"
        ),
        "en": (
            "ℹ️ <b>Admin commands</b>\n\n"
            "/login — Authenticate with password\n"
            "/logout — Close session\n"
            "/check — Single check\n"
            "/checkall — Bulk check via Excel\n"
            "/export — Download results\n"
            "/students — Student count\n\n"
            "<b>Student commands also:</b> /mystatus /forget /language"
        ),
        "ru": (
            "ℹ️ <b>Команды администратора</b>\n\n"
            "/login — Войти с паролем\n"
            "/logout — Выйти\n"
            "/check — Одиночная проверка\n"
            "/checkall — Массовая проверка через Excel\n"
            "/export — Скачать результаты\n"
            "/students — Количество студентов\n\n"
            "<b>Команды студента тоже:</b> /mystatus /forget /language"
        ),
    },

    # ── Language ──────────────────────────────────────────────────────────
    "choose_language": {
        "uz": "🌐 Tilni tanlang:",
        "en": "🌐 Choose your language:",
        "ru": "🌐 Выберите язык:",
    },
    "language_set": {
        "uz": "✅ Til: <b>O'zbekcha</b>",
        "en": "✅ Language: <b>English</b>",
        "ru": "✅ Язык: <b>Русский</b>",
    },

    # ── Visa type selection (admin only) ──────────────────────────────────
    "choose_visa_type": {
        "uz": "📋 Qaysi turdagi arizani tekshirasiz?",
        "en": "📋 Which application type do you want to check?",
        "ru": "📋 Какой тип заявки вы хотите проверить?",
    },

    # ── Student: ask passport ─────────────────────────────────────────────
    "ask_passport": {
        "uz": (
            "🛂 <b>Pasport raqamingizni kiriting</b>\n\n"
            "Format: <code>AB1234567</code>\n"
            "— 1-2 ta KATTA harf + 7-8 ta raqam\n"
            "— Bo'sh joy va tire bo'lmasin\n\n"
            "📍 <i>Pasport raqami qayerda? Quyidagi rasmga qarang.</i>"
        ),
        "en": (
            "🛂 <b>Enter your passport number</b>\n\n"
            "Format: <code>AB1234567</code>\n"
            "— 1-2 UPPERCASE letters + 7-8 digits\n"
            "— No spaces or dashes\n\n"
            "📍 <i>See the image below for location.</i>"
        ),
        "ru": (
            "🛂 <b>Введите номер паспорта</b>\n\n"
            "Формат: <code>AB1234567</code>\n"
            "— 1-2 заглавные буквы + 7-8 цифр\n"
            "— Без пробелов и тире\n\n"
            "📍 <i>Смотрите изображение ниже.</i>"
        ),
    },
    "passport_image_caption": {
        "uz": "☝️ Pasportingizning pastki qismidagi 2 ta qatorda (MRZ) — ikkinchi qatorning birinchi 9 ta belgisi sizning pasport raqamingiz.",
        "en": "☝️ Bottom of your passport photo page — the first 9 characters of line 2 (MRZ) are your passport number.",
        "ru": "☝️ Нижняя часть страницы с фото — первые 9 символов второй строки (MRZ) — это номер вашего паспорта.",
    },

    # ── Student: ask full name ────────────────────────────────────────────
    "ask_name": {
        "uz": (
            "👤 <b>To'liq ismingizni kiriting</b> (pasportdagidek)\n\n"
            "Format: <code>FAMILIYA ISMI OTASINING_ISMI UGLI/QIZI</code>\n"
            "Misol: <code>YUSUPOV JASURBEK SALIM UGLI</code>\n\n"
            "⚠️ O'zbek pasportida <b>otasining ismi</b> ham yoziladi (UGLI yoki QIZI).\n"
            "⚠️ Faqat KATTA LOTIN harflar, pasportdagi tartibda."
        ),
        "en": (
            "👤 <b>Enter your full name</b> (exactly as in passport)\n\n"
            "Format: <code>SURNAME GIVENNAME FATHERSNAME UGLI/QIZI</code>\n"
            "Example: <code>YUSUPOV JASURBEK SALIM UGLI</code>\n\n"
            "⚠️ Uzbek passports include the <b>father's name</b> (UGLI for male, QIZI for female).\n"
            "⚠️ UPPERCASE Latin letters only, exactly as printed in your passport."
        ),
        "ru": (
            "👤 <b>Введите полное имя</b> (как в паспорте)\n\n"
            "Формат: <code>ФАМИЛИЯ ИМЯ ОТЧЕСТВО UGLI/QIZI</code>\n"
            "Пример: <code>YUSUPOV JASURBEK SALIM UGLI</code>\n\n"
            "⚠️ В узбекском паспорте указывается <b>отчество</b> (UGLI — муж., QIZI — жен.).\n"
            "⚠️ Только ЗАГЛАВНЫЕ латинские буквы, как в паспорте."
        ),
    },

    # ── Student: ask DOB ──────────────────────────────────────────────────
    "ask_dob": {
        "uz": (
            "📅 <b>Tug'ilgan sanangizni kiriting</b>\n\n"
            "Format: <code>YYYYMMDD</code>\n"
            "Misol: <code>20010315</code> (1998-yil 15-mart)\n\n"
            "✅ Qabul qilinadi: <code>20010315</code> · <code>1998-12-17</code> · <code>1998.12.17</code>"
        ),
        "en": (
            "📅 <b>Enter your date of birth</b>\n\n"
            "Format: <code>YYYYMMDD</code>\n"
            "Example: <code>20010315</code> (15 March 2001)\n\n"
            "✅ Also accepted: <code>1998-12-17</code> · <code>1998.12.17</code>"
        ),
        "ru": (
            "📅 <b>Введите дату рождения</b>\n\n"
            "Формат: <code>YYYYMMDD</code>\n"
            "Пример: <code>20010315</code> (15 марта 2001)\n\n"
            "✅ Также принимается: <code>1998-12-17</code> · <code>1998.12.17</code>"
        ),
    },

    # ── Admin: ask receipt ────────────────────────────────────────────────
    "ask_receipt": {
        "uz": (
            "📋 <b>Ariza raqamini kiriting</b> (신청번호)\n\n"
            "Format: <code>1234500001</code> (10 ta raqam)\n"
            "HiKorea → Civil Service → Application Status → birinchi ustun"
        ),
        "en": (
            "📋 <b>Enter the application receipt number</b> (신청번호)\n\n"
            "Format: <code>1234500001</code> (10 digits)\n"
            "HiKorea → Civil Service → Application Status → first column"
        ),
        "ru": (
            "📋 <b>Введите номер заявки</b> (신청번호)\n\n"
            "Формат: <code>1234500001</code> (10 цифр)\n"
            "HiKorea → Civil Service → Application Status → первый столбец"
        ),
    },

    # ── Checking ──────────────────────────────────────────────────────────
    "checking": {
        "uz": "⏳ Tekshirilmoqda... (10–20 soniya)",
        "en": "⏳ Checking... (10–20 seconds)",
        "ru": "⏳ Проверка... (10–20 секунд)",
    },

    # ── Status result ─────────────────────────────────────────────────────
    "status_result": {
        "uz": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📋 <b>Viza Holati</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Holat:  <b>{status_emoji} {status_en}</b>\n"
            "🇰🇷 Koreya: {status_ko}\n"
            "{visa_line}"
            "{date_line}"
            "{reason_line}"
            "🕐 Tekshirildi: {checked_at}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        "en": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📋 <b>Visa Status</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Status:  <b>{status_emoji} {status_en}</b>\n"
            "🇰🇷 Korean: {status_ko}\n"
            "{visa_line}"
            "{date_line}"
            "{reason_line}"
            "🕐 Checked: {checked_at}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
        "ru": (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📋 <b>Статус визы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 Статус:   <b>{status_emoji} {status_en}</b>\n"
            "🇰🇷 Корейск: {status_ko}\n"
            "{visa_line}"
            "{date_line}"
            "{reason_line}"
            "🕐 Проверено: {checked_at}\n"
            "━━━━━━━━━━━━━━━━━━━━"
        ),
    },

    # ── Credentials saved ─────────────────────────────────────────────────
    "credentials_saved": {
        "uz": (
            "✅ Ma'lumotlaringiz saqlandi.\n"
            "Keyingi /mystatus da qayta kiritish shart emas.\n"
            "O'chirish uchun: /forget"
        ),
        "en": (
            "✅ Credentials saved.\n"
            "No re-entry needed next time.\n"
            "To clear: /forget"
        ),
        "ru": (
            "✅ Данные сохранены.\n"
            "Повторный ввод не нужен.\n"
            "Для удаления: /forget"
        ),
    },

    # ── Forget ────────────────────────────────────────────────────────────
    "forget_done": {
        "uz": "🗑 Ma'lumotlaringiz o'chirildi.",
        "en": "🗑 Your credentials have been cleared.",
        "ru": "🗑 Данные удалены.",
    },
    "forget_nothing": {
        "uz": "ℹ️ Saqlangan ma'lumot yo'q.",
        "en": "ℹ️ No saved credentials found.",
        "ru": "ℹ️ Сохранённых данных нет.",
    },

    # ── Validation errors ─────────────────────────────────────────────────
    "err_receipt_format": {
        "uz": (
            "❌ Noto'g'ri ariza raqami.\n"
            "Aniq <b>10 ta raqam</b> kiriting.\n"
            "✅ Misol: <code>1234500001</code>"
        ),
        "en": (
            "❌ Invalid receipt number.\n"
            "Enter exactly <b>10 digits</b>.\n"
            "✅ Example: <code>1234500001</code>"
        ),
        "ru": (
            "❌ Неверный номер заявки.\n"
            "Введите ровно <b>10 цифр</b>.\n"
            "✅ Пример: <code>1234500001</code>"
        ),
    },
    "err_passport_format": {
        "uz": (
            "❌ Noto'g'ri pasport raqami.\n"
            "<b>1-2 KATTA harf + 7-8 raqam</b>, bo'sh joysiz.\n"
            "✅ Misol: <code>AB1234567</code>"
        ),
        "en": (
            "❌ Invalid passport number.\n"
            "<b>1-2 UPPERCASE letters + 7-8 digits</b>, no spaces.\n"
            "✅ Example: <code>AB1234567</code>"
        ),
        "ru": (
            "❌ Неверный номер паспорта.\n"
            "<b>1-2 ЗАГЛАВНЫЕ буквы + 7-8 цифр</b>, без пробелов.\n"
            "✅ Пример: <code>AB1234567</code>"
        ),
    },
    "err_name_format": {
        "uz": (
            "❌ Noto'g'ri ism.\n"
            "Faqat KATTA LOTIN harflar, pasportdagidek.\n"
            "O'zbek pasportida: <b>FAMILIYA ISMI OTASINING_ISMI UGLI/QIZI</b>\n"
            "✅ Misol: <code>YUSUPOV JASURBEK SALIM UGLI</code>"
        ),
        "en": (
            "❌ Invalid name.\n"
            "UPPERCASE Latin letters only, exactly as in passport.\n"
            "For Uzbek passports include father's name: <b>SURNAME NAME FATHERSNAME UGLI/QIZI</b>\n"
            "✅ Example: <code>YUSUPOV JASURBEK SALIM UGLI</code>"
        ),
        "ru": (
            "❌ Неверное имя.\n"
            "Только ЗАГЛАВНЫЕ латинские буквы, как в паспорте.\n"
            "Для узбекских паспортов: <b>ФАМИЛИЯ ИМЯ ОТЧЕСТВО UGLI/QIZI</b>\n"
            "✅ Пример: <code>YUSUPOV JASURBEK SALIM UGLI</code>"
        ),
    },
    "err_dob_format": {
        "uz": (
            "❌ Noto'g'ri sana.\n"
            "Format: <code>YYYYMMDD</code>\n"
            "✅ Misol: <code>20010315</code>"
        ),
        "en": (
            "❌ Invalid date of birth.\n"
            "Format: <code>YYYYMMDD</code>\n"
            "✅ Example: <code>20010315</code>"
        ),
        "ru": (
            "❌ Неверная дата рождения.\n"
            "Формат: <code>YYYYMMDD</code>\n"
            "✅ Пример: <code>20010315</code>"
        ),
    },

    # ── Status descriptions ───────────────────────────────────────────────
    "status_desc_PENDING": {
        "uz": "⏳ Ariza ko'rib chiqilmoqda. Qaror hali chiqarilmagan.",
        "en": "⏳ Application is under review. No decision yet.",
        "ru": "⏳ Заявка на рассмотрении. Решение ещё не принято.",
    },
    "status_desc_APPROVED": {
        "uz": "🎉 Viza tasdiqlandi! Elchixona/konsullik bilan bog'laning.",
        "en": "🎉 Visa approved! Contact the embassy/consulate.",
        "ru": "🎉 Виза одобрена! Обратитесь в посольство/консульство.",
    },
    "status_desc_USED": {
        "uz": "✅ Viza tasdiqlangan va ishlatilgan (Koreya kirishda foydalanilgan).",
        "en": "✅ Visa was approved and used — the person has entered Korea.",
        "ru": "✅ Виза одобрена и использована — въезд в Корею состоялся.",
    },
    "status_desc_REJECTED": {
        "uz": "❌ Ariza rad etildi.",
        "en": "❌ Application was rejected.",
        "ru": "❌ Заявка отклонена.",
    },
    "status_desc_NOT_FOUND": {
        "uz": "⚠️ Ma'lumot topilmadi. Pasport raqami yoki ismni tekshiring.",
        "en": "⚠️ No data found. Double-check your passport number and name.",
        "ru": "⚠️ Данные не найдены. Проверьте номер паспорта и имя.",
    },
    "status_desc_ERROR": {
        "uz": "🔴 Texnik xatolik. Iltimos keyinroq urinib ko'ring.",
        "en": "🔴 Technical error. Please try again later.",
        "ru": "🔴 Техническая ошибка. Попробуйте позже.",
    },

    # ── Cancel ────────────────────────────────────────────────────────────
    "cancelled": {
        "uz": "❌ Bekor qilindi.",
        "en": "❌ Cancelled.",
        "ru": "❌ Отменено.",
    },

    # ── /guide ────────────────────────────────────────────────────────────
    "guide": {
        "uz": (
            "📖 <b>Qo'llanma</b>\n\n"
            "<b>Pasport raqami</b> — pasportingizning pastki qismidagi 2 ta qator (MRZ).\n"
            "Ikkinchi qatorning <b>dastlabki 9 belgisi</b> — pasport raqamingiz.\n"
            "Misol: <code>AB1234567</code>\n\n"
            "<b>To'liq ism</b> — pasportdagi inglizcha yozuv (familiya + ism + otasining ismi + UGLI/QIZI).\n"
            "Misol: <code>YUSUPOV JASURBEK SALIM UGLI</code>\n\n"
            "<b>Tug'ilgan sana</b> — format <code>YYYYMMDD</code>.\n"
            "Misol: <code>20010315</code>"
        ),
        "en": (
            "📖 <b>Guide</b>\n\n"
            "<b>Passport number</b> — at the bottom of your passport photo page (MRZ zone).\n"
            "The <b>first 9 characters</b> of line 2 are your passport number.\n"
            "Example: <code>AB1234567</code>\n\n"
            "<b>Full name</b> — as printed in your passport (surname + given name + father's name + UGLI/QIZI).\n"
            "Example: <code>YUSUPOV JASURBEK SALIM UGLI</code>\n\n"
            "<b>Date of birth</b> — format <code>YYYYMMDD</code>.\n"
            "Example: <code>20010315</code>"
        ),
        "ru": (
            "📖 <b>Инструкция</b>\n\n"
            "<b>Номер паспорта</b> — внизу страницы с фото (зона MRZ).\n"
            "Первые <b>9 символов</b> второй строки — это ваш номер паспорта.\n"
            "Пример: <code>AB1234567</code>\n\n"
            "<b>Полное имя</b> — как в паспорте: фамилия + имя + отчество + UGLI/QIZI.\n"
            "Пример: <code>YUSUPOV JASURBEK SALIM UGLI</code>\n\n"
            "<b>Дата рождения</b> — формат <code>YYYYMMDD</code>.\n"
            "Пример: <code>20010315</code>"
        ),
    },

    # ── Admin login ───────────────────────────────────────────────────────
    "admin_ask_password": {
        "uz": "🔐 Admin parolini kiriting:",
        "en": "🔐 Enter the admin password:",
        "ru": "🔐 Введите пароль администратора:",
    },
    "admin_login_ok": {
        "uz": "✅ Admin sessiyasi ochildi. /help — barcha buyruqlar.",
        "en": "✅ Admin session started. /help for all commands.",
        "ru": "✅ Сессия открыта. /help — все команды.",
    },
    "admin_login_fail": {
        "uz": "❌ Noto'g'ri parol. Qaytadan kiriting yoki /cancel.",
        "en": "❌ Wrong password. Try again or /cancel.",
        "ru": "❌ Неверный пароль. Попробуйте ещё раз или /cancel.",
    },
    "admin_already_logged_in": {
        "uz": "✅ Allaqachon admin sifatida kirdingiz.",
        "en": "✅ Already logged in as admin.",
        "ru": "✅ Уже вошли как администратор.",
    },
    "admin_logged_out": {
        "uz": "🔒 Admin sessiyasi yopildi.",
        "en": "🔒 Admin session closed.",
        "ru": "🔒 Сессия завершена.",
    },
    "admin_only": {
        "uz": "🚫 Bu buyruq faqat adminlar uchun. /login orqali kiring.",
        "en": "🚫 Admins only. Use /login first.",
        "ru": "🚫 Только для администраторов. Сначала /login.",
    },
    "admin_not_in_list": {
        "uz": (
            "🚫 <b>Sizda kirish huquqi yo'q.</b>\n\n"
            f"Sizning ID: <code>{{uid}}</code>\n"
            "Ruxsat olish uchun admin bilan bog'laning."
        ),
        "en": (
            "🚫 <b>You are not allowed to use this bot.</b>\n\n"
            f"Your user ID: <code>{{uid}}</code>\n"
            "Please contact the admin to get access."
        ),
        "ru": (
            "🚫 <b>У вас нет доступа к этому боту.</b>\n\n"
            f"Ваш ID: <code>{{uid}}</code>\n"
            "Обратитесь к администратору для получения доступа."
        ),
    },

    # ── Admin: /check ─────────────────────────────────────────────────────
    "admin_check_usage_evisa": {
        "uz": (
            "E-Viza tekshirish uchun 4 ta ma'lumot kiriting:\n"
            "<code>ARIZA_RAQAMI PASPORT TOLIQQSIM TUGULGAN_SANA</code>\n\n"
            "Misol:\n"
            "<code>1234500001 AB1234567 YUSUPOV JASURBEK SALIM UGLI 20010315</code>\n\n"
            "📌 Ism: pasportdagidek KATTA harflarda (familiya + ism + otasining ismi + UGLI/QIZI)\n"
            "📌 Sana: YYYYMMDD formatida (masalan: 20010315)"
        ),
        "en": (
            "E-Visa check requires 4 fields:\n"
            "<code>RECEIPT PASSPORT FULLNAME DOB</code>\n\n"
            "Example:\n"
            "<code>1234500001 AB1234567 YUSUPOV JASURBEK SALIM UGLI 20010315</code>\n\n"
            "📌 Name: UPPERCASE as on passport — include father's name (UGLI/QIZI for Uzbek passports)\n"
            "📌 DOB: YYYYMMDD format (e.g. 20010315)"
        ),
        "ru": (
            "Для проверки E-Visы нужны 4 поля:\n"
            "<code>НОМЕР_ЗАЯВКИ ПАСПОРТ ПОЛНОЕ_ИМЯ ДАТА_РОЖДЕНИЯ</code>\n\n"
            "Пример:\n"
            "<code>1234500001 AB1234567 YUSUPOV JASURBEK SALIM UGLI 20010315</code>\n\n"
            "📌 Имя: ЗАГЛАВНЫМИ буквами как в паспорте (включая отчество UGLI/QIZI)\n"
            "📌 Дата: формат YYYYMMDD (напр. 20010315)"
        ),
    },
    "admin_check_usage_diplomatic": {
        "uz": "Foydalanish: /check <code>PASSPORT NAME DOB</code>\nMisol: /check AB1234567 \"YUSUPOV JASURBEK SALIM UGLI\" 20010315",
        "en": "Usage: /check <code>PASSPORT NAME DOB</code>\nExample: /check AB1234567 \"YUSUPOV JASURBEK SALIM UGLI\" 20010315",
        "ru": "Использование: /check <code>PASSPORT NAME DOB</code>\nПример: /check AB1234567 \"YUSUPOV JASURBEK SALIM UGLI\" 20010315",
    },

    # ── Admin: /checkall ──────────────────────────────────────────────────
    "checkall_upload": {
        "uz": "📂 Excel faylni yuboring (.xlsx).\nFayl talabalar ro'yxatini o'z ichiga olishi kerak.",
        "en": "📂 Upload the Excel file (.xlsx) with the student list.",
        "ru": "📂 Загрузите Excel-файл (.xlsx) со списком студентов.",
    },
    "checkall_upload_diplomatic": {
        "uz": (
            "📎 <b>Diplomatic Office (재외공관) tekshiruvi</b>\n\n"
            "Excel faylni yuboring. Fayl quyidagi ustunlarni o'z ichiga olishi kerak:\n"
            "• <b>여권번호</b> yoki <b>passport</b> — Pasport raqami (majburiy)\n"
            "• <b>성명</b> yoki <b>name</b> — To'liq ism BOSH HARFLAR bilan (majburiy)\n"
            "• <b>생년월일</b> yoki <b>dob</b> — Tug'ilgan sana YYYYMMDD (majburiy)\n"
            "• Ariza raqami (receipt) — <i>ixtiyoriy, kerak emas</i>\n\n"
            "❌ Bekor qilish uchun /cancel"
        ),
        "en": (
            "📎 <b>Diplomatic Office (재외공관) bulk check</b>\n\n"
            "Upload your Excel file. Required columns:\n"
            "• <b>여권번호</b> or <b>passport</b> — Passport number (required)\n"
            "• <b>성명</b> or <b>name</b> — Full name in UPPERCASE (required)\n"
            "• <b>생년월일</b> or <b>dob</b> — Date of birth YYYYMMDD (required)\n"
            "• Receipt / application number — <i>not needed for diplomatic</i>\n\n"
            "❌ Type /cancel to abort"
        ),
        "ru": (
            "📎 <b>Проверка через Дипломатическое представительство (재외공관)</b>\n\n"
            "Загрузите Excel файл. Нужные столбцы:\n"
            "• <b>여권번호</b> или <b>passport</b> — Номер паспорта (обязательно)\n"
            "• <b>성명</b> или <b>name</b> — Полное имя ЗАГЛАВНЫМИ (обязательно)\n"
            "• <b>생년월일</b> или <b>dob</b> — Дата рождения YYYYMMDD (обязательно)\n"
            "• Номер заявки (receipt) — <i>не нужен для дипломатической проверки</i>\n\n"
            "❌ /cancel для отмены"
        ),
    },
    "checkall_start": {
        "uz": (
            "🚀 <b>Tekshiruv boshlandi</b>\n"
            "👥 Talabalar: <b>{count}</b> ta\n"
            "⏱ Taxminiy vaqt: ~<b>{eta} daqiqa</b>\n"
            "\n"
            "Natijalar tayyor bo'lgach fayl yuboriladi."
        ),
        "en": (
            "🚀 <b>Bulk check started</b>\n"
            "👥 Students: <b>{count}</b>\n"
            "⏱ Estimated time: ~<b>{eta} min</b>\n"
            "\n"
            "Results file will be sent when done."
        ),
        "ru": (
            "🚀 <b>Массовая проверка начата</b>\n"
            "👥 Студентов: <b>{count}</b>\n"
            "⏱ Примерное время: ~<b>{eta} мин</b>\n"
            "\n"
            "Файл результатов будет отправлен по завершении."
        ),
    },
    "checkall_progress": {
        "uz": (
            "⏳ <b>Tekshirilmoqda...</b>\n"
            "\n"
            "{bar}  <b>{done}/{total}</b>\n"
            "\n"
            "🟢 Tasdiqlangan: <b>{approved}</b>\n"
            "🟡 Kutilmoqda/Ko'rib chiqilmoqda: <b>{pending}</b>\n"
            "🔴 Rad etilgan: <b>{rejected}</b>\n"
            "⚪ Topilmadi:   <b>{not_found}</b>\n"
            "❌ Xato:        <b>{error}</b>\n"
            "\n"
            "⏱ {elapsed}s o'tdi · ~{remaining}s qoldi\n"
            "\n"
            "🔹 Oxirgi: <code>{last_name}</code> → {last_status}"
        ),
        "en": (
            "⏳ <b>Checking in progress...</b>\n"
            "\n"
            "{bar}  <b>{done}/{total}</b>\n"
            "\n"
            "🟢 Approved:  <b>{approved}</b>\n"
            "🟡 Pending/Under review: <b>{pending}</b>\n"
            "🔴 Rejected:  <b>{rejected}</b>\n"
            "⚪ Not found: <b>{not_found}</b>\n"
            "❌ Error:     <b>{error}</b>\n"
            "\n"
            "⏱ {elapsed}s elapsed · ~{remaining}s left\n"
            "\n"
            "🔹 Last: <code>{last_name}</code> → {last_status}"
        ),
        "ru": (
            "⏳ <b>Проверка идёт...</b>\n"
            "\n"
            "{bar}  <b>{done}/{total}</b>\n"
            "\n"
            "🟢 Одобрено:    <b>{approved}</b>\n"
            "🟡 На рассмотрении: <b>{pending}</b>\n"
            "🔴 Отказано:    <b>{rejected}</b>\n"
            "⚪ Не найдено:  <b>{not_found}</b>\n"
            "❌ Ошибка:      <b>{error}</b>\n"
            "\n"
            "⏱ Прошло {elapsed}s · осталось ~{remaining}s\n"
            "\n"
            "🔹 Последний: <code>{last_name}</code> → {last_status}"
        ),
    },
    "checkall_done": {
        "uz": (
            "✅ <b>Tekshiruv yakunlandi!</b>\n"
            "\n"
            "👥 Jami: <b>{total}</b> ta talaba\n"
            "⏱ Sarflangan vaqt: <b>{elapsed}</b>\n"
            "\n"
            "🟢 Tasdiqlangan: <b>{approved}</b>\n"
            "🟡 Kutilmoqda/Ko'rib chiqilmoqda: <b>{pending}</b>\n"
            "🔴 Rad etilgan: <b>{rejected}</b>\n"
            "⚪ Topilmadi:   <b>{not_found}</b>\n"
            "❌ Xato:        <b>{error}</b>\n"
            "\n"
            "📎 Excel fayl quyida yuborildi."
        ),
        "en": (
            "✅ <b>Bulk check complete!</b>\n"
            "\n"
            "👥 Total: <b>{total}</b> students\n"
            "⏱ Time taken: <b>{elapsed}</b>\n"
            "\n"
            "🟢 Approved:  <b>{approved}</b>\n"
            "🟡 Pending/Under review: <b>{pending}</b>\n"
            "🔴 Rejected:  <b>{rejected}</b>\n"
            "⚪ Not found: <b>{not_found}</b>\n"
            "❌ Errors:    <b>{error}</b>\n"
            "\n"
            "📎 Excel file attached below."
        ),
        "ru": (
            "✅ <b>Массовая проверка завершена!</b>\n"
            "\n"
            "👥 Всего: <b>{total}</b> студентов\n"
            "⏱ Время: <b>{elapsed}</b>\n"
            "\n"
            "🟢 Одобрено:    <b>{approved}</b>\n"
            "🟡 На рассмотрении: <b>{pending}</b>\n"
            "🔴 Отказано:    <b>{rejected}</b>\n"
            "⚪ Не найдено:  <b>{not_found}</b>\n"
            "❌ Ошибки:      <b>{error}</b>\n"
            "\n"
            "📎 Файл Excel прикреплён ниже."
        ),
    },
    "export_empty": {
        "uz": "📭 Natija yo'q. Avval /checkall ni ishga tushiring.",
        "en": "📭 No results yet. Run /checkall first.",
        "ru": "📭 Результатов нет. Сначала запустите /checkall.",
    },
    "export_ready": {
        "uz": "📥 Natijalar:",
        "en": "📥 Results file:",
        "ru": "📥 Файл результатов:",
    },
    "students_info": {
        "uz": "👥 Ro'yxatdan o'tgan talabalar: <b>{count}</b>",
        "en": "👥 Registered students: <b>{count}</b>",
        "ru": "👥 Зарегистрированных студентов: <b>{count}</b>",
    },
}

STATUS_EMOJI: dict[str, str] = {
    "PENDING":      "🟡",
    "APPROVED":     "🟢",
    "USED":         "✅",   # sausawagreed + used by student
    "REJECTED":     "🔴",
    "NOT_FOUND":    "⚪",
    "ERROR":        "🔴",
    "UNKNOWN":      "❓",
    "RECEIVED":     "🟡",
    "UNDER_REVIEW": "🟡",
    "ISSUED":       "🟢",
    "WITHDRAWN":    "⚪",
    "RETURNED":     "🟡",
    # ── Certificate download strings ──────────────────────────────────────
    "cert_downloading": {
        "uz": "⏳ Sertifikat yuklab olinmoqda, iltimos kuting…",
        "en": "⏳ Downloading certificate, please wait…",
        "ru": "⏳ Скачиваю справку, подождите…",
    },
    "cert_not_approved": {
        "uz": "⚠️ Vizangiz hali tasdiqlanmagan. Sertifikat faqat <b>허가 (Tasdiqlangan)</b> holatida mavjud.",
        "en": "⚠️ Your visa is not approved yet. Certificate available only at <b>허가 (Approved)</b> status.",
        "ru": "⚠️ Ваша виза ещё не одобрена. Справка доступна только при статусе <b>허가 (Одобрено)</b>.",
    },
    "cert_error": {
        "uz": "❌ Sertifikatni yuklab olishda xatolik: {error}",
        "en": "❌ Certificate download failed: {error}",
        "ru": "❌ Ошибка загрузки справки: {error}",
    },
    "cert_caption": {
        "uz": "📄 Viza tasdiqlanishi haqida ma'lumotnoma (비자발급확인서)",
        "en": "📄 Visa Approval Certificate (비자발급확인서)",
        "ru": "📄 Справка о выдаче визы (비자발급확인서)",
    },

    # ── Feedback ──────────────────────────────────────────────────────────────
    "feedback_prompt": {
        "uz": "📩 <b>Muammo bildirish</b>\n\nXatolik yoki muammo haqida yozing yoki screenshot yuboring.\nAdminlar tez orada ko'rib chiqadi.\n\n❌ Bekor qilish uchun /cancel",
        "en": "📩 <b>Report an Issue</b>\n\nDescribe your problem or send a screenshot.\nOur admins will review it shortly.\n\n❌ Type /cancel to cancel",
        "ru": "📩 <b>Сообщить о проблеме</b>\n\nОпишите проблему или отправьте скриншот.\nАдминистраторы рассмотрят ваше обращение.\n\n❌ /cancel для отмены",
    },
    "feedback_sent": {
        "uz": "✅ Muammongiz adminga yuborildi. Tez orada ko'rib chiqiladi.",
        "en": "✅ Your report has been sent to the admins. We will review it shortly.",
        "ru": "✅ Ваше сообщение отправлено администраторам. Мы рассмотрим его в ближайшее время.",
    },
    "feedback_empty": {
        "uz": "⚠️ Iltimos, muammo haqida matn yozing yoki screenshot yuboring.",
        "en": "⚠️ Please send a text message or a screenshot describing your issue.",
        "ru": "⚠️ Пожалуйста, напишите текст или отправьте скриншот с описанием проблемы.",
    },

}


# ── Public helpers ────────────────────────────────────────────────────────────

def t(key: str, lang: str, **kwargs: Any) -> str:
    lang = lang if lang in ("uz", "en", "ru") else "uz"
    entry = STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("en") or f"[{key}]"
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def format_result(result: dict, lang: str) -> str:
    status_en  = result.get("status_en", "UNKNOWN")
    status_ko  = result.get("status_ko") or "—"
    visa_type  = result.get("visa_type") or ""
    app_date   = result.get("app_date") or ""
    reason     = result.get("reason") or ""
    receipt    = result.get("receipt") or ""
    checked_at = result.get("checked_at") or "—"
    emoji      = STATUS_EMOJI.get(status_en, "❓")

    _v = {"uz": "🎓 Viza turi: ", "en": "🎓 Visa type: ", "ru": "🎓 Тип визы: "}
    _d = {"uz": "📅 Ariza sanasi: ", "en": "📅 App. date: ", "ru": "📅 Дата заявки: "}
    _r = {"uz": "📝 Sabab: ", "en": "📝 Reason: ", "ru": "📝 Причина: "}

    visa_line   = f"{_v.get(lang,_v['uz'])}{visa_type}\n" if visa_type else ""
    date_line   = f"{_d.get(lang,_d['uz'])}{app_date}\n"  if app_date  else ""
    reason_line = f"{_r.get(lang,_r['uz'])}{reason}\n"    if reason    else ""

    if receipt:
        receipt_line = {"uz": f"🔢 Ariza №: <code>{receipt}</code>\n",
                        "en": f"🔢 Receipt: <code>{receipt}</code>\n",
                        "ru": f"🔢 Заявка: <code>{receipt}</code>\n"}.get(lang, "")
    else:
        receipt_line = ""

    msg = t(
        "status_result", lang,
        status_emoji=emoji, status_en=status_en, status_ko=status_ko,
        visa_line=visa_line, date_line=date_line, reason_line=reason_line,
        checked_at=checked_at,
    )
    # prepend receipt line if present
    if receipt_line:
        msg = msg.replace("📊", receipt_line + "📊")

    desc_key = f"status_desc_{status_en}"
    if desc_key in STRINGS:
        msg += "\n\n" + t(desc_key, lang)

    return msg

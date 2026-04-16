# 🇰🇷 Korea Visa Status Bot

A multilingual Telegram bot that lets **students** check their Korean visa application status via the Diplomatic Office channel, and **admins** perform bulk/single checks for both E-Visa and Diplomatic Office channels — with full Excel import/export support.
<img width="300" height="200" alt="image" src="https://github.com/user-attachments/assets/a643a1b5-4f9b-4b04-b7ff-7999de87848a" />
<img width="300" height="200" alt="image" src="https://github.com/user-attachments/assets/78aaea84-996c-46c4-bf39-2b8ed17d6540" />



---

## 📋 Table of Contents
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration (.env)](#configuration-env)
- [Running the Bot](#running-the-bot)
- [Bot Usage](#bot-usage)
- [Student Commands](#student-commands)
- [Admin Commands](#admin-commands)
- [Visa Check Types](#visa-check-types)
- [Status Types & Colors](#status-types--colors)
- [Excel Format for Bulk Check](#excel-format-for-bulk-check)
- [Languages](#languages)
- [Deployment (Free Server)](#deployment-free-server)
- [GitHub Setup](#github-setup)
- [Troubleshooting](#troubleshooting)

---

## ✨ Features

| Feature | Student | Admin |
|---------|---------|-------|
| Check own visa status (Diplomatic) | ✅ | ✅ |
| Check E-Visa status | ❌ | ✅ |
| Bulk Excel check | ❌ | ✅ |
| Export results to Excel | ❌ | ✅ |
| View student list | ❌ | ✅ |
| Multilingual (UZ/EN/RU) | ✅ | ✅ |
| In-bot MRZ passport guide | ✅ | ✅ |
| Save credentials (first use only) | ✅ | — |

---

## 📁 Project Structure

```
korea-visa-bot/
├── .env.example          # Environment variable template
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── requirements.txt      # Python dependencies
├── run.py                # 🚀 Entry point — python run.py
│
├── assets/
│   └── passport_guide.png    # MRZ guide image (tracked by git)
│
├── bot/
│   ├── app.py            # Bot initialisation, dispatcher setup
│   ├── keyboards.py      # Inline & reply keyboards
│   ├── strings.py        # All UI strings (UZ/EN/RU) + MRZ image URL
│   └── handlers/
│       ├── common.py     # /start, /help, /language, /guide
│       ├── student.py    # /mystatus, /forget  (Diplomatic only)
│       └── admin.py      # /login, /check, /checkall, /export, /students
│
├── db/
│   ├── database.py       # SQLite schema + CRUD helpers
│   └── crypto.py         # Fernet encryption for student PII
│
├── src/
│   ├── cache.py          # Shared in-process result cache (OPT-E)
│   ├── checker.py        # Orchestrates scraper → returns result dict
│   ├── excel_reader.py   # Smart column detection for bulk import
│   ├── excel_writer.py   # Writes result .xlsx files
│   ├── rate_limiter.py   # Per-user check cooldown
│   └── scraper/
│       ├── driver_factory.py  # Headless Chrome setup
│       ├── facade.py          # Form fill, submit, parse (both visa types)
│       └── status_parser.py   # Korean status → English mapping
│
└── data/                 # Runtime data (ignored by git)
    └── visa_bot.db       # SQLite database (auto-created)
```

---

## ⚙️ Prerequisites

| Requirement | Version |
|------------|---------|
| Python | 3.10+ |
| Google Chrome | Latest stable |
| ChromeDriver | Matching Chrome version |
| Telegram Bot Token | From [@BotFather](https://t.me/BotFather) |

> **Install ChromeDriver:** Download from https://chromedriver.chromium.org/ and add to PATH, or place `chromedriver.exe` (Windows) / `chromedriver` (Linux/Mac) in the project root.

---

## 🚀 Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/korea-visa-bot.git
cd korea-visa-bot
```

### 2. Create & activate virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Then open `.env` in any text editor and fill in your values (see below).

---

## 🔑 Configuration (.env)

```env
# ─── Required ─────────────────────────────────────────────────────────────────
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ

# Comma-separated Telegram user IDs with admin access
ADMIN_CHAT_IDS=123456789,987654321

# Password required to unlock admin commands in chat
ADMIN_PASSWORD=your_secure_password_here

# ─── Security ─────────────────────────────────────────────────────────────────
# Encrypts student PII (passport, name, DOB) at rest in the database.
# Generate with: openssl rand -hex 32
# WARNING: do not change this after data has been saved.
SECRET_KEY=change_me_to_a_long_random_string

# Admin session TTL in hours (default: 24). Re-login required after expiry.
ADMIN_SESSION_TTL_HOURS=24

# Per-user cooldown between checks in seconds (default: 30).
USER_COOLDOWN_SECONDS=30

# ─── Optional ─────────────────────────────────────────────────────────────────
# Default language for new users: uz | en | ru
DEFAULT_LANG=uz

# SQLite database path (relative to project root)
DB_PATH=data/visa_bot.db

# Log level: DEBUG | INFO | WARNING | ERROR
LOG_LEVEL=INFO

# Chrome options: true for servers, false for local debugging
CHROME_HEADLESS=true

# Number of parallel Chrome workers (each ~200 MB RAM)
CHROME_POOL_SIZE=3

# Result cache TTL in seconds (default 300 = 5 minutes)
CACHE_TTL_SECONDS=300
```

> ⚠️ **Never commit your `.env` file!** It is listed in `.gitignore` by default.

---

## ▶️ Running the Bot

```bash
# Make sure venv is activated first
python run.py
```

You should see:
```
✅ Database initialised at data/visa_bot.db
🤖 Bot started — polling...
```

**Stop the bot:** `Ctrl + C`

---

## 🤖 Bot Usage

### Student Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message & menu |
| `/mystatus` | Check your visa status (Diplomatic Office) |
| `/forget` | Clear your saved passport/name/DOB |
| `/guide` | Passport & MRZ help with photo |
| `/language` | Switch language (UZ / EN / RU) |
| `/help` | Show available commands |

#### Student Flow — `/mystatus`

```
Student:  /mystatus
Bot:      📷 [Sends MRZ guide photo]
          Enter your passport number (e.g. FA4166021)
Student:  FA4166021
Bot:      Enter your full name exactly as in passport
          (e.g. SURNAME GIVEN NAME FATHER'S NAME)
Student:  SOMEONOV SOMEONE SOMEONE'S SON/DAUGHTER
Bot:      Enter date of birth (YYYYMMDD)
          (e.g. 19981217)
Student:  19981217
Bot:      ✅ Checking... [result shown]
          💾 Credentials saved for next time
```

On subsequent uses, `/mystatus` uses saved credentials automatically.

---

### Admin Commands

| Command | Description |
|---------|-------------|
| `/login` | Authenticate with admin password |
| `/logout` | End admin session |
| `/check` | Single visa check (choose E-Visa or Diplomatic) |
| `/checkall` | Bulk check via Excel upload |
| `/export` | Download last results as Excel |
| `/students` | View number of registered students |

#### Admin Login Flow

```
Admin:  /login
Bot:    Enter admin password:
Admin:  your_secure_password_here
Bot:    ✅ Admin session active. Commands unlocked.
```

#### Admin Single Check — `/check`

```
Admin:  /check
Bot:    Choose visa type:
        [E-Visa (Individual)] [Diplomatic Office]

# E-Visa selected:
Bot:    Enter: <receipt_number> <passport_number>
        Example: 5677400001 FA4166021
Admin:  5677400001 FA4166021
Bot:    🔍 Checking... ✅ Result displayed

# Diplomatic selected:
Bot:    Enter: <passport> <full_name> <DOB_YYYYMMDD>
        Example: FB1234567 SOMEONOV SOMEONE SOMEONE'S SON 19981217
Admin:  FB1234567 SOMEONOV SOMEONE SOMEONE'S SON 19981217
Bot:    🔍 Checking... ✅ Result displayed
```

---

## 🎫 Visa Check Types

| Type | Portal Tab | Who Uses | Required Fields |
|------|-----------|----------|-----------------|
| **Diplomatic Office** | searchType2 / gb02 | Students + Admins | Passport No., Full Name, DOB |
| **E-Visa Individual** | searchType1 / gb01 | Admins only | Receipt No. + Passport No. |

> The portal used is: **https://www.visa.go.kr**

---

## 🎨 Status Types & Colors

The portal returns Korean status strings which the bot maps to distinct English categories.
Each category has its **own emoji**, **bot message description**, and **Excel row color** so admins can tell them apart at a glance.

| Korean (진행상태) | English Code | Emoji | Excel Color | Meaning |
|------------------|-------------|-------|-------------|----------|
| 허가 | `APPROVED` | 🟢 | 💚 Light Green | Visa approved |
| 발급 / 발급완료 | `ISSUED` | 🟢 | 💚 Light Green | Visa issued |
| 사용완료 | `USED` | ✅ | 💚 Dark Green | Visa used — entered Korea |
| 접수 | `RECEIVED` | 🟡 | 💛 Light Yellow | Application received, no review yet |
| 심사 / 심사중 / 추가심사 | `UNDER_REVIEW` | 🔵 | 💙 Light Blue | Actively under review |
| 발급준비중 | `PENDING` | 🟡 | 💛 Yellow | Generic pending / preparing issuance |
| **보완요청 / 보완중** | **`SUPPLEMENT`** | **📋** | **🟧 Orange** | **Additional docs REQUESTED — action needed!** |
| **보완완료** | **`SUPPLEMENT_DONE`** | **📤** | **💙 Blue-grey** | **Docs submitted — back in review queue** |
| 불허 / 거부 | `REJECTED` | 🔴 | ❤️ Red | Application denied |
| 반려 | `RETURNED` | 🟠 | 🩷 Salmon | Returned by consulate |
| 취하 / 접수철회 | `WITHDRAWN` | ⚪ | 🩶 Grey | Applicant withdrew voluntarily |
| **신청취소** | **`CANCELLED`** | **⚫** | **🩶 Dark Grey** | **Application officially cancelled** |
| — | `NOT_FOUND` | ⬜ | ⬜ Light Grey | Record not found on portal |
| — | `ERROR` | 🟣 | 💜 Mauve | Technical error (retry later) |

> **Key distinction:** `SUPPLEMENT` (📋 orange) means the officer is **waiting for your documents** — it requires action.
> `SUPPLEMENT_DONE` (📤) means documents were submitted and the application is **back in the review queue** — treated as pending.

---

## 📊 Excel Format for Bulk Check

### E-Visa Bulk (`/checkall` → E-Visa)

| Column A | Column B |
|----------|----------|
| Receipt Number | Passport Number |
| 5677400001 | FA4166021 |
| 5677400002 | AB1234567 |

### Diplomatic Bulk (`/checkall` → Diplomatic)

| Column A | Column B | Column C |
|----------|----------|----------|
| Passport Number | Full Name | DOB (YYYYMMDD) |
| FB1234567 | SOMEONOV SOMEONE SOMEONE'S SON | 19981217 |

> The bot uses smart header detection — column names don't need to be exact. It searches for keywords like "receipt", "passport", "name", "birth".

---

## 🌐 Languages

The bot supports **3 languages**:

| Code | Language | Default |
|------|----------|---------|
| `uz` | O'zbek | ✅ Yes |
| `en` | English | |
| `ru` | Русский | |

Users switch language with `/language`. The preference is saved per Telegram user ID.

---

## ☁️ Deployment (Free Server)

### Option A — Railway.app (Recommended)

1. Push to GitHub (see below)
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Add environment variables (same as `.env`)
4. Set start command: `python run.py`
5. Done — bot runs 24/7

### Option B — Render.com

1. New Web Service → connect GitHub repo
2. Build command: `pip install -r requirements.txt`
3. Start command: `python run.py`
4. Add environment variables
5. **Note:** Add `CHROME_HEADLESS=true` and install Chrome buildpack

### Option C — VPS (Any Provider)

```bash
# Install dependencies
sudo apt-get install -y google-chrome-stable
pip install -r requirements.txt

# Run with screen (stays alive after SSH disconnect)
screen -S visabot
python run.py
# Ctrl+A, D to detach
```

---

## 📤 GitHub Setup

```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit — Korea Visa Bot v1.0"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/korea-visa-bot.git
git branch -M main
git push -u origin main
```

> `.gitignore` already excludes: `.env`, `*.db`, `__pycache__`, `venv/`, `data/`, `*.zip`

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in activated venv |
| `WebDriverException` | Check ChromeDriver version matches Chrome; add to PATH |
| Bot not responding | Verify `BOT_TOKEN` in `.env` is correct |
| `ADMIN_CHAT_IDS` not working | Use your numeric Telegram ID (get it from [@userinfobot](https://t.me/userinfobot)) |
| Status shows ERROR | Portal may be down; retry in a few minutes |
| Bulk check stops mid-way | Chrome session timed out; reduce batch size or increase timeout |

---

## 📝 Input Validation Rules

| Field | Format | Example | Regex |
|-------|--------|---------|-------|
| Passport No. | 2 letters + 7 digits | `FA4166021` | `^[A-Z]{2}[0-9]{7}$` |
| Receipt No. | 10 digits | `5677400001` | `^[0-9]{10}$` |
| Full Name | Uppercase letters + spaces | `SOMEONOV SOMEONE SOMEONE'S SON` | `^[A-Z\s]{2,}$` |
| DOB | YYYYMMDD | `19981217` | `^[0-9]{8}$` |

---

## 🔒 Security

| Feature | Detail |
|---------|--------|
| Student PII encryption | Passport, name, DOB encrypted with Fernet (AES-128) before DB storage. Set `SECRET_KEY` in `.env`. |
| Admin session TTL | Admin sessions expire after `ADMIN_SESSION_TTL_HOURS` (default 24 h). |
| Password protection | `/login` requires `ADMIN_PASSWORD` — empty password blocks all admin logins. |
| Per-user rate limiting | Students are rate-limited to one check per `USER_COOLDOWN_SECONDS` (default 30 s). |

---

## 📝 Changelog

### v1.0.6 (status categories overhaul)
- **NEW:** `SUPPLEMENT` status (보완요청/보완중) is now a **dedicated orange category** — clearly separated from pending.
- **NEW:** `SUPPLEMENT_DONE` status (보완완료) — docs submitted, mapped to **pending** (back in review queue).
- **NEW:** `CANCELLED` status (신청취소) — new portal status, shown as dark grey.
- **NEW:** `RETURNED` status (반려) — now has its **own salmon color**, separated from `REJECTED`.
- **NEW:** `UNDER_REVIEW` uses 🔵 blue emoji (was 🟡 yellow, same as `PENDING`).
- **NEW:** `ERROR` uses 🟣 purple emoji & mauve Excel color — no longer confused with `REJECTED`.
- **NEW:** Progress bar & `/stats` now show a **Supplement** counter as a separate row.
- **NEW:** 6 new `status_desc_*` bot messages (SUPPLEMENT_DONE, CANCELLED, RECEIVED, UNDER_REVIEW, ISSUED, RETURNED).
- **FIX (critical):** `strings.py` structural bug — `cert_*` and `feedback_*` strings were accidentally nested inside the `STATUS_EMOJI` dict instead of `STRINGS`. Moved them back to `STRINGS`.
- **FIX:** `facade.py` status mapping changed from dict to **ordered list** — prevents false substring matches (e.g. 보완완료 no longer matched by 보완 first, 접수철회 no longer matched by 접수 first).
- **IMPROVED:** Every status type now has a **unique Excel row color** — admins can scan bulk results visually.
- **IMPROVED:** `/stats` command shows separate rows for supplement, returned, withdrawn/cancelled.

### v1.0.2 (security & quality)
- **FIX (critical):** Auth bypass — empty `ADMIN_PASSWORD` no longer grants admin access to everyone.
- **FIX (security):** Admin sessions now expire after configurable TTL (default 24 h).
- **FIX (security):** Student PII (passport, name, DOB) is now Fernet-encrypted at rest.
- **FIX:** `DB_PATH` env var is now actually read by `database.py` (was documented but ignored).
- **FIX:** Duplicate result cache eliminated — `src/cache.py` is now the single source of truth.
- **NEW:** Per-user check cooldown (`USER_COOLDOWN_SECONDS`) prevents check spamming.
- **NEW:** `assets/passport_guide.png` moved out of gitignored `data/` — ships with the repo.
- **NEW:** `cryptography` added to `requirements.txt` for PII encryption.
- **IMPROVED:** `.gitignore` now excludes `data/screenshots/`, `data/certs/`, and `*.zip`.

---

## 📜 License

MIT License — free to use, modify, and distribute.

---

## 🙏 Credits

- Built with [python-telegram-bot](https://python-telegram-bot.org/) v20+
- Selenium WebDriver for portal scraping
- SQLite for lightweight persistent storage
- Portal: [visa.go.kr](https://www.visa.go.kr)

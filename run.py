"""
Entry point — run with:  python run.py

Python 3.14 compatibility:
  run_polling() is a synchronous blocking call that manages its own event loop
  internally. Python 3.14 stopped auto-creating event loops, so we explicitly
  create and set one before PTB touches it.

  WindowsSelectorEventLoopPolicy is NOT used here:
    • It is deprecated in Python 3.14 and removed in 3.16
    • PTB v20+ works correctly with the default ProactorEventLoop on Windows
    • The only thing Python 3.14 requires is that a loop already exists —
      asyncio.new_event_loop() + asyncio.set_event_loop() is sufficient.
"""

import asyncio
import logging
import os
import sys
import warnings
from dotenv import load_dotenv

# ── Warning filters ───────────────────────────────────────────────────────────
# Suppress the harmless PTBUserWarning about per_message=False + CallbackQueryHandler.
# Admin ConversationHandlers intentionally use per_message=False.
warnings.filterwarnings(
    "ignore",
    message=r".*per_message=False.*CallbackQueryHandler.*",
    category=UserWarning,
)

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
for _noisy in ("httpx", "selenium", "urllib3", "telegram.ext"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main() -> None:
    from bot.app import create_app
    app = create_app()
    logger.info("🤖  Korea Visa Bot is running — press Ctrl+C to stop")
    # run_polling() is synchronous — it manages its own event loop internally
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    # Python 3.14+ no longer auto-creates an event loop.
    # Pre-create one so PTB's run_polling() can find it.
    # asyncio.new_event_loop() and set_event_loop() are NOT deprecated —
    # they work on Python 3.6 through 3.16+ without any warnings.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()

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
import warnings
from dotenv import load_dotenv

warnings.filterwarnings(
    "ignore",
    message=r".*per_message=False.*CallbackQueryHandler.*",
    category=UserWarning,
)

load_dotenv()

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
    loop = asyncio.get_event_loop()

    # Start Telethon before run_polling() takes over
    try:
        from src.telethon_client import start_telethon
        loop.run_until_complete(start_telethon())
    except Exception as e:
        logger.warning("Telethon startup failed (profile card forwarding disabled): %s", e)

    from bot.app import create_app
    app = create_app()
    logger.info("🤖  Korea Visa Bot is running — press Ctrl+C to stop")
    try:
        app.run_polling(drop_pending_updates=True)
    finally:
        try:
            from src.telethon_client import stop_telethon
            loop.run_until_complete(stop_telethon())
        except Exception:
            pass


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()

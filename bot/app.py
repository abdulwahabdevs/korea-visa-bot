"""
Application builder — assembles the Telegram Application with all handlers.
"""

from __future__ import annotations
import logging
import os

from telegram.ext import Application
from telegram.request import HTTPXRequest

from bot.handlers import common, student, admin
from db.database import init_db
from src.worker_pool import get_pool, close_pool

logger = logging.getLogger(__name__)


def create_app() -> Application:
    """
    Initialise the database, build the Telegram Application,
    and register all handlers.
    """
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "BOT_TOKEN is not set.\n"
            "Create a .env file from .env.example and fill in your token."
        )

    init_db()

    # Increase timeouts — important for Uzbekistan (Telegram API can be slow/blocked)
    _request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=30,
        write_timeout=30,
        pool_timeout=30,
    )
    app = Application.builder().token(token).request(_request).build()

    # Register handlers in priority order
    # (admin > student > common — avoids ConversationHandler conflicts)
    admin.register(app)
    student.register(app)
    common.register(app)

    # OPT-F: pre-warm all pool workers in background so first checks
    # hit an already-loaded portal page.
    async def _post_init(application: Application) -> None:
        get_pool().pre_warm()   # warms all POOL_SIZE Chrome workers

    async def _post_shutdown(application: Application) -> None:
        close_pool()            # graceful Chrome shutdown on bot stop

    app.post_init     = _post_init
    app.post_shutdown = _post_shutdown

    logger.info("Application built — %d handlers registered", len(app.handlers))
    return app

"""
Telethon user client — used only for forwarding messages
so Telegram shows the real sender profile card with photo.
"""
from __future__ import annotations
import os
import logging

logger = logging.getLogger(__name__)

_client = None


def get_telethon_client():
    global _client
    if _client is None:
        api_id   = os.getenv("TELETHON_API_ID", "")
        api_hash = os.getenv("TELETHON_API_HASH", "")
        if not api_id or not api_hash:
            logger.warning("TELETHON_API_ID or TELETHON_API_HASH not set — Telethon disabled")
            return None
        try:
            from telethon import TelegramClient
            _client = TelegramClient(
                "data/support_session",
                int(api_id),
                api_hash,
            )
        except ImportError:
            logger.warning("Telethon not installed — run: pip install telethon")
            return None
    return _client


async def start_telethon() -> None:
    phone = os.getenv("TELETHON_PHONE", "")
    if not phone:
        logger.warning("TELETHON_PHONE not set — profile card forwarding disabled")
        return
    client = get_telethon_client()
    if client is None:
        return
    try:
        await client.start(phone=lambda: phone)
        me = await client.get_me()
        logger.info("✅ Telethon client started as: %s (@%s)", me.first_name, me.username)
    except Exception as e:
        logger.error("Telethon start failed: %s", e)


async def stop_telethon() -> None:
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        logger.info("Telethon client disconnected")
    _client = None


async def forward_as_user(from_chat_id: int, message_id: int, to_chat_id) -> bool:
    """
    Forward using the user account — shows real profile card with photo.
    Returns True on success, False if Telethon unavailable.
    """
    client = get_telethon_client()
    if client is None or not client.is_connected():
        return False
    try:
        await client.forward_messages(
            entity=to_chat_id,
            messages=message_id,
            from_peer=from_chat_id,
        )
        return True
    except Exception as e:
        logger.warning("Telethon forward failed: %s", e)
        return False
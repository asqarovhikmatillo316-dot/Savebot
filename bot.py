import asyncio
import logging
import os
import html
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from aiohttp import web
from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import yt_dlp

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- SOZLAMALAR ---
# Render -> Environment bo'limiga BOT_TOKEN nomli variable qo'shing.
TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = "@Tillosave_bot"
ADMIN_ID = 5621433060

# Bot ushbu ikkala kanalga ham administrator qilib qo'yilishi kerak.
REQUIRED_CHANNELS = [
    {
        "id": -3973741534,
        "link": "https://t.me/+8ibfJL_Q_FU5YzEy",
        "title": "1-kanal",
    },
    {
        "id": -4406015595,
        "link": "https://t.me/+I55yoIA3bYhmZDBi",
        "title": "2-kanal",
    },
]


def subscription_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📢 {channel['title']}ga a'zo bo'lish",
                              url=channel["link"])]
        for channel in REQUIRED_CHANNELS
    ] + [[InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")]])


async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Foydalanuvchi barcha majburiy kanallarga a'zo ekanini tekshiradi."""
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(
                chat_id=channel["id"],
                user_id=user_id,
            )
            if member.status not in ("member", "administrator", "creator"):
                return False
            # Restricted foydalanuvchi a'zo bo'lishi mumkin, lekin is_member False bo'lsa rad etamiz.
            if member.status == "restricted" and not getattr(member, "is_member", False):
                return False
        except TelegramError as exc:
            logger.warning(
                "Obunani tekshirib bo'lmadi (%s): %s",
                channel["title"],
                exc,
            )
            # Kanal IDsi yoki bot ruxsati noto'g'ri bo'lsa, yuklashga ruxsat bermaymiz.
            return False
    return True


async def require_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    if await check_subscription(user.id, context):
        return True

    text = (
        "🔒 <b>Botdan foydalanish uchun ikkala kanalga ham a'zo bo'ling.</b>\n\n"

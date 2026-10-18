import asyncio
import logging
import os
import html
import tempfile
import shutil
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

# --- SOZLAMALAR (XAVFSIZ) ---
TOKEN = os.getenv("BOT_TOKEN", "8891447881:AAGK544Dd5-qmdJhXRHpnrIuLxKF1NXGmPA").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5621433060"))
BOT_USERNAME = "@Tillosave_bot"

# Majburiy obuna kanallari
REQUIRED_CHANNELS = [
    {
        "id": -1001973741534,
        "link": "https://t.me/+8ibfJL_Q_FU5YzEy",
        "title": "1-Kanal 📢",
    },
    {
        "id": -1002440601559,
        "link": "https://t.me/+I55yoIA3bYhmZDBi",
        "title": "2-Kanal 📢",
    },
]


def subscription_keyboard():
    buttons = [
        [InlineKeyboardButton(text=f"✨ {channel['title']} ga ulanish", url=channel["link"])]
        for channel in REQUIRED_CHANNELS
    ]
    buttons.append([InlineKeyboardButton(text="🔄 Obunani tasdiqlash", callback_data="check_sub")])
    return InlineKeyboardMarkup(buttons)


async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Foydalanuvchi majburiy kanallarga a'zo ekanini tekshiradi."""
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(
                chat_id=channel["id"],
                user_id=user_id,
            )
            if member.status in ("left", "kicked"):
                return False
        except TelegramError as exc:
            logger.warning(f"Obuna tekshirishda ogohlantirish ({channel['title']}): {exc}")
            continue
    return True


async def require_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    if await check_subscription(user.id, context):
        return True

    text = (
        "⚡️ <b>Botdan foydalanish uchun rasmiy kanallarimizga a'zo bo'ling!</b>\n\n"
        "<i>Quyidagi tugmalar orqali kanallarga kiring va a'zo bo'ling, so'ngra <b>«Obunani tasdiqlash»</b> tugmasini bosing:</i>"
    )

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=subscription_keyboard(),
            )
        except TelegramError:
            await update.callback_query.message.reply_text(
                text, parse_mode="HTML", reply_markup=subscription_keyboard()
            )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=subscription_keyboard(),
        )
    return False


# --- START HANDLER ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.effective_message:
        return

    if not await require_subscription(update, context):
        return

    await update.effective_message.reply_text(
        f"👋 <b>Xush kelibsiz, {html.escape(user.first_name)}!</b>\n\n"
        "📸 Menga <b>Instagram</b> (Reels, Post, IGTV) havolasini yuboring.\n"
        "Men uni sizga to'g'ri va eng yuqori sifatda yuklab beraman! ⚡️🎬",
        parse_mode="HTML",
    )

    # Admin bildirishi
    try:
        user_name = html.escape(user.full_name or "Noma'lum")
        username = f"@{user.username}" if user.username else "yo'q"
        admin_text = (
            "🚀 <b>Yangi foydalanuvchi start bosdi!</b>\n\n"
            f"👤 <b>Ismi:</b> {user_name}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"🔗 <b>Username:</b> {html.escape(username)}"
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML"
        )
    except Exception as exc:
        logger.warning(f"Adminga bildirishnoma yuborilmadi: {exc}")


# --- INSTAGRAM YUKLASH FUNKSIYASI ---
def download_instagram_video(url: str, output_template: str) -> str:
    ydl_opts = {
        "outtmpl": output_template,
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 5,
        "socket_timeout": 30,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "nocache": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    if not Path(filename).exists():
        candidate = str(Path(filename).with_suffix(".mp4"))
        if Path(candidate).exists():
            filename = candidate

    if not Path(filename).exists():
        raise FileNotFoundError("Yuklangan video topilmadi.")
    return filename


# --- HAVOLA KELGANDA ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    if not await require_subscription(update, context):
        return

    url = update.message.text.strip()
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        await update.message.reply_text(
            "❌ <b>Iltimos, to'g'ri Instagram havolasini yuboring.</b> 🔗",
            parse_mode="HTML",
        )
        return

    domain = parsed.netloc.lower()

    if "instagram.com" not in domain:
        await update.message.reply_text(
            "ℹ️ <b>Ushbu bot faqat Instagram videolarini yuklaydi.</b>\n"
            "Iltimos, Instagram Reels yoki Post havolasini yuboring.",
            parse_mode="HTML",
        )
        return

    status_msg = await update.message.reply_text(
        "⚡️ <i>Instagram video yuklanmoqda, kuting...</i>", parse_mode="HTML"
    )

    temp_dir = tempfile.mkdtemp(prefix="insta_")
    output_template = str(Path(temp_dir) / "download.%(ext)s")

    try:
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(
            None, download_instagram_video, url, output_template
        )

        if os.path.getsize(file_path) > 49 * 1024 * 1024:
            await status_msg.edit_text(
                "❌ <b>Fayl hajmi Telegram chekovidan (49 MB) oshib ketdi.</b>",
                parse_mode="HTML",
            )
            return

        with open(file_path, "rb") as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=f"🎬 <b>Yuklab olindi:</b> {BOT_USERNAME}",
                parse_mode="HTML",
                supports_streaming=True,
            )
        await status_msg.delete()

    except Exception as exc:
        logger.exception(f"Instagram yuklashda xatolik: {exc}")
        await status_msg.edit_text(
            "❌ <b>Instagram videoni yuklab bo'lmadi.</b>\n"
            "<i>Havola to'g'riligini va sahifa ochiqligini (Public) tekshiring.</i>",
            parse_mode="HTML",
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# --- CALLBACK QUERY (OBUNA TEKSHIRISH) ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    if query.data == "check_sub":
        if await check_subscription(query.from_user.id, context):
            await query.answer("✅ Obuna tasdiqlandi!", show_alert=True)
            try:
                await query.edit_message_text(
                    "🎉 <b>Obuna muvaffaqiyatli tasdiqlandi!</b>\n\n"
                    "<i>Endi Instagram havolasini yuborishingiz mumkin.</i>",
                    parse_mode="HTML",
                )
            except TelegramError:
                pass
        else:
            await query.answer(
                "❌ Hali ikkala kanalga ham to'liq a'zo bo'lmadingiz!",
                show_alert=True,
            )
            try:
                await query.edit_message_reply_markup(
                    reply_markup=subscription_keyboard()
                )
            except TelegramError:
                pass


# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Botda kutilmagan xatolik yuz berdi:", exc_info=context.error)


# --- RENDER WEB SERVER ---
async def handle_ping(request):
    return web.Response(text="Bot is running cleanly!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000")))
    await site.start()


# --- ASOSIY ISHGA TUSHIRISH ---
async def main_async():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi!")

    application = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .connect_timeout(60)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)

    asyncio.create_task(start_web_server())

    async with application:
        await application.initialize()
        await application.bot.set_my_commands([
            BotCommand("start", "Botni ishga tushirish 🔄")
        ])
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main_async())

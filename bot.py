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

# --- SOZLAMALAR ---
TOKEN = "8891447881:AAHl-rmeiem-VevnAtVO0MoMQky9yZfufVw"
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
        [InlineKeyboardButton(f"📢 {channel['title']}ga a'zo bo'lish", url=channel["link"])]
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
            if member.status == "restricted" and not getattr(member, "is_member", False):
                return False
        except TelegramError as exc:
            logger.warning(
                "Obunani tekshirib bo'lmadi (%s): %s",
                channel["title"],
                exc,
            )
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
        "1. Quyidagi ikkita kanalga kiring.\n"
        "2. A'zo bo'ling.\n"
        "3. «Obunani tekshirish» tugmasini bosing."
    )

    if update.callback_query:
        await update.callback_query.answer()
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


# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.effective_message:
        return

    if not await require_subscription(update, context):
        pass
    else:
        await update.effective_message.reply_text(
            "👋 <b>Xush kelibsiz!</b>\n\n"
            "Menga <b>Instagram</b> 📸 yoki <b>YouTube</b> 🔴 video havolasini yuboring.\n"
            "Uni <b>MP4 video</b> yoki <b>MP3 audio</b> ko'rinishida yuklab olishingiz mumkin. ⚡️",
            parse_mode="HTML",
        )

    try:
        user_name = html.escape(user.full_name or "Noma'lum")
        username = f"@{user.username}" if user.username else "yo'q"
        admin_text = (
            "🚀 <b>Yangi foydalanuvchi /start bosdi!</b>\n\n"
            f"👤 <b>Ismi:</b> {user_name}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"🔗 <b>Username:</b> {html.escape(username)}"
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML"
        )
    except TelegramError as exc:
        logger.warning("Adminga bildirishnoma yuborilmadi: %s", exc)


# --- YUKLASH ---
def download_media(url: str, output_template: str, is_audio: bool = False) -> str:
    """YouTube va Instagram'dan media yuklaydi (IP bloki va format sozlamalari bilan)."""
    ydl_opts = {
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "socket_timeout": 30,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "web_creator"],
                "player_skip": ["webpage", "configs"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "Accept-Language": "en-US,en;q=0.9",
        }
    }

    if is_audio:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": "best[ext=mp4]/best",
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    if is_audio:
        filename = str(Path(filename).with_suffix(".mp3"))
    elif not Path(filename).exists():
        candidate = str(Path(filename).with_suffix(".mp4"))
        if Path(candidate).exists():
            filename = candidate

    if not Path(filename).exists():
        raise FileNotFoundError("Yuklangan fayl topilmadi.")
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
            "Iltimos, to'g'ri Instagram yoki YouTube havolasini yuboring. 🔗"
        )
        return

    context.user_data["pending_url"] = url
    context.user_data["pending_chat_id"] = update.effective_chat.id

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎬 Video (MP4)", callback_data="fmt_mp4"),
        InlineKeyboardButton("🎵 Audio (MP3)", callback_data="fmt_mp3"),
    ]])

    await update.message.reply_text(
        "Qaysi formatda yuklashni xohlaysiz?",
        reply_markup=keyboard,
    )


# --- TUGMALAR ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    if query.data == "check_sub":
        if await check_subscription(query.from_user.id, context):
            await query.answer("✅ Ikkala kanalga ham a'zosiz!", show_alert=True)
            try:
                await query.edit_message_text(
                    "✅ Obuna tasdiqlandi!\n\n"
                    "Endi Instagram yoki YouTube havolasini yuboring."
                )
            except TelegramError:
                pass
        else:
            await query.answer(
                "❌ Ikkala kanalga ham a'zo bo'ling, so'ng qayta tekshiring.",
                show_alert=True,
            )
            try:
                await query.edit_message_reply_markup(
                    reply_markup=subscription_keyboard()
                )
            except TelegramError:
                pass
        return

    if query.data not in ("fmt_mp4", "fmt_mp3"):
        await query.answer("Noma'lum tugma.", show_alert=True)
        return

    if not await check_subscription(query.from_user.id, context):
        await query.answer("Avval ikkala kanalga a'zo bo'ling.", show_alert=True)
        await query.edit_message_text(
            "🔒 <b>Davom etish uchun ikkala kanalga a'zo bo'ling.</b>",
            parse_mode="HTML",
            reply_markup=subscription_keyboard(),
        )
        return

    url = context.user_data.get("pending_url")
    if not url:
        await query.answer("Havola topilmadi. Havolani qayta yuboring.", show_alert=True)
        return

    is_audio = query.data == "fmt_mp3"
    await query.answer()
    await query.edit_message_text(
        "⚡️ Audio yuklanmoqda, kuting..." if is_audio
        else "⚡️ Video yuklanmoqda, kuting..."
    )

    temp_dir = tempfile.mkdtemp(prefix="tillosave_")
    output_template = str(Path(temp_dir) / "download.%(ext)s")
    file_path = None

    try:
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(
            None, download_media, url, output_template, is_audio
        )

        if os.path.getsize(file_path) > 49 * 1024 * 1024:
            await query.message.reply_text(
                "❌ Fayl hajmi Telegram orqali yuborish uchun juda katta (49 MB dan oshdi)."
            )
            return

        with open(file_path, "rb") as media_file:
            if is_audio:
                await query.message.reply_audio(
                    audio=media_file,
                    caption=f"🤖 {BOT_USERNAME}",
                )
            else:
                await query.message.reply_video(
                    video=media_file,
                    caption=f"🤖 {BOT_USERNAME}",
                    supports_streaming=True,
                )

        try:
            await query.delete_message()
        except TelegramError:
            pass

    except Exception as exc:
        logger.exception("Media yuklashda xatolik: %s", exc)
        message = (
            "❌ Faylni yuklashda xatolik yuz berdi. Havolani tekshirib, qayta urinib ko'ring."
        )
        try:
            await query.edit_message_text(message)
        except TelegramError:
            await query.message.reply_text(message)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Botda kutilmagan xatolik yuz berdi:", exc_info=context.error)


# --- RENDER WEB SERVER ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000")))
    await site.start()


# --- MAIN ---
async def main_async():
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

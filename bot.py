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
TOKEN = os.getenv("BOT_TOKEN", "8891447881:AAGK544Dd5-qmdJhXRHpnrIuLxKF1NXGmPA").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5621433060"))
BOT_USERNAME = "@Tillosave_bot"
COOKIES_TEXT = os.getenv("YOUTUBE_COOKIES", "").strip()

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


async def get_unsubscribed_channels(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> list:
    unsubscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(
                chat_id=channel["id"],
                user_id=user_id,
            )
            if member.status in ("left", "kicked"):
                unsubscribed.append(channel)
        except TelegramError as exc:
            logger.warning(f"Obuna tekshirishda ogohlantirish ({channel['title']}): {exc}")
            continue
    return unsubscribed


def build_subscription_keyboard(unsubscribed_channels: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"✨ {channel['title']} ga ulanish", url=channel["link"])]
        for channel in unsubscribed_channels
    ]
    buttons.append([InlineKeyboardButton(text="🔄 Obunani tasdiqlash", callback_data="check_sub")])
    return InlineKeyboardMarkup(buttons)


async def require_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    unsubscribed = await get_unsubscribed_channels(user.id, context)
    if not unsubscribed:
        return True

    text = (
        "⚡️ <b>Botdan foydalanish uchun quyidagi kanal(lar)ga a'zo bo'ling:</b>\n\n"
        "<i>Kanalga kirib a'zo bo'ling, so'ngra <b>«Obunani tasdiqlash»</b> tugmasini bosing:</i>"
    )

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=build_subscription_keyboard(unsubscribed),
            )
        except TelegramError:
            await update.callback_query.message.reply_text(
                text, parse_mode="HTML", reply_markup=build_subscription_keyboard(unsubscribed)
            )
    elif update.effective_message:
        await update.effective_message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=build_subscription_keyboard(unsubscribed),
        )
    return False


# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.effective_message:
        return

    if not await require_subscription(update, context):
        return

    await update.effective_message.reply_text(
        f"👋 <b>Xush kelibsiz, {html.escape(user.first_name)}!</b>\n\n"
        "🌟 Menga <b>Instagram</b> 📸 yoki <b>YouTube</b> 🔴 havolasini yuboring.\n\n"
        "• <b>Instagram:</b> Avtomatik eng yuqori sifatda yuklanadi 🎬\n"
        "• <b>YouTube:</b> Video sifatini (720p, 480p, ...) yoki MP3 formatini tanlashingiz mumkin 🎵",
        parse_mode="HTML",
    )

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


# --- MEDIA YUKLASH FUNKSIYASI ---
def download_media(url: str, output_template: str, format_spec: str = "best", is_audio: bool = False, cookies_path: str = None) -> str:
    ydl_opts = {
        "format": format_spec,
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "cachedir": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android_creator", "ios", "web"],
                "player_skip": ["configs"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    # Əgar GitHub'ga yuklangan youtube_cookies.txt fayli mavjud bo'lsa, shundan o'qiydi
    if Path("youtube_cookies.txt").exists():
        ydl_opts["cookiefile"] = "youtube_cookies.txt"
    elif cookies_path and Path(cookies_path).exists():
        ydl_opts["cookiefile"] = cookies_path

    if is_audio:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
        })
    else:
        ydl_opts.update({
            "format": format_spec,
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

    if is_audio:
        candidate_mp3 = str(Path(filename).with_suffix(".mp3"))
        if Path(candidate_mp3).exists():
            return candidate_mp3

    if not Path(filename).exists():
        candidate = str(Path(filename).with_suffix(".mp4"))
        if Path(candidate).exists():
            return candidate

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
            "❌ <b>Iltimos, to'g'ri Instagram yoki YouTube havolasini yuboring.</b> 🔗",
            parse_mode="HTML",
        )
        return

    domain = parsed.netloc.lower()

    # INSTAGRAM BO'LSA
    if "instagram.com" in domain:
        status_msg = await update.message.reply_text(
            "⚡️ <i>Instagram video yuklanmoqda, kuting...</i>", parse_mode="HTML"
        )

        temp_dir = tempfile.mkdtemp(prefix="insta_")
        output_template = str(Path(temp_dir) / "download.%(ext)s")

        try:
            loop = asyncio.get_running_loop()
            file_path = await loop.run_in_executor(
                None, download_media, url, output_template, "best[ext=mp4]/best", False, None
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
        return

    # YOUTUBE BO'LSA
    elif "youtube.com" in domain or "youtu.be" in domain:
        context.user_data["pending_url"] = url

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎥 720p HD", callback_data="yt_720"),
                InlineKeyboardButton("📹 480p", callback_data="yt_480"),
            ],
            [
                InlineKeyboardButton("📹 360p", callback_data="yt_360"),
                InlineKeyboardButton("📹 240p", callback_data="yt_240"),
                InlineKeyboardButton("📹 144p", callback_data="yt_144"),
            ],
            [
                InlineKeyboardButton("🎵 MP3 Audio", callback_data="yt_mp3")
            ]
        ])

        await update.message.reply_text(
            "🔴 <b>YouTube videoni qaysi sifatda yuklamoqchisiz?</b>\n\n"
            "<i>Sifat yoki audio formatini tanlang:</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "ℹ️ <b>Faqat Instagram va YouTube havolalari qo'llab-quvvatlanadi.</b>",
            parse_mode="HTML"
        )


# --- CALLBACK QUERY ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    if query.data == "check_sub":
        unsubscribed = await get_unsubscribed_channels(query.from_user.id, context)

        if not unsubscribed:
            await query.answer("✅ Barcha kanallarga a'zosiz!", show_alert=True)
            try:
                await query.edit_message_text(
                    "🎉 <b>Obuna muvaffaqiyatli tasdiqlandi!</b>\n\n"
                    "<i>Endi Instagram yoki YouTube havolasini yuborishingiz mumkin.</i>",
                    parse_mode="HTML",
                )
            except TelegramError:
                pass
        else:
            await query.answer(
                "❌ Hali barcha kanallarga a'zo bo'lmadingiz!",
                show_alert=True,
            )
            text = (
                "⚡️ <b>Deyarli tayyor! Qolgan kanal(lar)ga ham a'zo bo'ling:</b>\n\n"
                "<i>Quyidagi kanalga kirib a'zo bo'ling, so'ngra qayta <b>«Obunani tasdiqlash»</b> tugmasini bosing:</i>"
            )
            try:
                await query.edit_message_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=build_subscription_keyboard(unsubscribed),
                )
            except TelegramError:
                pass
        return

    if not query.data.startswith("yt_"):
        return

    if not await require_subscription(update, context):
        await query.answer("Avval kanallarga a'zo bo'ling.", show_alert=True)
        return

    url = context.user_data.get("pending_url")
    if not url:
        await query.answer("Havola topilmadi. Qayta yuboring.", show_alert=True)
        return

    choice = query.data
    is_audio = (choice == "yt_mp3")

    if choice == "yt_720":
        fmt = "b[height<=720]/bv*[height<=720]+ba/b"
        quality_label = "720p Video"
    elif choice == "yt_480":
        fmt = "b[height<=480]/bv*[height<=480]+ba/b"
        quality_label = "480p Video"
    elif choice == "yt_360":
        fmt = "b[height<=360]/bv*[height<=360]+ba/b"
        quality_label = "360p Video"
    elif choice == "yt_240":
        fmt = "b[height<=240]/bv*[height<=240]+ba/b"
        quality_label = "240p Video"
    elif choice == "yt_144":
        fmt = "b[height<=144]/bv*[height<=144]+ba/b"
        quality_label = "144p Video"
    else:
        fmt = "ba/b"
        quality_label = "MP3 Audio"

    await query.answer()
    await query.edit_message_text(f"⚡️ <b>{quality_label} yuklanmoqda, biroz kuting...</b>", parse_mode="HTML")

    temp_dir = tempfile.mkdtemp(prefix="yt_")
    output_template = str(Path(temp_dir) / "download.%(ext)s")
    
    cookies_path = None
    if COOKIES_TEXT:
        cookies_path = str(Path(temp_dir) / "cookies.txt")
        with open(cookies_path, "w", encoding="utf-8") as f:
            f.write(COOKIES_TEXT)

    try:
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(
            None, download_media, url, output_template, fmt, is_audio, cookies_path
        )

        if os.path.getsize(file_path) > 49 * 1024 * 1024:
            await query.message.reply_text(
                "❌ <b>Fayl hajmi Telegram chekovidan (49 MB) oshib ketdi. Nisbatan pastroq sifatni tanlang.</b>",
                parse_mode="HTML"
            )
            return

        with open(file_path, "rb") as media_file:
            if is_audio:
                await query.message.reply_audio(
                    audio=media_file,
                    caption=f"🎵 <b>Yuklab olindi:</b> {BOT_USERNAME}",
                    parse_mode="HTML"
                )
            else:
                await query.message.reply_video(
                    video=media_file,
                    caption=f"🎬 <b>Sifat:</b> {quality_label}\n🤖 <b>Manba:</b> {BOT_USERNAME}",
                    parse_mode="HTML",
                    supports_streaming=True,
                )

        try:
            await query.delete_message()
        except TelegramError:
            pass

    except Exception as exc:
        logger.exception(f"YouTube yuklashda xatolik: {exc}")
        message = "❌ <b>Ushbu sifatdagi videoni yuklab bo'lmadi. Boshqa sifatni tanlab ko'ring.</b>"
        try:
            await query.edit_message_text(message, parse_mode="HTML")
        except TelegramError:
            await query.message.reply_text(message, parse_mode="HTML")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


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


# --- MAIN ---
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
        asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main_async())

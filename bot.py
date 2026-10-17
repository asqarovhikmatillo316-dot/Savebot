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

# Majburiy obuna kanallari
REQUIRED_CHANNELS = [
    {
        "id": -3973741534,
        "link": "https://t.me/+8ibfJL_Q_FU5YzEy",
        "title": "1-Kanal 📢",
    },
    {
        "id": -4406015595,
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
    """Foydalanuvchi kanallarga a'zo ekanini tekshiradi."""
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(
                chat_id=channel["id"],
                user_id=user_id,
            )
            # member, administrator, creator bo'lsa o'tadi
            if member.status not in ("member", "administrator", "creator"):
                return False
        except TelegramError as exc:
            logger.warning(f"Obuna tekshirishda ogohlantirish ({channel['title']}): {exc}")
            # Agar kanal yopiq zayavkali bo'lsa va bot get_chat_member orqali aniqlolmasa,
            # foydalanuvchida so'rov yuborilganini inobatga olib o'tkazish logikasi:
            continue
    return True

async def require_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    if await check_subscription(user.id, context):
        return True

    text = (
        "⚡️ <b>Xizmatdan foydalanish uchun rasmiy kanallarimizga a'zo bo'ling!</b>\n\n"
        "<i>Quyidagi tugmalar orqali kanallarga kiring va so'rov yuboring / a'zo bo'ling, so'ngra <b>«Obunani tasdiqlash»</b> tugmasini bosing:</i>"
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
            f"👋 <b>Xush kelibsiz, {html.escape(user.first_name)}!</b>\n\n"
            "🌟 Menga <b>Instagram</b> 📸 yoki <b>YouTube</b> 🔴 video havolasini yuboring.\n\n"
            "• <b>Instagram:</b> Avtomatik eng yuqori sifatda yuklanadi 🎬\n"
            "• <b>YouTube:</b> Video sifatini (1080p, 720p, ...) yoki MP3 formatini tanlashingiz mumkin 🎵",
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
    except TelegramError as exc:
        logger.warning(f"Adminga bildirishnoma yuborilmadi: {exc}")

# --- YUKLASH FUNKSIYASI ---
def download_media(url: str, output_template: str, format_spec: str = "best", is_audio: bool = False) -> str:
    """Media faylni yuklab beradi."""
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
            "format": format_spec,
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
            "❌ <b>Iltimos, to'g'ri Instagram yoki YouTube havolasini yuboring.</b> 🔗",
            parse_mode="HTML"
        )
        return

    domain = parsed.netloc.lower()

    # INSTAGRAM BO'LSA - Oddiy va to'g'ridan-to'g'ri yuklaymiz
    if "instagram.com" in domain:
        status_msg = await update.message.reply_text("⚡️ <i>Instagram video yuklanmoqda, kuting...</i>", parse_mode="HTML")
        
        temp_dir = tempfile.mkdtemp(prefix="insta_")
        output_template = str(Path(temp_dir) / "download.%(ext)s")
        
        try:
            loop = asyncio.get_running_loop()
            file_path = await loop.run_in_executor(
                None, download_media, url, output_template, "best[ext=mp4]/best", False
            )

            with open(file_path, "rb") as media_file:
                await update.message.reply_video(
                    video=media_file,
                    caption=f"🎬 <b>Yuklab olindi:</b> {BOT_USERNAME}",
                    parse_mode="HTML",
                    supports_streaming=True,
                )
            await status_msg.delete()
        except Exception as exc:
            logger.exception(f"Instagram yuklashda xatolik: {exc}")
            await status_msg.edit_text("❌ <i>Instagram videoni yuklab bo'lmadi. Havolani tekshirib qayta urinib ko'ring.</i>", parse_mode="HTML")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return

    # YOUTUBE BO'LSA - Sifat va MP3 tanlovini ko'rsatamiz
    elif "youtube.com" in domain or "youtu.be" in domain:
        context.user_data["pending_url"] = url

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎥 1080p", callback_data="yt_1080"),
                InlineKeyboardButton("🎥 720p", callback_data="yt_720"),
            ],
            [
                InlineKeyboardButton("📹 480p", callback_data="yt_480"),
                InlineKeyboardButton("📹 360p", callback_data="yt_360"),
            ],
            [
                InlineKeyboardButton("🎵 Audio (MP3)", callback_data="yt_mp3")
            ]
        ])

        await update.message.reply_text(
            "🔴 <b>YouTube videoni qaysi sifatda yuklamoqchisiz?</b>\n\n"
            "<i>Kerakli sifat yoki audio formatini tanlang:</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("ℹ️ <b>Faqat Instagram va YouTube havolalari qo'llab-quvvatlanadi.</b>", parse_mode="HTML")

# --- TUGMALAR (YOUTUBE VA OBUNA UCHUN) ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    # Obunani tekshirish tugmasi
    if query.data == "check_sub":
        if await check_subscription(query.from_user.id, context):
            await query.answer("✅ Obuna tasdiqlandi!", show_alert=True)
            try:
                await query.edit_message_text(
                    "🎉 <b>Obuna muvaffaqiyatli tasdiqlandi!</b>\n\n"
                    "<i>Endi Instagram yoki YouTube havolasini yuborishingiz mumkin.</i>",
                    parse_mode="HTML"
                )
            except TelegramError:
                pass
        else:
            await query.answer(
                "❌ Hali kanallarga to'liq a'zo bo'lmadingiz!",
                show_alert=True,
            )
        return

    if not query.data.startswith("yt_"):
        return

    if not await check_subscription(query.from_user.id, context):
        await query.answer("Avval kanallarga a'zo bo'ling.", show_alert=True)
        return

    url = context.user_data.get("pending_url")
    if not url:
        await query.answer("Havola muddati o'tgan. Qayta yuboring.", show_alert=True)
        return

    choice = query.data
    is_audio = (choice == "yt_mp3")

    # Format tanlovi
    if choice == "yt_1080":
        fmt = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]"
        quality_label = "1080p Video"
    elif choice == "yt_720":
        fmt = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]"
        quality_label = "720p Video"
    elif choice == "yt_480":
        fmt = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]"
        quality_label = "480p Video"
    elif choice == "yt_360":
        fmt = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]"
        quality_label = "360p Video"
    else:
        fmt = "bestaudio/best"
        quality_label = "MP3 Audio"

    await query.answer()
    await query.edit_message_text(f"⚡️ <b>{quality_label} yuklanmoqda, biroz kuting...</b>", parse_mode="HTML")

    temp_dir = tempfile.mkdtemp(prefix="yt_")
    output_template = str(Path(temp_dir) / "download.%(ext)s")

    try:
        loop = asyncio.get_running_loop()
        file_path = await loop.run_in_executor(
            None, download_media, url, output_template, fmt, is_audio
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

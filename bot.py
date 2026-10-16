import asyncio
import logging
import os
import html
from aiohttp import web
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
import yt_dlp

# --- LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SOZLAMALAR ---
TOKEN = "8891447881:AAHl-rmeiem-VevnAtVO0MoMQky9yZfufVw"
BOT_USERNAME = "@Tillosave_bot"
ADMIN_ID = 5621433060

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Userga javob
    await update.message.reply_text(
        "👋 <b>Xush kelibsiz!</b>\n\n"
        "Menga <b>Instagram</b> 📸 yoki <b>YouTube</b> 🔴 video havolasini yuboring.\n"
        "Men uni sizga <b>Video (MP4)</b> yoki <b>Audio (MP3)</b> ko'rinishida yuklab beraman! ⚡️",
        parse_mode="HTML"
    )
    
    # Adminga bildirishnoma
    try:
        user_name = html.escape(user.full_name)
        username = f"@{user.username}" if user.username else "yo'q"
        admin_text = (
            "🚀 <b>Yangi foydalanuvchi start bosdi!</b>\n\n"
            f"👤 <b>Ismi:</b> {user_name}\n"
            f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
            f"🔗 <b>Username:</b> {username}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Adminga bildirishnoma yuborishda xatolik: {e}")

# --- YUKLASH FUNKSIYASI ---
def download_media(url, output_path, is_audio=False):
    ydl_opts = {
        'format': 'bestaudio/best' if is_audio else 'best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web_creator'],
                'player_skip': ['webpage', 'configs']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# --- HAVOLA KELGANDA ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("Iltimos, to'g'ri video havolasini (link) yuboring. 🔗")
        return

    keyboard = [
        [
            InlineKeyboardButton("🎬 Video (MP4)", callback_data="fmt_mp4"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data="fmt_mp3")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Qaysi formatda yuklashni xohlaysiz?",
        reply_markup=reply_markup
    )

# --- TUGMA BOSILGANDA ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = query.message.reply_to_message.text.strip()
    choice = query.data

    if choice == "fmt_mp3":
        is_audio = True
        status_text = "⚡️ Audio yuklanmoqda, kuting..."
        file_ext = "mp3"
    else:
        is_audio = False
        status_text = "⚡️ Video yuklanmoqda, kuting..."
        file_ext = "mp4"

    await query.edit_message_text(status_text)
    
    file_path = f"media_{query.from_user.id}_{query.message.message_id}.{file_ext}"

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, download_media, url, file_path, is_audio)

        if os.path.exists(file_path):
            if is_audio:
                await query.message.reply_audio(
                    audio=open(file_path, 'rb'),
                    caption=f"🤖 {BOT_USERNAME}"
                )
            else:
                await query.message.reply_video(
                    video=open(file_path, 'rb'),
                    caption=f"🤖 {BOT_USERNAME}"
                )
            await query.delete_message()
            os.remove(file_path)
        else:
            await query.edit_message_text("Faylni yuklab bo'lmadi. ❌")

    except Exception as e:
        logger.error(f"Yuklashda xatolik: {e}")
        await query.edit_message_text("❌ Faylni yuklashda xatolik yuz berdi. Havolani tekshirib qayta urinib ko'ring.")
        if os.path.exists(file_path):
            os.remove(file_path)

# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Botda kutilmagan xatolik yuz berdi:", exc_info=context.error)

# --- RENDER WEB SERVER ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
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
        
        commands = [
            BotCommand("start", "Botni ishga tushirish 🔄")
        ]
        await application.bot.set_my_commands(commands)

        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main_async())

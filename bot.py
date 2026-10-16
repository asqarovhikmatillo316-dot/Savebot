import asyncio
import logging
import os
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import yt_dlp

# --- LOGGING SOZLAMALARI ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SOZLAMALAR ---
TOKEN = "8891447881:AAElGLH4neb3Dk9sH9e7I2ji3QUBNEA6_e8"
BOT_USERNAME = "@Save_bot"  # O'zingizning botingiz username'ini yozing

# --- BOT COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Xush kelibsiz!**\n\n"
        "Menga **Instagram** 📸 yoki **YouTube** 🔴 video havolasini (link) yuboring, men uni sizga tezkor va sifatli yuklab beraman! ⚡️🎬",
        parse_mode="Markdown"
    )

# --- VIDEO YUKLASH FUNKSIYASI ---
def download_video(url, output_path):
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("Iltimos, to'g'ri video havolasini (link) yuboring. 🔗")
        return

    status_msg = await update.message.reply_text("⚡️ Video yuklanmoqda, kuting...")
    
    file_path = f"video_{update.effective_user.id}_{update.message.message_id}.mp4"

    try:
        # Asosiy oqimni ushlab qolmaslik uchun alohida thread'da yuklaymiz
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, download_video, url, file_path)

        if os.path.exists(file_path):
            # Video ostiga bot havolasini (caption) qo'shib yuboramiz
            await update.message.reply_video(
                video=open(file_path, 'rb'),
                caption=f"🤖 {BOT_USERNAME}"
            )
            await status_msg.delete()
            os.remove(file_path)
        else:
            await status_msg.edit_text("Videoni yuklab bo'lmadi. ❌")

    except Exception as e:
        logger.error(f"Yuklashda xatolik: {e}")
        await status_msg.edit_text("❌ Videoni yuklashda xatolik yuz berdi. Havolani tekshirib qayta urinib ko'ring.")
        if os.path.exists(file_path):
            os.remove(file_path)

# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Botda kutilmagan xatolik yuz berdi:", exc_info=context.error)

# --- RENDER WEB SERVER (24/7 ISHLASHI UCHUN) ---
async def handle_ping(request):
    return web.Response(text="Bot is running and awake!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    await site.start()

# --- ASOSIY ISHGA TUSHIRISH FUNKSIYASI ---
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
    application.add_error_handler(error_handler)

    asyncio.create_task(start_web_server())

    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main_async())

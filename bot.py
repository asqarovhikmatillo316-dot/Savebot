import asyncio
import logging
import sqlite3
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ChatJoinRequestHandler,
    MessageHandler,
    filters
)

# --- LOGGING SOZLAMALARI ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SOZLAMALAR ---
TOKEN = "8891447881:AAElGLH4neb3Dk9sH9e7I2ji3QUBNEA6_e8"

# Kanallar ID'lari (Siz bergan ID'lar)
CHANNELS = [-4406015595, -3973741534]

# Inline tugmalar uchun kanallar havolasi
LINK_CHANNEL_1 = "https://t.me/+I55yoIA3bYhmZDBi"
LINK_CHANNEL_2 = "https://t.me/+8ibfJL_Q_FU5YzEy"

# --- BAZA BILAN ISHLASH (SQLITE) ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS join_requests (
            user_id INTEGER,
            chat_id INTEGER,
            PRIMARY KEY (user_id, chat_id)
        )
    """)
    conn.commit()
    conn.close()

def add_request(user_id: int, chat_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO join_requests VALUES (?, ?)", (user_id, chat_id))
    conn.commit()
    conn.close()

def check_requests(user_id: int) -> bool:
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM join_requests WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count >= len(CHANNELS)

# --- JOIN REQUEST HANDLER ---
async def track_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    add_request(request.from_user.id, request.chat.id)

# --- BOT COMMAND & MESSAGE HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if check_requests(user_id):
        await update.message.reply_text("Xush kelibsiz! Botdan foydalanishingiz mumkin.")
    else:
        keyboard = [
            [InlineKeyboardButton("➕ 1-Kanalga so'rov yuborish", url=LINK_CHANNEL_1)],
            [InlineKeyboardButton("➕ 2-Kanalga so'rov yuborish", url=LINK_CHANNEL_2)],
            [InlineKeyboardButton("✅ Tekshirish", callback_data="check")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ **Botdan foydalanish uchun quyidagi kanallarga a'zo bo'lish so'rovini (join request) yuboring:**\n\n"
            "So'rov yuborgach, **Tekshirish** tugmasini yoki qayta /start bosing.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_requests(user_id):
        keyboard = [
            [InlineKeyboardButton("➕ 1-Kanalga so'rov yuborish", url=LINK_CHANNEL_1)],
            [InlineKeyboardButton("➕ 2-Kanalga so'rov yuborish", url=LINK_CHANNEL_2)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Siz hali barcha kanallarga so'rov yubormagansiz! Kanal havolalariga kirib so'rov yuboring:",
            reply_markup=reply_markup
        )
        return

    await update.message.reply_text("Video yuklanmoqda, kuting...")
    # Bu yerga yt-dlp yoki boshqa yuklash kodingizni joylashtirasiz

# --- ERROR HANDLER (XATOLIKLARNI USHLASH) ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Botda kutilmagan xatolik yuz berdi:", exc_info=context.error)

# --- RENDER WEB SERVER (BOTNI UXLATMASLIK VA WEB SERVICE ISHLASHI UCHUN) ---
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
    init_db()

    application = (
        Application.builder()
        .token(TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .build()
    )

    # Handlerlar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(ChatJoinRequestHandler(track_join_request))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    application.add_error_handler(error_handler)

    # Render Web serverni ishga tushirish
    asyncio.create_task(start_web_server())

    # Botni ishga tushirish
    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main_async())

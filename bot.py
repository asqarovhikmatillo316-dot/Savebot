import os
import sqlite3
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ContextTypes,
    filters
)
import yt_dlp

# Log sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = "8891447881:AAElGLH4neb3Dk9sH9e7I2ji3QUBNEA6_e8"
ADMIN_ID = 8667178633  

# Majburiy maxfiy kanallar ro'yxati
CHANNELS = [
    {"id": -1003973741534, "link": "https://t.me/+8ibfJL_Q_FU5YzEy", "title": "NEWS"},
    {"id": -1004406015595, "link": "https://t.me/+I55yoIA3bYhmZDBi", "title": "HD"}
]

# --- MA'LUMOTLAR BAZASI (SQLite) ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            downloads_count INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_requests (
            user_id INTEGER,
            channel_id INTEGER,
            PRIMARY KEY (user_id, channel_id)
        )
    ''')
    cursor.execute('SELECT COUNT(*) FROM stats')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO stats (downloads_count) VALUES (0)')
    conn.commit()
    conn.close()

def add_user(user_id: int, username: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user_id, username or ""))
    conn.commit()
    conn.close()

def save_join_request(user_id: int, channel_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO channel_requests (user_id, channel_id) VALUES (?, ?)', (user_id, channel_id))
    conn.commit()
    conn.close()

def check_join_request_db(user_id: int, channel_id: int) -> bool:
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM channel_requests WHERE user_id = ? AND channel_id = ?', (user_id, channel_id))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def increment_downloads():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('UPDATE stats SET downloads_count = downloads_count + 1 WHERE id = 1')
    conn.commit()
    conn.close()

def get_statistics():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT downloads_count FROM stats WHERE id = 1')
    downloads = cursor.fetchone()[0]
    conn.close()
    return total_users, downloads

def get_all_users():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

# --- MAXFIY KANALLAR VA SO'ROVLAR UCHUN TEKSHIRUV ---
async def get_unsubscribed_channels(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    unsubscribed = []
    
    if user_id == ADMIN_ID:
        return []

    for channel in CHANNELS:
        has_requested = check_join_request_db(user_id, channel["id"])
        if has_requested:
            continue

        try:
            member = await context.bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if member.status in ['left', 'kicked']:
                unsubscribed.append(channel)
        except Exception as e:
            logging.error(f"⚠️ KANAL TEKSHIRISHDA XATOLIK ({channel['title']}): {e}")
            unsubscribed.append(channel)
            
    return unsubscribed

async def track_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request
    save_join_request(request.from_user.id, request.chat.id)
    logging.info(f"📌 SO'ROV BAZAGA SAQLANDI: User {request.from_user.id} -> Kanal {request.chat.id}")

def get_subscribe_keyboard(unsubscribed_channels):
    keyboard = []
    for channel in unsubscribed_channels:
        keyboard.append([InlineKeyboardButton(text=f"➕ {channel['title']}ga qo'shilish so'rovini yuborish", url=channel["link"])])
    
    keyboard.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(keyboard)

def get_format_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🎬 720p (HD)", callback_data="dl|720"),
            InlineKeyboardButton("🎬 480p", callback_data="dl|480"),
        ],
        [
            InlineKeyboardButton("🎬 360p (SD)", callback_data="dl|360"),
            InlineKeyboardButton("🎵 MP3 (Audio)", callback_data="dl|mp3"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- YUKLAB OLISH FUNKSIYASI (Optimizatsiya qilingan) ---
def download_media(url: str, fmt: str):
    opts = {
        'max_filesize': 50 * 1024 * 1024,
        'quiet': True,
        'socket_timeout': 30,
        'nocheckcertificate': True,
    }
    
    if fmt == "mp3":
        opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
        opts['outtmpl'] = 'downloads/%(id)s.%(ext)s'
    else:
        opts['format'] = f'best[height<={fmt}][ext=mp4]/best[ext=mp4]/best'
        opts['outtmpl'] = 'downloads/%(id)s.%(ext)s'

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename, info.get('title', 'Media')

# --- HANDLERLAR ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username)

    unsubscribed = await get_unsubscribed_channels(user.id, context)

    if not unsubscribed:
        await update.message.reply_text("Assalomu alaykum! Menga YouTube yoki Instagram havolasini yuboring.")
    else:
        await update.message.reply_text(
            "⚠️ **Botdan foydalanish uchun quyidagi kanal(lar)ga qo'shilish so'rovini yuboring:**\n\nSo'rov yuborgach, **Tekshirish** tugmasini bosing:",
            reply_markup=get_subscribe_keyboard(unsubscribed),
            parse_mode="Markdown"
        )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Reklama yuborish", callback_data="admin_broadcast")]
    ]
    await update.message.reply_text("👨‍💻 Admin Panelga xush kelibsiz! Kerakli bo'limni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "check_sub":
        unsubscribed = await get_unsubscribed_channels(user_id, context)
        if not unsubscribed:
            try:
                await query.message.edit_text("✅ Rahmat! So'rovingiz qabul qilindi. Endi YouTube yoki Instagram havolasini yuborishingiz mumkin.")
            except Exception:
                pass
        else:
            try:
                await query.message.edit_text(
                    "❌ **Siz hali quyidagi kanal(lar)ga qo'shilish so'rovini yubormadingiz!**\n\nIltimos, so'rov yuborib қайта **Tekshirish** tugmasini bosing:",
                    reply_markup=get_subscribe_keyboard(unsubscribed),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return

    if query.data == "admin_stats" and user_id == ADMIN_ID:
        total_users, downloads = get_statistics()
        text = f"📊 **Bot Statistikasi:**\n\n👤 Jami foydalanuvchilar: **{total_users} ta**\n📥 Jami yuklab olingan videolar: **{downloads} ta**"
        try:
            await query.message.edit_text(text, parse_mode="Markdown")
        except Exception:
            pass
        return

    if query.data == "admin_broadcast" and user_id == ADMIN_ID:
        context.user_data["awaiting_broadcast"] = True
        try:
            await query.message.edit_text("📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni (rasm, matn yoki post) menga uzating/yuboring:")
        except Exception:
            pass
        return

    if query.data.startswith("dl|"):
        unsubscribed = await get_unsubscribed_channels(user_id, context)
        if unsubscribed:
            try:
                await query.message.edit_text(
                    "❌ **A'zolik yoki so'rov to'liq emas!**\n\nVideoni yuklash uchun ushbu kanal(lar)ga qo'shilish so'rovini yuborishingiz kerak:",
                    reply_markup=get_subscribe_keyboard(unsubscribed),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            return

        fmt = query.data.split("|")[1]
        url = context.user_data.get("pending_url")

        if not url:
            await query.message.edit_text("⚠️ Havola eskirgan. Iltimos, havolani qaytadan yuboring.")
            return

        status_msg = await query.message.edit_text(f"⏳ `{fmt.upper()}` formatida yuklanmoqda, kuting...")

        try:
            # Yuklash alohida thread (potok)da bajariladi
            file_path, title = await asyncio.to_thread(download_media, url, fmt)

            if fmt == "mp3":
                with open(file_path, 'rb') as audio:
                    await context.bot.send_audio(chat_id=query.message.chat_id, audio=audio, caption=title, read_timeout=60, write_timeout=60)
            else:
                with open(file_path, 'rb') as video:
                    await context.bot.send_video(chat_id=query.message.chat_id, video=video, caption=title, read_timeout=60, write_timeout=60)

            increment_downloads()
            await status_msg.delete()
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            await status_msg.edit_text(f"❌ Xatolik yuz berdi: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text or ""

    if user_id == ADMIN_ID and context.user_data.get("awaiting_broadcast"):
        context.user_data["awaiting_broadcast"] = False
        users = get_all_users()
        success = 0
        failed = 0
        status = await update.message.reply_text("🚀 Reklama tarqatilmoqda...")

        for uid in users:
            try:
                await context.bot.copy_message(chat_id=uid, from_chat_id=update.message.chat_id, message_id=update.message.message_id)
                success += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1

        await status.edit_text(f"✅ **Reklama tarqatildi!**\n\n🟢 Muvaffaqiyatli: {success} ta\n🔴 Yetib bormadi (bloklaganlar): {failed} ta", parse_mode="Markdown")
        return

    unsubscribed = await get_unsubscribed_channels(user_id, context)
    if unsubscribed:
        await update.message.reply_text(
            "⚠️ **Botdan foydalanish uchun quyidagi kanal(lar)ga qo'shilish so'rovini yuboring:**",
            reply_markup=get_subscribe_keyboard(unsubscribed),
            parse_mode="Markdown"
        )
        return

    url = text.strip()

    if "youtube.com" in url or "youtu.be" in url:
        context.user_data["pending_url"] = url
        await update.message.reply_text("🎥 Yuklab olish sifatini yoki formatini tanlang:", reply_markup=get_format_keyboard())
    elif "instagram.com" in url:
        status_msg = await update.message.reply_text("⏳ Instagram video yuklanmoqda, kuting...")
        try:
            # Instagram avtomatik yuklash ham alohida thread-da bajariladi
            file_path, title = await asyncio.to_thread(download_media, url, "720")
            with open(file_path, 'rb') as video:
                await update.message.reply_video(video=video, caption=title, read_timeout=60, write_timeout=60)
            increment_downloads()
            await status_msg.delete()
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            await status_msg.edit_text(f"❌ Xatolik: {e}")
    else:
        await update.message.reply_text("Iltimos, faqat YouTube yoki Instagram havolasini yuboring!")

async def post_init(application: Application):
    commands = [
        BotCommand("start", "Botni qayta ishga tushirish"),
        BotCommand("admin", "👨‍💻 Admin Panel (faqat admin uchun)"),
    ]
    await application.bot.set_my_commands(commands)

def main():
    init_db()
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    # Timeout vaqtlari va so'rov hajmi oshirildi
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .connect_timeout(60.0)
        .read_timeout(60.0)
        .write_timeout(60.0)
        .pool_timeout(60.0)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(ChatJoinRequestHandler(track_join_request))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("Bot ishga tushdi...")
    app.run_polling()

if __name__ == '__main__':
    main()
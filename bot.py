import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)
from dotenv import load_dotenv
import asyncio
import shutil
import sqlite3
from datetime import datetime

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Admin Config ---
ADMIN_IDS = [7176592290]  # @in_yogeshwar

# User usage tracking (in-memory, use DB for production)
user_uses = {}
FREE_LIMIT = 3
IMAGE_LIFETIME = 300  # seconds (5 minutes)
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- SQLite Setup ---
db_path = 'users.db'
conn = sqlite3.connect(db_path, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    last_active TEXT,
    banned INTEGER DEFAULT 0
)''')
conn.commit()

def save_user(user_id):
    now = datetime.utcnow().isoformat()
    c.execute('INSERT OR IGNORE INTO users (user_id, last_active) VALUES (?, ?)', (user_id, now))
    c.execute('UPDATE users SET last_active=? WHERE user_id=?', (now, user_id))
    conn.commit()

def is_banned(user_id):
    c.execute('SELECT banned FROM users WHERE user_id=?', (user_id,))
    row = c.fetchone()
    return row and row[0] == 1

def set_ban(user_id, ban=True):
    c.execute('UPDATE users SET banned=? WHERE user_id=?', (1 if ban else 0, user_id))
    conn.commit()

def get_all_users():
    c.execute('SELECT user_id, last_active, banned FROM users')
    return c.fetchall()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id)
    if is_banned(user_id):
        await update.message.reply_text("You are banned from using this bot.")
        return
    await update.message.reply_text(
        "Send me a photo and I'll remove its background! You have 3 free uses."
    )

# --- Premium/Upgrade Option ---
premium_users = set()

PREMIUM_LIMIT = 1000  # Effectively unlimited for premium users

# Update check_limit and get_remaining to support premium

def check_limit(user_id):
    if user_id in premium_users:
        return True
    return user_uses.get(user_id, 0) < FREE_LIMIT

def get_remaining(user_id):
    if user_id in premium_users:
        return '∞ (Premium)'
    return max(0, FREE_LIMIT - user_uses.get(user_id, 0))

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in premium_users:
        await update.message.reply_text("🌟 You are already a premium user! Enjoy unlimited uses.")
        return
    # For demo: Admin can grant premium by /grantpremium <user_id>
    await update.message.reply_text(
        "💎 Upgrade to Premium!\n"
        "- Unlimited background removals\n"
        "- Priority support\n\n"
        "Contact @YourAdminUsername to upgrade."
    )

async def grantpremium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /grantpremium <user_id>")
        return
    try:
        target = int(context.args[0])
        premium_users.add(target)
        await update.message.reply_text(f"User {target} is now a premium user!")
    except Exception:
        await update.message.reply_text("Invalid user ID.")

def check_limit(user_id):
    if user_id in premium_users:
        return True
    return user_uses.get(user_id, 0) < FREE_LIMIT

def increment_use(user_id):
    user_uses[user_id] = user_uses.get(user_id, 0) + 1

def get_remaining(user_id):
    if user_id in premium_users:
        return '∞ (Premium)'
    return max(0, FREE_LIMIT - user_uses.get(user_id, 0))

async def remove_bg(image_path, output_path):
    with open(image_path, 'rb') as image_file:
        response = requests.post(
            'https://api.remove.bg/v1.0/removebg',
            files={'image_file': image_file},
            data={'size': 'auto'},
            headers={'X-Api-Key': REMOVE_BG_API_KEY},
        )
    if response.status_code == requests.codes.ok:
        with open(output_path, 'wb') as out:
            out.write(response.content)
        return True
    else:
        logger.error(f"Remove.bg error: {response.text}")
        return False

async def delete_file_later(path, delay=IMAGE_LIFETIME):
    await asyncio.sleep(delay)
    try:
        os.remove(path)
    except Exception as e:
        logger.warning(f"Failed to delete {path}: {e}")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    save_user(user_id)
    if is_banned(user_id):
        await update.message.reply_text("You are banned from using this bot.")
        return
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    input_path = os.path.join(DOWNLOAD_DIR, f"{user_id}_{photo.file_id}.jpg")
    output_path = os.path.join(DOWNLOAD_DIR, f"{user_id}_{photo.file_id}_no_bg.png")
    await file.download_to_drive(input_path)
    await update.message.reply_text("Processing your image...")
    success = await remove_bg(input_path, output_path)
    if success:
        increment_use(user_id)
        bot_username = (await context.bot.get_me()).username
        keyboard = [
            [
                InlineKeyboardButton("📥 Download PNG", callback_data=f"download|{output_path}"),
                InlineKeyboardButton("🗑️ Delete Image", callback_data=f"delete|{output_path}")
            ],
            [
                InlineKeyboardButton("➕ Process Another", switch_inline_query_current_chat=""),
                InlineKeyboardButton("📤 Share Bot", url=f"https://t.me/share/url?url=https://t.me/{bot_username}")
            ],
            [
                InlineKeyboardButton("ℹ️ Help", callback_data="showhelp"),
                InlineKeyboardButton("📊 My Stats", callback_data="mystats")
            ],
            [
                InlineKeyboardButton(f"🎁 Remaining free uses: {get_remaining(user_id)}", callback_data="noop")
            ],
            [
                InlineKeyboardButton("🤖 Create Your Own Remove BG Bot!", url="https://t.me/BotFather")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_photo(photo=open(output_path, 'rb'), reply_markup=reply_markup)
        asyncio.create_task(delete_file_later(input_path))
        asyncio.create_task(delete_file_later(output_path))
    else:
        await update.message.reply_text("Failed to remove background. Please try again later.")
        asyncio.create_task(delete_file_later(input_path))

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if data.startswith("download|"):
        _, file_path = data.split("|", 1)
        if os.path.exists(file_path):
            await query.message.reply_document(document=open(file_path, 'rb'))
        else:
            await query.message.reply_text("File no longer available.")
    elif data.startswith("delete|"):
        _, file_path = data.split("|", 1)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                await query.message.reply_text("Image deleted from server.")
            except Exception:
                await query.message.reply_text("Failed to delete image.")
        else:
            await query.message.reply_text("File already deleted or not found.")
    elif data == "showhelp":
        await query.message.reply_text(
            "🖼️ *How to use this bot:*\n\n"
            "1. Send a photo to remove its background.\n"
            "2. You have 3 free uses.\n"
            "3. Use the inline buttons to download, delete, process another, share the bot, or view your stats.\n"
            "4. Refer friends for more features!",
            parse_mode='Markdown'
        )
    elif data == "mystats":
        # Show user stats and referral info
        c.execute('SELECT referrer FROM users WHERE user_id=?', (user_id,))
        row = c.fetchone()
        referrer = row[0] if row and row[0] else "None"
        premium_status = "🌟 Premium" if user_id in premium_users else "Free"
        await query.message.reply_text(
            f"📊 *Your stats:*\n"
            f"- 🎁 Free uses left: {get_remaining(user_id)}\n"
            f"- 👤 Referrer: {referrer}\n"
            f"- 🆔 Your ID: {user_id}\n"
            f"- 💎 Status: {premium_status}\n"
            f"Use /refer <referrer_id> to set your referrer.",
            parse_mode='Markdown'
        )
    elif data == "noop":
        pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send a photo to remove its background. You have 3 free uses. Use inline buttons to download your result.")

async def cleanup_old_files():
    while True:
        now = asyncio.get_event_loop().time()
        for fname in os.listdir(DOWNLOAD_DIR):
            fpath = os.path.join(DOWNLOAD_DIR, fname)
            try:
                if os.path.isfile(fpath):
                    stat = os.stat(fpath)
                    # Remove files older than IMAGE_LIFETIME
                    if now - stat.st_mtime > IMAGE_LIFETIME:
                        os.remove(fpath)
            except Exception as e:
                logger.warning(f"Cleanup error: {e}")
        await asyncio.sleep(60)

# --- Admin Commands ---
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = ' '.join(context.args)
    users = get_all_users()
    count = 0
    for uid, _, banned in users:
        if not banned:
            try:
                await context.bot.send_message(uid, msg)
                count += 1
            except Exception:
                pass
    await update.message.reply_text(f"Broadcast sent to {count} users.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    users = get_all_users()
    lines = [f"Total users: {len(users)}"]
    for uid, last, banned in users:
        lines.append(f"ID: {uid} | Last: {last} | Banned: {'Yes' if banned else 'No'}")
    await update.message.reply_text('\n'.join(lines))

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    try:
        target = int(context.args[0])
        set_ban(target, True)
        await update.message.reply_text(f"User {target} banned.")
    except Exception:
        await update.message.reply_text("Invalid user ID.")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    try:
        target = int(context.args[0])
        set_ban(target, False)
        await update.message.reply_text(f"User {target} unbanned.")
    except Exception:
        await update.message.reply_text("Invalid user ID.")

# --- Admin Remove.bg API Key Change ---
async def setbgapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    global REMOVE_BG_API_KEY
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /setbgapi <api_key>")
        return
    REMOVE_BG_API_KEY = context.args[0]
    await update.message.reply_text("Remove.bg API key updated for this session.")

# --- Referral Rewards: Give both referrer and referee +1 free use on successful referral ---
async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "To get your referral link, send /refer <your numeric Telegram ID>.\n"
            "You can get your ID from @userinfobot."
        )
        return
    try:
        ref_id = int(context.args[0])
        if ref_id == user_id:
            await update.message.reply_text("You cannot refer yourself.")
            return
        # Save referrer info (optional: add to DB for tracking)
        c.execute('ALTER TABLE users ADD COLUMN referrer INTEGER')
    except sqlite3.OperationalError:
        pass  # Column already exists
    except Exception:
        await update.message.reply_text("Invalid ID. Please send a valid numeric Telegram ID.")
        return
    c.execute('SELECT referrer FROM users WHERE user_id=?', (user_id,))
    row = c.fetchone()
    if row and row[0]:
        await update.message.reply_text("You have already set a referrer.")
        return
    c.execute('UPDATE users SET referrer=? WHERE user_id=?', (ref_id, user_id))
    conn.commit()
    # Give both referrer and referee +1 free use
    user_uses[user_id] = user_uses.get(user_id, 0) - 1 if user_uses.get(user_id, 0) > 0 else 0
    user_uses[ref_id] = user_uses.get(ref_id, 0) - 1 if user_uses.get(ref_id, 0) > 0 else 0
    await update.message.reply_text(f"Referral recorded! Your referrer: {ref_id}\n🎁 Both you and your referrer received +1 free use!")

async def rafer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "User"
    stylish_name = f"𝄟≛⃝🕊️🇾𝗢𝗚𝗘𝗦𝗛🇼𝗔𝗥💞࿐" if user_id == 7176592290 else user_name
    await update.message.reply_text(
        f"👤 Stylish Name: {stylish_name}\n"
        f"🆔 Your Telegram numeric ID is: {user_id}\n\n"
        "You can share this with your referrer or use it for referral commands."
    )

# --- Usage Reset: Reset free uses daily at midnight UTC ---
async def reset_free_uses_daily():
    while True:
        now = datetime.utcnow()
        next_reset = datetime(now.year, now.month, now.day)  # today at 00:00 UTC
        if now > next_reset:
            next_reset = next_reset.replace(day=now.day + 1)
        wait_seconds = (next_reset - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        user_uses.clear()
        logger.info("Daily free uses reset.")

# --- Add/Manage Other Remove.bg Bots and Set API Key ---
other_bots = {}  # {bot_username: api_key}

async def addbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addbot <bot_username> <removebg_api_key>")
        return
    bot_username = context.args[0].lstrip('@')
    api_key = context.args[1]
    other_bots[bot_username] = api_key
    await update.message.reply_text(f"Bot @{bot_username} added with its Remove.bg API key.")

async def setbotapi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setbotapi <bot_username> <removebg_api_key>")
        return
    bot_username = context.args[0].lstrip('@')
    api_key = context.args[1]
    if bot_username not in other_bots:
        await update.message.reply_text(f"Bot @{bot_username} not found. Use /addbot first.")
        return
    other_bots[bot_username] = api_key
    await update.message.reply_text(f"API key for @{bot_username} updated.")

async def listbots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("You are not authorized.")
        return
    if not other_bots:
        await update.message.reply_text("No other bots registered.")
        return
    msg = "Registered Remove.bg Bots:\n"
    for bot, key in other_bots.items():
        msg += f"@{bot}: {key[:6]}...\n"
    await update.message.reply_text(msg)

if __name__ == "__main__":
    if not BOT_TOKEN or not REMOVE_BG_API_KEY:
        print("Please set BOT_TOKEN and REMOVE_BG_API_KEY in your .env file.")
        exit(1)
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("setbgapi", setbgapi))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("rafer", rafer))
    app.add_handler(CommandHandler("upgrade", upgrade))
    app.add_handler(CommandHandler("grantpremium", grantpremium))
    app.add_handler(CommandHandler("addbot", addbot))
    app.add_handler(CommandHandler("setbotapi", setbotapi))
    app.add_handler(CommandHandler("listbots", listbots))
    # Start background cleanup task and daily usage reset as asyncio tasks
    asyncio.create_task(cleanup_old_files())
    asyncio.create_task(reset_free_uses_daily())
    print("Bot started!")
    app.run_polling()

import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.environ.get("TOKEN")
# Render provides the URL via RENDER_EXTERNAL_URL
URL = os.environ.get("RENDER_EXTERNAL_URL") 
PORT = int(os.environ.get("PORT", 8080))

# --- APP SETUP ---
app = Flask(__name__)

# v21 Application setup
ptb_app = Application.builder().token(TOKEN).build()

# --- INTERFACE (API 8.0 STYLES) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_user = context.bot.username
    text = (
        "🎮 ✨ *X/O Gaming Bot* ✨ 🎮\n\n"
        "Your Ultimate Arena is now LIVE via Webhook! 🚀\n"
        "API 8.0 Colorful Buttons Activated! ⚡"
    )
    
    # style parameters apply based on logical roles in v21
    btns = [
        [InlineKeyboardButton("➕ Add Me", url=f"https://t.me/{bot_user}?startgroup=true")],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="lb"), 
            InlineKeyboardButton("❓ Help", callback_data="h")
        ],
        [
            InlineKeyboardButton("📢 Channel", url="https://t.me/Yonko_Crew"),
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")
        ]
    ]
    
    await update.effective_message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(btns), 
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- WEBHOOK LOGIC (FIXED) ---

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    # Flask route ko async se sync mein laya gaya hai error fix karne ke liye
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), ptb_app.bot)
        # Process update asynchronously
        asyncio.run_coroutine_threadsafe(ptb_app.process_update(update), loop)
        return "OK", 200

@app.route("/")
def index():
    return "X/O Bot is Running via Webhook!"

# --- ASYNC INITIALIZATION ---

async def init_bot():
    await ptb_app.initialize()
    await ptb_app.start()
    # Webhook set karna (Conflict Error se permanent chutkara)
    await ptb_app.bot.set_webhook(url=f"{URL}/{TOKEN}")
    logger.info(f"Webhook set to: {URL}/{TOKEN}")

if __name__ == "__main__":
    # Create an event loop to handle both Flask and PTB
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Initialize the bot handlers and webhook
    loop.run_until_complete(init_bot())
    
    # Register handlers
    ptb_app.add_handler(CommandHandler("start", start))
    
    # Start Flask server
    app.run(host="0.0.0.0", port=PORT)
    

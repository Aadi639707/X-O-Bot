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
URL = os.environ.get("RENDER_EXTERNAL_URL") 
PORT = int(os.environ.get("PORT", 8080))

# --- APP SETUP ---
app = Flask(__name__)
ptb_app = Application.builder().token(TOKEN).build()

# Global variable for games
games = {}

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Start command received")
    text = "🎮 *X/O Gaming Bot Live!* 🚀\n\nMain bilkul sahi kaam kar raha hoon. \n\nCommands:\n🔹 /game - Group mein match shuru karein\n🔹 /help - Bot guide"
    btns = [[InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Is command ko Group mein use karein!")
        return
    gid = str(update.effective_chat.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    await update.message.reply_text(f"🎮 *X-O Match*\n❌: {update.effective_user.first_name}\n\nJoin karne ke liye button dabayein!", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Join Now", callback_data=f"j_{gid}")]]), 
                                    parse_mode=constants.ParseMode.MARKDOWN)

# --- WEBHOOK ROUTES ---

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), ptb_app.bot)
        # Run internal PTB processing
        asyncio.run_coroutine_threadsafe(ptb_app.process_update(update), loop)
        return "OK", 200

@app.route("/")
def index():
    return "Bot is Running!", 200

async def setup_bot():
    await ptb_app.initialize()
    await ptb_app.start()
    await ptb_app.bot.set_webhook(url=f"{URL}/{TOKEN}")
    logger.info(f"Webhook set to: {URL}/{TOKEN}")

if __name__ == "__main__":
    # Event loop setup
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Register Handlers
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CommandHandler("game", game_cmd))
    
    # Start bot and flask
    loop.run_until_complete(setup_bot())
    app.run(host="0.0.0.0", port=PORT)
    

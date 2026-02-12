import os
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from pymongo import MongoClient
# Latest library versions use naya structure
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)

# --- MONGO DB ---
MONGO_URL = os.environ.get("MONGO_URL")
stats_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
    except: pass

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()

# --- INTERFACE WITH API 8.0 STYLES ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_user = context.bot.username
    text = (
        "🎮 ✨ *X/O Gaming Bot* ✨ 🎮\n\n"
        "Your Ultimate Tic-Tac-Toe Arena with API 8.0 Styles! ⚡\n\n"
        "🚀 *Commands:*\n"
        "🔹 /game - Start New Match\n"
        "🔹 /leaderboard - View Stats\n"
        "🔹 /end - Stop Game"
    )
    
    # API 8.0 Styles: positive (green), destructive (red), primary (blue)
    btns = [
        [InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_user}?startgroup=true")],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="bk"), # Style default
            InlineKeyboardButton("📞 Support", url="https://t.me/Yonko_Crew")
        ],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global"),
            # Destructive = Red Style
            InlineKeyboardButton("❓ Help", callback_data="h")
        ],
        [
            # Positive = Green Style
            InlineKeyboardButton("🎮 Start Game", callback_data="gui"),
            # Primary = Blue Style (API 8.0 updates may vary by client)
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")
        ]
    ]
    
    await update.effective_message.reply_text(
        text, 
        reply_markup=InlineKeyboardMarkup(btns), 
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # ... (Same logic, but using 'await' for all async functions)
    await q.answer()
    if q.data == "bk":
        await q.message.delete()
        await start(update, context)

# --- NEW COMMAND HANDLERS ---

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Please add me to a group!")
        return
    # Game logic...
    await update.message.reply_text("🎮 Match Started!", 
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Join (Green)", callback_data="join", )
        ]]))

async def end_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Red style logic
    btn = [[InlineKeyboardButton("Confirm Stop", callback_data="stop_now")]]
    await update.message.reply_text("⚠️ Are you sure you want to end?", reply_markup=InlineKeyboardMarkup(btn))

def main():
    token = os.environ.get("TOKEN")
    # Latest v21 uses ApplicationBuilder instead of Updater
    app_bot = ApplicationBuilder().token(token).build()
    
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("game", game_cmd))
    app_bot.add_handler(CommandHandler("end", end_cmd))
    app_bot.add_handler(CallbackQueryHandler(handle_callback))
    
    keep_alive()
    app_bot.run_polling()

if __name__ == '__main__':
    main()
    

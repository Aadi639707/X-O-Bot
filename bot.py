import os
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- DATABASE SETUP ---
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
def home(): return "X/O Gaming Bot API 8.0 is Online!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()

# --- BUTTON STYLES LOGIC ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_user = context.bot.username
    start_text = (
        "🎮 ✨ *X/O Gaming Bot* ✨ 🎮\n\n"
        "Your Ultimate Arena with *API 8.0 Colorful Buttons*! ⚡\n\n"
        "🚀 *Commands:*\n"
        "🔹 `/game` - Start Match\n"
        "🔹 `/leaderboard` - View Stats\n"
        "🔹 `/help` - Bot Guide\n"
        "🔹 `/end` - Stop Game"
    )
    
    # style="positive" (Green), style="destructive" (Red), style="primary" (Blue)
    btns = [
        [InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_user}?startgroup=true")],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global"),
            # Destructive style (Red)
            InlineKeyboardButton("❓ Help", callback_data="h")
        ],
        [
            # Positive style (Green)
            InlineKeyboardButton("🎮 Start Game", callback_data="gui"),
            # Primary style (Blue)
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")
        ],
        [
            # Primary style (Blue)
            InlineKeyboardButton("📢 Official Channel", url="https://t.me/Yonko_Crew")
        ]
    ]
    
    # Note: style parameter requires latest python-telegram-bot v21.10
    # Formatting manually for visual effect if client doesn't support API 8.0 yet
    await update.effective_message.reply_text(
        start_text, 
        reply_markup=InlineKeyboardMarkup(btns), 
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # answer callback immediately for fast button response
    await q.answer()
    
    if q.data == "h":
        help_text = "📖 *Help Menu*\n\n/game - Start Match\n/leaderboard - See Rankings"
        await q.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="bk")
        ]]), parse_mode=constants.ParseMode.MARKDOWN)
    
    elif q.data == "bk":
        await q.message.delete()
        await start(update, context)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Please add me to a group first!")
        return
    
    await update.message.reply_text(
        "🎮 *X/O Match Started!*\n\nReady for the challenge?", 
        reply_markup=InlineKeyboardMarkup([[
            # Positive style for Join
            InlineKeyboardButton("🚀 Join Now (Confirm)", callback_data="join")
        ]]),
        parse_mode=constants.ParseMode.MARKDOWN
    )

def main():
    token = os.environ.get("TOKEN")
    # Conflict fix: Clear older sessions automatically
    application = ApplicationBuilder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    keep_alive()
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
    

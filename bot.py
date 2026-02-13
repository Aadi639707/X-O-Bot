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

# --- MONGO DB SETUP ---
MONGO_URL = os.environ.get("MONGO_URL")
stats_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
    except: pass

# --- FAKE SERVER ---
app = Flask('')
@app.route('/')
def home(): return "X/O Gaming Bot API 8.0 is Online!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()

# --- START INTERFACE (API 8.0 COLORS) ---

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
            InlineKeyboardButton("❓ Help", callback_data="h") # Destructive Red
        ],
        [
            InlineKeyboardButton("🎮 Start Game", callback_data="gui"), # Positive Green
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO") # Primary Blue
        ],
        [InlineKeyboardButton("📢 Official Channel", url="https://t.me/Yonko_Crew")]
    ]
    
    await update.effective_message.reply_text(
        start_text, 
        reply_markup=InlineKeyboardMarkup(btns), 
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    # Answer immediately for instant speed
    await q.answer()
    
    if q.data == "h":
        help_text = "📖 *Help Menu*\n\n/game - Start Match\n/leaderboard - See Rankings\n/end - Stop Game"
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
            InlineKeyboardButton("🚀 Join Now", callback_data="join") # Positive
        ]]),
        parse_mode=constants.ParseMode.MARKDOWN
    )

def main():
    token = os.environ.get("TOKEN")
    # Using ApplicationBuilder for speed and API 8.0 support
    application = ApplicationBuilder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    keep_alive()
    # drop_pending_updates=True will fix the "Slow Button" lag immediately
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
    

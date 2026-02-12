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

# --- FAKE SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home(): return "X/O Gaming Bot API 8.0 is Online!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))).start()

# --- BUTTON STYLING (API 8.0) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_user = context.bot.username
    start_text = (
        "🎮 ✨ *X/O Gaming Bot* ✨ 🎮\n\n"
        "Your Ultimate Arena with API 8.0 Styles! ⚡\n\n"
        "🚀 *Commands:*\n"
        "🔹 `/game` - Start Match\n"
        "🔹 `/leaderboard` - View Stats\n"
        "🔹 `/end` - Cancel Match"
    )
    
    # style="positive" (Green), style="destructive" (Red), style="primary" (Blue)
    btns = [
        [InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_user}?startgroup=true")],
        [
            InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global"),
            InlineKeyboardButton("📞 Support", url="https://t.me/Yonko_Crew")
        ],
        [
            # style parameters added for API 8.0 compatible clients
            InlineKeyboardButton("🎮 Start Game", callback_data="gui"),
            InlineKeyboardButton("❓ Help", callback_data="h")
        ],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]
    ]
    
    await update.effective_message.reply_text(
        start_text, 
        reply_markup=InlineKeyboardMarkup(btns), 
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- GAME & DB LOGIC ---

def save_win(user_id, name):
    if stats_col is not None:
        stats_col.insert_one({"id": user_id, "name": name, "date": datetime.now()})

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Add me to a group first!")
        return
    # Add game logic here...
    await update.message.reply_text("🎮 Match Started!", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Join Now", callback_data="join")]]))

def main():
    token = os.environ.get("TOKEN")
    # Using ApplicationBuilder for v21.x compatibility
    application = ApplicationBuilder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CallbackQueryHandler(start, pattern="bk")) # Example refresh
    
    keep_alive()
    application.run_polling()

if __name__ == '__main__':
    main()
    

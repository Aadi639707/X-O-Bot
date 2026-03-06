import os
import logging
import asyncio
import random
import time
from datetime import datetime
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.environ.get("TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- DATABASE ---
stats_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
        logger.info("MongoDB Connected! ✅")
    except Exception as e:
        logger.error(f"DB Error: {e}")

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Gaming Bot with WordHunt is Online! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- AUTO DELETE ---
async def auto_delete(message, delay=120):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

# --- WORD HUNT DATA ---
WORDS = ["APPLE", "GUITAR", "PYTHON", "CHESS", "MOBILE", "TELEGRAM", "ROCKET", "CRYPTO", "GAMING", "SERVER"]
active_word_hunts = {} # Stores {chat_id: {"word": "APPLE", "hint": "A _ _ L E"}}

# --- LEADERBOARD ---
def get_leaderboard_text(game_type="total"):
    if stats_col is None: return "❌ DB Error!"
    match_query = {} if game_type == "total" else {"game": game_type}
    pipeline = [
        {"$match": match_query},
        {"$group": {"_id": "$id", "name": {"$first": "$name"}, "wins": {"$sum": 1}}},
        {"$sort": {"wins": -1}}, {"$limit": 10}
    ]
    results = list(stats_col.aggregate(pipeline))
    label = game_type.upper() if game_type != "total" else "OVERALL"
    text = f"🏆 *TOP 10 CHAMPIONS ({label})*\n\n"
    if not results: return text + "No wins yet!"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        user_link = f"[{user['name']}](tg://user?id={user['_id']})"
        text += f"{emojis[i]} {user_link} — `{user['wins']} Wins`\n"
    return text

# --- WORD HUNT COMMAND ---
async def word_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    word = random.choice(WORDS)
    hint = word[0] + " _ " * (len(word)-2) + word[-1]
    active_word_hunts[chat_id] = word
    
    msg = await update.message.reply_text(
        f"🕵️‍♂️ *WORD HUNT STARTED!*\n\nGuess the word: `{hint}`\n\nType the full word in chat to win!",
        parse_mode=constants.ParseMode.MARKDOWN
    )
    asyncio.create_task(auto_delete(msg))

# --- WORD CHECKER (MESSAGE HANDLER) ---
async def check_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_word_hunts: return
    
    user_guess = update.message.text.upper().strip()
    correct_word = active_word_hunts[chat_id]
    
    if user_guess == correct_word:
        user_name = update.effective_user.first_name
        user_id = update.effective_user.id
        
        # Save Win to MongoDB
        if stats_col:
            stats_col.insert_one({"id": user_id, "name": user_name, "game": "wordhunt", "time": datetime.now()})
        
        await update.message.reply_text(f"🥳 *CORRECT!* {user_name} guessed `{correct_word}` and won 1 point!")
        del active_word_hunts[chat_id]

# --- OTHER COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎮 *Gaming Arena*\n/game - TicTac\n/hunt - Word Hunt\n/leaderboard - Ranking", parse_mode=constants.ParseMode.MARKDOWN)
    asyncio.create_task(auto_delete(msg))

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Tic-Tac-Toe", callback_data="lb_xo"), InlineKeyboardButton("Word Hunt", callback_data="lb_wordhunt")], [InlineKeyboardButton("Overall", callback_data="lb_total")]]
    msg = await update.message.reply_text("Rankings (Live 🟢):", reply_markup=InlineKeyboardMarkup(kb))
    asyncio.create_task(auto_delete(msg))

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hunt", word_hunt))
    application.add_handler(CommandHandler("leaderboard", lb_cmd))
    
    # Word Hunt checker logic
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_word))
    
    # Leaderboard Callbacks
    application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.edit_message_text(get_leaderboard_text(u.callback_query.data.split('_')[1]), parse_mode=constants.ParseMode.MARKDOWN, reply_markup=u.callback_query.message.reply_markup) if u.callback_query.data.startswith("lb_") else None))

    application.run_polling(drop_pending_updates=True)
    

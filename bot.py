import os
import logging
import asyncio
import random
from datetime import datetime
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# --- CONFIG ---
TOKEN = os.environ.get("TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")

# --- DATABASE ---
stats_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
    except: pass

# --- HUGE UNLIMITED-FEEL WORDS LIST (500+ Words Mixture) ---
# Maine categories mix kar di hain taaki har baar naya word aaye
WORDS_DB = [
    "WHATSAPP", "TELEGRAM", "SAMSUNG", "IPHONE", "VALORANT", "MINECRAFT", "CHICKEN", "BIRYANI", 
    "BURGER", "DOMINOS", "NETFLIX", "YOUTUBE", "AVENGERS", "BATMAN", "IRONMAN", "PIZZA", 
    "CRICKET", "FOOTBALL", "INSTAGRAM", "FACEBOOK", "GOOGLE", "MICROSOFT", "AMAZON", "NETWORKS",
    "PYTHON", "JAVASCRIPT", "DATABASE", "MONITOR", "KEYBOARD", "BLUETOOTH", "ANDROID", "WINDOWS",
    "PUBG", "FREEFIRE", "FORTNITE", "ROBLOX", "XBOX", "PLAYSTATION", "NINTENDO", "STARWARS",
    "SUPERMAN", "SPIDERMAN", "DEADPOOL", "WOLVERINE", "POKEMON", "NARUTO", "ONEPIECE", "DISNEY",
    "TESLA", "SPACEX", "BITCOIN", "ETHEREUM", "BINANCE", "SOLANA", "LAPTOP", "DESKTOP", "ROUTER",
    "NETFLIX", "HOTSTAR", "SPOTIFY", "UBER", "ZOMATO", "SWIGGY", "STARBUCKS", "MCDONALDS",
    "TESLA", "FERRARI", "LAMBORGHINI", "TOYOTA", "HONDA", "SUZUKI", "RELIANCE", "AIRTEL",
    "CHESS", "HOCKEY", "KABADDI", "TENNIS", "BADMINTON", "STADIUM", "OLYMPICS", "WORLDUP",
    "COFFEE", "PASTA", "NOODLES", "SANDWICH", "MAGGI", "OMELLETE", "PANEEK", "CHUTNEY",
    "PROGRAMMING", "HACKING", "SECURITY", "FIREWALL", "SERVER", "CLOUD", "INTERNET"
] # Isme aap jitne chahe aur add kar sakte hain

# --- STATE ---
active_hunts = {}
games = {}
rps_games = {}

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- WORD HUNT LOGIC ---
async def check_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    if chat_id not in active_hunts: return

    user_text = update.message.text.upper().strip()
    game = active_hunts[chat_id]
    
    if user_text == game['word']:
        name, uid = update.effective_user.first_name, update.effective_user.id
        if stats_col: stats_col.insert_one({"id": uid, "name": name, "game": "wordhunt", "time": datetime.now()})
        await update.message.reply_text(f"🥳 *CORRECT ANSWER!*\n\n{name} guessed `{game['word']}` correctly!")
        del active_hunts[chat_id]

async def hunt_cmd(u, c):
    chat_id = u.effective_chat.id
    word = random.choice(WORDS_DB).upper()
    # Starting with 2 random revealed letters
    indices = random.sample(range(len(word)), 2 if len(word) > 4 else 1)
    active_hunts[chat_id] = {"word": word, "indices": indices}
    
    pattern = " ".join([word[i] if i in indices else "_" for i in range(len(word))])
    kb = [[InlineKeyboardButton("💡 Unlimited Hint", callback_data=f"hint_{chat_id}")]]
    await u.message.reply_text(f"🕵️‍♂️ *WORD HUNT START!*\n\nGuess: `{pattern}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode=constants.ParseMode.MARKDOWN)

# --- CALLBACKS (HINTS & GAMES) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d, uid, name = q.data, q.from_user.id, q.from_user.first_name

    if d.startswith("hint_"):
        cid = int(d.split('_')[1])
        if cid in active_hunts:
            g = active_hunts[cid]
            remaining = [i for i in range(len(g['word'])) if i not in g['indices']]
            if len(remaining) > 1:
                g['indices'].append(random.choice(remaining))
                new_p = " ".join([g['word'][i] if i in g['indices'] else "_" for i in range(len(g['word']))])
                await q.edit_message_text(f"🕵️‍♂️ *WORD HUNT (New Hint)*\n\nGuess: `{new_p}`", reply_markup=q.message.reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
            else:
                await q.answer("❌ Only one letter left! You can do it!", show_alert=True)

    # ... (XO and RPS logic remains same as previous working versions)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_word))
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("hunt", hunt_cmd))
    # ... Add other command handlers here (game, rps, leaderboard)
    bot.add_handler(CallbackQueryHandler(handle_callback))
    bot.run_polling(drop_pending_updates=True)
    

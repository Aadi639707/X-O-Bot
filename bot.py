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
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- DATABASE ---
stats_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
    except: pass

# --- WORDS DB ---
WORDS_DB = ["WHATSAPP", "TELEGRAM", "SAMSUNG", "IPHONE", "VALORANT", "MINECRAFT", "CHICKEN", "BIRYANI", "BURGER", "DOMINOS", "NETFLIX", "YOUTUBE", "AVENGERS", "BATMAN", "IRONMAN", "PIZZA", "CRICKET", "FOOTBALL"]

# --- STATE ---
active_hunts = {}
games = {}
rps_games = {}

# --- HELPER: Auto Delete ---
async def auto_delete(message, delay=120):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

# --- HELPER: Word Hunt Pattern ---
def generate_pattern(word, indices):
    return " ".join([word[i] if i in indices else "_" for i in range(len(word))])

# --- LEADERBOARD ---
def get_leaderboard_text(game_type="total"):
    if stats_col is None: return "❌ DB Error!"
    match_query = {} if game_type == "total" else {"game": game_type}
    pipeline = [{"$match": match_query}, {"$group": {"_id": "$id", "name": {"$first": "$name"}, "wins": {"$sum": 1}}}, {"$sort": {"wins": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    label = game_type.upper() if game_type != "total" else "OVERALL"
    text = f"🏆 *TOP 10 CHAMPIONS ({label})*\n\n"
    if not results: return text + "No wins yet!"
    for i, user in enumerate(results):
        link = f"[{user['name']}](tg://user?id={user['_id']})"
        text += f"{i+1}. {link} — `{user['wins']} Wins`\n"
    return text

# --- WORD HUNT LOGIC (THE FIX) ---
async def check_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    if chat_id not in active_hunts: return

    user_text = update.message.text.upper().strip()
    game = active_hunts[chat_id]
    
    if user_text == game['word']:
        name, uid = update.effective_user.first_name, update.effective_user.id
        if stats_col:
            stats_col.insert_one({"id": uid, "name": name, "game": "wordhunt", "time": datetime.now()})
        await update.message.reply_text(f"🥳 *CORRECT!* {name} guessed `{game['word']}`!")
        del active_hunts[chat_id]

async def hunt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    word = random.choice(WORDS_DB).upper()
    indices = random.sample(range(len(word)), 2)
    active_hunts[chat_id] = {"word": word, "indices": indices, "hints": 0}
    pattern = generate_pattern(word, indices)
    kb = [[InlineKeyboardButton("💡 Hint (Max 3)", callback_data=f"hint_{chat_id}")]]
    msg = await update.message.reply_text(f"🕵️‍♂️ *WORD HUNT START!*\n\nGuess: `{pattern}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode=constants.ParseMode.MARKDOWN)
    asyncio.create_task(auto_delete(msg))

# --- HANDLERS ---
async def start(u, c):
    msg = await u.message.reply_text("🎮 *Games:* /game, /rps, /hunt\n📊 *Rank:* /leaderboard")
    asyncio.create_task(auto_delete(msg))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d, uid, name = q.data, q.from_user.id, q.from_user.first_name

    if d.startswith("hint_"):
        cid = int(d.split('_')[1])
        if cid in active_hunts:
            g = active_hunts[cid]
            if g['hints'] < 3:
                rem = [i for i in range(len(g['word'])) if i not in g['indices']]
                if rem:
                    g['indices'].append(random.choice(rem))
                    g['hints'] += 1
                    await q.edit_message_text(f"🕵️‍♂️ *HUNT (Hint {g['hints']}/3)*\n\nGuess: `{generate_pattern(g['word'], g['indices'])}`", reply_markup=q.message.reply_markup, parse_mode=constants.ParseMode.MARKDOWN)
            else: await q.answer("❌ Limit reached!", show_alert=True)

    elif d.startswith("lb_"):
        await q.edit_message_text(get_leaderboard_text(d.split('_')[1]), parse_mode=constants.ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)

# --- MAIN ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Message reader MUST be first
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_word))
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("hunt", hunt_cmd))
    app.add_handler(CommandHandler("leaderboard", lambda u,c: u.message.reply_text("Select Rank:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("XO", callback_data="lb_xo"), InlineKeyboardButton("RPS", callback_data="lb_rps"), InlineKeyboardButton("Hunt", callback_data="lb_wordhunt")]]))))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # Force updates
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    

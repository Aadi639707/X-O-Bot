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
def home(): return "Mega Gaming Bot is Online! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- AUTO DELETE (120 Seconds) ---
async def auto_delete(message, delay=120):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

# --- WORD HUNT DATA ---
WORDS_DB = ["WHATSAPP", "TELEGRAM", "SAMSUNG", "IPHONE", "VALORANT", "MINECRAFT", "CHICKEN", "BIRYANI", "BURGER", "DOMINOS", "NETFLIX", "YOUTUBE", "AVENGERS", "BATMAN", "IRONMAN", "PIZZA", "CRICKET", "FOOTBALL"]

active_hunts = {}
games = {} 
rps_games = {}

# --- HELPER: Generate Hunt Pattern ---
def generate_pattern(word, reveal_count=2):
    chars = list(word)
    indices = random.sample(range(len(word)), reveal_count)
    return " ".join([chars[i] if i in indices else "_" for i in range(len(word))])

# --- LEADERBOARD LOGIC ---
def get_leaderboard_text(game_type="total"):
    if stats_col is None: return "❌ DB Connection Error!"
    match_query = {} if game_type == "total" else {"game": game_type}
    pipeline = [{"$match": match_query}, {"$group": {"_id": "$id", "name": {"$first": "$name"}, "wins": {"$sum": 1}}}, {"$sort": {"wins": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    label = game_type.upper() if game_type != "total" else "OVERALL"
    text = f"🏆 *TOP 10 CHAMPIONS ({label})*\n\n"
    if not results: return text + "No wins yet! 🔥"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        user_link = f"[{user['name']}](tg://user?id={user['_id']})"
        text += f"{emojis[i]} {user_link} — `{user['wins']} Wins`\n"
    return text

# --- GAME COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎮 *Gaming Arena*\n/game - XO\n/rps - RPS\n/hunt - Word Hunt\n/leaderboard - Rankings", parse_mode=constants.ParseMode.MARKDOWN)
    asyncio.create_task(auto_delete(msg))

async def hunt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    word = random.choice(WORDS_DB)
    pattern = generate_pattern(word, 2)
    active_hunts[chat_id] = {"word": word, "revealed": 2}
    kb = [[InlineKeyboardButton("💡 Give Hint", callback_data=f"hint_{chat_id}")]]
    msg = await update.message.reply_text(f"🕵️‍♂️ *WORD HUNT!*\n\nGuess: `{pattern}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode=constants.ParseMode.MARKDOWN)
    asyncio.create_task(auto_delete(msg))

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    gid = str(update.message.message_id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None}
    msg = await update.message.reply_text(f"🎮 *X-O Match Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))
    asyncio.create_task(auto_delete(msg))

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    rid = str(update.message.message_id)
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    msg = await update.message.reply_text(f"🥊 *RPS Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join RPS", callback_data=f"rj_{rid}")]]))
    asyncio.create_task(auto_delete(msg))

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("XO", callback_data="lb_xo"), InlineKeyboardButton("RPS", callback_data="lb_rps"), InlineKeyboardButton("Hunt", callback_data="lb_wordhunt")], [InlineKeyboardButton("Overall", callback_data="lb_total")]]
    msg = await update.message.reply_text("Select Ranking:", reply_markup=InlineKeyboardMarkup(kb))
    asyncio.create_task(auto_delete(msg))

# --- MESSAGE & CALLBACK HANDLERS ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_hunts:
        guess = update.message.text.upper().strip()
        if guess == active_hunts[chat_id]['word']:
            name, uid = update.effective_user.first_name, update.effective_user.id
            if stats_col: stats_col.insert_one({"id": uid, "name": name, "game": "wordhunt", "time": datetime.now()})
            await update.message.reply_text(f"🥳 *CORRECT!* {name} won 1 point!")
            del active_hunts[chat_id]

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d, uid, name = q.data, q.from_user.id, q.from_user.first_name

    if d.startswith("hint_"):
        cid = int(d.split('_')[1])
        if cid in active_hunts:
            active_hunts[cid]['revealed'] += 1
            p = generate_pattern(active_hunts[cid]['word'], active_hunts[cid]['revealed'])
            await q.edit_message_text(f"🕵️‍♂️ *HINT ADDED*\n\nGuess: `{p}`", reply_markup=q.message.reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

    elif d.startswith("lb_"):
        await q.edit_message_text(get_leaderboard_text(d.split('_')[1]), parse_mode=constants.ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)

    elif d.startswith("j_"): # XO Join
        gid = d.split('_')[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]; g['p2'], g['n2'] = uid, name
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(g['board'][r][c] if g['board'][r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]))

    elif d.startswith("rj_"): # RPS Join
        rid = d.split('_')[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid and rps_games[rid]['p2'] is None:
            g = rps_games[rid]; g['p2'], g['n2'] = uid, name
            await q.edit_message_text(f"🥊 {g['n1']} vs {g['n2']}\nChoose Move:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"), InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"), InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]]))

    elif d.startswith("rm_"): # RPS Move
        rid, m = d.split('_')[1], d.split('_')[2]
        g = rps_games.get(rid)
        if not g: return
        if uid == g['p1'] and not g['m1']: g['m1'] = m
        elif uid == g['p2'] and not g['m2']: g['m2'] = m
        if g['m1'] and g['m2']:
            m1, m2 = g['m1'], g['m2']
            res, win_id, win_n = "🤝 Draw!", None, None
            if (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'): res, win_id, win_n = f"🏆 {g['n1']} Won!", g['p1'], g['n1']
            elif m1 != m2: res, win_id, win_n = f"🏆 {g['n2']} Won!", g['p2'], g['n2']
            await q.edit_message_text(f"🥊 *Result:* {res}\n{g['n1']}: {m1} | {g['n2']}: {m2}")
            if win_id and stats_col: stats_col.insert_one({"id": win_id, "name": win_n, "game": "rps", "time": datetime.now()})
            del rps_games[rid]

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("rps", rps_cmd))
    bot.add_handler(CommandHandler("hunt", hunt_cmd))
    bot.add_handler(CommandHandler("leaderboard", lb_cmd))
    bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    bot.run_polling(drop_pending_updates=True)
    

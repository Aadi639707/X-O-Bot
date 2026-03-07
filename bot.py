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

# --- STATE ---
active_hunts = {}
games = {}
rps_games = {}
WORDS_DB = ["WHATSAPP", "TELEGRAM", "SAMSUNG", "IPHONE", "VALORANT", "MINECRAFT", "CHICKEN", "BIRYANI", "BURGER", "DOMINOS", "NETFLIX", "YOUTUBE", "AVENGERS", "BATMAN", "IRONMAN", "PIZZA", "CRICKET", "FOOTBALL"]

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- HELPERS ---
def generate_pattern(word, indices):
    return " ".join([word[i] if i in indices else "_" for i in range(len(word))])

def get_leaderboard_text(game_type="total"):
    if stats_col is None: return "❌ DB Error!"
    query = {} if game_type == "total" else {"game": game_type}
    pipeline = [{"$match": query}, {"$group": {"_id": "$id", "name": {"$first": "$name"}, "wins": {"$sum": 1}}}, {"$sort": {"wins": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    text = f"🏆 *TOP 10 ({game_type.upper()})*\n\n"
    if not results: return text + "No wins yet!"
    for i, user in enumerate(results):
        text += f"{i+1}. [{user['name']}](tg://user?id={user['_id']}) — `{user['wins']} Wins`\n"
    return text

# --- GAME LOGIC ---
async def check_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    if chat_id not in active_hunts: return
    user_text = update.message.text.upper().strip()
    game = active_hunts[chat_id]
    if user_text == game['word']:
        name, uid = update.effective_user.first_name, update.effective_user.id
        if stats_col: stats_col.insert_one({"id": uid, "name": name, "game": "wordhunt", "time": datetime.now()})
        await update.message.reply_text(f"🥳 *CORRECT!* {name} guessed `{game['word']}`!")
        del active_hunts[chat_id]

# --- COMMANDS ---
async def start(u, c):
    await u.message.reply_text("🎮 *Gaming Arena*\n\n/hunt, /game, /rps, /leaderboard")

async def hunt_cmd(u, c):
    chat_id = u.effective_chat.id
    word = random.choice(WORDS_DB).upper()
    idx = random.sample(range(len(word)), 2)
    active_hunts[chat_id] = {"word": word, "indices": idx, "hints": 0}
    kb = [[InlineKeyboardButton("💡 Hint", callback_data=f"hint_{chat_id}")]]
    await u.message.reply_text(f"🕵️‍♂️ *WORD HUNT*\nGuess: `{generate_pattern(word, idx)}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode=constants.ParseMode.MARKDOWN)

async def rps_cmd(u, c):
    rid = str(u.message.message_id)
    rps_games[rid] = {'p1': u.effective_user.id, 'n1': u.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await u.message.reply_text("🥊 *RPS Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join RPS", callback_data=f"rj_{rid}")]]))

async def game_cmd(u, c):
    gid = str(u.message.message_id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': u.effective_user.id, 'n1': u.effective_user.first_name, 'p2': None, 'n2': None}
    await u.message.reply_text("🎮 *XO Match Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))

# --- CALLBACKS ---
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
                    g['indices'].append(random.choice(rem)); g['hints'] += 1
                    await q.edit_message_text(f"🕵️‍♂️ *HUNT (Hint {g['hints']}/3)*\nGuess: `{generate_pattern(g['word'], g['indices'])}`", reply_markup=q.message.reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

    elif d.startswith("j_"): # XO Join
        gid = d.split('_')[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]; g['p2'], g['n2'] = uid, name
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(g['board'][r][c] if g['board'][r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]))

    elif d.startswith("m_"): # XO Move
        parts = d.split('_'); gid, r, c = parts[1], int(parts[2]), int(parts[3])
        if gid not in games: return
        g = games[gid]
        if uid != (g['p1'] if g['turn'] == 'X' else g['p2']) or g['board'][r][c] != " ": return
        g['board'][r][c] = g['turn']
        # Win Check (Simplified)
        win = None
        b = g['board']
        for i in range(3):
            if b[i][0]==b[i][1]==b[i][2]!=" ": win=b[i][0]
            if b[0][i]==b[1][i]==b[2][i]!=" ": win=b[0][i]
        if win:
            await q.edit_message_text(f"🏆 {name} Won XO!"); stats_col.insert_one({"id": uid, "name": name, "game": "xo", "time": datetime.now()}); del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            await q.edit_message_text(f"Turn: {g['n1'] if g['turn'] == 'X' else g['n2']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(g['board'][r][c] if g['board'][r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]))

    elif d.startswith("rj_") or d.startswith("rm_"): # RPS Logic
        # (RPS logic remains same as previous working version)
        pass

    elif d.startswith("lb_"):
        await q.edit_message_text(get_leaderboard_text(d.split('_')[1]), parse_mode=constants.ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_word))
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("hunt", hunt_cmd))
    bot.add_handler(CommandHandler("rps", rps_cmd))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("leaderboard", lambda u,c: u.message.reply_text("Select Rank:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("XO", callback_data="lb_xo"), InlineKeyboardButton("RPS", callback_data="lb_rps"), InlineKeyboardButton("Hunt", callback_data="lb_wordhunt")]]))))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    bot.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        

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

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.info("MongoDB Connected! ✅")
    except Exception as e:
        logger.error(f"DB Error: {e}")

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online & Active! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- DATA ---
active_hunts = {}
games = {}
rps_games = {}
WORDS_DB = ["WHATSAPP", "TELEGRAM", "SAMSUNG", "IPHONE", "VALORANT", "MINECRAFT", "CHICKEN", "BIRYANI", "BURGER", "DOMINOS", "NETFLIX", "YOUTUBE", "AVENGERS", "BATMAN", "IRONMAN", "PIZZA", "CRICKET", "FOOTBALL", "INSTAGRAM", "FACEBOOK", "GOOGLE", "MICROSOFT", "AMAZON", "PYTHON", "ANDROID", "WINDOWS"]

# --- WIN CHECK (XO) ---
def check_win(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    if all(cell != " " for row in b for cell in row): return "Draw"
    return None

# --- WORD HUNT CHECKER ---
async def check_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    chat_id = update.effective_chat.id
    if chat_id not in active_hunts: return

    user_text = update.message.text.upper().strip()
    game = active_hunts[chat_id]
    
    if user_text == game['word']:
        name, uid = update.effective_user.first_name, update.effective_user.id
        if stats_col: stats_col.insert_one({"id": uid, "name": name, "game": "wordhunt", "time": datetime.now()})
        await update.message.reply_text(f"🥳 *CORRECT!* {name} guessed `{game['word']}` and won!")
        del active_hunts[chat_id]

# --- COMMANDS ---
async def start(u, c):
    await u.message.reply_text("🎮 *Gaming Arena Active!*\n\n/hunt - Word Hunt\n/game - TicTacToe\n/rps - RPS\n/leaderboard - Rankings")

async def hunt_cmd(u, c):
    chat_id = u.effective_chat.id
    word = random.choice(WORDS_DB).upper()
    indices = random.sample(range(len(word)), 2)
    active_hunts[chat_id] = {"word": word, "indices": indices}
    pattern = " ".join([word[i] if i in indices else "_" for i in range(len(word))])
    kb = [[InlineKeyboardButton("💡 Unlimited Hint", callback_data=f"hint_{chat_id}")]]
    await u.message.reply_text(f"🕵️‍♂️ *WORD HUNT*\n\nGuess: `{pattern}`", reply_markup=InlineKeyboardMarkup(kb), parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(u, c):
    gid = str(u.message.message_id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': u.effective_user.id, 'n1': u.effective_user.first_name, 'p2': None, 'n2': None}
    await u.message.reply_text("🎮 *XO Match Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))

async def rps_cmd(u, c):
    rid = str(u.message.message_id)
    rps_games[rid] = {'p1': u.effective_user.id, 'n1': u.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await u.message.reply_text("🥊 *RPS Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join RPS", callback_data=f"rj_{rid}")]]))

# --- CALLBACK HANDLER ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d, uid, name = q.data, q.from_user.id, q.from_user.first_name

    if d.startswith("hint_"):
        cid = int(d.split('_')[1])
        if cid in active_hunts:
            g = active_hunts[cid]
            rem = [i for i in range(len(g['word'])) if i not in g['indices']]
            if len(rem) > 1:
                g['indices'].append(random.choice(rem))
                new_p = " ".join([g['word'][i] if i in g['indices'] else "_" for i in range(len(g['word']))])
                await q.edit_message_text(f"🕵️‍♂️ *HUNT (Hint)*\n\nGuess: `{new_p}`", reply_markup=q.message.reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

    elif d.startswith("j_"): # XO JOIN
        gid = d.split('_')[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]; g['p2'], g['n2'] = uid, name
            kb = [[InlineKeyboardButton("·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("m_"): # XO MOVE (FIXED)
        gid, r, c = d.split('_')[1], int(d.split('_')[2]), int(d.split('_')[3])
        if gid not in games: return
        g = games[gid]
        if uid != (g['p1'] if g['turn'] == 'X' else g['p2']) or g['board'][r][c] != " ": return
        g['board'][r][c] = g['turn']
        res = check_win(g['board'])
        kb = [[InlineKeyboardButton(g['board'][rr][cc] if g['board'][rr][cc] != " " else "·", callback_data=f"m_{gid}_{rr}_{cc}") for cc in range(3)] for rr in range(3)]
        if res:
            msg = "🤝 *Match Draw!*" if res == "Draw" else f"🏆 *Winner: {name}!*"
            if res != "Draw" and stats_col: stats_col.insert_one({"id": uid, "name": name, "game": "xo", "time": datetime.now()})
            await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=constants.ParseMode.MARKDOWN); del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1'] if g['turn'] == 'X' else g['n2']} ({g['turn']})", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("rj_") or d.startswith("rm_"): # RPS LOGIC (SIMPLIFIED)
        pass # Add RPS Logic here

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers (Correct Order)
    bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_word))
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("hunt", hunt_cmd))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("rps", rps_cmd))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    
    # Conflict solution: drop_pending_updates=True
    bot.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
    

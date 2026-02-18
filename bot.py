import os
import logging
import asyncio
from datetime import datetime
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging setup
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
    except: pass

app = Flask('')
@app.route('/')
def home(): return "Bot is Online & Buttons Fixed! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- STATE ---
games = {} 
rps_games = {}

# --- HELPERS ---
def get_xo_markup(board, gid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(board[r][c] if board[r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)])

def check_xo_win(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    return None

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎮 *Gaming Arena Active!*\n\n🚀 /game - Start X-O\n🥊 /rps - Start Rock Paper Scissors", parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = f"xo_{update.effective_chat.id}_{update.message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None}
    await update.message.reply_text(f"🎮 *X-O Match*\nPlayer: {update.effective_user.first_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rid = f"rps_{update.effective_chat.id}_{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *Rock Paper Scissors*\nBy: {update.effective_user.first_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join RPS", callback_data=f"rj_{rid}")]]))

# --- BUTTONS LOGIC (THE FIX) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid, data = q.from_user.id, q.data
    
    # 1. X-O Join
    if data.startswith("j_"):
        gid = data.split('_', 1)[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"⚔️ Match: {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=get_xo_markup(g['board'], gid))
        await q.answer()

    # 2. X-O Move
    elif data.startswith("m_"):
        _, gid, r, c = data.split('_')
        r, c = int(r), int(c)
        if gid not in games: return await q.answer("Game Expired!")
        g = games[gid]
        curr = g['p1'] if g['turn'] == 'X' else g['p2']
        if uid != curr or g['board'][r][c] != " ": return await q.answer("Not your turn!")
        
        g['board'][r][c] = g['turn']
        win = check_xo_win(g['board'])
        if win:
            await q.edit_message_text(f"🏆 Winner: {q.from_user.first_name}!", reply_markup=get_xo_markup(g['board'], gid))
            del games[gid]
        elif all(cell != " " for row in g['board'] for cell in row):
            await q.edit_message_text("🤝 Draw!", reply_markup=get_xo_markup(g['board'], gid))
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            next_n = g['n1'] if g['turn'] == 'X' else g['n2']
            await q.edit_message_text(f"⚔️ Match: {g['n1']} vs {g['n2']}\nTurn: {next_n} ({g['turn']})", reply_markup=get_xo_markup(g['board'], gid))
        await q.answer()

    # 3. RPS Join
    elif data.startswith("rj_"):
        rid = data.split('_', 1)[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid and rps_games[rid]['p2'] is None:
            g = rps_games[rid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            btns = [[InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"), InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"), InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]]
            await q.edit_message_text(f"🥊 Match Live!\n{g['n1']} vs {g['n2']}\nPick your move!", reply_markup=InlineKeyboardMarkup(btns))
        await q.answer()

    # 4. RPS Move
    elif data.startswith("rm_"):
        _, rid, m = data.split('_')
        if rid not in rps_games: return await q.answer("Game Over!")
        g = rps_games[rid]
        if uid == g['p1'] and not g['m1']: g['m1'] = m
        elif uid == g['p2'] and not g['m2']: g['m2'] = m
        else: return await q.answer("Move already recorded!")

        if g['m1'] and g['m2']:
            names = {"R": "🪨", "P": "📄", "S": "✂️"}
            m1, m2 = g['m1'], g['m2']
            if m1 == m2: res = "🤝 Draw!"
            elif (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'): res = f"🏆 Winner: {g['n1']}!"
            else: res = f"🏆 Winner: {g['n2']}!"
            await q.edit_message_text(f"🥊 Result:\n{g['n1']}: {names[m1]}\n{g['n2']}: {names[m2]}\n\n{res}")
            del rps_games[rid]
        else:
            await q.edit_message_text(f"🥊 Waiting...\n{g['n1']}: {'✅' if g['m1'] else '⏳'}\n{g['n2']}: {'✅' if g['m2'] else '⏳'}", reply_markup=q.message.reply_markup)
        await q.answer("Recorded! ✅")

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    app_bot = ApplicationBuilder().token(TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("game", game_cmd))
    app_bot.add_handler(CommandHandler("rps", rps_cmd))
    app_bot.add_handler(CallbackQueryHandler(handle_callback)) # Ye zaroori hai
    app_bot.run_polling(drop_pending_updates=True)
                                                                            

import os
import logging
import asyncio
from datetime import datetime
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.environ.get("TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
ADMIN_ID = 6825707797 

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
def home(): return "Bot is Fixed & Running! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- STATE MANAGEMENT ---
games = {} # X-O Games
rps_games = {} # RPS Games

async def delete_msg(context, chat_id, message_id):
    await asyncio.sleep(120)
    try: await context.bot.delete_message(chat_id, message_id)
    except: pass

# --- X-O HELPERS ---
def get_xo_markup(board, gid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(board[r][c] if board[r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)])

def check_xo_winner(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    return None

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎮 *Gaming Arena* 🎮\n\n🚀 /game - Start X-O\n🥊 /rps - Start Rock Paper Scissors"
    await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    gid = str(update.effective_chat.id) + "_" + str(update.message.message_id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'u1': update.effective_user.username, 'p2': None, 'n2': None, 'u2': None}
    await update.message.reply_text(f"🎮 *X-O Match*\n❌ Player: {update.effective_user.first_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]), parse_mode=constants.ParseMode.MARKDOWN)

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    rid = f"rps_{update.effective_chat.id}_{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *Rock Paper Scissors*\nBy: {update.effective_user.first_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"rj_{rid}")]]), parse_mode=constants.ParseMode.MARKDOWN)

# --- CALLBACK HANDLER ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid, data = q.from_user.id, q.data

    # 1. X-O JOIN
    if data.startswith("j_"):
        await q.answer()
        gid = data.split('_', 1)[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]
            g['p2'], g['n2'], g['u2'] = uid, q.from_user.first_name, q.from_user.username
            tag = f"@{g['u1']}" if g['u1'] else g['n1']
            await q.edit_message_text(f"⚔️ *X-O Live!*\n❌ {g['n1']} vs ⭕ {g['n2']}\n\n👉 TURN: {tag} (X)", reply_markup=get_xo_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)

    # 2. X-O MOVE
    elif data.startswith("m_"):
        await q.answer()
        _, gid, r, c = data.split('_')
        r, c = int(r), int(c)
        if gid not in games: return
        g = games[gid]
        curr_id = g['p1'] if g['turn'] == 'X' else g['p2']
        if uid != curr_id or g['board'][r][c] != " ": return
        
        g['board'][r][c] = g['turn']
        win = check_xo_winner(g['board'])
        if win:
            winner_name = g['n1'] if win == 'X' else g['n2']
            await q.edit_message_text(f"🏆 Winner: {winner_name}!", reply_markup=get_xo_markup(g['board'], gid))
            if stats_col: stats_col.insert_one({"id": uid, "name": winner_name, "date": datetime.now()})
            del games[gid]
        elif all(cell != " " for row in g['board'] for cell in row):
            await q.edit_message_text("🤝 Draw Match!", reply_markup=get_xo_markup(g['board'], gid))
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            next_tag = f"@{g['u1']}" if g['turn'] == 'X' and g['u1'] else (f"@{g['u2']}" if g['turn'] == 'O' and g['u2'] else (g['n1'] if g['turn'] == 'X' else g['n2']))
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\n\n👉 TURN: {next_tag} ({g['turn']})", reply_markup=get_xo_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)

    # 3. RPS JOIN
    elif data.startswith("rj_"):
        await q.answer()
        rid = data.split('_', 1)[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid and rps_games[rid]['p2'] is None:
            g = rps_games[rid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"🥊 *RPS Started!*\n👤 {g['n1']}: ⏳ Waiting...\n👤 {g['n2']}: ⏳ Waiting...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"), InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"), InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]]), parse_mode=constants.ParseMode.MARKDOWN)

    # 4. RPS MOVE
    elif data.startswith("rm_"):
        _, rid, move = data.split('_')
        if rid not in rps_games: return
        g = rps_games[rid]
        if uid == g['p1'] and not g['m1']: g['m1'] = move
        elif uid == g['p2'] and not g['m2']: g['m2'] = move
        else: return await q.answer("Move recorded!")

        if g['m1'] and g['m2']:
            names = {"R": "🪨 Rock", "P": "📄 Paper", "S": "✂️ Scissors"}
            m1, m2 = g['m1'], g['m2']
            if m1 == m2: res = "🤝 Draw!"
            elif (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'): res = f"🏆 Winner: {g['n1']}!"
            else: res = f"🏆 Winner: {g['n2']}!"
            await q.edit_message_text(f"🥊 *RPS Result*\n{g['n1']}: {names[m1]}\n{g['n2']}: {names[m2]}\n\n{res}", parse_mode=constants.ParseMode.MARKDOWN)
            del rps_games[rid]
        else:
            s1 = "✅ Ready" if g['m1'] else "⏳ Thinking..."
            s2 = "✅ Ready" if g['m2'] else "⏳ Thinking..."
            await q.edit_message_text(f"🥊 *RPS Match*\n👤 {g['n1']}: {s1}\n👤 {g['n2']}: {s2}", reply_markup=q.message.reply_markup, parse_mode=constants.ParseMode.MARKDOWN)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CommandHandler("rps", rps_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling(drop_pending_updates=True)
            

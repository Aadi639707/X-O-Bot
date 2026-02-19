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
ADMIN_ID = 8306853454  # Updated Admin ID ✅

# --- DATABASE ---
stats_col = None
users_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
        users_col = db['users']
    except: pass

app = Flask('')
@app.route('/')
def home(): return "Admin Updated & Bot Live! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- STATE ---
games = {} 
rps_games = {}

# --- UTILS ---
def get_leaderboard_text():
    if stats_col is None: return "❌ Database not connected!"
    pipeline = [{"$group": {"_id": "$id", "name": {"$first": "$name"}, "wins": {"$sum": 1}}}, {"$sort": {"wins": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    if not results: return "🏆 *LEADERBOARD*\n\nNo wins yet! 🔥"
    text = "🏆 *TOP 10 CHAMPIONS* 🏆\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['wins']} Wins`\n"
    return text

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
    if users_col is not None:
        users_col.update_one({"id": update.effective_user.id}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    await update.message.reply_text("🎮 *Gaming Arena*\n\n/game - X-O Match\n/rps - RPS Match\n/leaderboard - Rankings", parse_mode=constants.ParseMode.MARKDOWN)

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_leaderboard_text(), parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = f"{update.message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None}
    await update.message.reply_text(f"🎮 *X-O Match*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rid = f"{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *RPS Match*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"rj_{rid}")]]))

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ Permission Denied.")
    msg_text = " ".join(context.args)
    if not msg_text or users_col is None: return
    users = list(users_col.find({}, {"id": 1}))
    sent, failed = 0, 0
    for u in users:
        try:
            await context.bot.send_message(u['id'], msg_text)
            sent += 1
            await asyncio.sleep(0.05)
        except: failed += 1
    await update.message.reply_text(f"✅ *Broadcast Done*\nSent: {sent}\nFailed: {failed}")

# --- CALLBACK HANDLER ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid, data = q.from_user.id, q.data
    parts = data.split('_')

    if data.startswith("j_"):
        gid = parts[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=get_xo_markup(g['board'], gid))

    elif data.startswith("m_"):
        gid, r, c = parts[1], int(parts[2]), int(parts[3])
        if gid not in games: return
        g = games[gid]
        curr = g['p1'] if g['turn'] == 'X' else g['p2']
        if uid != curr or g['board'][r][c] != " ": return
        g['board'][r][c] = g['turn']
        win = check_xo_win(g['board'])
        if win:
            await q.edit_message_text(f"🏆 Winner: {q.from_user.first_name}!", reply_markup=get_xo_markup(g['board'], gid))
            if stats_col: stats_col.insert_one({"id": uid, "name": q.from_user.first_name, "date": datetime.now()})
            del games[gid]
        elif all(cell != " " for row in g['board'] for cell in row):
            await q.edit_message_text("🤝 Draw!", reply_markup=get_xo_markup(g['board'], gid))
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            nxt = g['n1'] if g['turn'] == 'X' else g['n2']
            await q.edit_message_text(f"⚔️ Turn: {nxt} ({g['turn']})", reply_markup=get_xo_markup(g['board'], gid))

    elif data.startswith("rj_"):
        rid = parts[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid and rps_games[rid]['p2'] is None:
            g = rps_games[rid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            btns = [[InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"), InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"), InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]]
            await q.edit_message_text(f"🥊 {g['n1']} vs {g['n2']}\nChose move!", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("rm_"):
        rid, m = parts[1], parts[2]
        if rid not in rps_games: return
        g = rps_games[rid]
        if uid == g['p1'] and not g['m1']: g['m1'] = m
        elif uid == g['p2'] and not g['m2']: g['m2'] = m
        else: return
        if g['m1'] and g['m2']:
            m1, m2 = g['m1'], g['m2']
            res, win_uid, win_n = "🤝 Draw!", None, None
            if (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'):
                res, win_uid, win_n = f"🏆 Winner: {g['n1']}!", g['p1'], g['n1']
            elif m1 != m2:
                res, win_uid, win_n = f"🏆 Winner: {g['n2']}!", g['p2'], g['n2']
            await q.edit_message_text(f"Result: {res}")
            if win_uid and stats_col: stats_col.insert_one({"id": win_uid, "name": win_n, "date": datetime.now()})
            del rps_games[rid]
        else:
            await q.edit_message_text(f"🥊 Waiting moves...", reply_markup=q.message.reply_markup)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("rps", rps_cmd))
    bot.add_handler(CommandHandler("leaderboard", lb_cmd))
    bot.add_handler(CommandHandler("broadcast", broadcast))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    bot.run_polling(drop_pending_updates=True)
    

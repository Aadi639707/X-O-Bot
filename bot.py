import os
import logging
import asyncio
import time
from datetime import datetime
from flask import Flask
from threading import Thread
from pymongo import MongoClient
import urllib.request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.environ.get("TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
ADMIN_ID = 8306853454  
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- DATABASE ---
stats_col = None
users_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
        users_col = db['users']
        logger.info("MongoDB Connected! ✅")
    except Exception as e:
        logger.error(f"DB Error: {e}")

# --- SERVER & ANTI-SLEEP PINGER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online! ♟️"

def pinger():
    if not RENDER_URL: return
    while True:
        try:
            urllib.request.urlopen(RENDER_URL)
        except: pass
        time.sleep(300)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- STATE ---
games = {} 
rps_games = {}

# --- LEADERBOARD UTILS ---
def get_leaderboard_text(game_type="total"):
    if stats_col is None: return "❌ Database error!"
    match_filter = {} if game_type == "total" else {"game": game_type}
    pipeline = [
        {"$match": match_filter},
        {"$group": {"_id": "$id", "name": {"$first": "$name"}, "wins": {"$sum": 1}}},
        {"$sort": {"wins": -1}},
        {"$limit": 10}
    ]
    results = list(stats_col.aggregate(pipeline))
    label = game_type.upper() if game_type != "total" else "OVERALL"
    text = f"🏆 *TOP 10 CHAMPIONS ({label})*\n\n"
    if not results: return text + "No records yet! 🔥"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['wins']} Wins`\n"
    return text

# --- GAMES MARKUP ---
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
    if users_col:
        users_col.update_one({"id": update.effective_user.id}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    await update.message.reply_text("🎮 *Gaming Arena*\n\n/game - Tic Tac Toe\n/rps - RPS\n/chess - Chess TMA\n/leaderboard - Rankings", parse_mode=constants.ParseMode.MARKDOWN)

async def chess_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fixed for Group Chat (Removed Private Check)
    game_id = f"chess_{abs(update.effective_chat.id)}" 
    url = f"https://Chess-bice-beta.vercel.app?gameId={game_id}"
    keyboard = [[InlineKeyboardButton("♟️ Join Chess Match", web_app=WebAppInfo(url=url))]]
    await update.message.reply_text(
        "🏁 *Grandmaster Arena Ready!*\n\nClick below to join. Board unlocks when 2 players enter.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    gid = f"{update.message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None}
    await update.message.reply_text(f"🎮 *X-O Match Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    rid = f"{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *RPS Challenge*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join RPS", callback_data=f"rj_{rid}")]]))

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Tic-Tac-Toe", callback_data="lb_xo"), InlineKeyboardButton("RPS", callback_data="lb_rps")], [InlineKeyboardButton("Chess", callback_data="lb_chess"), InlineKeyboardButton("Overall", callback_data="lb_total")]]
    await update.message.reply_text("Select game leaderboard:", reply_markup=InlineKeyboardMarkup(keyboard))

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args: return
    txt, sent = " ".join(context.args), 0
    for u in list(users_col.find({}, {"id": 1})):
        try:
            await context.bot.send_message(u['id'], txt)
            sent += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text(f"✅ Sent to {sent} users.")

# --- CALLBACK HANDLER ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid, data = q.from_user.id, q.data
    
    if data.startswith("lb_"):
        await q.edit_message_text(get_leaderboard_text(data.split('_')[1]), parse_mode=constants.ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)
    
    elif data.startswith("j_"):
        gid = data.split('_')[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=get_xo_markup(g['board'], gid))

    elif data.startswith("m_"):
        parts = data.split('_')
        gid, r, c = parts[1], int(parts[2]), int(parts[3])
        if gid not in games: return
        g = games[gid]
        if uid != (g['p1'] if g['turn'] == 'X' else g['p2']) or g['board'][r][c] != " ": return
        g['board'][r][c] = g['turn']
        win = check_xo_win(g['board'])
        if win:
            await q.edit_message_text(f"🏆 Winner: {q.from_user.first_name}!", reply_markup=get_xo_markup(g['board'], gid))
            if stats_col: stats_col.insert_one({"id": uid, "name": q.from_user.first_name, "game": "xo", "date": datetime.now()})
            del games[gid]
        elif all(cell != " " for row in g['board'] for cell in row):
            await q.edit_message_text("🤝 Draw Match!", reply_markup=get_xo_markup(g['board'], gid))
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            await q.edit_message_text(f"⚔️ Turn: {g['n1'] if g['turn'] == 'X' else g['n2']} ({g['turn']})", reply_markup=get_xo_markup(g['board'], gid))

    elif data.startswith("rj_"):
        rid = data.split('_')[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid and rps_games[rid]['p2'] is None:
            g = rps_games[rid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            btns = [[InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"), InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"), InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]]
            await q.edit_message_text(f"🥊 {g['n1']} vs {g['n2']}\nChoose your move!", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("rm_"):
        parts = data.split('_')
        rid, m = parts[1], parts[2]
        if rid not in rps_games: return
        g = rps_games[rid]
        if uid == g['p1'] and not g['m1']: g['m1'] = m
        elif uid == g['p2'] and not g['m2']: g['m2'] = m
        else: return
        if g['m1'] and g['m2']:
            n = {"R": "🪨 Rock", "P": "📄 Paper", "S": "✂️ Scissors"}
            m1, m2 = g['m1'], g['m2']
            res, win_id, win_n = "🤝 Draw!", None, None
            if (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'): res, win_id, win_n = f"🏆 Winner: {g['n1']}!", g['p1'], g['n1']
            elif m1 != m2: res, win_id, win_n = f"🏆 Winner: {g['n2']}!", g['p2'], g['n2']
            await q.edit_message_text(f"🥊 Result: {res}\n{g['n1']}: {n[m1]} | {g['n2']}: {n[m2]}")
            if win_id and stats_col: stats_col.insert_one({"id": win_id, "name": win_n, "game": "rps", "date": datetime.now()})
            del rps_games[rid]
        else:
            await q.edit_message_text(f"🥊 Waiting for opponent...", reply_markup=q.message.reply_markup)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    if RENDER_URL: Thread(target=pinger, daemon=True).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("chess", chess_cmd))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("rps", rps_cmd))
    bot.add_handler(CommandHandler("leaderboard", lb_cmd))
    bot.add_handler(CommandHandler("broadcast", broadcast))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    bot.run_polling(drop_pending_updates=True)
    

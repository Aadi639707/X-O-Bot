import os
import logging
import asyncio
import random
from datetime import datetime
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

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

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Gaming Bot is Online! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- STATE ---
games = {}
rps_games = {}

# --- WIN LOGIC (XO) ---
def check_win(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    if all(cell != " " for row in b for cell in row): return "Draw"
    return None

# --- LEADERBOARD ---
def get_leaderboard_text(game_type="total"):
    if stats_col is None: return "❌ Database Error!"
    query = {} if game_type == "total" else {"game": game_type}
    pipeline = [{"$match": query}, {"$group": {"_id": "$id", "name": {"$first": "$name"}, "wins": {"$sum": 1}}}, {"$sort": {"wins": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    text = f"🏆 *TOP 10 ({game_type.upper()})*\n\n"
    if not results: return text + "No records found!"
    for i, user in enumerate(results):
        text += f"{i+1}. [{user['name']}](tg://user?id={user['_id']}) — `{user['wins']} Wins`\n"
    return text

# --- COMMANDS ---
async def start(u, c):
    await u.message.reply_text("🎮 *Gaming Bot*\n\n/game - TicTacToe\n/rps - Rock Paper Scissors\n/leaderboard - Rankings", parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(u, c):
    gid = str(u.message.message_id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': u.effective_user.id, 'n1': u.effective_user.first_name, 'p2': None, 'n2': None}
    await u.message.reply_text("🎮 *XO Match Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))

async def rps_cmd(u, c):
    rid = str(u.message.message_id)
    rps_games[rid] = {'p1': u.effective_user.id, 'n1': u.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await u.message.reply_text("🥊 *RPS Challenge!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join RPS", callback_data=f"rj_{rid}")]]))

# --- CALLBACK HANDLER ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d, uid, name = q.data, q.from_user.id, q.from_user.first_name

    # --- XO LOGIC ---
    if d.startswith("j_"):
        gid = d.split('_')[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]; g['p2'], g['n2'] = uid, name
            kb = [[InlineKeyboardButton("·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("m_"):
        gid, r, c = d.split('_')[1], int(d.split('_')[2]), int(d.split('_')[3])
        if gid not in games: return
        g = games[gid]
        if uid != (g['p1'] if g['turn'] == 'X' else g['p2']) or g['board'][r][c] != " ": return
        
        g['board'][r][c] = g['turn']
        res = check_win(g['board'])
        kb = [[InlineKeyboardButton(g['board'][rr][cc] if g['board'][rr][cc] != " " else "·", callback_data=f"m_{gid}_{rr}_{cc}") for cc in range(3)] for rr in range(3)]
        
        if res:
            msg = "🤝 *Match Draw!*" if res == "Draw" else f"🏆 *Winner: {name}!*"
            if res != "Draw" and stats_col:
                stats_col.insert_one({"id": uid, "name": name, "game": "xo", "time": datetime.now()})
            await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=constants.ParseMode.MARKDOWN)
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1'] if g['turn'] == 'X' else g['n2']} ({g['turn']})", reply_markup=InlineKeyboardMarkup(kb))

    # --- RPS LOGIC ---
    elif d.startswith("rj_"):
        rid = d.split('_')[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid and rps_games[rid]['p2'] is None:
            g = rps_games[rid]; g['p2'], g['n2'] = uid, name
            kb = [[InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"), 
                   InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"), 
                   InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]]
            await q.edit_message_text(f"🥊 {g['n1']} vs {g['n2']}\nMake your move!", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("rm_"):
        rid, move = d.split('_')[1], d.split('_')[2]
        if rid not in rps_games: return
        g = rps_games[rid]
        if uid == g['p1'] and not g['m1']: g['m1'] = move
        elif uid == g['p2'] and not g['m2']: g['m2'] = move
        else: return

        if g['m1'] and g['m2']:
            m1, m2 = g['m1'], g['m2']
            res_text, win_id, win_n = "🤝 Draw!", None, None
            if (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'):
                res_text, win_id, win_n = f"🏆 {g['n1']} Won!", g['p1'], g['n1']
            elif m1 != m2:
                res_text, win_id, win_n = f"🏆 {g['n2']} Won!", g['p2'], g['n2']
            
            await q.edit_message_text(f"🥊 *RPS Result:*\n{res_text}\n{g['n1']}: {m1} | {g['n2']}: {m2}", parse_mode=constants.ParseMode.MARKDOWN)
            if win_id and stats_col:
                stats_col.insert_one({"id": win_id, "name": win_n, "game": "rps", "time": datetime.now()})
            del rps_games[rid]

    elif d.startswith("lb_"):
        await q.edit_message_text(get_leaderboard_text(d.split('_')[1]), parse_mode=constants.ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("rps", rps_cmd))
    bot.add_handler(CommandHandler("leaderboard", lambda u,c: u.message.reply_text("Select Rankings:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("XO", callback_data="lb_xo"), InlineKeyboardButton("RPS", callback_data="lb_rps")], [InlineKeyboardButton("Overall", callback_data="lb_total")]]))))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    bot.run_polling(drop_pending_updates=True)

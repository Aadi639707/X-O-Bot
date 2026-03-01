import os
import logging
import asyncio
import time
from datetime import datetime
from flask import Flask
from threading import Thread
from pymongo import MongoClient, DESCENDING
import urllib.request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.environ.get("TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- DATABASE CONNECTION ---
stats_col = None
users_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins'] 
        users_col = db['users']
        # Indexing for Speed
        stats_col.create_index([("id", 1)])
        logger.info("MongoDB Connected & Indexed! ✅")
    except Exception as e:
        logger.error(f"DB Error: {e}")

# --- SERVER & PINGER ---
app = Flask('')
@app.route('/')
def home(): return "Fast Gaming Bot is Online! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- AUTO DELETE (2 MINS) ---
async def auto_delete(message, delay=120):
    await asyncio.sleep(delay)
    try: await message.delete()
    except: pass

# --- FIXED LEADERBOARD (REAL-TIME DB) ---
def get_leaderboard_text(game_type="total"):
    if stats_col is None: return "❌ DB Connection Error!"
    
    # Filter by game type if specified
    match_query = {} if game_type == "total" else {"game": game_type}
    
    # Powerful aggregation to get real-time counts
    pipeline = [
        {"$match": match_query},
        {"$group": {
            "_id": "$id", 
            "name": {"$first": "$name"}, 
            "wins": {"$sum": 1}
        }},
        {"$sort": {"wins": -1}},
        {"$limit": 10}
    ]
    
    results = list(stats_col.aggregate(pipeline))
    label = game_type.upper() if game_type != "total" else "OVERALL"
    text = f"🏆 *TOP 10 CHAMPIONS ({label})*\n\n"
    
    if not results: return text + "No new wins recorded yet! ⚡"
    
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        user_link = f"[{user['name']}](tg://user?id={user['_id']})"
        text += f"{emojis[i]} {user_link} — `{user['wins']} Wins`\n"
    return text

# --- STATE ---
games = {} 
rps_games = {}

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎮 *Gaming Arena*\n/game, /rps, /leaderboard", parse_mode=constants.ParseMode.MARKDOWN)
    asyncio.create_task(auto_delete(msg))

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    gid = str(update.message.message_id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None}
    msg = await update.message.reply_text(f"🎮 *X-O Match started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))
    asyncio.create_task(auto_delete(msg))

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Tic-Tac-Toe", callback_data="lb_xo"), InlineKeyboardButton("RPS", callback_data="lb_rps")], [InlineKeyboardButton("Overall", callback_data="lb_total")]]
    msg = await update.message.reply_text("Rankings (Updating Live 🟢):", reply_markup=InlineKeyboardMarkup(kb))
    asyncio.create_task(auto_delete(msg))

# --- CALLBACK LOGIC ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data, uid, u_name = q.data, q.from_user.id, q.from_user.first_name
    
    if data.startswith("lb_"):
        await q.edit_message_text(get_leaderboard_text(data.split('_')[1]), parse_mode=constants.ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)

    elif data.startswith("j_"):
        gid = data.split('_')[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]; g['p2'], g['n2'] = uid, u_name
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(g['board'][r][c] if g['board'][r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]))

    elif data.startswith("m_"):
        parts = data.split('_'); gid, r, c = parts[1], int(parts[2]), int(parts[3])
        if gid not in games: return
        g = games[gid]
        if uid != (g['p1'] if g['turn'] == 'X' else g['p2']) or g['board'][r][c] != " ": return
        g['board'][r][c] = g['turn']
        
        # Win Check Logic
        win_char = None
        b = g['board']
        for i in range(3):
            if b[i][0]==b[i][1]==b[i][2]!=" ": win_char=b[i][0]
            if b[0][i]==b[1][i]==b[2][i]!=" ": win_char=b[0][i]
        if b[0][0]==b[1][1]==b[2][2]!=" ": win_char=b[0][0]
        if b[0][2]==b[1][1]==b[2][0]!=" ": win_char=b[0][2]

        if win_char:
            await q.edit_message_text(f"🏆 *{u_name}* Won!", parse_mode=constants.ParseMode.MARKDOWN)
            if stats_col: # SAVING TO MONGODB
                stats_col.insert_one({"id": uid, "name": u_name, "game": "xo", "time": datetime.now()})
            del games[gid]
        elif all(cell != " " for row in b for cell in row):
            await q.edit_message_text("🤝 Draw Match!"); del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1'] if g['turn'] == 'X' else g['n2']} ({g['turn']})", 
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(g['board'][r][c] if g['board'][r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]))

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CommandHandler("leaderboard", lb_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling(drop_pending_updates=True)
    

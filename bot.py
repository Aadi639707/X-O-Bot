import os
import logging
import asyncio
from datetime import datetime, timedelta
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
users_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
        users_col = db['users']
        logger.info("MongoDB Connected! ✅")
    except: logger.error("DB Connection Failed")

app = Flask('')
@app.route('/')
def home(): return "Leaderboard Fixed & Online! 🏆"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- STATE ---
games = {} 
rps_games = {}

# --- UTILS ---
def get_lb_text(mode="global"):
    if stats_col is None: return "❌ Database not connected!"
    now = datetime.now()
    query = {}
    if mode == "today": 
        query = {"date": {"$gte": now.replace(hour=0, minute=0, second=0, microsecond=0)}}
    
    pipeline = [
        {"$match": query}, 
        {"$group": {"_id": "$id", "name": {"$first": "$name"}, "count": {"$sum": 1}}}, 
        {"$sort": {"count": -1}}, 
        {"$limit": 10}
    ]
    results = list(stats_col.aggregate(pipeline))
    if not results: return f"🏆 *{mode.upper()} LEADERBOARD*\n\nNo wins recorded yet! 🔥"
    
    text = f"🎊 *TOP 10 PLAYERS - {mode.upper()}* 🎊\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['count']} Wins`\n"
    return text

def get_xo_markup(board, gid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(board[r][c] if board[r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)])

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if users_col is not None:
        users_col.update_one({"id": update.effective_user.id}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    text = "🎮 *Gaming Arena*\n\n/game - Tic Tac Toe\n/rps - Rock Paper Scissors\n/leaderboard - Top Players"
    btns = [[InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global")],
            [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btns = [[InlineKeyboardButton("Today", callback_data="lb_today"), InlineKeyboardButton("Global", callback_data="lb_global")]]
    await update.message.reply_text(get_lb_text("global"), reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = f"{update.message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    await update.message.reply_text(f"🎮 *X-O Match*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rid = f"{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *RPS Match*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join RPS", callback_data=f"rj_{rid}")]]))

# --- CALLBACK HANDLER ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid, data = q.from_user.id, q.data
    parts = data.split('_')

    # LEADERBOARD Logic
    if data.startswith("lb_"):
        mode = parts[1]
        btns = [[InlineKeyboardButton("Today", callback_data="lb_today"), InlineKeyboardButton("Global", callback_data="lb_global")]]
        await q.edit_message_text(get_lb_text(mode), reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

    # XO & RPS Logic (Same as pichla working code)
    elif data.startswith("j_"):
        gid = parts[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=get_xo_markup(g['board'], gid))
            
    # ... (Baaki move handlers m_ aur rm_ pichle code jaise hi rahenge)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("rps", rps_cmd))
    bot.add_handler(CommandHandler("leaderboard", lb_cmd))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    bot.run_polling(drop_pending_updates=True)
        

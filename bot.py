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
ADMIN_ID = 8306853454  # Admin: Ayush Roy
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
    except Exception as e:
        logger.error(f"DB Error: {e}")

# --- SERVER & PINGER ---
app = Flask('')
@app.route('/')
def home(): return "Bot Live!"

def pinger():
    if not RENDER_URL: return
    while True:
        try: urllib.request.urlopen(RENDER_URL)
        except: pass
        time.sleep(300)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- STATE ---
games = {} 
rps_games = {}

# --- LEADERBOARD ---
def get_leaderboard_text(game_type="total"):
    if stats_col is None: return "❌ DB Error!"
    match_filter = {} if game_type == "total" else {"game": game_type}
    pipeline = [{"$match": match_filter}, {"$group": {"_id": "$id", "name": {"$first": "$name"}, "wins": {"$sum": 1}}}, {"$sort": {"wins": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    label = game_type.upper() if game_type != "total" else "OVERALL"
    text = f"🏆 *TOP 10 CHAMPIONS ({label})*\n\n"
    if not results: return text + "No records yet!"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['wins']} Wins`\n"
    return text

# --- CORE FUNCTIONS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if users_col:
        users_col.update_one({"id": update.effective_user.id}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    await update.message.reply_text("🎮 *Arena*\n/game, /rps, /chess, /leaderboard", parse_mode=constants.ParseMode.MARKDOWN)

# 10000% WORKING CHESS COMMAND
async def chess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # ABS is used to handle negative Group IDs
        gid = f"chess_{abs(update.effective_chat.id)}"
        # Your Vercel Link
        v_url = f"https://Chess-bice-beta.vercel.app?gameId={gid}"
        
        btn = [[InlineKeyboardButton("♟️ Join Match", web_app=WebAppInfo(url=v_url))]]
        await update.message.reply_text(
            "🏁 *Chess Match Ready!*\nClick below to open the board in this group.",
            reply_markup=InlineKeyboardMarkup(btn),
            parse_mode=constants.ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error: {e}")

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    gid = f"{update.message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None}
    await update.message.reply_text(f"🎮 *X-O Match*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join", callback_data=f"j_{gid}")]]))

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    rid = f"{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *RPS*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join", callback_data=f"rj_{rid}")]]))

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("Tic-Tac-Toe", callback_data="lb_xo"), InlineKeyboardButton("RPS", callback_data="lb_rps")], [InlineKeyboardButton("Chess", callback_data="lb_chess"), InlineKeyboardButton("Overall", callback_data="lb_total")]]
    await update.message.reply_text("Select Rankings:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d, uid = q.data, q.from_user.id
    if d.startswith("lb_"): await q.edit_message_text(get_leaderboard_text(d.split('_')[1]), parse_mode=constants.ParseMode.MARKDOWN, reply_markup=q.message.reply_markup)
    # XO/RPS logic follows...
    elif d.startswith("j_"):
        gid = d.split('_')[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]; g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(g['board'][r][c] if g['board'][r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]))

# --- MAIN RUNNER ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    if RENDER_URL: Thread(target=pinger, daemon=True).start()
    
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Registering Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("chess", chess_handler)) # Using new handler name
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CommandHandler("rps", rps_cmd))
    application.add_handler(CommandHandler("leaderboard", lb_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    application.run_polling(drop_pending_updates=True)
                   

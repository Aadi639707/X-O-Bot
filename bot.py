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
    except: pass

app = Flask('')
@app.route('/')
def home(): return "Bot is Ultra Fast & Ready! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- LOGIC ---
games = {}
rps_games = {}

async def delete_msg(context, chat_id, message_id):
    await asyncio.sleep(120)
    try: await context.bot.delete_message(chat_id, message_id)
    except: pass

def get_board_markup(board, gid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(board[r][c] if board[r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)]
        for r in range(3)
    ])

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tracking users for broadcast
    if users_col is not None:
        users_col.update_one({"id": update.effective_user.id}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    
    text = "🎮 *Gaming Hub* 🎮\n\n🚀 /game - Start X-O\n🥊 /rps - Start RPS\n🏆 /leaderboard - Stats"
    btns = [[InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global")],
            [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    args = context.args
    if not args: return await update.message.reply_text("Usage: /broadcast [text]")
    
    msg_text = " ".join(args)
    users = list(users_col.find({}, {"id": 1}))
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(u['id'], msg_text)
            sent += 1
            await asyncio.sleep(0.1)
        except: pass
    await update.message.reply_text(f"✅ Sent to {sent} users.")

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return await update.message.reply_text("❌ Use in Groups!")
    gid = str(update.effective_chat.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 
                  'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 
                  'u1': update.effective_user.username, 'p2': None}
    
    await update.message.reply_text(
        f"🎮 *X-O Match Started!*\n❌ Player: {update.effective_user.first_name}\n\nWaiting for Player 2...",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]),
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- CALLBACK HANDLER ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer() # FAST RESPONSE
    uid, data = q.from_user.id, q.data

    if data.startswith("j_"):
        gid = data.split('_')[1]
        if gid in games and games[gid]['p1'] != uid:
            g = games[gid]
            g['p2'], g['n2'], g['u2'] = uid, q.from_user.first_name, q.from_user.username
            tag = f"@{g['u1']}" if g['u1'] else g['n1']
            await q.edit_message_text(
                f"⚔️ *Match Live!*\n❌ {g['n1']} vs ⭕ {g['n2']}\n\n👉 TURN: {tag} (X)",
                reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN
            )

    elif data.startswith("m_"):
        _, gid, r, c = data.split('_')
        r, c = int(r), int(c)
        if gid not in games: return
        g = games[gid]
        
        curr_id = g['p1'] if g['turn'] == 'X' else g['p2']
        if uid != curr_id: return # Ignore wrong player clicks silently for speed

        if g['board'][r][c] == " ":
            g['board'][r][c] = g['turn']
            winner = None # winner check logic here...
            # (Winner logic as-is, just update turn text with TAG)
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            next_name = g['n1'] if g['turn'] == 'X' else g['n2']
            next_tag = f"@{g['u1']}" if g['turn'] == 'X' and g['u1'] else (f"@{g['u2']}" if g['turn'] == 'O' and g['u2'] else next_name)
            
            await q.edit_message_text(
                f"⚔️ {g['n1']} vs {g['n2']}\n\n👉 NEXT TURN: {next_tag} ({g['turn']})",
                reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN
        )
            

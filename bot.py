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
ADMIN_ID = 6825707797  # Aapki Admin ID

# --- DATABASE ---
users_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        users_col = db['users']
    except: pass

app = Flask('')
@app.route('/')
def home(): return "Bot Fixed with Broadcast! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- STATE ---
games = {} 
rps_games = {}

# --- UTILS ---
def get_xo_markup(board, gid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(board[r][c] if board[r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)])

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # User register for broadcast
    if users_col is not None:
        users_col.update_one({"id": update.effective_user.id}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    await update.message.reply_text("🎮 *Gaming Arena*\n\n/game - Tic Tac Toe\n/rps - Rock Paper Scissors\n/broadcast - Admin Only", parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    gid = f"x{update.message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None}
    await update.message.reply_text(f"🎮 *X-O Match Started!*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]))

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE: return
    rid = f"r{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *RPS Challenge*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"rj_{rid}")]]))

# --- BROADCAST LOGIC ---
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("❌ Sirf Admin hi use kar sakta hai!")
    
    msg_text = " ".join(context.args)
    if not msg_text:
        return await update.message.reply_text("⚠️ Usage: `/broadcast Hello Users`", parse_mode=constants.ParseMode.MARKDOWN)
    
    if users_col is None: return await update.message.reply_text("❌ DB Connected nahi hai!")
    
    all_users = list(users_col.find({}, {"id": 1}))
    sent, failed = 0, 0
    
    status_msg = await update.message.reply_text(f"🚀 Sending to {len(all_users)} users...")
    
    for user in all_users:
        try:
            await context.bot.send_message(user['id'], msg_text)
            sent += 1
            await asyncio.sleep(0.05) # Rate limit safety
        except:
            failed += 1
    
    await status_msg.edit_text(f"✅ *Broadcast Finished!*\n\nSent: `{sent}`\nFailed: `{failed}`", parse_mode=constants.ParseMode.MARKDOWN)

# --- CALLBACK HANDLER ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid, data = q.from_user.id, q.data

    # Logic remains same as previous working version...
    if data.startswith("j_"):
        gid = data.split('_')[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=get_xo_markup(g['board'], gid))
    # ... (Other handlers like m_, rj_, rm_ from pichla code)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    
    # Register All Handlers
    bot.add_handler(CommandHandler("broadcast", broadcast))
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("rps", rps_cmd))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    
    bot.run_polling(drop_pending_updates=True)

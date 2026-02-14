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

# --- DATABASE ---
stats_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
    except: pass

app = Flask('')
@app.route('/')
def home(): return "Bot is Ultra Fast! 🚀"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- LOGIC ---
games = {}

async def delete_message_after(context, chat_id, message_id, delay=120):
    """Auto-delete message after 2 minutes"""
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except: pass

def get_board_markup(board, gid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(board[r][c] if board[r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)]
        for r in range(3)
    ])

def check_winner(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    return None

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎮 *X/O Arena Ready!* 🎮\n\n🚀 /game - Start\n🏆 /leaderboard - Stats\n❓ /help - Guide"
    btns = [[InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO"),
             InlineKeyboardButton("📢 Updates", url="https://t.me/Yonko_Crew")]]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📖 *Help Guide*\n\n1. Add bot to group.\n2. Use /game to start.\n3. Wait for friend to join.\n4. First one to get 3 in a row wins!"
    await update.effective_message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot import get_lb_text # Ensure it's defined or just call direct
    await update.effective_message.reply_text("🏆 Use Buttons in /start for Leaderboard.")

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Use in Groups!")
        return
    gid = str(update.effective_chat.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    await update.message.reply_text(f"🎮 *X-O Match Started!*\n❌: {update.effective_user.first_name}", 
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join", callback_data=f"j_{gid}")]]), 
                                    parse_mode=constants.ParseMode.MARKDOWN)

# --- CALLBACKS ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer() 
    uid, data = q.from_user.id, q.data

    if data.startswith("j_"):
        gid = data.split('_')[1]
        if gid in games and games[gid]['p1'] != uid:
            g = games[gid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"Match: {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=get_board_markup(g['board'], gid))

    elif data.startswith("m_"):
        _, gid, r, c = data.split('_')
        r, c = int(r), int(c)
        if gid not in games: return
        g = games[gid]
        curr_id = g['p1'] if g['turn'] == 'X' else g['p2']
        if uid != curr_id or g['board'][r][c] != " ": return

        g['board'][r][c] = g['turn']
        win = check_winner(g['board'])
        
        if win:
            name = g['n1'] if win == 'X' else g['n2']
            msg = await q.edit_message_text(f"🏆 Winner: {name}!\n\n_This message will delete in 2 minutes._", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)
            if stats_col: stats_col.insert_one({"id": uid, "name": name, "date": datetime.now()})
            del games[gid]
            # Auto-Delete Task
            asyncio.create_task(delete_message_after(context, q.message.chat_id, msg.message_id))
            
        elif all(cell != " " for row in g['board'] for cell in row):
            msg = await q.edit_message_text("🤝 Draw Match!\n\n_Deleting in 2 minutes..._", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)
            del games[gid]
            asyncio.create_task(delete_message_after(context, q.message.chat_id, msg.message_id))
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            next_p = g['n1'] if g['turn'] == 'X' else g['n2']
            await q.edit_message_text(f"Turn: {next_p} ({g['turn']})", reply_markup=get_board_markup(g['board'], gid))

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    bot = ApplicationBuilder().token(TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("game", game_cmd))
    bot.add_handler(CommandHandler("help", help_cmd))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    bot.run_polling(drop_pending_updates=True, poll_interval=0.1)
        

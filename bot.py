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
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
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

# --- SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive! 🚀"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- GAME LOGIC ---
games = {}

def get_board_markup(board, gid):
    # Board state ko buttons mein convert karna
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
    await update.effective_message.reply_text("🎮 *X/O Arena Ready!*\n\nUse /game in groups.", parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Group mein shuru karein!")
        return
    gid = str(update.effective_chat.id)
    # New Game Initialization
    games[gid] = {
        'board': [[" "]*3 for _ in range(3)], 
        'turn': 'X', 
        'p1': update.effective_user.id, 
        'n1': update.effective_user.first_name, 
        'p2': None, 'n2': None
    }
    await update.message.reply_text(
        f"🎮 *X-O Match*\n❌: {update.effective_user.first_name}\n⭕: Waiting...",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]),
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- CALLBACK HANDLER (The Fix) ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data
    
    if data.startswith("j_"):
        gid = data.split('_')[1]
        if gid not in games: 
            await q.answer("Game expired!")
            return
        g = games[gid]
        if g['p1'] == uid:
            await q.answer("Aapne hi game start kiya hai!", show_alert=True)
            return
        if g['p2'] is not None:
            await q.answer("Game full hai!")
            return
        
        g['p2'], g['n2'] = uid, q.from_user.first_name
        await q.edit_message_text(
            f"🎮 *Match Live!*\n❌: {g['n1']}\n⭕: {g['n2']}\n\nTurn: {g['n1']} (X)",
            reply_markup=get_board_markup(g['board'], gid),
            parse_mode=constants.ParseMode.MARKDOWN
        )

    elif data.startswith("m_"):
        _, gid, r, c = data.split('_')
        r, c = int(r), int(c)
        if gid not in games: return
        g = games[gid]

        # Player check
        current_id = g['p1'] if g['turn'] == 'X' else g['p2']
        if uid != current_id:
            await q.answer("Abhi aapki turn nahi hai!", show_alert=True)
            return
        
        if g['board'][r][c] != " ":
            await q.answer("Ye box pehle se bhara hai!")
            return

        # Update Board
        g['board'][r][c] = g['turn']
        winner = check_winner(g['board'])
        
        if winner:
            winner_name = g['n1'] if winner == 'X' else g['n2']
            await q.edit_message_text(
                f"🏆 *Match Over!*\nWinner: {winner_name} ({winner})",
                reply_markup=get_board_markup(g['board'], gid),
                parse_mode=constants.ParseMode.MARKDOWN
            )
            del games[gid]
        elif all(cell != " " for row in g['board'] for cell in row):
            await q.edit_message_text("🤝 *Draw Match!*", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            next_name = g['n1'] if g['turn'] == 'X' else g['n2']
            await q.edit_message_text(
                f"Match: {g['n1']} vs {g['n2']}\nTurn: {next_name} ({g['turn']})",
                reply_markup=get_board_markup(g['board'], gid)
            )
    await q.answer()

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # DROP PENDING UPDATES is must to avoid 409 Conflict
    application.run_polling(drop_pending_updates=True)
        

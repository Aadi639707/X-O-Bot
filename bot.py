import os
import logging
import asyncio
from datetime import datetime, timedelta
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
        logger.info("MongoDB Connected Successfully! ✅")
    except Exception as e: 
        logger.error(f"MongoDB Error: {e}")

# --- SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home(): return "X/O Bot is Online & English Mode Active! 🚀"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- LOGIC ---
games = {}

def get_lb_text(mode="global"):
    if stats_col is None: return "❌ Database connection error!"
    now = datetime.now()
    query = {}
    if mode == "today": 
        query = {"date": {"$gte": now.replace(hour=0, minute=0, second=0, microsecond=0)}}
    elif mode == "week": 
        query = {"date": {"$gte": now - timedelta(days=7)}}

    # Aggregation to get winner names and counts correctly
    pipeline = [
        {"$match": query}, 
        {"$group": {"_id": "$id", "name": {"$first": "$name"}, "count": {"$sum": 1}}}, 
        {"$sort": {"count": -1}}, 
        {"$limit": 10}
    ]
    results = list(stats_col.aggregate(pipeline))
    
    if not results: return f"🏆 *{mode.upper()} LEADERBOARD*\n\nNo records found yet! 🔥"
    
    text = f"🎊 *TOP PLAYERS - {mode.upper()}* 🎊\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['count']} Wins`\n"
    return text

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
    text = (
        "🎮 *Welcome to X/O Arena!* 🎮\n\n"
        "Play the ultimate Tic-Tac-Toe match here.\n\n"
        "🚀 /game - Start a Group Match\n"
        "🏆 /leaderboard - Check Top Players\n"
        "ℹ️ /help - Game Instructions"
    )
    btns = [
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO"),
         InlineKeyboardButton("📢 Updates", url="https://t.me/Yonko_Crew")]
    ]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btns = [[InlineKeyboardButton("Today", callback_data="lb_today"), 
             InlineKeyboardButton("Global", callback_data="lb_global")]]
    await update.effective_message.reply_text(get_lb_text("global"), reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Please use this command in a group chat!")
        return
    gid = str(update.effective_chat.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    await update.message.reply_text(
        f"🎮 *X-O Match Started!*\n❌ Player: {update.effective_user.first_name}\n\nWaiting for Player 2 to join...", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]])), 
        parse_mode=constants.ParseMode.MARKDOWN
    )

# --- CALLBACKS ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer() 
    uid, data = q.from_user.id, q.data

    if data.startswith("lb_"):
        mode = data.split("_")[1]
        await q.edit_message_text(get_lb_text(mode), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="lb_global")]]), parse_mode=constants.ParseMode.MARKDOWN)

    elif data.startswith("j_"):
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
            winner_name = g['n1'] if win == 'X' else g['n2']
            await q.edit_message_text(f"🏆 Match Winner: {winner_name}!", reply_markup=get_board_markup(g['board'], gid))
            # LEADERBOARD FIX: Saving win data
            if stats_col is not None:
                stats_col.insert_one({"id": uid, "name": winner_name, "date": datetime.now()})
            del games[gid]
        elif all(cell != " " for row in g['board'] for cell in row):
            await q.edit_message_text("🤝 Match Draw!", reply_markup=get_board_markup(g['board'], gid))
            del games[gid]
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
    bot.add_handler(CommandHandler("leaderboard", lb_cmd))
    bot.add_handler(CallbackQueryHandler(handle_callback))
    
    bot.run_polling(drop_pending_updates=True, poll_interval=0.1)

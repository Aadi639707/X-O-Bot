import os
import logging
import asyncio
from datetime import datetime, timedelta
from flask import Flask, request
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIG ---
TOKEN = os.environ.get("TOKEN")
URL = os.environ.get("RENDER_EXTERNAL_URL") 
PORT = int(os.environ.get("PORT", 8080))
MONGO_URL = os.environ.get("MONGO_URL")

# --- DATABASE CONNECTION ---
stats_col = None
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
        logger.info("MongoDB Connected Successfully!")
    except Exception as e: 
        logger.error(f"MongoDB Connection Failed: {e}")

# --- APP SETUP ---
app = Flask(__name__)
ptb_app = Application.builder().token(TOKEN).build()
games = {}

# --- HELPER FUNCTIONS ---
def save_win(user_id, name):
    if stats_col is not None:
        stats_col.insert_one({"id": user_id, "name": name, "date": datetime.now()})

def get_lb_text(mode="global"):
    if stats_col is None: return "❌ Database not connected!"
    now = datetime.now()
    query = {}
    if mode == "today": query = {"date": {"$gte": now.replace(hour=0, minute=0, second=0)}}
    elif mode == "week": query = {"date": {"$gte": now - timedelta(days=7)}}
    elif mode == "month": query = {"date": {"$gte": now - timedelta(days=30)}}

    pipeline = [
        {"$match": query}, 
        {"$group": {"_id": "$id", "name": {"$first": "$name"}, "count": {"$sum": 1}}}, 
        {"$sort": {"count": -1}}, 
        {"$limit": 10}
    ]
    results = list(stats_col.aggregate(pipeline))
    if not results: return f"🏆 *{mode.upper()} LEADERBOARD*\n\nNo records yet! 🔥"
    
    text = f"🎊 *TOP PLAYERS - {mode.upper()}* 🎊\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['count']} Wins`\n"
    return text

def get_board_markup(board, gid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(board[r][c] if board[r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)])

def check_winner(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    return None

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_user = context.bot.username
    text = (
        "🎮 ✨ *X/O Gaming Bot* ✨ 🎮\n\n"
        "Your Ultimate Tic-Tac-Toe Arena ⚡\n"
        "API 8.0 Colorful Styles Active! 🎨\n\n"
        "🚀 *Commands:*\n"
        "🔹 /game - Start Match\n"
        "🔹 /leaderboard - View Stats\n"
        "🔹 /help - Bot Guide"
    )
    btns = [
        [InlineKeyboardButton("➕ Add Me", url=f"https://t.me/{bot_user}?startgroup=true")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global"),
         InlineKeyboardButton("❓ Help", callback_data="h")],
        [InlineKeyboardButton("📢 Channel", url="https://t.me/Yonko_Crew"),
         InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]
    ]
    msg = update.message if update.message else update.callback_query.message
    await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Please use this command in a group!")
        return
    gid = str(update.effective_chat.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    await update.message.reply_text(
        f"🎮 *X-O Challenge*\n❌: {update.effective_user.first_name}\n\nWaiting for Player 2...", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Join Now", callback_data=f"j_{gid}")]]), 
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lb_btns = [
        [InlineKeyboardButton("Today", callback_data="lb_today"), InlineKeyboardButton("Week", callback_data="lb_week")],
        [InlineKeyboardButton("Month", callback_data="lb_month"), InlineKeyboardButton("Global", callback_data="lb_global")]
    ]
    await update.effective_message.reply_text(get_lb_text("global"), reply_markup=InlineKeyboardMarkup(lb_btns), parse_mode=constants.ParseMode.MARKDOWN)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📖 *Help Menu*\n\n/game - Start Match\n/leaderboard - See Rankings\n/start - Main Menu"
    await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)

# --- CALLBACK HANDLER ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid, data = q.from_user.id, q.data
    await q.answer()

    if data.startswith("lb_"):
        mode = data.split("_")[1]
        lb_btns = [[InlineKeyboardButton("Today", callback_data="lb_today"), InlineKeyboardButton("Week", callback_data="lb_week")],
                   [InlineKeyboardButton("Month", callback_data="lb_month"), InlineKeyboardButton("Global", callback_data="lb_global")],
                   [InlineKeyboardButton("🔙 Back", callback_data="bk")]]
        await q.edit_message_text(get_lb_text(mode), reply_markup=InlineKeyboardMarkup(lb_btns), parse_mode=constants.ParseMode.MARKDOWN)
    
    elif data == "bk":
        await q.message.delete()
        await start(update, context)

    elif data.startswith("j_"):
        gid = data.split('_')[1]
        if gid not in games: return
        g = games[gid]
        if g['p1'] == uid: return
        g['p2'], g['n2'] = uid, q.from_user.first_name
        await q.edit_message_text(f"🎮 *Match Live!*\n❌: {g['n1']}\n⭕: {g['n2']}\n\nTurn: {g['n1']} (X)", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)

    elif data.startswith("m_"):
        _, gid, r, c = data.split('_')
        if gid not in games: return
        g, r, c = games[gid], int(r), int(c)
        current_p = g['p1'] if g['turn'] == 'X' else g['p2']
        if uid != current_p or g['board'][r][c] != " ": return
        g['board'][r][c] = g['turn']
        win = check_winner(g['board'])
        if win:
            await q.edit_message_text(f"🏆 *{g['n1'] if win == 'X' else g['n2']} Won!*", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)
            save_win(uid, g['n1'] if win == 'X' else g['n2'])
            del games[gid]
        elif all(cell != " " for row in g['board'] for cell in row):
            await q.edit_message_text("🤝 *Draw!*", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            next_name = g['n2'] if g['turn'] == 'O' else g['n1']
            await q.edit_message_text(f"🎮 *Match Live!*\n❌: {g['n1']}\n⭕: {g['n2']}\n\nTurn: {next_name} ({g['turn']})", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)

# --- WEBHOOK & APP ENGINE ---

@app.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    asyncio.run_coroutine_threadsafe(ptb_app.process_update(update), loop)
    return "OK", 200

@app.route("/")
def index(): return "X/O Bot is Live! 🚀"

async def init_bot():
    await ptb_app.initialize()
    await ptb_app.start()
    await ptb_app.bot.set_webhook(url=f"{URL}/{TOKEN}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_bot())
    
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CommandHandler("game", game_cmd))
    ptb_app.add_handler(CommandHandler("leaderboard", lb_cmd))
    ptb_app.add_handler(CommandHandler("help", help_cmd))
    ptb_app.add_handler(CallbackQueryHandler(handle_callback))
    
    app.run(host="0.0.0.0", port=PORT)
    

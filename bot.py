import os
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MONGO DB SETUP ---
MONGO_URL = os.environ.get("MONGO_URL")
stats_col = None

if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        client.server_info() # Check connection
        db = client['xo_gaming_db']
        stats_col = db['wins']
        logger.info("MongoDB Connected Successfully!")
    except Exception as e:
        logger.error(f"MongoDB Connection Failed: {e}")
else:
    logger.warning("MONGO_URL not found! Leaderboard will not work.")

def save_win(user_id, name):
    if stats_col is not None:
        stats_col.insert_one({"id": user_id, "name": name, "date": datetime.now()})

def get_leaderboard(mode="global"):
    if stats_col is None:
        return "❌ Leaderboard is temporarily unavailable (DB Not Connected)."
    
    now = datetime.now()
    query = {}
    if mode == "today":
        query = {"date": {"$gte": now.replace(hour=0, minute=0, second=0, microsecond=0)}}
    elif mode == "week":
        query = {"date": {"$gte": now - timedelta(days=7)}}
    elif mode == "month":
        query = {"date": {"$gte": now - timedelta(days=30)}}

    pipeline = [
        {"$match": query},
        {"$group": {"_id": "$id", "name": {"$first": "$name"}, "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    results = list(stats_col.aggregate(pipeline))
    
    if not results:
        return f"🏆 *{mode.upper()} LEADERBOARD*\n\nNo records found! Be the first to win! 🔥"
    
    text = f"🎊 *TOP PLAYERS - {mode.upper()}* 🎊\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['count']} Wins`\n"
    return text

# --- FAKE SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- START INTERFACE (PREMIUM LOOK) ---
def start(update: Update, context: CallbackContext):
    msg = update.message if update.message else update.callback_query.message
    bot_user = context.bot.username
    
    start_text = (
        "🎮 ✨ *Welcome to X/O Gaming Bot* ✨ 🎮\n\n"
        "Your Ultimate Tic-Tac-Toe Arena ⚡\n"
        "Play in groups with *Zero Lag* and *Anti-Edit Protection* 🛡️\n\n"
        "🚀 *Features:*\n"
        "🏆 Real-time Leaderboards (Today/Week/Global)\n"
        "🤝 Smooth Multiplayer Interface\n\n"
        "Invite me to your group & start the challenge! 🔥"
    )
    
    btns = [
        [InlineKeyboardButton("➕ Add Me", url=f"https://t.me/{bot_user}?startgroup=true"),
         InlineKeyboardButton("📞 Support", url="https://t.me/Yonko_Crew")],
        [InlineKeyboardButton("📖 Help", callback_data="h"),
         InlineKeyboardButton("🔄 Refresh", callback_data="bk")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]
    ]
    
    msg.reply_text(text=start_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

# --- GAME LOGIC (Rest is same but included for completeness) ---
games = {}

def get_board_markup(board, game_id):
    keyboard = []
    for r in range(3):
        row = []
        for c in range(3):
            text = board[r][c] if board[r][c] != " " else "·"
            row.append(InlineKeyboardButton(text, callback_data=f"m_{game_id}_{r}_{c}"))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def check_winner(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    return None

def handle_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    uid, data = q.from_user.id, q.data

    if data.startswith("lb_"):
        mode = data.split("_")[1]
        lb_btns = [
            [InlineKeyboardButton("📅 Today", callback_data="lb_today"), InlineKeyboardButton("🗓️ Week", callback_data="lb_week")],
            [InlineKeyboardButton("📊 Month", callback_data="lb_month"), InlineKeyboardButton("🌎 Global", callback_data="lb_global")],
            [InlineKeyboardButton("🔙 Back", callback_data="bk")]
        ]
        q.edit_message_text(get_leaderboard(mode), reply_markup=InlineKeyboardMarkup(lb_btns), parse_mode='Markdown')
    elif data == "bk":
        q.message.delete()
        start(update, context)
    elif data == "h":
        q.edit_message_text("📖 *Help*\n\nUse /game in groups to play.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="bk")]]), parse_mode='Markdown')
    elif data.startswith("j_") or data.startswith("m_"):
        action, gid = data.split('_')[0], data.split('_')[1]
        if gid not in games: return
        g = games[gid]
        if action == "j":
            if g['p1'] == uid: return
            g['p2'], g['n2'] = uid, q.from_user.first_name
            q.edit_message_reply_markup(get_board_markup(g['board'], gid))
        elif action == "m":
            r, c = int(data.split('_')[2]), int(data.split('_')[3])
            p = g['p1'] if g['turn'] == 'X' else g['p2']
            if uid != p or g['board'][r][c] != " ": return
            g['board'][r][c] = g['turn']
            win = check_winner(g['board'])
            if win:
                q.edit_message_reply_markup(get_board_markup(g['board'], gid))
                w_name = g['n1'] if win == 'X' else g['n2']
                save_win(uid, w_name)
                context.bot.send_message(q.message.chat_id, f"🏆 {w_name} won!")
                del games[gid]
            elif all(cell != " " for row in g['board'] for cell in row):
                q.edit_message_reply_markup(get_board_markup(g['board'], gid))
                context.bot.send_message(q.message.chat_id, "🤝 Draw!")
                del games[gid]
            else:
                g['turn'] = 'O' if g['turn'] == 'X' else 'X'
                q.edit_message_reply_markup(get_board_markup(g['board'], gid))

def game_cmd(update: Update, context: CallbackContext):
    if update.effective_chat.type == "private": return
    gid = f"{update.effective_chat.id}{update.effective_message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    update.message.reply_text(f"🎮 *X-O Challenge*\n❌: {update.effective_user.first_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join 🚀", callback_data=f"j_{gid}")]]), parse_mode='Markdown')

def main():
    token = os.environ.get("TOKEN")
    updater = Updater(token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game_cmd))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    keep_alive()
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
    

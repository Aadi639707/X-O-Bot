import os
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Logging setup
logging.basicConfig(level=logging.INFO)

# --- MONGO DB SETUP ---
MONGO_URL = os.environ.get("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client['xo_bot_db']
stats_col = db['wins']

def save_win(user_id, name):
    stats_col.insert_one({
        "id": user_id,
        "name": name,
        "date": datetime.now()
    })

def get_leaderboard(mode="global"):
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
        return f"🏆 *{mode.upper()} LEADERBOARD*\n\nNo records found! Start playing now! 🔥"
    
    text = f"🎊 *TOP PLAYERS - {mode.upper()}* 🎊\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['count']} Wins`\n"
    return text

# --- FAKE SERVER ---
app = Flask('')
@app.route('/')
def home(): return "X/O Premium Bot is Live!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    Thread(target=run).start()

# --- START INTERFACE (PREMIUM LOOK) ---

def start(update: Update, context: CallbackContext):
    msg = update.message if update.message else update.callback_query.message
    bot_user = context.bot.username
    
    # Premium Interface jaisa aapne screenshot me dikhaya
    start_text = (
        "🎮 ✨ *Welcome to X/O Gaming Bot* ✨ 🎮\n\n"
        "Your Ultimate Tic-Tac-Toe Arena ⚡\n"
        "Play with friends in groups with *Zero Lag* and *Anti-Edit Protection* 🛡️\n\n"
        "🚀 *Features:*\n"
        "🏆 Real-time Global Leaderboards\n"
        "🤝 Smooth Multiplayer Interface\n"
        "🛡️ Protection against Message Deletion\n\n"
        "💪 *Community deserves real fun!*\n"
        "Invite me to your group & start the challenge!"
    )
    
    btns = [
        [InlineKeyboardButton("➕ Add Me", url=f"https://t.me/{bot_user}?startgroup=true"),
         InlineKeyboardButton("📞 Support", url="https://t.me/Yonko_Crew")],
        [InlineKeyboardButton("📖 Help", callback_data="h"),
         InlineKeyboardButton("🔄 Refresh", callback_data="bk")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global")],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]
    ]
    
    msg.reply_text(
        text=start_text,
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode='Markdown'
    )

def handle_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    uid, data = q.from_user.id, q.data

    if data.startswith("lb_"):
        mode = data.split("_")[1]
        lb_btns = [
            [InlineKeyboardButton("📅 Today", callback_data="lb_today"), InlineKeyboardButton("🗓️ Week", callback_data="lb_week")],
            [InlineKeyboardButton("📊 Month", callback_data="lb_month"), InlineKeyboardButton("🌎 Global", callback_data="lb_global")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="bk")]
        ]
        q.edit_message_text(get_leaderboard(mode), reply_markup=InlineKeyboardMarkup(lb_btns), parse_mode='Markdown')
    
    elif data == "bk":
        q.message.delete()
        start(update, context)

    elif data == "h":
        h_text = "📖 *X/O BOT COMMANDS*\n\n🔹 `/game` - Start game in any group\n🔹 `/start` - Open this menu\n\nEnjoy gaming! 🎮"
        q.edit_message_text(h_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="bk")]]), parse_mode='Markdown')

    elif data.startswith("j_") or data.startswith("m_"):
        # ... (Game logic remains same as previous optimized version)
        action, g_id = data.split('_')[0], data.split('_')[1]
        if g_id not in games: return
        g = games[g_id]
        if action == "j":
            if g['p1'] == uid: return
            g['p2'], g['n2'] = uid, q.from_user.first_name
            q.edit_message_reply_markup(get_board_markup(g['board'], g_id))
        elif action == "m":
            # ... (Existing move logic)
            pass

def game_cmd(update: Update, context: CallbackContext):
    if update.effective_chat.type == "private":
        update.message.reply_text("❌ Please add me to a group to play!")
        return
    gid = f"{update.effective_chat.id}{update.effective_message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    update.message.reply_text(f"🎮 *X-O CHALLENGE*\n\n❌ Player 1: {update.effective_user.first_name}\n⭕ Player 2: Waiting...", 
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Join Now", callback_data=f"j_{gid}")]]), 
                              parse_mode='Markdown')

# Rest of the functions (check_winner, get_board_markup, main) stay the same...

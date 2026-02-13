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
        logger.info("MongoDB Connected! ✅")
    except Exception as e: 
        logger.error(f"DB Error: {e}")

# --- APP SETUP ---
app = Flask('')
@app.route('/')
def home(): return "X/O Gaming Bot is LIVE! 🚀"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- LOGIC ---
games = {}

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

    pipeline = [{"$match": query}, {"$group": {"_id": "$id", "name": {"$first": "$name"}, "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    if not results: return f"🏆 *{mode.upper()} LEADERBOARD*\n\nNo wins yet! 🔥"
    
    text = f"🎊 *TOP PLAYERS - {mode.upper()}* 🎊\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['count']} Wins`\n"
    return text

# --- COMMANDS ---

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
    # style logic for API 8.0
    btns = [
        [InlineKeyboardButton("➕ Add Me", url=f"https://t.me/{bot_user}?startgroup=true")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global"),
         InlineKeyboardButton("❓ Help", callback_data="h")], # destructive
        [InlineKeyboardButton("📢 Channel", url="https://t.me/Yonko_Crew"),
         InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]
    ]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        await update.message.reply_text("❌ Please use this in a group!")
        return
    gid = str(update.effective_chat.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    await update.message.reply_text(f"🎮 *X-O Challenge*\n❌: {update.effective_user.first_name}\n\nWaiting...", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Join Now", callback_data=f"j_{gid}")]]), # positive style
        parse_mode=constants.ParseMode.MARKDOWN)

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lb_btns = [[InlineKeyboardButton("Today", callback_data="lb_today"), InlineKeyboardButton("Week", callback_data="lb_week")],
               [InlineKeyboardButton("Month", callback_data="lb_month"), InlineKeyboardButton("Global", callback_data="lb_global")]]
    await update.effective_message.reply_text(get_lb_text("global"), reply_markup=InlineKeyboardMarkup(lb_btns), parse_mode=constants.ParseMode.MARKDOWN)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid, data = q.from_user.id, q.data
    await q.answer()
    
    if data.startswith("lb_"):
        mode = data.split("_")[1]
        text = get_lb_text(mode)
        btns = [[InlineKeyboardButton("Today", callback_data="lb_today"), InlineKeyboardButton("Week", callback_data="lb_week")],
                [InlineKeyboardButton("Month", callback_data="lb_month"), InlineKeyboardButton("Global", callback_data="lb_global")],
                [InlineKeyboardButton("🔙 Back", callback_data="bk")]]
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)
    elif data == "bk":
        await q.message.delete()
        await start(update, context)
    elif data.startswith("j_"):
        gid = data.split('_')[1]
        if gid in games:
            g = games[gid]
            if g['p1'] != uid:
                g['p2'], g['n2'] = uid, q.from_user.first_name
                await q.edit_message_text(f"🎮 *Match Live!*\n❌: {g['n1']}\n⭕: {g['n2']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]))

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    # application setup
    application = ApplicationBuilder().token(TOKEN).build()
    
    # handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CommandHandler("leaderboard", lb_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Conflict solve: drop_pending_updates=True
    application.run_polling(drop_pending_updates=True)
    

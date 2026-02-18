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
def home(): return "Bot is Fully Active! 🚀"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- LOGIC ---
games = {}
rps_games = {}

async def delete_msg(context, chat_id, message_id):
    await asyncio.sleep(120)
    try: await context.bot.delete_message(chat_id, message_id)
    except: pass

def get_lb_text(mode="global"):
    if stats_col is None: return "❌ DB Error!"
    now = datetime.now()
    query = {}
    if mode == "today": query = {"date": {"$gte": now.replace(hour=0, minute=0, second=0, microsecond=0)}}
    pipeline = [{"$match": query}, {"$group": {"_id": "$id", "name": {"$first": "$name"}, "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    if not results: return f"🏆 *{mode.upper()} LEADERBOARD*\n\nEmpty! 🔥"
    text = f"🎊 *TOP PLAYERS - {mode.upper()}* 🎊\n\n"
    for i, user in enumerate(results):
        text += f"{i+1}. {user['name']} — `{user['count']} Wins`\n"
    return text

# --- COMMAND HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if users_col is not None:
        users_col.update_one({"id": update.effective_user.id}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    text = "🎮 *Gaming Arena* 🎮\n\n🚀 /game - X-O\n🥊 /rps - Rock Paper Scissors\n🏆 /leaderboard - Stats"
    btns = [[InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global")],
            [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def lb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btns = [[InlineKeyboardButton("Today", callback_data="lb_today"), InlineKeyboardButton("Global", callback_data="lb_global")]]
    await update.effective_message.reply_text(get_lb_text("global"), reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return await update.message.reply_text("❌ Use in Groups!")
    rid = f"{update.effective_chat.id}_{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *Rock Paper Scissors*\nChallenge by: {update.effective_user.first_name}", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"rj_{rid}")]]), parse_mode=constants.ParseMode.MARKDOWN)

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg_text = " ".join(context.args)
    if not msg_text: return await update.message.reply_text("Usage: /broadcast [text]")
    users = list(users_col.find({}, {"id": 1}))
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(u['id'], msg_text)
            sent += 1
            await asyncio.sleep(0.1)
        except: pass
    await update.message.reply_text(f"✅ Sent to {sent} users.")

# --- CALLBACKS (Logic for all buttons) ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid, data = q.from_user.id, q.data

    if data.startswith("rj_"):
        rid = data.split('_', 1)[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid:
            g = rps_games[rid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            btns = [[InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"),
                     InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"),
                     InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]]
            await q.edit_message_text(f"🥊 Match: {g['n1']} vs {g['n2']}\nChoose your move!", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("rm_"):
        _, rid, move = data.split('_')
        if rid not in rps_games: return
        g = rps_games[rid]
        if uid == g['p1'] and not g['m1']: g['m1'] = move
        elif uid == g['p2'] and not g['m2']: g['m2'] = move
        else: return
        
        if g['m1'] and g['m2']:
            m1, m2 = g['m1'], g['m2']
            win_id, win_name = None, None
            if m1 == m2: res = "🤝 It's a DRAW!"
            elif (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'): win_id, win_name = g['p1'], g['n1']
            else: win_id, win_name = g['p2'], g['n2']
            
            final = f"🥊 *Rock Paper Scissors Result*\n{g['n1']}: {m1} | {g['n2']}: {m2}\n\n"
            if win_id:
                final += f"🏆 Winner: {win_name}!"
                if stats_col: stats_col.insert_one({"id": win_id, "name": win_name, "date": datetime.now()})
            else: final += res
            msg = await q.edit_message_text(final + "\n\n_Deleting in 2m..._")
            del rps_games[rid]
            asyncio.create_task(delete_msg(context, q.message.chat_id, msg.message_id))

    elif data.startswith("lb_"):
        await q.edit_message_text(get_lb_text(data.split("_")[1]), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="lb_global")]]), parse_mode=constants.ParseMode.MARKDOWN)

# (Add X-O Join and Move handlers here too)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    app_bot = ApplicationBuilder().token(TOKEN).build()
    
    # Handlers Registration (ORDER MATTERS)
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("game", start)) # Temporarily linking to test
    app_bot.add_handler(CommandHandler("rps", rps_cmd))
    app_bot.add_handler(CommandHandler("leaderboard", lb_cmd))
    app_bot.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app_bot.add_handler(CallbackQueryHandler(handle_callback))
    
    app_bot.run_polling(drop_pending_updates=True, poll_interval=0.1)
    

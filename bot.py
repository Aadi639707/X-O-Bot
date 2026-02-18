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
        logger.info("MongoDB Connected! ✅")
    except Exception as e:
        logger.error(f"DB Error: {e}")

# --- SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Ultra Fast & Alive! ⚡"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- LOGIC ---
games = {}
rps_games = {}

async def delete_msg(context, chat_id, message_id):
    await asyncio.sleep(120) # 2 minutes delete timer
    try:
        await context.bot.delete_message(chat_id, message_id)
    except: pass

def get_lb_text(mode="global"):
    if stats_col is None: return "❌ Database connection issue!"
    now = datetime.now()
    query = {}
    if mode == "today": 
        query = {"date": {"$gte": now.replace(hour=0, minute=0, second=0, microsecond=0)}}
    pipeline = [{"$match": query}, {"$group": {"_id": "$id", "name": {"$first": "$name"}, "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}]
    results = list(stats_col.aggregate(pipeline))
    if not results: return f"🏆 *{mode.upper()} LEADERBOARD*\n\nNo records yet! 🔥"
    text = f"🎊 *TOP PLAYERS - {mode.upper()}* 🎊\n\n"
    emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(results):
        text += f"{emojis[i]} {user['name']} — `{user['count']} Wins`\n"
    return text

def get_board_markup(board, gid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(board[r][c] if board[r][c] != " " else "·", callback_data=f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)])

def get_rps_markup(rid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"), InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"), InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]])

def check_winner(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    return None

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if users_col is not None:
        users_col.update_one({"id": update.effective_user.id}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    text = "🎮 *Welcome to Gaming Arena!* 🎮\n\n🚀 /game - Start X-O\n🥊 /rps - Start Rock Paper Scissors\n🏆 /leaderboard - View Stats"
    btns = [[InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global")], [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

async def game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return await update.message.reply_text("❌ Use this in Groups!")
    gid = str(update.effective_chat.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'u1': update.effective_user.username, 'p2': None}
    await update.message.reply_text(f"🎮 *X-O Match Started!*\n❌ Player: {update.effective_user.first_name}\n\nWaiting for Player 2...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"j_{gid}")]]), parse_mode=constants.ParseMode.MARKDOWN)

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return await update.message.reply_text("❌ Use this in Groups!")
    rid = f"{update.effective_chat.id}_{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *Rock Paper Scissors*\nChallenge by: {update.effective_user.first_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"rj_{rid}")]]), parse_mode=constants.ParseMode.MARKDOWN)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    msg_text = " ".join(context.args)
    if not msg_text: return await update.message.reply_text("Usage: /broadcast [text]")
    users = list(users_col.find({}, {"id": 1}))
    sent = 0
    for u in users:
        try:
            await context.bot.send_message(u['id'], msg_text)
            sent += 1
            await asyncio.sleep(0.05)
        except: pass
    await update.message.reply_text(f"✅ Sent to {sent} users.")

# --- CALLBACK HANDLER ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid, data = q.from_user.id, q.data

    # --- RPS HANDLERS ---
    if data.startswith("rj_"):
        await q.answer("Joining Match...")
        rid = data.split('_', 1)[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid:
            g = rps_games[rid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"🥊 *Match Live!*\n👤 {g['n1']}: ⏳ Thinking...\n👤 {g['n2']}: ⏳ Thinking...\n\nChoose your move below!", reply_markup=get_rps_markup(rid), parse_mode=constants.ParseMode.MARKDOWN)

    elif data.startswith("rm_"):
        await q.answer("Move Recorded! ✅")
        _, rid, move = data.split('_')
        if rid not in rps_games: return
        g = rps_games[rid]
        if uid == g['p1'] and not g['m1']: g['m1'] = move
        elif uid == g['p2'] and not g['m2']: g['m2'] = move
        else: return

        if g['m1'] and g['m2']:
            m1, m2 = g['m1'], g['m2']
            names = {"R": "🪨 Rock", "P": "📄 Paper", "S": "✂️ Scissors"}
            win_id, win_name = None, None
            if m1 == m2: res = "🤝 It's a DRAW!"
            elif (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'): win_id, win_name = g['p1'], g['n1']
            else: win_id, win_name = g['p2'], g['n2']
            
            final = f"🥊 *RPS Result*\n👤 {g['n1']}: {names[m1]}\n👤 {g['n2']}: {names[m2]}\n\n"
            if win_id:
                final += f"🏆 Winner: {win_name}!"
                if stats_col: stats_col.insert_one({"id": win_id, "name": win_name, "date": datetime.now()})
            else: final += res
            msg = await q.edit_message_text(final + "\n\n_Deleting in 2m..._", parse_mode=constants.ParseMode.MARKDOWN)
            del rps_games[rid]
            asyncio.create_task(delete_msg(context, q.message.chat_id, msg.message_id))
        else:
            s1 = "✅ Ready" if g['m1'] else "⏳ Thinking..."
            s2 = "✅ Ready" if g['m2'] else "⏳ Thinking..."
            await q.edit_message_text(f"🥊 *Match in Progress!*\n👤 {g['n1']}: {s1}\n👤 {g['n2']}: {s2}", reply_markup=get_rps_markup(rid), parse_mode=constants.ParseMode.MARKDOWN)

    # --- X-O HANDLERS ---
    elif data.startswith("j_"):
        await q.answer()
        gid = data.split('_')[1]
        if gid in games and games[gid]['p1'] != uid:
            g = games[gid]
            g['p2'], g['n2'], g['u2'] = uid, q.from_user.first_name, q.from_user.username
            tag = f"@{g['u1']}" if g['u1'] else g['n1']
            await q.edit_message_text(f"⚔️ Match Live!\n❌ {g['n1']} vs ⭕ {g['n2']}\n\n👉 TURN: {tag} (X)", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)

    elif data.startswith("m_"):
        await q.answer()
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
            msg = await q.edit_message_text(f"🏆 Winner: {name}!\n\n_Deleting in 2m..._", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)
            if stats_col: stats_col.insert_one({"id": uid, "name": name, "date": datetime.now()})
            del games[gid]
            asyncio.create_task(delete_msg(context, q.message.chat_id, msg.message_id))
        elif all(cell != " " for row in g['board'] for cell in row):
            msg = await q.edit_message_text("🤝 Draw Match!", reply_markup=get_board_markup(g['board'], gid))
            del games[gid]
            asyncio.create_task(delete_msg(context, q.message.chat_id, msg.message_id))
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            tag = f"@{g['u1']}" if g['turn'] == 'X' and g['u1'] else (f"@{g['u2']}" if g['turn'] == 'O' and g['u2'] else (g['n1'] if g['turn'] == 'X' else g['n2']))
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\n\n👉 TURN: {tag} ({g['turn']})", reply_markup=get_board_markup(g['board'], gid), parse_mode=constants.ParseMode.MARKDOWN)

    elif data.startswith("lb_"):
        await q.answer()
        await q.edit_message_text(get_lb_text(data.split("_")[1]), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="lb_global")]]), parse_mode=constants.ParseMode.MARKDOWN)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("game", game_cmd))
    application.add_handler(CommandHandler("rps", rps_cmd))
    application.add_handler(CommandHandler("leaderboard", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling(drop_pending_updates=True, poll_interval=0.1)
    

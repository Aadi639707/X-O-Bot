import os
import logging
import asyncio
from datetime import datetime
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
if MONGO_URL:
    try:
        client = MongoClient(MONGO_URL)
        db = client['xo_premium_db']
        stats_col = db['wins']
    except: pass

app = Flask('')
@app.route('/')
def home(): return "RPS Ultra Logic Active! 🥊"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- LOGIC ---
rps_games = {}

async def delete_msg(context, chat_id, message_id):
    await asyncio.sleep(120)
    try: await context.bot.delete_message(chat_id, message_id)
    except: pass

def get_rps_markup(rid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪨 Rock", callback_data=f"rm_{rid}_R"),
         InlineKeyboardButton("📄 Paper", callback_data=f"rm_{rid}_P"),
         InlineKeyboardButton("✂️ Scissors", callback_data=f"rm_{rid}_S")]
    ])

# --- COMMANDS ---

async def rps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == constants.ChatType.PRIVATE:
        return await update.message.reply_text("❌ Use in Groups!")
    rid = f"{update.effective_chat.id}_{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *Rock Paper Scissors*\nChallenge by: {update.effective_user.first_name}\n\nWaiting for opponent...", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"rj_{rid}")]]), parse_mode=constants.ParseMode.MARKDOWN)

# --- CALLBACKS ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid, data = q.from_user.id, q.data

    if data.startswith("rj_"):
        await q.answer("Joining Match...")
        rid = data.split('_', 1)[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid:
            g = rps_games[rid]
            g['p2'], g['n2'] = uid, q.from_user.first_name
            await q.edit_message_text(f"🥊 *Match Live!*\n\n👤 {g['n1']}: Waiting...\n👤 {g['n2']}: Waiting...\n\nChoose your move below!", reply_markup=get_rps_markup(rid), parse_mode=constants.ParseMode.MARKDOWN)

    elif data.startswith("rm_"):
        _, rid, move = data.split('_')
        if rid not in rps_games: 
            return await q.answer("Game Expired!", show_alert=True)
        
        g = rps_games[rid]
        if uid != g['p1'] and uid != g['p2']:
            return await q.answer("You are not in this game!", show_alert=True)

        if uid == g['p1']:
            if g['m1']: return await q.answer("You already moved!", show_alert=True)
            g['m1'] = move
            await q.answer("Move Recorded! ✅")
        elif uid == g['p2']:
            if g['m2']: return await q.answer("You already moved!", show_alert=True)
            g['m2'] = move
            await q.answer("Move Recorded! ✅")

        # Update board to show who has moved
        s1 = "✅ Ready" if g['m1'] else "⏳ Thinking..."
        s2 = "✅ Ready" if g['m2'] else "⏳ Thinking..."
        
        if g['m1'] and g['m2']:
            # REVEAL RESULTS
            m1, m2 = g['m1'], g['m2']
            names = {"R": "🪨 Rock", "P": "📄 Paper", "S": "✂️ Scissors"}
            win_id, win_name = None, None
            
            if m1 == m2: res = "🤝 It's a DRAW!"
            elif (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'):
                win_id, win_name = g['p1'], g['n1']
            else:
                win_id, win_name = g['p2'], g['n2']
            
            final_text = (f"🥊 *Rock Paper Scissors Result*\n\n"
                          f"👤 {g['n1']}: {names[m1]}\n"
                          f"👤 {g['n2']}: {names[m2]}\n\n")
            
            if win_id:
                final_text += f"🏆 *Winner: {win_name}!*"
                if stats_col is not None:
                    stats_col.insert_one({"id": win_id, "name": win_name, "date": datetime.now()})
            else:
                final_text += f"*{res}*"
            
            msg = await q.edit_message_text(final_text + "\n\n_Deleting in 2m..._", parse_mode=constants.ParseMode.MARKDOWN)
            del rps_games[rid]
            asyncio.create_task(delete_msg(context, q.message.chat_id, msg.message_id))
        else:
            # Show progress
            await q.edit_message_text(f"🥊 *Match in Progress!*\n\n👤 {g['n1']}: {s1}\n👤 {g['n2']}: {s2}\n\nWaiting for both players...", 
                                      reply_markup=get_rps_markup(rid), parse_mode=constants.ParseMode.MARKDOWN)

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("rps", rps_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling(drop_pending_updates=True)
    

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
def home(): return "RPS Logic Fixed! 🚀"

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
        return await update.message.reply_text("❌ Groups mein khelein!")
    rid = f"{update.effective_chat.id}_{update.message.message_id}"
    rps_games[rid] = {'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await update.message.reply_text(f"🥊 *Rock Paper Scissors*\nChallenge by: {update.effective_user.first_name}\n\nWaiting for Player 2...", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", callback_data=f"rj_{rid}")]]), parse_mode=constants.ParseMode.MARKDOWN)

# --- CALLBACK HANDLER ---

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data

    # RPS JOINING
    if data.startswith("rj_"):
        rid = data.split('_', 1)[1]
        if rid in rps_games:
            g = rps_games[rid]
            if g['p1'] == uid:
                return await q.answer("Apne hi challenge mein join nahi kar sakte! 😂", show_alert=True)
            if g['p2'] is None:
                g['p2'], g['n2'] = uid, q.from_user.first_name
                await q.answer("Match Joined! 🥊")
                await q.edit_message_text(f"🥊 *Match Started!*\n\n👤 {g['n1']}: ⏳ Thinking...\n👤 {g['n2']}: ⏳ Thinking...\n\nDono apna move chunein!", reply_markup=get_rps_markup(rid), parse_mode=constants.ParseMode.MARKDOWN)
            else:
                await q.answer("Match pehle hi full hai! ❌", show_alert=True)

    # RPS MOVE RECORDING
    elif data.startswith("rm_"):
        _, rid, move = data.split('_')
        if rid not in rps_games:
            return await q.answer("Game khatam ho gaya! ❌", show_alert=True)
        
        g = rps_games[rid]
        if uid != g['p1'] and uid != g['p2']:
            return await q.answer("Ye aapka match nahi hai! 🧐", show_alert=True)

        # Move save logic
        if uid == g['p1']:
            if g['m1']: return await q.answer("Aapne move chun liya hai! ✅", show_alert=True)
            g['m1'] = move
            await q.answer("Recorded! 🪨📄✂️")
        elif uid == g['p2']:
            if g['m2']: return await q.answer("Aapne move chun liya hai! ✅", show_alert=True)
            g['m2'] = move
            await q.answer("Recorded! 🪨📄✂️")

        # Check status
        if g['m1'] and g['m2']:
            # RESULT REVEAL
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
            
            msg = await q.edit_message_text(final_text + "\n\n_Auto-deleting in 2m..._", parse_mode=constants.ParseMode.MARKDOWN)
            del rps_games[rid]
            asyncio.create_task(delete_msg(context, q.message.chat_id, msg.message_id))
        else:
            # Status update (READY / THINKING)
            s1 = "✅ Ready" if g['m1'] else "⏳ Thinking..."
            s2 = "✅ Ready" if g['m2'] else "⏳ Thinking..."
            # Edit tabhi karein jab move naya ho
            try:
                await q.edit_message_text(f"🥊 *Match in Progress!*\n\n👤 {g['n1']}: {s1}\n👤 {g['n2']}: {s2}\n\nWaiting for the other player...", 
                                          reply_markup=get_rps_markup(rid), parse_mode=constants.ParseMode.MARKDOWN)
            except: pass

# --- MAIN ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("rps", rps_cmd))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling(drop_pending_updates=True)
    

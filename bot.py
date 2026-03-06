import os
import logging
import asyncio
import random
from datetime import datetime
from flask import Flask
from threading import Thread
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

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

# --- WORDS ---
WORDS_DB = ["WHATSAPP", "TELEGRAM", "SAMSUNG", "IPHONE", "VALORANT", "MINECRAFT", "CHICKEN", "BIRYANI", "BURGER", "DOMINOS", "NETFLIX", "YOUTUBE", "AVENGERS", "BATMAN", "IRONMAN", "PIZZA", "CRICKET", "FOOTBALL"]

active_hunts = {}

# --- HELPER: Generate Pattern ---
def generate_pattern(word, reveal_indices):
    return " ".join([word[i] if i in reveal_indices else "_" for i in range(len(word))])

# --- COMMANDS ---
async def hunt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    word = random.choice(WORDS_DB).upper()
    
    # Randomly reveal 2 letters at start
    reveal_indices = random.sample(range(len(word)), 2)
    
    active_hunts[chat_id] = {
        "word": word,
        "indices": reveal_indices,
        "hints_used": 0 # Limit starts here
    }
    
    pattern = generate_pattern(word, reveal_indices)
    kb = [[InlineKeyboardButton("💡 Get Hint (Max 3)", callback_data=f"hint_{chat_id}")]]
    
    await update.message.reply_text(
        f"🕵️‍♂️ *WORD HUNT STARTED!*\n\nGuess: `{pattern}`\n\n_Type the full word in chat!_",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

# --- HINT CALLBACK (WITH LIMIT) ---
async def handle_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = int(q.data.split('_')[1])
    
    if chat_id not in active_hunts:
        await q.answer("No active game!")
        return

    game = active_hunts[chat_id]
    
    # 🛑 HINT LIMIT: Max 3 hints
    if game['hints_used'] >= 3:
        await q.answer("❌ Limit reached! No more hints.", show_alert=True)
        return

    # Reveal one more unique index
    remaining = [i for i in range(len(game['word'])) if i not in game['indices']]
    if not remaining:
        await q.answer("All letters revealed!")
        return
        
    new_idx = random.choice(remaining)
    game['indices'].append(new_idx)
    game['hints_used'] += 1
    
    new_pattern = generate_pattern(game['word'], game['indices'])
    
    await q.edit_message_text(
        f"🕵️‍♂️ *WORD HUNT (Hint {game['hints_used']}/3)*\n\nGuess: `{new_pattern}`",
        parse_mode=constants.ParseMode.MARKDOWN,
        reply_markup=q.message.reply_markup
    )
    await q.answer(f"Hint added! {3 - game['hints_used']} left.")

# --- MESSAGE CHECKER (THE FIX) ---
async def check_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in active_hunts:
        return

    user_text = update.message.text.upper().strip()
    correct_word = active_hunts[chat_id]['word']

    if user_text == correct_word:
        name, uid = update.effective_user.first_name, update.effective_user.id
        if stats_col:
            stats_col.insert_one({"id": uid, "name": name, "game": "wordhunt", "time": datetime.now()})
        
        await update.message.reply_text(f"🥳 *CORRECT!* {name} guessed `{correct_word}`!\n+1 Point added to Leaderboard.")
        del active_hunts[chat_id]

# --- MAIN ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("hunt", hunt_cmd))
    app.add_handler(CallbackQueryHandler(handle_hint, pattern="^hint_"))
    
    # Important: MessageHandler MUST be added last or with a lower priority
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_word))
    
    # Add other handlers (start, game, rps, lb) here...
    app.run_polling(drop_pending_updates=True)
    

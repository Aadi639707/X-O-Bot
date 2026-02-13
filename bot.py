import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging
logging.basicConfig(level=logging.INFO)

# --- CONFIG ---
TOKEN = os.environ.get("TOKEN")
# Render ki URL (e.g., https://your-app-name.onrender.com)
URL = os.environ.get("RENDER_EXTERNAL_URL") 
PORT = int(os.environ.get("PORT", 8080))

# --- APP SETUP ---
app = Flask(__name__)
ptb_app = Application.builder().token(TOKEN).build()

# --- INTERFACE ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_user = context.bot.username
    text = "🎮 ✨ *X/O Gaming Bot* ✨ 🎮\n\nAPI 8.0 Styles Activated! ⚡"
    btns = [
        [InlineKeyboardButton("➕ Add Me", url=f"https://t.me/{bot_user}?startgroup=true")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="lb"), 
         InlineKeyboardButton("❓ Help", callback_data="h")] # Destructive (handled by Telegram UI)
    ]
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=constants.ParseMode.MARKDOWN)

# --- WEBHOOK ROUTES ---
@app.route(f"/{TOKEN}", methods=["POST"])
async def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    await ptb_app.process_update(update)
    return "OK", 200

@app.route("/")
def index(): return "Bot is Online via Webhook!"

# --- MAIN ---
async def main():
    # Set Webhook
    await ptb_app.bot.set_webhook(url=f"{URL}/{TOKEN}")
    # Handlers
    ptb_app.add_handler(CommandHandler("start", start))
    ptb_app.add_handler(CallbackQueryHandler(start, pattern="bk"))
    
    # Isme Application run nahi karni, sirf initialize karni hai
    await ptb_app.initialize()
    await ptb_app.start()

if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
    app.run(host="0.0.0.0", port=PORT)
    

import os
import logging
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Logging
logging.basicConfig(level=logging.INFO)

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

# --- GAME LOGIC ---
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

# --- START INTERFACE ---

def start(update: Update, context: CallbackContext):
    msg = update.message if update.message else update.callback_query.message
    bot_username = context.bot.username
    
    # Ye image link direct hai aur fast load hogi
    img_url = "https://telegra.ph/file/0c9a40578848f8a186259.jpg"
    
    start_text = (
        "🎮 *Welcome to Tic-Tac-Toe Ultimate!*\n\n"
        "Play X-O in groups with zero lag and anti-edit protection.\n\n"
        "Click the buttons below to interact!"
    )
    
    # SAARE LINKS BUTTONS MEIN HAIN
    btns = [
        [InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [
            InlineKeyboardButton("📢 Channel", url="https://t.me/Yonko_crew"),
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")
        ],
        [
            InlineKeyboardButton("🎮 Start Game", callback_data="gui"),
            InlineKeyboardButton("❓ Help", callback_data="h")
        ]
    ]

    try:
        msg.reply_photo(photo=img_url, caption=start_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')
    except:
        msg.reply_text(start_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

def handle_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    uid = q.from_user.id
    data = q.data

    if data == "h":
        h_text = "📖 *Help Menu*\n\n/game - Start Game in Group\n/start - Main Menu"
        q.edit_message_caption(caption=h_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="bk")]]), parse_mode='Markdown')
    
    elif data == "bk":
        q.message.delete()
        start(update, context)

    elif data == "gui":
        q.answer("Go to a group and type /game to play!", show_alert=True)

    elif data.startswith("j_") or data.startswith("m_"):
        # Game moves logic
        action, g_id = data.split('_')[0], data.split('_')[1]
        if g_id not in games:
            q.answer("Game Expired!"); return
        
        g = games[g_id]
        if action == "j":
            if g['p1'] == uid: q.answer("Wait for Player 2!", show_alert=True); return
            g['p2'] = uid
            q.edit_message_reply_markup(reply_markup=get_board_markup(g['board'], g_id))
            q.answer("Joined!")
        
        elif action == "m":
            r, c = int(data.split('_')[2]), int(data.split('_')[3])
            turn = g['turn']
            p = g['p1'] if turn == 'X' else g['p2']
            if uid != p: q.answer(f"It's {turn}'s turn!", show_alert=True); return
            if g['board'][r][c] != " ": return
            
            g['board'][r][c] = turn
            win = check_winner(g['board'])
            if win:
                q.edit_message_reply_markup(reply_markup=get_board_markup(g['board'], g_id))
                context.bot.send_message(q.message.chat_id, f"🏆 Player {win} Won!")
                del games[g_id]
            else:
                g['turn'] = 'O' if turn == 'X' else 'X'
                q.edit_message_reply_markup(reply_markup=get_board_markup(g['board'], g_id))
                q.answer()

def game_cmd(update: Update, context: CallbackContext):
    gid = f"{update.effective_chat.id}{update.effective_message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'p2': None}
    update.message.reply_text(f"🎮 *X-O Challenge*\n❌: {update.effective_user.first_name}\n⭕: Waiting...", 
                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join ⭕", callback_data=f"j_{gid}")]]), 
                              parse_mode='Markdown')

def main():
    updater = Updater(os.environ.get("TOKEN"))
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game_cmd))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    keep_alive()
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
    

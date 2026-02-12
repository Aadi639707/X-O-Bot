import os
import logging
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Logging setup for faster debugging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- FAKE SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online and Ready!"

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

# --- UI COMMANDS ---

def start(update: Update, context: CallbackContext):
    # Chat context check for button and command calls
    msg = update.message if update.message else update.callback_query.message
    bot_user = context.bot.username
    
    # Image provided for X/O theme
    image_url = "https://raw.githubusercontent.com/Ansh8840/Img-storage/main/Tic-Tac-Toe.jpg"
    
    start_text = (
        "🎮 *Welcome to Tic-Tac-Toe Ultimate!*\n\n"
        "Play X-O in groups with zero lag and anti-edit protection.\n\n"
        "👨‍💻 *Developer:* @SANATANI_GOJO\n"
        "📢 *Updates:* @Yonko_Crew"
    )
    
    btns = [
        [InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_user}?startgroup=true")],
        [
            InlineKeyboardButton("❓ Help", callback_data="h"), 
            InlineKeyboardButton("📢 Channel", url="https://t.me/Yonko_Crew")
        ],
        [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")],
        [InlineKeyboardButton("🎮 Start Game", callback_data="gui")]
    ]

    try:
        msg.reply_photo(
            photo=image_url,
            caption=start_text,
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Image error: {e}")
        msg.reply_text(start_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

def handle_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    u_id = q.from_user.id
    data = q.data

    # Immediate answer to make buttons feel faster
    if not data.startswith("m_"):
        q.answer()

    if data == "h":
        text = "📖 *Help Menu*\n\n/game - Start Game in Group\n/start - Open Main Menu\n\nClick 'Add Me' to invite the bot to your group!"
        q.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="bk")]]), parse_mode='Markdown')
    
    elif data == "bk":
        q.message.delete()
        start(update, context)

    elif data == "gui":
        q.answer("Send /game in a group to play!", show_alert=True)

    elif data.startswith("j_") or data.startswith("m_"):
        action, g_id = data.split('_')[0], data.split('_')[1]
        if g_id not in games:
            q.answer("Game Session Expired!", show_alert=True)
            return
        
        g = games[g_id]
        if action == "j":
            if g['p1'] == u_id:
                q.answer("You are already Player 1!", show_alert=True)
                return
            g['p2'] = u_id
            q.edit_message_reply_markup(reply_markup=get_board_markup(g['board'], g_id))
            q.answer("You joined as Player O!")
        
        elif action == "m":
            r, c = int(data.split('_')[2]), int(data.split('_')[3])
            turn = g['turn']
            p = g['p1'] if turn == 'X' else g['p2']
            
            if u_id != p:
                q.answer(f"It is {turn}'s turn!", show_alert=True)
                return
            if g['board'][r][c] != " ":
                q.answer("Cell already filled!")
                return
            
            g['board'][r][c] = turn
            win = check_winner(g['board'])
            
            if win:
                q.edit_message_reply_markup(reply_markup=get_board_markup(g['board'], g_id))
                context.bot.send_message(q.message.chat_id, f"🏆 *Congratulations!*\nPlayer {win} has won the game!", parse_mode='Markdown')
                del games[g_id]
            elif all(cell != " " for row in g['board'] for cell in row):
                q.edit_message_reply_markup(reply_markup=get_board_markup(g['board'], g_id))
                context.bot.send_message(q.message.chat_id, "🤝 *It's a Draw!*")
                del games[g_id]
            else:
                g['turn'] = 'O' if turn == 'X' else 'X'
                q.edit_message_reply_markup(reply_markup=get_board_markup(g['board'], g_id))
                q.answer()

def game_cmd(update: Update, context: CallbackContext):
    if update.effective_chat.type == "private":
        update.message.reply_text("Please add me to a group to play!")
        return
        
    gid = f"{update.effective_chat.id}{update.effective_message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'p2': None}
    
    update.message.reply_text(
        f"🎮 *X-O Challenge*\n\n❌ Player 1: {update.effective_user.first_name}\n⭕ Player 2: Waiting to join...", 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join ⭕", callback_data=f"j_{gid}")]]), 
        parse_mode='Markdown'
    )

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
    

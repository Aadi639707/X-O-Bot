import os
import logging
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- FAKE SERVER FOR RENDER ---
app = Flask('')
@app.route('/')
def home(): return "X-O Bot is Live and Ready!"

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

# --- INTERFACE COMMANDS ---

def start(update: Update, context: CallbackContext):
    bot_username = context.bot.username
    start_text = (
        "🎮 *Welcome to Tic-Tac-Toe Ultimate!*\n\n"
        "Play the classic X-O game directly in your groups with high-end graphics "
        "and zero message-edit lag.\n\n"
        "👤 *Developer:* [SANATANI GOJO](https://t.me/SANATANI_GOJO)\n"
        "📢 *Updates:* [Yonko Crew](https://t.me/Yonko_crew)\n\n"
        "Click the buttons below to explore!"
    )
    
    buttons = [
        [
            InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true"),
            InlineKeyboardButton("❓ Help & Commands", callback_data="help_menu")
        ],
        [
            InlineKeyboardButton("📢 Channel", url="https://t.me/Yonko_crew"),
            InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")
        ],
        [
            InlineKeyboardButton("🎮 Start New Game", callback_data="start_game_ui")
        ]
    ]
    
    # Image URL: Aap yahan apni pasand ki koi bhi image link daal sakte hain
    image_url = "https://telegra.ph/file/5640375a03490989d53c7.jpg" 
    
    update.message.reply_photo(
        photo=image_url,
        caption=start_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode='Markdown'
    )

def help_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    help_text = (
        "📖 *Tic-Tac-Toe Help Menu*\n\n"
        "*/game* - Start a new game in the group.\n"
        "*/start* - See the welcome menu and bot info.\n\n"
        "• The game works with inline buttons.\n"
        "• To avoid 'Anti-Edit' bots, we only update the grid.\n"
        "• If someone doesn't join, the game expires."
    )
    query.edit_message_caption(
        caption=help_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]]),
        parse_mode='Markdown'
    )

def game_command(update: Update, context: CallbackContext):
    user = update.effective_user
    game_id = f"{update.effective_chat.id}{update.effective_message.message_id}"
    
    games[game_id] = {
        'board': [[" " for _ in range(3)] for _ in range(3)],
        'turn': 'X', 'p1': user.id, 'p2': None, 'name1': user.first_name
    }
    
    update.message.reply_text(
        f"🎮 *X-O Challenge*\n\n❌ Player 1: {user.first_name}\n⭕ Player 2: Waiting...",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join Game ⭕", callback_data=f"j_{game_id}")]]),
        parse_mode='Markdown'
    )

def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data == "help_menu":
        help_callback(update, context)
    elif data == "back_to_start":
        # Redirecting back to start logic (simplified here)
        query.message.delete()
        start(update.callback_query, context)
    elif data == "start_game_ui":
        query.answer("Use /game in a group to start playing!", show_alert=True)
    
    # Game Logic (Join/Move)
    elif data.startswith("j_") or data.startswith("m_"):
        action, game_id = data.split('_')[0], data.split('_')[1]
        if game_id not in games:
            query.answer("Game Expired!")
            return
        
        game = games[game_id]
        
        if action == "j":
            if game['p1'] == user_id:
                query.answer("You started this game!", show_alert=True)
                return
            game['p2'], game['name2'] = user_id, query.from_user.first_name
            query.edit_message_reply_markup(reply_markup=get_board_markup(game['board'], game_id))
            query.answer("Game Started!")

        elif action == "m":
            r, c = int(data.split('_')[2]), int(data.split('_')[3])
            curr = game['turn']
            player = game['p1'] if curr == 'X' else game['p2']
            
            if user_id != player:
                query.answer(f"It's {curr}'s turn!", show_alert=True)
                return
            if game['board'][r][c] != " ":
                query.answer("Taken!")
                return
            
            game['board'][r][c] = curr
            win = check_winner(game['board'])
            
            if win:
                query.edit_message_reply_markup(reply_markup=get_board_markup(game['board'], game_id))
                context.bot.send_message(query.message.chat_id, f"🏆 {win} Won!")
                del games[game_id]
            else:
                game['turn'] = 'O' if curr == 'X' else 'X'
                query.edit_message_reply_markup(reply_markup=get_board_markup(game['board'], game_id))
                query.answer(f"Turn: {game['turn']}")

def main():
    TOKEN = os.environ.get("TOKEN")
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game_command))
    dp.add_handler(CallbackQueryHandler(handle_callback))

    keep_alive()
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
  

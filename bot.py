import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Logging
logging.basicConfig(level=logging.INFO)

# --- DATABASE LOGIC ---
DB_FILE = "stats.json"

def load_stats():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "wins": []} # wins: [{"id": 123, "name": "Gojo", "date": "2026-02-12"}]

def save_win(user_id, name):
    stats = load_stats()
    # Save win with date
    stats["wins"].append({
        "id": user_id,
        "name": name,
        "date": datetime.now().strftime("%Y-%m-%d")
    })
    with open(DB_FILE, "w") as f:
        json.dump(stats, f)

def get_leaderboard(mode="global"):
    stats = load_stats()
    wins = stats["wins"]
    now = datetime.now()
    
    filtered_wins = []
    if mode == "today":
        target = now.strftime("%Y-%m-%d")
        filtered_wins = [w for w in wins if w["date"] == target]
    elif mode == "week":
        last_week = now - timedelta(days=7)
        filtered_wins = [w for w in wins if datetime.strptime(w["date"], "%Y-%m-%d") > last_week]
    elif mode == "month":
        last_month = now - timedelta(days=30)
        filtered_wins = [w for w in wins if datetime.strptime(w["date"], "%Y-%m-%d") > last_month]
    else: # global
        filtered_wins = wins

    # Count wins per user
    counts = {}
    for w in filtered_wins:
        uid = w["id"]
        counts[uid] = counts.get(uid, {"name": w["name"], "count": 0})
        counts[uid]["count"] += 1
    
    # Sort
    sorted_lb = sorted(counts.values(), key=lambda x: x["count"], reverse=True)[:10]
    
    if not sorted_lb:
        return "No wins recorded yet for this period!"
    
    text = f"🏆 *{mode.upper()} LEADERBOARD*\n\n"
    for i, user in enumerate(sorted_lb, 1):
        text += f"{i}. {user['name']} — {user['count']} wins\n"
    return text

# --- FAKE SERVER ---
app = Flask('')
@app.route('/')
def home(): return "X/O Gaming Bot is Online!"

def run():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    Thread(target=run).start()

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
    msg = update.message if update.message else update.callback_query.message
    bot_username = context.bot.username
    start_text = "🎮 *Welcome to X/O Gaming Bot!*\n\nBest Tic-Tac-Toe with Anti-Edit & Leaderboards."
    btns = [
        [InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("🏆 Leaderboard", callback_data="lb_global"), InlineKeyboardButton("❓ Help", callback_data="h")],
        [InlineKeyboardButton("📢 Channel", url="https://t.me/Yonko_Crew"), InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/SANATANI_GOJO")]
    ]
    msg.reply_text(start_text, reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

def handle_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    uid, data = q.from_user.id, q.data

    if data.startswith("lb_"):
        mode = data.split("_")[1]
        lb_btns = [
            [InlineKeyboardButton("Today", callback_data="lb_today"), InlineKeyboardButton("Week", callback_data="lb_week")],
            [InlineKeyboardButton("Month", callback_data="lb_month"), InlineKeyboardButton("Global", callback_data="lb_global")],
            [InlineKeyboardButton("🔙 Back", callback_data="bk")]
        ]
        q.edit_message_text(get_leaderboard(mode), reply_markup=InlineKeyboardMarkup(lb_btns), parse_mode='Markdown')
    
    elif data == "bk":
        q.message.delete()
        start(update, context)

    elif data == "h":
        q.edit_message_text("📖 /game - Start\n/start - Menu", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="bk")]]))

    elif data.startswith("j_") or data.startswith("m_"):
        action, g_id = data.split('_')[0], data.split('_')[1]
        if g_id not in games: return
        g = games[g_id]
        if action == "j":
            if g['p1'] == uid: return
            g['p2'], g['n2'] = uid, q.from_user.first_name
            q.edit_message_reply_markup(get_board_markup(g['board'], g_id))
        elif action == "m":
            r, c = int(data.split('_')[2]), int(data.split('_')[3])
            turn = g['turn']
            p = g['p1'] if turn == 'X' else g['p2']
            if uid != p or g['board'][r][c] != " ": return
            g['board'][r][c] = turn
            win = check_winner(g['board'])
            if win:
                q.edit_message_reply_markup(get_board_markup(g['board'], g_id))
                winner_name = g['n1'] if win == 'X' else g['n2']
                winner_id = g['p1'] if win == 'X' else g['p2']
                save_win(winner_id, winner_name) # Save to Leaderboard
                context.bot.send_message(q.message.chat_id, f"🏆 {winner_name} won!")
                del games[g_id]
            elif all(cell != " " for row in g['board'] for cell in row):
                q.edit_message_reply_markup(get_board_markup(g['board'], g_id))
                context.bot.send_message(q.message.chat_id, "🤝 Draw!")
                del games[g_id]
            else:
                g['turn'] = 'O' if turn == 'X' else 'X'
                q.edit_message_reply_markup(get_board_markup(g['board'], g_id))

def game_cmd(update: Update, context: CallbackContext):
    if update.effective_chat.type == "private": return
    gid = f"{update.effective_chat.id}{update.effective_message.message_id}"
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': update.effective_user.id, 'n1': update.effective_user.first_name, 'p2': None}
    update.message.reply_text(f"🎮 X-O Start!\n❌: {update.effective_user.first_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Join ⭕", callback_data=f"j_{gid}")]]))

def main():
    updater = Updater(os.environ.get("TOKEN"), use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game_cmd))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    keep_alive()
    updater.start_polling()
    updater.idle()

if __name__ == '__main__': main()
            

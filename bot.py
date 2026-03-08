import os
import json
import asyncio
import logging
from flask import Flask
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- RENDER PORT FIX (FLASK) ---
# Ye Render ke 'No open ports' error ko fix karne ke liye hai
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is Running & Port is Active! ⚡"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
STRING_SESSION = os.environ.get("STRING_SESSION")

# Client Setup (String Session)
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

# --- GLOBAL STATE ---
games = {}
rps_games = {}

# --- DATABASE LOGIC (Saved Messages / Cloud Storage) ---
async def get_db():
    try:
        # Saved Messages (me) se DB message search karna
        async for message in app.get_chat_history("me", limit=50):
            if message.text and "DATABASE_STATS:" in message.text:
                data_str = message.text.replace("DATABASE_STATS:", "").strip()
                return json.loads(data_str), message.id
        return {}, None
    except Exception as e:
        logger.error(f"DB Load Error: {e}")
        return {}, None

async def save_win(uid, name, game_type):
    data, msg_id = await get_db()
    user_id = str(uid)
    
    if user_id not in data:
        data[user_id] = {"name": name, "xo": 0, "rps": 0, "total": 0}
    
    data[user_id][game_type] += 1
    data[user_id]["total"] += 1
    data[user_id]["name"] = name
    
    db_text = f"DATABASE_STATS:\n{json.dumps(data, indent=4)}"
    
    if msg_id:
        await app.edit_message_text("me", msg_id, db_text)
    else:
        await app.send_message("me", db_text)

# --- XO WIN LOGIC ---
def check_win(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    if all(cell != " " for row in b for cell in row): return "Draw"
    return None

# --- COMMANDS ---
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply("🎮 **Mega Arena Active!**\n\n/game - TicTacToe (XO)\n/rps - Rock Paper Scissors\n/leaderboard - Stats")

@app.on_message(filters.command("game") & filters.group)
async def game_cmd(client, message):
    gid = str(message.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': message.from_user.id, 'n1': message.from_user.first_name, 'p2': None, 'n2': None}
    await message.reply("🎮 **XO Match!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join Match", f"j_{gid}")]]))

@app.on_message(filters.command("rps") & filters.group)
async def rps_cmd(client, message):
    rid = str(message.id)
    rps_games[rid] = {'p1': message.from_user.id, 'n1': message.from_user.first_name, 'p2': None, 'n2': None, 'm1': None, 'm2': None}
    await message.reply("🥊 **RPS Challenge!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join RPS", f"rj_{rid}")]]))

@app.on_message(filters.command("leaderboard"))
async def lb_cmd(client, message):
    data, _ = await get_db()
    sorted_data = sorted(data.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
    text = "🏆 **TOP 10 CHAMPIONS**\n\n"
    if not sorted_data: text += "No records found!"
    for i, (uid, info) in enumerate(sorted_data):
        text += f"{i+1}. [{info['name']}](tg://user?id={uid}) — `{info['total']} Wins`\n"
    await message.reply(text)

# --- CALLBACK HANDLER ---
@app.on_callback_query()
async def handle_callback(client, q: CallbackQuery):
    uid, name, d = q.from_user.id, q.from_user.first_name, q.data

    # --- XO LOGIC ---
    if d.startswith("j_"):
        gid = d.split("_")[1]
        if gid in games and games[gid]['p1'] != uid and games[gid]['p2'] is None:
            g = games[gid]; g['p2'], g['n2'] = uid, name
            kb = [[InlineKeyboardButton("·", f"m_{gid}_{r}_{c}") for c in range(3)] for r in range(3)]
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {g['n1']} (X)", reply_markup=InlineKeyboardMarkup(kb))

    elif d.startswith("m_"):
        gid, r, c = d.split("_")[1], int(d.split("_")[2]), int(d.split("_")[3])
        if gid not in games: return
        g = games[gid]
        if uid != (g['p1'] if g['turn'] == 'X' else g['p2']) or g['board'][r][c] != " ": return
        
        g['board'][r][c] = g['turn']
        res = check_win(g['board'])
        kb = [[InlineKeyboardButton(g['board'][rr][cc] if g['board'][rr][cc] != " " else "·", f"m_{gid}_{rr}_{cc}") for cc in range(3)] for rr in range(3)]
        
        if res:
            msg = "🤝 **Match Draw!**" if res == "Draw" else f"🏆 **Winner: {name}!**"
            if res != "Draw": await save_win(uid, name, "xo")
            await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            current_turn_name = g['n1'] if g['turn'] == 'X' else g['n2']
            await q.edit_message_text(f"⚔️ {g['n1']} vs {g['n2']}\nTurn: {current_turn_name} ({g['turn']})", reply_markup=InlineKeyboardMarkup(kb))

    # --- RPS LOGIC ---
    elif d.startswith("rj_"):
        rid = d.split("_")[1]
        if rid in rps_games and rps_games[rid]['p1'] != uid and rps_games[rid]['p2'] is None:
            g = rps_games[rid]; g['p2'], g['n2'] = uid, name
            await q.edit_message_text(f"🥊 {g['n1']} vs {g['n2']}\nChoose:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪨 Rock", f"rm_{rid}_R"), InlineKeyboardButton("📄 Paper", f"rm_{rid}_P"), InlineKeyboardButton("✂️ Scissors", f"rm_{rid}_S")]]))

    elif d.startswith("rm_"):
        rid, m = d.split("_")[1], d.split("_")[2]
        if rid not in rps_games: return
        g = rps_games[rid]
        if uid == g['p1'] and not g['m1']: g['m1'] = m
        elif uid == g['p2'] and not g['m2']: g['m2'] = m
        else: return

        if g['m1'] and g['m2']:
            m1, m2 = g['m1'], g['m2']
            res_txt, win_id, win_n = "🤝 Draw!", None, None
            if (m1=='R' and m2=='S') or (m1=='S' and m2=='P') or (m1=='P' and m2=='R'):
                res_txt, win_id, win_n = f"🏆 {g['n1']} Won!", g['p1'], g['n1']
            elif m1 != m2:
                res_txt, win_id, win_n = f"🏆 {g['n2']} Won!", g['p2'], g['n2']
            
            await q.edit_message_text(f"🥊 {res_txt}\n{g['n1']}: {m1} | {g['n2']}: {m2}")
            if win_id: await save_win(win_id, win_n, "rps")
            del rps_games[rid]

# --- START BOT ---
if __name__ == "__main__":
    # Start Flask Port-binding in background
    Thread(target=run_flask).start()
    print("Web Port binding active. Starting Pyrogram Bot...")
    app.run()
    

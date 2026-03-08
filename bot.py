import os
import json
import asyncio
import logging
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- RENDER PORT FIX ---
web_app = Flask('')
@web_app.route('/')
def home(): return "Bot is Active! ⚡"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- CONFIG ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
STRING_SESSION = os.environ.get("STRING_SESSION")

# Client Setup
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION)

# --- DATABASE LOGIC ---
async def get_db():
    try:
        async for message in app.get_chat_history("me", limit=50):
            if message.text and "DATABASE_STATS:" in message.text:
                data_str = message.text.replace("DATABASE_STATS:", "").strip()
                return json.loads(data_str), message.id
        return {}, None
    except:
        return {}, None

async def save_win(uid, name, game_type):
    data, msg_id = await get_db()
    u_id = str(uid)
    if u_id not in data: data[u_id] = {"name": name, "xo": 0, "rps": 0, "total": 0}
    data[u_id][game_type] += 1
    data[u_id]["total"] += 1
    db_text = f"DATABASE_STATS:\n{json.dumps(data, indent=4)}"
    if msg_id: await app.edit_message_text("me", msg_id, db_text)
    else: await app.send_message("me", db_text)

# --- XO WIN LOGIC ---
def check_win(b):
    for i in range(3):
        if b[i][0] == b[i][1] == b[i][2] != " ": return b[i][0]
        if b[0][i] == b[1][i] == b[2][i] != " ": return b[0][i]
    if b[0][0] == b[1][1] == b[2][2] != " ": return b[0][0]
    if b[0][2] == b[1][1] == b[2][0] != " ": return b[0][2]
    if all(cell != " " for row in b for cell in row): return "Draw"
    return None

# --- STATE ---
games = {}

# --- HANDLERS ---
@app.on_message(filters.command("start"))
async def start_h(c, m):
    await m.reply("🎮 **Arena Online!**\nUse /game to play.")

@app.on_message(filters.command("game"))
async def game_h(c, m):
    gid = str(m.id)
    games[gid] = {'board': [[" "]*3 for _ in range(3)], 'turn': 'X', 'p1': m.from_user.id, 'n1': m.from_user.first_name, 'p2': None, 'n2': None}
    await m.reply("🎮 **XO Match!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Join", f"j_{gid}")]]))

@app.on_callback_query()
async def cb_h(c, q: CallbackQuery):
    uid, name, d = q.from_user.id, q.from_user.first_name, q.data
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
            msg = "🤝 Draw!" if res == "Draw" else f"🏆 Winner: {name}!"
            if res != "Draw": await save_win(uid, name, "xo")
            await q.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(kb))
            del games[gid]
        else:
            g['turn'] = 'O' if g['turn'] == 'X' else 'X'
            await q.edit_message_text(f"Turn: {g['n1'] if g['turn'] == 'X' else g['n2']} ({g['turn']})", reply_markup=InlineKeyboardMarkup(kb))

# --- MAIN ---
if __name__ == "__main__":
    Thread(target=run_flask).start()
    app.run()
    

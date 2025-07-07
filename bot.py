import asyncio
import os
import sys
import json
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChatAdminRequiredError
from telethon.tl.functions.channels import CreateChannelRequest, EditAdminRequest, InviteToChannelRequest
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import ChatAdminRights

# ======== CONFIG ========
BOT_TOKEN = '8195096775:AAEsEFoYpltqo1KrMXORzYfC-4BeIMTMh-4'
TELETHON_API_ID = 28369489
TELETHON_API_HASH = '369653d4ba4277f81d109368af59f82f'
ADMIN_ID = 5802051984  # ← faqat shu ID ishlata oladi

SESSIONS_DIR = 'sessions'
DATA_FILE = 'data.json'
LOG_FILE = 'guruhlar.txt'

os.makedirs(SESSIONS_DIR, exist_ok=True)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ======== STATES ========
class AddSession(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_password = State()

# ======== UTILS ========
def load_data():
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def add_session(name, info):
    data = load_data()
    data[name] = info
    save_data(data)

def remove_session(name):
    data = load_data()
    if name in data:
        del data[name]
        save_data(data)
    path = os.path.join(SESSIONS_DIR, f"{name}.session")
    if os.path.exists(path):
        os.remove(path)

def update_session(name, updates):
    data = load_data()
    if name in data:
        data[name].update(updates)
        save_data(data)

def get_session(name):
    return load_data().get(name)

# ======== BACKGROUND ========
running_tasks = {}

oylar = {
    1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel",
    5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
    9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
}

admin_rights = ChatAdminRights(
    change_info=True,
    delete_messages=True,
    ban_users=True,
    invite_users=True,
    pin_messages=True,
    add_admins=False,
    manage_call=True
)

async def run_session(name):
    params = get_session(name)
    if not params or params["status"] != "running":
        return

    session_file = os.path.join(SESSIONS_DIR, f"{name}.session")
    client = TelegramClient(session_file, TELETHON_API_ID, TELETHON_API_HASH)
    await client.start(params["phone_number"])

    while True:
        current = get_session(name)
        if not current or current["status"] != "running":
            await client.disconnect()
            break
        try:
            hozir = datetime.now()
            guruh_nom = f'{current["group_name"]} {current["index"]}'
            sana_oy = oylar[hozir.month]
            sana_xabar = hozir.strftime(f"%d-{sana_oy} %Y yil")

            result = await client(CreateChannelRequest(
                title=guruh_nom,
                about="Avtomatik yaratilgan",
                megagroup=True
            ))
            superchat = result.chats[0]
            link = (await client(ExportChatInviteRequest(superchat.id))).link

            await client(InviteToChannelRequest(superchat, [current["admin_user"]]))
            await client(EditAdminRequest(superchat, current["admin_user"], admin_rights, rank="Admin"))
            await client.send_message(superchat.id, f"📅 Guruh ochildi: {sana_xabar}\n🔗 Havola: {link}")

            with open(LOG_FILE, "a") as f:
                f.write(f"{link}\n")

            update_session(name, {"index": current["index"] + 1})
            await asyncio.sleep(current["delay"])

        except FloodWaitError as e:
            await bot.send_message(current["owner_id"], f"⚠️ FloodWait {e.seconds} soniya session: {name}")
            await asyncio.sleep(e.seconds + 5)
        except ChatAdminRequiredError as e:
            await bot.send_message(current["owner_id"], f"❌ Admin required error: {e}")
            break
        except Exception as e:
            await bot.send_message(current["owner_id"], f"❌ Umumiy xato: {e}")
            break

    await client.disconnect()

# ======== COMMANDS ========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
    "🤖 Bot ishga tushdi.\n\n"
    "📌 Buyruqlar ro'yxati:\n\n"
    "/newsession - Yangi session qo'shish\n"
    "/run - Sessionni ishga tushirish \n"
    "/sessions - Sessionlar ro'yxatini ko'rish \n"
    "/stop - Sessionni to'xtatish \n"
    "/stopall - Barcha sessionlarni to'xtatish \n"
    "/remove - Sessionni o'chirish \n"
    "/setdelay - Sessionlar kutish vaqtini o'zgartirish \n"
    "/status - Sessionlar holatini ko'rish "
)


# ======== ADMIN GUARD ========
async def admin_guard(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ Bu buyruq faqat admin uchun ruxsat etilgan.")
        return False
    return True

# ======== ADMIN COMMANDS ========
@dp.message(Command("run"))
async def cmd_run(message: Message):
    if not await admin_guard(message): return
    args = message.text.strip().split(maxsplit=5)
    if len(args) != 6:
        return await message.answer("⚠️ /run <name> \"<guruh_nomi>\" <index> <admin_username> <delay>")
    _, name, gname, index, admin, delay = args
    index = int(index)
    delay = int(delay)
    session = get_session(name)
    if not session:
        return await message.answer("❌ Session topilmadi.")

    update_session(name, {
        "group_name": gname,
        "index": index,
        "admin_user": admin,
        "delay": delay,
        "status": "running",
        "owner_id": message.from_user.id
    })
    task = asyncio.create_task(run_session(name))
    running_tasks[name] = task
    await message.answer(f"✅ Session '{name}' ishga tushdi.")

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    if not await admin_guard(message): return
    args = message.text.strip().split()
    if len(args) != 2:
        return await message.answer("⚠️ /stop <session_name>")
    _, name = args
    session = get_session(name)
    if not session:
        return await message.answer("❌ Topilmadi.")
    update_session(name, {"status": "stopped"})
    await message.answer(f"🛑 Session '{name}' to'xtatildi.")

@dp.message(Command("stopall"))
async def cmd_stopall(message: Message):
    if not await admin_guard(message): return
    data = load_data()
    for name in data.keys():
        update_session(name, {"status": "stopped"})
    await message.answer("🛑 Hammasi to'xtatildi.")

@dp.message(Command("remove"))
async def cmd_remove(message: Message):
    if not await admin_guard(message): return
    parts = message.text.strip().split()
    if len(parts) != 2:
        return await message.answer("⚠️ /remove <session_name>")
    _, name = parts
    remove_session(name)
    await message.answer(f"🗑️ Session '{name}' o'chirildi.")

@dp.message(Command("sessions"))
async def cmd_sessions(message: Message):
    if not await admin_guard(message): return
    data = load_data()
    if not data:
        return await message.answer("📭 Sessionlar yo'q.")
    text = "📋 Sessionlar:\n"
    for k, v in data.items():
        text += (f"\n✅ {k}\n"
                 f"• Phone: {v['phone_number']}\n"
                 f"• Group: {v['group_name']}\n"
                 f"• Admin: {v['admin_user']}\n"
                 f"• Index: {v['index']}\n"
                 f"• Delay: {v['delay']}s\n"
                 f"• Status: {v['status']}\n")
    await message.answer(text)

@dp.message(Command("setdelay"))
async def cmd_setdelay(message: Message):
    if not await admin_guard(message): return
    args = message.text.strip().split()
    if len(args) != 2:
        return await message.answer("⚠️ /setdelay <sekundlar>")
    try:
        seconds = int(args[1])
        data = load_data()
        for name in data.keys():
            update_session(name, {"delay": seconds})
        await message.answer(f"✅ Delay {seconds} sekundga o'rnatildi.")
    except ValueError:
        await message.answer("❗ Delay butun son bo'lishi kerak.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    if not await admin_guard(message): return
    data = load_data()
    if not data:
        return await message.answer("📭 Hech narsa yo'q.")
    text = "🟢 Statuslar:\n"
    for k, v in data.items():
        text += f"\n✅ {k}: {v['status']}"
    await message.answer(text)

# ======== NEWSESSION (ochiq) ========
# bu yerda avvalgi newsession FSM kodingni qo'yasan
# (shu qismini o'zgartirmay tur, ochiq qoladi!)

# ======== STARTUP ========
async def main():
    await bot.set_my_commands([
    BotCommand(command="start", description="Botni boshlash"),
    BotCommand(command="newsession", description="Yangi session qo'shish"),
    BotCommand(command="run", description="Sessionni ishga tushirish"),
    BotCommand(command="stop", description="Sessionni to'xtatish"),
    BotCommand(command="stopall", description="Barcha sessionlarni to'xtatish"),
    BotCommand(command="remove", description="Sessionni o'chirish"),
    BotCommand(command="sessions", description="Sessionlar ro'yxatini ko'rish"),
    BotCommand(command="setdelay", description="Sessionlar delay vaqtini o'zgartirish"),
    BotCommand(command="status", description="Sessionlar holatini ko'rish")
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

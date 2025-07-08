import asyncio
import json
import os
import time
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# === CONFIG ===
BOT_TOKEN = '8195096775:AAEsEFoYpltqo1KrMXORzYfC-4BeIMTMh-4'
TELETHON_API_ID = 28369489
TELETHON_API_HASH = '369653d4ba4277f81d109368af59f82f'
ADMIN_ID = 5802051984 

DATA_FILE = "data.json"
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

# === FSM States ===
class AddSession(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

# === UTILS ===
def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def add_session(name, phone):
    data = load_data()
    data[name] = {
        "phone_number": phone,
        "status": "stopped",
        "floodwait_until": None,
        "group_name": "",
        "index": 1,
        "admin_user": "",
        "delay": 60
    }
    save_data(data)

def update_session(name, updates):
    data = load_data()
    if name in data:
        data[name].update(updates)
        save_data(data)

def remove_session(name):
    data = load_data()
    if name in data:
        del data[name]
        save_data(data)
    path = os.path.join(SESSIONS_DIR, f"{name}.session")
    if os.path.exists(path):
        os.remove(path)

def get_session(name):
    return load_data().get(name)

# === AIROGRAM setup ===
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

running_tasks = {}

# === ADMIN GUARD ===
async def admin_guard(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Bu buyruq faqat admin uchun!")
        return False
    return True

# === HANDLERS ===
@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🤖 Bot ishlayapti.\n\n"
        "📌 Buyruqlar:\n"
        "/newsession - Session qo'shish\n"
        "/run - Sessionni ishga tushirish\n"
        "/stop - Sessionni to'xtatish\n"
        "/stopall - Hammasini to'xtatish\n"
        "/remove - Sessionni o'chirish\n"
        "/sessions - Sessionlar ro'yxati"
    )

@router.message(Command("newsession"))
async def cmd_newsession(message: Message, state: FSMContext):
    if not await admin_guard(message): return
    await message.answer("📌 Session nomini kiriting:")
    await state.set_state(AddSession.waiting_for_name)

@router.message(AddSession.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("📞 Telefon raqamini kiriting (kod bilan):")
    await state.set_state(AddSession.waiting_for_phone)

@router.message(AddSession.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    phone = message.text.strip()
    add_session(name, phone)
    await message.answer(f"✅ Session '{name}' qo'shildi!")
    await state.clear()

@router.message(Command("sessions"))
async def cmd_sessions(message: Message):
    if not await admin_guard(message): return
    data = load_data()
    if not data:
        await message.answer("📭 Sessionlar yo'q.")
        return

    now = int(time.time())
    text = "📋 Sessionlar:\n"
    for name, v in data.items():
        line = (f"\n✅ {name}\n"
                f"• Phone: {v['phone_number']}\n"
                f"• Status: {v['status']}")
        if v.get("floodwait_until"):
            remain = v["floodwait_until"] - now
            if remain > 0:
                line += f"\n⚠️ FloodWait qolgan: {remain} sekund"
            else:
                update_session(name, {"floodwait_until": None})
        text += f"{line}\n"
    await message.answer(text)

@router.message(Command("stopall"))
async def cmd_stopall(message: Message):
    if not await admin_guard(message): return
    data = load_data()
    for name in data.keys():
        update_session(name, {"status": "stopped"})
    await message.answer("🛑 Hammasi to'xtatildi.")

@router.message(Command("remove"))
async def cmd_remove(message: Message):
    if not await admin_guard(message): return
    args = message.text.strip().split()
    if len(args) != 2:
        return await message.answer("⚠️ /remove <session_name>")
    _, name = args
    remove_session(name)
    await message.answer(f"🗑️ Session '{name}' o'chirildi.")

@router.message(Command("run"))
async def cmd_run(message: Message):
    if not await admin_guard(message): return
    args = message.text.strip().split(maxsplit=5)
    if len(args) != 6:
        return await message.answer("⚠️ /run <name> \"<group_name>\" <index> <admin_username> <delay>")
    _, name, gname, index, admin, delay = args
    index = int(index)
    delay = int(delay)

    session = get_session(name)
    if not session:
        return await message.answer("❌ Session topilmadi.")

    # Check if floodwait over
    now = int(time.time())
    if session.get("floodwait_until") and session["floodwait_until"] > now:
        remain = session["floodwait_until"] - now
        return await message.answer(f"⚠️ FloodWait tugamagan. {remain} sekund kuting!")

    # Update and "run" session
    update_session(name, {
        "group_name": gname,
        "index": index,
        "admin_user": admin,
        "delay": delay,
        "status": "running",
        "floodwait_until": None
    })

    await message.answer(f"✅ Session '{name}' ishga tushdi!")

    # Simulate background task
    async def fake_task():
        try:
            while True:
                current = get_session(name)
                if not current or current["status"] != "running":
                    break
                # Simulate creating channel
                await asyncio.sleep(delay)
                # Randomly simulate floodwait
                if current["index"] % 5 == 0:
                    fw = 60
                    until = int(time.time()) + fw
                    update_session(name, {"status": "stopped", "floodwait_until": until})
                    await bot.send_message(message.from_user.id, f"⚠️ FloodWait {fw} sekund.")
                    break
                update_session(name, {"index": current["index"] + 1})
        except asyncio.CancelledError:
            pass

    # Cancel if running
    task = running_tasks.get(name)
    if task and not task.done():
        task.cancel()

    running_tasks[name] = asyncio.create_task(fake_task())

# === BOT START ===
async def main():
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni boshlash"),
        BotCommand(command="newsession", description="Yangi session qo'shish"),
        BotCommand(command="run", description="Sessionni ishga tushirish"),
        BotCommand(command="stopall", description="Barcha sessionlarni to'xtatish"),
        BotCommand(command="remove", description="Sessionni o'chirish"),
        BotCommand(command="sessions", description="Sessionlar ro'yxatini ko'rish"),
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

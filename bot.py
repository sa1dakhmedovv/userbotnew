import asyncio
import os
import sys
import json
import time
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

# ========== CONFIG ==========
BOT_TOKEN = '8195096775:AAEsEFoYpltqo1KrMXORzYfC-4BeIMTMh-4'
TELETHON_API_ID = 28369489
TELETHON_API_HASH = '369653d4ba4277f81d109368af59f82f'
ADMIN_ID = 5802051984 

SESSIONS_DIR = 'sessions'
DATA_FILE = 'data.json'
LOG_FILE = 'guruhlar.txt'

os.makedirs(SESSIONS_DIR, exist_ok=True)
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, 'w') as f:
        json.dump({}, f)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== STATES ==========
class AddSession(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_code = State()

# ========== UTILS ==========
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

# ========== BACKGROUND ==========
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
            until_timestamp = int(time.time()) + e.seconds
            update_session(name, {
                "status": "stopped",
                "floodwait_until": until_timestamp
            })
            await bot.send_message(current["owner_id"], f"⚠️ FloodWait {e.seconds} soniya session: {name}")
            break
        except ChatAdminRequiredError as e:
            await bot.send_message(current["owner_id"], f"❌ Admin required error: {e}")
            break
        except Exception as e:
            await bot.send_message(current["owner_id"], f"❌ Umumiy xato: {e}")
            break

    await client.disconnect()

# ========== ADMIN GUARD ==========
async def admin_guard(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ Bu buyruq faqat admin uchun ruxsat etilgan.")
        return False
    return True

# ========== COMMANDS ==========
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🤖 Bot ishga tushdi.\n\n"
        "📌 Buyruqlar:\n"
        "/newsession - Session qo'shish\n"
        "/run - Session ishga tushirish\n"
        "/stop - Session to'xtatish\n"
        "/stopall - Hammasini to'xtatish\n"
        "/remove - Session o'chirish\n"
        "/sessions - Sessionlar ro'yxati\n"
        "/setdelay - Kutish vaqtini o'zgartirish\n"
        "/status - Status ko'rish"
    )

@dp.message(Command("newsession"))
async def start_newsession(message: Message, state: FSMContext):
    if not await admin_guard(message): return
    await message.answer("📱 Session nomini kiriting:")
    await state.set_state(AddSession.waiting_for_name)

@dp.message(AddSession.waiting_for_name)
async def get_session_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("📞 Telefon raqamini kiriting (kod bilan):")
    await state.set_state(AddSession.waiting_for_phone)

@dp.message(AddSession.waiting_for_phone)
async def get_phone_number(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data['name']
    phone = message.text.strip()

    session_file = os.path.join(SESSIONS_DIR, f"{name}.session")
    client = TelegramClient(session_file, TELETHON_API_ID, TELETHON_API_HASH)
    await client.connect()
    try:
        await client.send_code_request(phone)
    except Exception as e:
        await message.answer(f"❌ Kod yuborishda xato: {e}")
        await client.disconnect()
        await state.clear()
        return

    await state.update_data(client=client)
    await state.update_data(phone=phone)
    await message.answer("✅ Kod yuborildi, uni kiriting:")
    await state.set_state(AddSession.waiting_for_code)

@dp.message(AddSession.waiting_for_code)
async def get_code(message: Message, state: FSMContext):
    data = await state.get_data()
    client: TelegramClient = data['client']
    phone = data['phone']
    code = message.text.strip()

    try:
        await client.sign_in(phone, code)
    except SessionPasswordNeededError:
        await message.answer("🔐 2FA parol o'rnatilgan. Session qo'shilmadi.")
        await client.disconnect()
        await state.clear()
        return
    except Exception as e:
        await message.answer(f"❌ Xato: {e}")
        await client.disconnect()
        await state.clear()
        return

    add_session(data['name'], {
        "phone_number": phone,
        "group_name": "",
        "index": 1,
        "admin_user": "",
        "delay": 60,
        "status": "stopped"
    })
    await client.disconnect()
    await message.answer("✅ Session muvaffaqiyatli qo'shildi!")
    await state.clear()

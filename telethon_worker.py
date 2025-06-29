import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.channels import (
    CreateChannelRequest, EditAdminRequest, InviteToChannelRequest
)
from telethon.tl.functions.messages import ExportChatInviteRequest
from telethon.tl.types import ChatAdminRights
from telethon.errors import FloodWaitError
from session_manager import add_or_update_session, get_session

oylar = {
    1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel",
    5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
    9: "sentabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"
}

# Barcha ishchi tasklar va statuslar
active_tasks = {}
stop_flags = {}

async def guruh_ochish(client, session_name, params, bot_send=None):
    hozir = datetime.now()
    guruh_nom = f"{params['group_name']} {params['index']}"
    sana_oy = oylar[hozir.month]
    sana_xabar = hozir.strftime(f"%d-{sana_oy} %Y yil")

    # ✅ Superguruh yaratish
    result = await client(CreateChannelRequest(
        title=guruh_nom,
        about="Avtomatik yaratilgan guruh",
        megagroup=True
    ))
    superchat = result.chats[0]

    # ✅ Havola olish
    link = (await client(ExportChatInviteRequest(peer=superchat.id))).link

    # ✅ Foydalanuvchini qo'shish
    await client(InviteToChannelRequest(superchat, [params['admin_user']]))
    await client(EditAdminRequest(
        superchat,
        params['admin_user'],
        ChatAdminRights(
            change_info=True,
            delete_messages=True,
            ban_users=True,
            invite_users=True,
            pin_messages=True,
            add_admins=False,
            manage_call=True
        ),
        rank="Main boss"
    ))

    # ✅ Xabar yuborish
    await client.send_message(superchat.id, f"📅 Guruh ochildi: {sana_xabar}\n🔗 Havola: {link}")

    if bot_send:
        await bot_send(f"[{session_name}] ✅ Guruh yaratildi: {guruh_nom}\n🔗 {link}")

    # ✅ Indexni oshirish
    params['index'] += 1
    add_or_update_session(session_name, params)

async def session_worker(session_name, api_id, api_hash, bot_send=None):
    params = get_session(session_name)
    if not params:
        if bot_send:
            await bot_send(f"❌ Parametrlar topilmadi: {session_name}")
        return

    session_file = f"sessions/{session_name}"
    client = TelegramClient(session_file, api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        if bot_send:
            await bot_send(f"❌ {session_name} login qilmagan!")
        await client.disconnect()
        return

    stop_flags[session_name] = False
    if bot_send:
        await bot_send(f"✅ {session_name} ishga tushdi. Delay: {params['delay']}s")

    while not stop_flags[session_name]:
        try:
            await guruh_ochish(client, session_name, params, bot_send)

            # Delay teskari sanash
            for s in range(params['delay'], 0, -1):
                if stop_flags[session_name]:
                    break
                if bot_send:
                    await bot_send(f"[{session_name}] ⏳ {s} sekund qoldi...")
                await asyncio.sleep(1)

        except FloodWaitError as e:
            if bot_send:
                await bot_send(f"⚠️ [FloodWait] {session_name}: {e.seconds} sekund kutyapmiz...")
            for s in range(e.seconds, 0, -1):
                if stop_flags[session_name]:
                    break
                if bot_send:
                    await bot_send(f"[{session_name}] ⏳ FloodWait: {s}...")
                await asyncio.sleep(1)
        except Exception as e:
            if bot_send:
                await bot_send(f"❌ {session_name}: Xatolik: {e}")
            break

    await client.disconnect()
    if bot_send:
        await bot_send(f"🛑 {session_name} to‘xtadi.")

def stop_session(session_name):
    stop_flags[session_name] = True

def stop_all_sessions():
    for s in stop_flags:
        stop_flags[s] = True

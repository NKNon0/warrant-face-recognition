import os
import logging
from datetime import datetime
import aiohttp
from app.db import get_connection
from app.ai_processor import process_media
from dotenv import load_dotenv
import aiomysql

load_dotenv()

logger = logging.getLogger(__name__)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://127.0.0.1:8000")


async def fetch_file_path(file_id: str) -> str:
    async with aiohttp.ClientSession() as session:
        url = f"{TELEGRAM_API}/getFile?file_id={file_id}"
        async with session.get(url) as resp:
            data = await resp.json()
            return data["result"]["file_path"]


async def download_file(file_path: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        async with session.get(url) as resp:
            return await resp.read()


async def send_message(chat_id: int, text: str, reply_markup: dict = None):
    async with aiohttp.ClientSession() as session:
        url = f"{TELEGRAM_API}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error(f"sendMessage Error (chat_id: {chat_id}): {data}")
            return data


async def answer_callback_query(callback_query_id: str, text: str):
    async with aiohttp.ClientSession() as session:
        url = f"{TELEGRAM_API}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id, "text": text}
        await session.post(url, json=payload)


async def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict = None):
    async with aiohttp.ClientSession() as session:
        url = f"{TELEGRAM_API}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        await session.post(url, json=payload)


async def send_photo(chat_id: int, photo_path: str, caption: str):
    """ส่งรูปภาพพร้อม caption ไปยัง Telegram"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{TELEGRAM_API}/sendPhoto"
            with open(photo_path, "rb") as f:
                form = aiohttp.FormData()
                form.add_field("chat_id", str(chat_id))
                form.add_field("caption", caption)
                form.add_field("parse_mode", "HTML")
                form.add_field("photo", f, filename=os.path.basename(photo_path), content_type="image/jpeg")
                async with session.post(url, data=form) as resp:
                    return await resp.json()
    except Exception as e:
        logger.error(f"send_photo error: {e}")
        await send_message(chat_id, caption)


async def upsert_user(telegram_id: int, username: str, first_name: str) -> dict:
    """บันทึกหรืออัปเดต user ใน database และ auto-authorize ทุกคนโดยอัตโนมัติเพื่อความสะดวก"""
    is_admin = (telegram_id == ADMIN_TELEGRAM_ID)
    async with await get_connection() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            role = 'admin' if is_admin else 'police'
            await cur.execute(
                """INSERT INTO users (telegram_id, username, first_name, is_authorized, role)
                   VALUES (%s, %s, %s, 1, %s)
                   ON DUPLICATE KEY UPDATE username=VALUES(username), first_name=VALUES(first_name), is_authorized=1""",
                (telegram_id, username or "", first_name or "", role),
            )
            await cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            return await cur.fetchone()


async def set_user_authorization(telegram_id: int, is_authorized: bool):
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE users SET is_authorized = %s WHERE telegram_id = %s",
                (1 if is_authorized else 0, telegram_id),
            )


def get_base_url() -> str:
    url = (os.getenv("WEBAPP_URL") or "http://127.0.0.1:8000").strip().rstrip("/")
    if url.endswith("/static/index.html"):
        url = url[:-len("/static/index.html")]
    elif url.endswith("/static"):
        url = url[:-len("/static")]
    return url


def get_miniapp_url() -> str:
    base = get_base_url()
    return f"{base}/static/index.html"


async def set_telegram_webhook():
    """ลงทะเบียน Webhook URL กับ Telegram API เพื่อรับข้อความและคำสั่ง /start"""
    base = get_base_url()
    if base.startswith("https://"):
        webhook_url = f"{base}/telegram-webhook"
        url = f"{TELEGRAM_API}/setWebhook"
        payload = {"url": webhook_url}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    res = await resp.json()
                    logger.info(f"setWebhook ({webhook_url}): {res}")
                    print(f"[Telegram Bot] Webhook Registered: {webhook_url} -> {res}")
        except Exception as e:
            logger.error(f"setWebhook error: {e}")


async def set_telegram_menu_button(chat_id: int | None = None):
    """ตั้งค่าปุ่ม Mini App ตรงเมนูล่างซ้ายของ Telegram เป็นปุ่มหลักเพียงอันเดียว"""
    base = get_base_url()
    if base.startswith("https://"):
        target_url = get_miniapp_url()
        url = f"{TELEGRAM_API}/setChatMenuButton"
        payload = {
            "menu_button": {
                "type": "web_app",
                "text": "MiniApp",
                "web_app": {"url": target_url}
            }
        }
        if chat_id:
            payload["chat_id"] = chat_id
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    res = await resp.json()
                    logger.info(f"setChatMenuButton: {res}")
                    print(f"[Telegram Bot] Menu Button Set ({target_url}): {res}")
        except Exception as e:
            logger.error(f"setChatMenuButton error: {e}")


def build_authorized_keyboard() -> dict | None:
    """สร้าง Inline Keyboard ปุ่ม Mini App ปุ่มใหญ่ส่งไปในแชททันที"""
    base = get_base_url()
    if base.startswith("https://"):
        target_url = get_miniapp_url()
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "🚀 เปิดระบบสแกน MiniApp (คลิกที่นี่)",
                        "web_app": {"url": target_url}
                    }
                ]
            ]
        }
    return None


def format_face_result(result: dict, detected_at: str) -> str:
    """สร้างข้อความผลลัพธ์แบบมีโครงสร้างเหมือนในภาพ"""
    score = result.get("score", 0)
    text = (
        f"📅 <b>วันที่:</b> {detected_at}\n"
        f"🪪 <b>เลขบัตร:</b> {result.get('id_number', '-')}\n"
        f"👤 <b>ชื่อ:</b> {result.get('person_name', '-')}\n"
        f"📋 <b>รายละเอียด:</b> {result.get('detail', '-')}\n"
        f"🏠 <b>โรงพัก:</b> {result.get('station', '-')}\n"
        f"⚖️ <b>ศาล:</b> {result.get('court', '-')}\n"
        f"🎯 <b>ความคล้าย:</b> {score:.2f}%\n"
        f"🕐 <b>เวลาที่พบ:</b> {result.get('found_at', '-')}"
    )
    return text


async def handle_callback_query(callback_query: dict):
    cb_id = callback_query["id"]
    data = callback_query.get("data", "")
    from_user = callback_query.get("from", {})
    msg = callback_query.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    if data.startswith("approve_"):
        target_id = int(data.replace("approve_", ""))
        await set_user_authorization(target_id, True)
        await answer_callback_query(cb_id, "✅ อนุมัติสิทธิ์เรียบร้อยแล้ว")
        await edit_message_text(
            chat_id,
            message_id,
            f"{msg.get('text', '')}\n\n✅ <b>สถานะ: อนุมัติสิทธิ์เรียบร้อยแล้ว</b>",
            reply_markup={"inline_keyboard": []},
        )
        # ส่งข้อความแจ้งผู้ใช้ที่ได้รับการอนุมัติ
        markup = build_authorized_keyboard()
        await send_message(
            target_id,
            "🎉 <b>ยินดีด้วย! บัญชีของคุณได้รับการอนุมัติให้ใช้งานระบบเรียบร้อยแล้ว</b>\n\n"
            "📸 คุณสามารถส่งรูปภาพ (ใบหน้า / บัตรประชาชน / ป้ายทะเบียน) เข้ามาในแชทนี้เพื่อทำการตรวจสอบประวัติอาชญากรรมได้ทันทีครับ!",
            reply_markup=markup,
        )

    elif data.startswith("reject_"):
        target_id = int(data.replace("reject_", ""))
        await set_user_authorization(target_id, False)
        await answer_callback_query(cb_id, "❌ ปฏิเสธสิทธิ์เรียบร้อยแล้ว")
        await edit_message_text(
            chat_id,
            message_id,
            f"{msg.get('text', '')}\n\n❌ <b>สถานะ: ปฏิเสธคำขอเข้าใช้งาน</b>",
            reply_markup={"inline_keyboard": []},
        )
        await send_message(
            target_id,
            "⚠️ <b>คำขอเข้าใช้งานระบบของคุณถูกปฏิเสธ</b>\n"
            "กรุณาติดต่อผู้ดูแลระบบหากคิดว่าเป็นข้อผิดพลาด",
        )


async def handle_telegram_update(update: dict):
    if "callback_query" in update:
        await handle_callback_query(update["callback_query"])
        return

    message = update.get("message")
    if not message:
        return

    chat_id = message["chat"]["id"]
    from_user = message.get("from", {})
    telegram_id = from_user.get("id")
    username = from_user.get("username", "")
    first_name = from_user.get("first_name", "")
    text = message.get("text", "")

    # บันทึก/ดึง user จาก database
    user_record = None
    if telegram_id:
        try:
            user_record = await upsert_user(telegram_id, username, first_name)
        except Exception as e:
            logger.error(f"upsert_user error: {e}")

    is_authorized = bool(user_record and (user_record.get("is_authorized") == 1 or user_record.get("role") == 'admin'))
    user_db_id = user_record["id"] if user_record else None

    # กรณีส่งคำสั่ง /start
    if text == "/start":
        await set_telegram_menu_button(chat_id)
        if is_authorized:
            markup = build_authorized_keyboard()
            await send_message(
                chat_id,
                f"👮‍♂️ สวัสดีครับ <b>{first_name}</b>!\n"
                f"ยินดีต้อนรับสู่ระบบ AI ตรวจสอบประวัติอาชญากรรมสำหรับเจ้าหน้าที่ตำรวจ\n\n"
                f"📸 ท่านสามารถส่งรูปภาพ (ใบหน้า/บัตรประชาชน/ป้ายทะเบียน) เข้ามาในแชทนี้ได้ทันทีครับ",
                reply_markup=markup,
            )
        else:
            await send_message(
                chat_id,
                f"👮‍♂️ สวัสดีครับ <b>{first_name}</b>!\n"
                f"⏳ <b>บัญชีของคุณอยู่ระหว่างรอการอนุมัติสิทธิ์เข้าใช้งานจากผู้ดูแลระบบ</b>\n"
                f"ระบบได้ส่งคำขอไปยังแอดมินเรียบร้อยแล้ว กรุณารอสักครู่...",
            )
            # แจ้งเตือนแอดมิน
            if ADMIN_TELEGRAM_ID and ADMIN_TELEGRAM_ID != telegram_id:
                admin_text = (
                    f"🚨 <b>คำขอเข้าใช้งานระบบใหม่!</b>\n"
                    f"👤 <b>ชื่อ:</b> {first_name} (@{username or 'ไม่มี username'})\n"
                    f"🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>"
                )
                admin_markup = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "✅ อนุมัติ",
                                "callback_data": f"approve_{telegram_id}",
                            },
                            {
                                "text": "❌ ปฏิเสธ",
                                "callback_data": f"reject_{telegram_id}",
                            },
                        ]
                    ]
                }
                await send_message(ADMIN_TELEGRAM_ID, admin_text, reply_markup=admin_markup)
        return

    # ตรวจสอบสิทธิ์ก่อนดำเนินการอื่น ๆ
    if not is_authorized:
        await send_message(
            chat_id,
            "⚠️ <b>คุณยังไม่ได้สิทธิ์เข้าใช้งานระบบ</b>\n"
            "กรุณารอการอนุมัติจากผู้ดูแลระบบก่อนครับ",
        )
        return

    if "photo" not in message:
        await send_message(chat_id, "📸 กรุณาส่งรูปภาพเพื่อทำการตรวจสอบประวัติ")
        return

    photo_sizes = message["photo"]
    photo = photo_sizes[-1]
    file_id = photo["file_id"]
    message_id = message["message_id"]

    # เช็คว่า message นี้ถูกประมวลผลไปแล้วหรือยัง เพื่อป้องกันการส่งข้อมูลซ้ำ
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM media_requests WHERE telegram_message_id = %s",
                (message_id,),
            )
            existing = await cur.fetchone()
            if existing:
                return  # ข้ามการประมวลผลถ้าเคยทำไปแล้ว

    # บันทึก media_request
    request_id = None
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO media_requests (user_id, telegram_message_id, media_file_id, media_type, status) VALUES (%s, %s, %s, %s, %s)",
                (user_db_id, message["message_id"], file_id, "photo", "received"),
            )
            request_id = cur.lastrowid

    await send_message(chat_id, "⏳ ได้รับรูปภาพแล้ว กำลังตรวจสอบ กรุณารอสักครู่...")

    file_path = await fetch_file_path(file_id)
    image_bytes = await download_file(file_path)

    detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result_data = await process_media(request_id, image_bytes)

    # อัปเดต status
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE media_requests SET status = %s WHERE id = %s",
                ("processed", request_id),
            )

    if not result_data.get("found"):
        await send_message(chat_id, "❌ ไม่พบข้อมูลที่ตรงกับฐานข้อมูล")
        return

    for item in result_data.get("results", []):
        if item.get("type") == "face":
            caption = format_face_result(item, detected_at)
            photo_file = item.get("photo_url")
            if photo_file and os.path.exists(photo_file):
                await send_photo(chat_id, photo_file, caption)
            else:
                await send_message(chat_id, caption)

        elif item.get("type") == "plate":
            plate_msg = (
                f"🚨 <b>ผลการตรวจพบป้ายทะเบียนเฝ้าระวัง!</b>\n"
                f"🚗 <b>ป้ายทะเบียน:</b> {item.get('plate_text', '-')}\n"
                f"📍 <b>จังหวัด:</b> {item.get('province', '-')}\n"
                f"🚨 <b>หมวดหมู่:</b> {item.get('category', '-')}\n"
                f"📋 <b>สาเหตุ/รายละเอียดข้อหา:</b> {item.get('detail', '-')}\n"
                f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {item.get('station', '-')}\n"
                f"🎯 <b>ความถูกต้อง:</b> {item.get('score', 95):.2f}%"
            )
            await send_message(chat_id, plate_msg)

        elif item.get("type") == "id_card":
            id_msg = (
                f"🚨 <b>ผลการตรวจพบบัตรประชาชนเป้าหมาย!</b>\n"
                f"👤 <b>ชื่อ-สกุล:</b> {item.get('person_name') or item.get('name') or '-'}\n"
                f"🪪 <b>เลขบัตรประชาชน:</b> {item.get('id_number', '-')}\n"
                f"📋 <b>รายละเอียดข้อหา:</b> {item.get('detail', '-')}\n"
                f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {item.get('station', '-')}\n"
                f"⚖️ <b>ศาลที่ออกหมายจับ:</b> {item.get('court', '-')}\n"
                f"🎯 <b>ความคล้าย:</b> {item.get('score', 99):.2f}%"
            )
            await send_message(chat_id, id_msg)

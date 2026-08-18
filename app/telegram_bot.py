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


def format_face_result(result: dict, detected_at: str) -> str:
    """สร้างข้อความผลลัพธ์การตรวจพบใบหน้า"""
    score = result.get("score", 0.0)
    text = (
        f"🚨 <b>ผลการตรวจพบใบหน้าบุคคลเป้าหมาย!</b>\n"
        f"🔍 <b>ประเภทภาพที่ AI ตรวจพบ:</b> 👤 ใบหน้าบุคคล\n"
        f"👤 <b>ชื่อ-สกุล:</b> {result.get('person_name', '-')}\n"
        f"🪪 <b>เลขบัตรประชาชน:</b> {result.get('id_number', '-')}\n"
        f"📋 <b>รายละเอียดข้อหา:</b> {result.get('detail', '-')}\n"
        f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {result.get('station', '-')}\n"
        f"⚖️ <b>ศาลที่ออกหมายจับ:</b> {result.get('court', '-')}\n"
        f"🎯 <b>ความคล้ายคลึง:</b> {score:.2f}%\n"
        f"🕐 <b>เวลาที่ตรวจพบ:</b> {detected_at}"
    )
    return text


async def handle_callback_query(callback_query: dict):
    cb_id = callback_query["id"]
    data = callback_query.get("data", "")
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
        await send_message(
            target_id,
            "🎉 <b>ยินดีด้วย! บัญชีของคุณได้รับการอนุมัติให้ใช้งานระบบเรียบร้อยแล้ว</b>\n\n"
            "📸 <b>วิธีใช้งาน:</b>\n"
            "ท่านสามารถส่งรูปภาพ (ใบหน้า / ป้ายทะเบียนรถ / บัตรประชาชน) เข้ามาในแชทนี้ได้โดยตรง ระบบ AI จะวิเคราะห์และตรวจสอบให้ทันทีครับ!",
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

    # กรณีส่งคำสั่ง /start หรือ /help
    if text in ["/start", "/help"]:
        if is_authorized:
            welcome_msg = (
                f"👮‍♂️ สวัสดีครับ <b>{first_name}</b>!\n"
                f"ยินดีต้อนรับสู่ระบบ <b>AI ตรวจสอบประวัติอาชญากรรมและหมายจับอัตโนมัติ</b>\n\n"
                f"📸 <b>วิธีใช้งาน:</b>\n"
                f"ส่งรูปภาพเข้ามาในแชทนี้ได้ทันทีครับ โดย AI จะทำการแยกประเภทอัตโนมัติ:\n"
                f" • 👤 <b>ใบหน้าบุคคล</b> ➔ ค้นหาเปรียบเทียบใบหน้าผู้ต้องหาตามหมายจับ\n"
                f" • 🚗 <b>ป้ายทะเบียนรถ</b> ➔ ตรวจสอบรถชนแล้วหนี / รถผิดกฎหมาย / รถ พ.ร.บ ขาด\n"
                f" • 🪪 <b>บัตรประชาชน</b> ➔ ตรวจสอบเลขประจำตัว 13 หลักและชื่อผู้ต้องหา\n\n"
                f"<i>ท่านสามารถถ่ายภาพหรือแนบรูปภาพส่งเข้ามาได้ตลอดเวลาครับ 🚀</i>"
            )
            await send_message(chat_id, welcome_msg)
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
        await send_message(
            chat_id,
            "📸 กรุณาส่งรูปภาพ (ใบหน้าบุคคล / ป้ายทะเบียนรถ / บัตรประชาชน) เข้ามาในแชทเพื่อเริ่มการตรวจสอบครับ"
        )
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
                return

    # บันทึก media_request
    request_id = None
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO media_requests (user_id, telegram_message_id, media_file_id, media_type, status) VALUES (%s, %s, %s, %s, %s)",
                (user_db_id, message["message_id"], file_id, "photo", "received"),
            )
            request_id = cur.lastrowid

    await send_message(chat_id, "⏳ <b>ได้รับรูปภาพแล้ว</b> AI กำลังจำแนกประเภทและตรวจสอบกับฐานข้อมูลหมายจับ...")

    file_path = await fetch_file_path(file_id)
    image_bytes = await download_file(file_path)

    detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result_data = await process_media(request_id, image_bytes, mode="auto")

    # อัปเดต status
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE media_requests SET status = %s WHERE id = %s",
                ("processed", request_id),
            )

    detected_type_label = result_data.get("detected_type_label", "🔍 ภาพที่ส่งเข้ามา")

    if not result_data.get("found"):
        not_found_msg = (
            f"❌ <b>ไม่พบข้อมูลในฐานข้อมูลหมายจับ</b>\n"
            f"🔍 <b>ประเภทภาพที่ AI ตรวจพบ:</b> {detected_type_label}\n\n"
            f"ℹ️ ตรวจสอบแล้วไม่พบข้อมูลประวัติหมายจับ ยานพาหนะเฝ้าระวัง หรือข้อมูลผู้ต้องสงสัยในระบบ"
        )
        await send_message(chat_id, not_found_msg)
        return

    for item in result_data.get("results", []):
        item_type = item.get("type")

        if item_type == "face":
            caption = format_face_result(item, detected_at)
            photo_file = item.get("photo_url")
            if photo_file and os.path.exists(photo_file):
                await send_photo(chat_id, photo_file, caption)
            else:
                await send_message(chat_id, caption)

        elif item_type == "plate":
            score = item.get("score", 95.0)
            plate_msg = (
                f"🚨 <b>ผลการตรวจพบป้ายทะเบียนรถเฝ้าระวัง!</b>\n"
                f"🔍 <b>ประเภทภาพที่ AI ตรวจพบ:</b> 🚗 ป้ายทะเบียนรถ\n"
                f"🚗 <b>ป้ายทะเบียน:</b> {item.get('plate_text', '-')}\n"
                f"📍 <b>จังหวัด:</b> {item.get('province', '-')}\n"
                f"🚨 <b>หมวดหมู่:</b> {item.get('category', '-')}\n"
                f"📋 <b>สาเหตุ/รายละเอียดข้อหา:</b> {item.get('detail', '-')}\n"
                f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {item.get('station', '-')}\n"
                f"🎯 <b>ความถูกต้อง:</b> {score:.2f}%\n"
                f"🕐 <b>เวลาที่ตรวจพบ:</b> {detected_at}"
            )
            await send_message(chat_id, plate_msg)

        elif item_type == "id_card":
            score = item.get("score", 99.85)
            id_msg = (
                f"🚨 <b>ผลการตรวจพบบัตรประชาชนหมายจับ!</b>\n"
                f"🔍 <b>ประเภทภาพที่ AI ตรวจพบ:</b> 🪪 บัตรประจำตัวประชาชน\n"
                f"👤 <b>ชื่อ-สกุล:</b> {item.get('person_name') or item.get('name') or '-'}\n"
                f"🪪 <b>เลขบัตรประชาชน:</b> {item.get('id_number', '-')}\n"
                f"📋 <b>รายละเอียดข้อหา:</b> {item.get('detail', '-')}\n"
                f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {item.get('station', '-')}\n"
                f"⚖️ <b>ศาลที่ออกหมายจับ:</b> {item.get('court', '-')}\n"
                f"🎯 <b>ความคล้ายคลึง:</b> {score:.2f}%\n"
                f"🕐 <b>เวลาที่ตรวจพบ:</b> {detected_at}"
            )
            await send_message(chat_id, id_msg)

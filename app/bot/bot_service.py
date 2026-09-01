import os
import logging
from datetime import datetime
import aiohttp
import aiomysql
from app.config import TELEGRAM_TOKEN, TELEGRAM_API, ADMIN_TELEGRAM_ID
from app.db.mysql import get_connection
from app.core.router import process_media
from .formatter import format_face_result, format_plate_result, format_id_card_result

logger = logging.getLogger(__name__)


async def fetch_file_path(file_id: str) -> str:
    """ดึง URL เส้นทางไฟล์จาก Telegram API"""
    async with aiohttp.ClientSession() as session:
        url = f"{TELEGRAM_API}/getFile?file_id={file_id}"
        async with session.get(url) as resp:
            data = await resp.json()
            return data["result"]["file_path"]


async def download_file(file_path: str) -> bytes:
    """ดาวน์โหลดรูปภาพจาก Telegram Server"""
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        async with session.get(url) as resp:
            return await resp.read()


async def send_message(chat_id: int, text: str, reply_markup: dict = None):
    """ส่งข้อความ HTML ไปยัง Telegram Chat"""
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
    """ตอบรับ Callback Query จาก Inline Buttons"""
    async with aiohttp.ClientSession() as session:
        url = f"{TELEGRAM_API}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id, "text": text}
        await session.post(url, json=payload)


async def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict = None):
    """แก้ไขข้อความเดิมใน Telegram Chat"""
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
    """ส่งรูปภาพพร้อม Caption ไปยัง Telegram"""
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
    """ปรับสถานะการอนุญาตเข้าใช้งาน"""
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE users SET is_authorized = %s WHERE telegram_id = %s",
                (1 if is_authorized else 0, telegram_id),
            )


async def remove_telegram_menu_button(chat_id: int | None = None):
    """ลบปุ่ม Mini App, Menu Button และ Command List ออกจาก Telegram ทั้งหมดอย่างถาวร"""
    try:
        async with aiohttp.ClientSession() as session:
            # 1. รีเซ็ต Menu Button ให้เป็น Default (ไม่มีปุ่มเปิดเว็บ/แอป)
            menu_url = f"{TELEGRAM_API}/setChatMenuButton"
            payload = {"menu_button": {"type": "default"}}
            if chat_id:
                payload["chat_id"] = chat_id
            await session.post(menu_url, json=payload)

            # 2. ล้างคำสั่งเมนูบอท (deleteMyCommands)
            del_cmd_url = f"{TELEGRAM_API}/deleteMyCommands"
            await session.post(del_cmd_url, json={})
    except Exception as e:
        logger.error(f"remove_telegram_menu_button error: {e}")


async def handle_callback_query(callback_query: dict):
    """จัดการการกดปุ่ม Inline Buttons"""
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
    """ฟังก์ชันหลักสำหรับรับและประมวลผลข้อความจาก Telegram Bot (Direct Chat Architecture)"""
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

    # ผู้ดูแลระบบ (Admin) และผู้ใช้ทุกคนได้รับสิทธิ์เข้าใช้งานทันที (Instant Access / Auto-Authorized)
    is_admin = (telegram_id == ADMIN_TELEGRAM_ID) or (user_record and user_record.get("role") == "admin")
    if is_admin:
        is_authorized = True
    elif user_record:
        # หากมีข้อมูลในฐานข้อมูล และไม่ถูกระงับสิทธิ์ชัดเจน
        is_authorized = bool(user_record.get("is_authorized", 1) == 1)
    else:
        # อนุญาตให้เข้าใช้งานได้ทันทีสำหรับการปฏิบัติงาน
        is_authorized = True

    user_db_id = user_record["id"] if user_record else None

    # กรณีส่งคำสั่ง /start หรือ /help
    if text in ["/start", "/help"]:
        await remove_telegram_menu_button(chat_id)
        welcome_msg = (
            f"👮‍♂️ สวัสดีครับ <b>{first_name}</b>!\n"
            f"ยินดีต้อนรับสู่ระบบ <b>AI ตรวจสอบประวัติอาชญากรรมและหมายจับอัตโนมัติ (C.I.A.S.)</b>\n\n"
            f"📸 <b>วิธีใช้งาน:</b>\n"
            f"ส่งรูปภาพเข้ามาในแชทนี้ได้ทันทีครับ โดย AI จะทำการแยกประเภทอัตโนมัติ:\n"
            f" • 👤 <b>ใบหน้าบุคคล</b> ➔ ค้นหาเปรียบเทียบใบหน้าผู้ต้องหาตามหมายจับ (ชุดข้อมูล 31 บุคคล)\n"
            f" • 🚗 <b>ป้ายทะเบียนรถ</b> ➔ ตรวจสอบรถชนแล้วหนี / รถผิดกฎหมาย / รถ พ.ร.บ ขาด (4 หมวด)\n"
            f" • 🪪 <b>บัตรประชาชน</b> ➔ ตรวจสอบเลขประจำตัว 13 หลักและชื่อผู้ต้องหา\n\n"
            f"<i>ท่านสามารถถ่ายภาพหรือแนบรูปภาพส่งเข้ามาได้ตลอดเวลาครับ 🚀</i>"
        )
        await send_message(chat_id, welcome_msg)
        return

    # ตรวจสอบสิทธิ์กรณีถูกระงับสิทธิ์โดยชัดเจน
    if not is_authorized:
        await send_message(
            chat_id,
            "⚠️ <b>บัญชีของคุณถูกระงับสิทธิ์การใช้งานชั่วคราว</b>\n"
            "กรุณาติดต่อผู้ดูแลระบบเพื่อขอเปิดใช้งานสิทธิ์ครับ",
        )
        return

    if "photo" not in message:
        await send_message(
            chat_id,
            "📸 <b>กรุณาส่งรูปภาพเข้ามาในแชท</b>\n"
            "ท่านสามารถส่งภาพถ่ายใบหน้าบุคคล ป้ายทะเบียนรถ หรือบัตรประชาชน เพื่อให้ AI ตรวจสอบได้ทันทีครับ!",
        )
        return

    photo_sizes = message["photo"]
    photo = photo_sizes[-1]
    file_id = photo["file_id"]
    message_id = message["message_id"]

    # 1. เช็คว่า message นี้ถูกประมวลผลไปแล้วหรือยัง เพื่อป้องกันการส่งข้อมูลซ้ำ
    try:
        async with await get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT id FROM media_requests WHERE telegram_message_id = %s",
                    (message_id,),
                )
                existing = await cur.fetchone()
                if existing:
                    return
    except Exception as e:
        logger.debug(f"check existing media_request note: {e}")

    # 2. บันทึก media_request
    request_id = None
    try:
        async with await get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO media_requests (user_id, telegram_message_id, media_file_id, media_type, status) VALUES (%s, %s, %s, %s, %s)",
                    (user_db_id, message["message_id"], file_id, "photo", "received"),
                )
                request_id = cur.lastrowid
    except Exception as e:
        logger.debug(f"insert media_request note: {e}")

    await send_message(chat_id, "⏳ <b>ได้รับรูปภาพแล้ว</b> AI กำลังจำแนกประเภทและตรวจสอบกับฐานข้อมูลหมายจับ...")

    file_path = await fetch_file_path(file_id)
    image_bytes = await download_file(file_path)

    detected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        result_data = await process_media(request_id, image_bytes, mode="auto")
    except Exception as ex:
        logger.error(f"Error in process_media: {ex}")
        result_data = {
            "found": False,
            "detected_type_label": "🔍 ภาพที่ส่งเข้ามา",
            "message": f"เกิดข้อผิดพลาดในการประมวลผลรูปภาพ: {ex}"
        }

    # 3. อัปเดต status
    if request_id:
        try:
            async with await get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "UPDATE media_requests SET status = %s WHERE id = %s",
                        ("processed", request_id),
                    )
        except Exception as e:
            logger.debug(f"update media_requests status note: {e}")

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
            plate_msg = format_plate_result(item, detected_at)
            await send_message(chat_id, plate_msg)

        elif item_type == "id_card":
            id_msg = format_id_card_result(item, detected_at)
            await send_message(chat_id, id_msg)

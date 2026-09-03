import os
import logging
from datetime import datetime
from urllib.parse import quote_plus
import socket
import aiohttp
import aiomysql
from app.config import TELEGRAM_TOKEN, TELEGRAM_API, ADMIN_TELEGRAM_ID
from app.db.mysql import get_connection
from app.core.router import process_media
from .formatter import format_face_result, format_plate_result, format_id_card_result

logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    """ดึงหมายเลข IPv4 สำหรับเชื่อมต่อจากอุปกรณ์ในเครือข่าย Local Network"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


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


async def answer_callback_query(callback_query_id: str, text: str, show_alert: bool = False):
    """ตอบรับ Callback Query จาก Inline Buttons พร้อมแจ้งเตือนแบบ Modal Alert"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{TELEGRAM_API}/answerCallbackQuery"
            payload = {
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": show_alert,
            }
            await session.post(url, json=payload)
    except Exception as e:
        logger.error(f"answer_callback_query error: {e}")


async def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict = None):
    """แก้ไขข้อความเดิมใน Telegram Chat พร้อมดักจับข้อผิดพลาด"""
    try:
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
            async with session.post(url, json=payload) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    logger.error(f"editMessageText Error: {data}")
                return data
    except Exception as e:
        logger.error(f"edit_message_text error: {e}")


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


async def get_user(telegram_id: int) -> dict | None:
    """ดึงข้อมูลผู้ใช้จากฐานข้อมูลตาม telegram_id"""
    try:
        async with await get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                return await cur.fetchone()
    except Exception as e:
        logger.error(f"get_user error: {e}")
        return None


async def upsert_user(telegram_id: int, username: str, first_name: str) -> dict:
    """บันทึกหรืออัปเดต user ใน database โดยแยก Admin กับ ผู้ใช้งานใหม่ที่ต้องลงทะเบียน"""
    is_admin = (telegram_id == ADMIN_TELEGRAM_ID)
    async with await get_connection() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            user_record = await cur.fetchone()

            if is_admin:
                await cur.execute(
                    """INSERT INTO users (telegram_id, username, first_name, is_authorized, role)
                       VALUES (%s, %s, %s, 1, 'admin')
                       ON DUPLICATE KEY UPDATE username=VALUES(username), first_name=VALUES(first_name), is_authorized=1, role='admin'""",
                    (telegram_id, username or "", first_name or ""),
                )
            elif not user_record:
                # ผู้ใช้ใหม่ที่ยังไม่เคยลงทะเบียน: บันทึกสถานะเริ่มต้น รอการกรอกข้อมูลใน URL
                await cur.execute(
                    """INSERT INTO users (telegram_id, username, first_name, is_authorized, role)
                       VALUES (%s, %s, %s, 0, 'police')""",
                    (telegram_id, username or "", first_name or ""),
                )
            else:
                # อัปเดต username ล่าสุด โดยไม่แตะต้องสถานะอนุมัติและข้อมูลยศ/สังกัด
                await cur.execute(
                    """UPDATE users SET username = %s, first_name = %s WHERE telegram_id = %s""",
                    (username or "", first_name or "", telegram_id),
                )

            await conn.commit()
            await cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
            return await cur.fetchone()


async def set_user_authorization(telegram_id: int, is_authorized: bool) -> bool:
    """ปรับสถานะการอนุญาตเข้าใช้งานและ commit ทันที"""
    try:
        async with await get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE users SET is_authorized = %s WHERE telegram_id = %s",
                    (1 if is_authorized else 0, telegram_id),
                )
                await conn.commit()
                return True
    except Exception as e:
        logger.error(f"set_user_authorization error: {e}")
        return False


async def remove_telegram_menu_button(chat_id: int | None = None):
    """ลบปุ่ม Mini App, Menu Button และ Command List ออกจาก Telegram ทั้งหมดอย่างถาวร"""
    try:
        async with aiohttp.ClientSession() as session:
            menu_url = f"{TELEGRAM_API}/setChatMenuButton"
            payload = {"menu_button": {"type": "default"}}
            if chat_id:
                payload["chat_id"] = chat_id
            await session.post(menu_url, json=payload)

            del_cmd_url = f"{TELEGRAM_API}/deleteMyCommands"
            await session.post(del_cmd_url, json={})
    except Exception as e:
        logger.error(f"remove_telegram_menu_button error: {e}")


async def handle_callback_query(callback_query: dict):
    """จัดการการกดปุ่ม Inline Buttons อนุมัติ/ระงับสิทธิ์ พร้อมแจ้งเตือนทันที"""
    cb_id = callback_query["id"]
    data = callback_query.get("data", "")
    msg = callback_query.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    message_id = msg.get("message_id")

    try:
        if data.startswith("approve_"):
            target_id = int(data.replace("approve_", ""))
            # 1. ปรับสถานะในฐานข้อมูล
            await set_user_authorization(target_id, True)

            # 2. ดึงข้อมูลผู้ใช้เพื่อแสดงผล
            user_info = await get_user(target_id)
            rank = (user_info.get("rank_title") or "") if user_info else ""
            name = (user_info.get("first_name") or "") if user_info else ""
            station = (user_info.get("police_station") or "") if user_info else ""
            phone = (user_info.get("phone_number") or "") if user_info else ""
            display_name = f"{rank} {name}".strip() or f"User ({target_id})"

            # 3. เด้ง Modal Alert บนหน้าจอ Admin ทันที
            await answer_callback_query(
                cb_id,
                f"✅ อนุมัติสิทธิ์เรียบร้อยแล้ว!\nเจ้าหน้าที่: {display_name}",
                show_alert=True,
            )

            # 4. ปรับเปลี่ยนการ์ดใน Telegram ของ Admin ให้แสดงสถานะอนุมัติเรียบร้อย
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            updated_card = (
                f"🚨 <b>ข้อมูลคำขอลงทะเบียนเข้าใช้งาน (C.I.A.S.)</b>\n\n"
                f"🎖️ <b>ยศ - ชื่อ:</b> {display_name}\n"
                f"🏢 <b>ตำแหน่ง/สังกัด:</b> {station or '-'}\n"
                f"📞 <b>เบอร์โทรศัพท์:</b> {phone or '-'}\n"
                f"🆔 <b>Telegram ID:</b> <code>{target_id}</code>\n\n"
                f"==============================\n"
                f"✅ <b>สถานะ: อนุมัติสิทธิ์เรียบร้อยแล้ว</b>\n"
                f"👮‍♂️ <b>ผู้อนุมัติ:</b> ผู้ดูแลระบบ (Admin)\n"
                f"🕒 <b>เวลาที่อนุมัติ:</b> {now_str}\n"
                f"=============================="
            )
            update_markup = {
                "inline_keyboard": [
                    [
                        {"text": "🔒 ระงับสิทธิ์การใช้งาน", "callback_data": f"reject_{target_id}"}
                    ]
                ]
            }
            await edit_message_text(chat_id, message_id, updated_card, reply_markup=update_markup)

            # 5. ส่งข้อความต้อนรับและแจ้งผลไปยัง User ทันที
            user_notify = (
                f"🎉 <b>ยินดีด้วยครับ! บัญชีของท่านได้รับการอนุมัติเรียบร้อยแล้ว</b>\n\n"
                f"🎖️ <b>ยศ - ชื่อ:</b> {display_name}\n"
                f"🏢 <b>ตำแหน่ง/สังกัด:</b> {station or '-'}\n\n"
                f"✅ <b>ท่านได้รับสิทธิ์เข้าใช้งานระบบสืบค้น AI เต็มรูปแบบ:</b>\n"
                f" • 👤 <b>ค้นหาใบหน้า</b> ➔ ส่งภาพใบหน้าเพื่อตรวจจับและเทียบหมายจับ\n"
                f" • 🚗 <b>ค้นหาป้ายทะเบียน</b> ➔ ส่งภาพรถเพื่อตรวจจับป้ายทะเบียน 4 หมวด\n"
                f" • 🪪 <b>ค้นหาบัตรประชาชน</b> ➔ ตรวจสอบเลข 13 หลักและชื่อผู้ต้องหา\n\n"
                f"<i>ท่านสามารถส่งรูปภาพเข้ามาในแชทนี้ได้ทันทีครับ 🚀</i>"
            )
            await send_message(target_id, user_notify)

            # 6. ส่งข้อความยืนยันในห้องแชทของ Admin
            admin_confirm = (
                f"✅ <b>ดำเนินการสำเร็จ:</b>\n"
                f"อนุมัติสิทธิ์ให้แก่ <b>{display_name}</b> (สังกัด: {station or '-'}) เรียบร้อยแล้ว พร้อมส่งการแจ้งเตือนหาเจ้าหน้าที่แล้วครับ 🚀"
            )
            await send_message(chat_id, admin_confirm)

        elif data.startswith("reject_"):
            target_id = int(data.replace("reject_", ""))
            # 1. ปรับสถานะเป็นระงับ
            await set_user_authorization(target_id, False)

            # 2. ดึงข้อมูลผู้ใช้
            user_info = await get_user(target_id)
            rank = (user_info.get("rank_title") or "") if user_info else ""
            name = (user_info.get("first_name") or "") if user_info else ""
            station = (user_info.get("police_station") or "") if user_info else ""
            phone = (user_info.get("phone_number") or "") if user_info else ""
            display_name = f"{rank} {name}".strip() or f"User ({target_id})"

            # 3. เด้ง Modal Alert บนหน้าจอ Admin
            await answer_callback_query(
                cb_id,
                f"🔒 ระงับสิทธิ์เรียบร้อยแล้ว!\nเจ้าหน้าที่: {display_name}",
                show_alert=True,
            )

            # 4. อัปเดตการ์ดเป็นสถานะระงับสิทธิ์ พร้อมปุ่มเปิดอนุมัติอีกครั้ง
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            updated_card = (
                f"🚨 <b>ข้อมูลคำขอลงทะเบียนเข้าใช้งาน (C.I.A.S.)</b>\n\n"
                f"🎖️ <b>ยศ - ชื่อ:</b> {display_name}\n"
                f"🏢 <b>ตำแหน่ง/สังกัด:</b> {station or '-'}\n"
                f"📞 <b>เบอร์โทรศัพท์:</b> {phone or '-'}\n"
                f"🆔 <b>Telegram ID:</b> <code>{target_id}</code>\n\n"
                f"==============================\n"
                f"🔒 <b>สถานะ: ระงับสิทธิ์การใช้งาน</b>\n"
                f"👮‍♂️ <b>ผู้ดำเนินการ:</b> ผู้ดูแลระบบ (Admin)\n"
                f"🕒 <b>เวลาที่ระงับ:</b> {now_str}\n"
                f"=============================="
            )
            update_markup = {
                "inline_keyboard": [
                    [
                        {"text": "✅ เปิดอนุมัติสิทธิ์อีกครั้ง", "callback_data": f"approve_{target_id}"}
                    ]
                ]
            }
            await edit_message_text(chat_id, message_id, updated_card, reply_markup=update_markup)

            # 5. แจ้งเตือนผู้ใช้
            user_notify = (
                f"⚠️ <b>แจ้งเตือน: บัญชีของท่านถูกระงับสิทธิ์การใช้งานชั่วคราว</b>\n\n"
                f"หากคิดว่าเป็นข้อผิดพลาด กรุณาติดต่อผู้ดูแลระบบเพื่อตรวจสอบข้อมูลครับ"
            )
            await send_message(target_id, user_notify)

            # 6. แจ้งยืนยัน Admin
            admin_confirm = f"🔒 <b>ดำเนินการสำเร็จ:</b> ได้ระงับสิทธิ์ของ <b>{display_name}</b> เรียบร้อยแล้ว"
            await send_message(chat_id, admin_confirm)

    except Exception as e:
        logger.error(f"Error handling callback_query {data}: {e}", exc_info=True)
        await answer_callback_query(cb_id, f"❌ เกิดข้อผิดพลาด: {e}", show_alert=True)


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

    user_db_id = user_record["id"] if user_record else None

    # ==========================================
    # 👑 ฝั่งผู้ดูแลระบบ (Admin)
    # ==========================================
    is_admin = (telegram_id == ADMIN_TELEGRAM_ID) or (user_record and user_record.get("role") == "admin")

    if is_admin:
        if text in ["/start", "/help"]:
            await remove_telegram_menu_button(chat_id)
            admin_url = "http://127.0.0.1:8000/admin/users"
            admin_welcome = (
                f"👑 <b>สวัสดีครับท่านผู้ดูแลระบบ (Admin)</b>\n"
                f"ยินดีต้อนรับสู่ระบบ <b>C.I.A.S. Management Core</b>\n\n"
                f"⚙️ <b>การจัดการระบบ:</b>\n"
                f"👉 <a href='{admin_url}'>กดที่นี่เพื่อเปิดแดชบอร์ดจัดการผู้ใช้งาน</a> (คลิกเปิดได้ทันที)\n\n"
                f"🔍 <b>ทดสอบสืบค้น AI:</b> ส่งรูปภาพใบหน้า ป้ายทะเบียน หรือบัตรประชาชน เพื่อทดสอบได้ตลอดเวลาครับ 🚀"
            )
            await send_message(chat_id, admin_welcome)
            return

    # ==========================================
    # 👮‍♂️ ฝั่งผู้ใช้งาน / เจ้าหน้าที่ตำรวจ (User)
    # ==========================================
    else:
        # ตรวจสอบว่าผู้ใช้ได้รับอนุมัติสิทธิ์หรือไม่ (is_authorized == 1)
        is_user_authorized = bool(user_record and user_record.get("is_authorized") == 1)

        if not is_user_authorized:
            # ผู้ใช้ยังไม่ได้รับอนุมัติ: ตรวจสอบว่าเคยกรอกข้อมูลใน URL แล้วหรือยัง
            has_registered = bool(
                user_record and (user_record.get("rank_title") or user_record.get("phone_number"))
            )

            if not has_registered:
                # 1. ยังไม่ได้ลงทะเบียน: ส่ง URL ให้คลิกเปิดได้ทันที
                reg_url = f"http://127.0.0.1:8000/register?tid={telegram_id}&name={quote_plus(first_name or '')}&username={quote_plus(username or '')}"

                reg_msg = (
                    f"👮‍♂️ สวัสดีครับคุณ <b>{first_name}</b>!\n"
                    f"ยินดีต้อนรับสู่ระบบ <b>AI ตรวจสอบประวัติอาชญากรรมและหมายจับอัตโนมัติ (C.I.A.S.)</b>\n\n"
                    f"⚠️ <b>จำเป็นต้องลงทะเบียนยืนยันตัวตนก่อนเริ่มใช้งาน:</b>\n"
                    f"เนื่องจากระบบจำกัดการเข้าถึงเฉพาะเจ้าหน้าที่ตำรวจและผู้ได้รับมอบหมายตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล (PDPA)\n\n"
                    f"👉 <a href='{reg_url}'>กดที่นี่เพื่อเปิดหน้าลงทะเบียน</a> (คลิกเปิดได้ทันที)\n\n"
                    f"<i>(กรอก: ยศ, ชื่อ-นามสกุล, ตำแหน่ง/สังกัด, และเบอร์โทรศัพท์)</i>\n"
                    f"เมื่อส่งข้อมูลแล้ว กรุณารอรับการอนุมัติสิทธิ์จากผู้ดูแลระบบครับ ⏳"
                )
                await send_message(chat_id, reg_msg)
                return
            else:
                # 2. ลงทะเบียนแล้ว แต่อยู่ระหว่างรออนุมัติ หรือถูกระงับสิทธิ์
                rank_str = user_record.get("rank_title") or ""
                name_str = user_record.get("first_name") or first_name
                pending_msg = (
                    f"⏳ <b>บัญชีของท่านอยู่ระหว่างรอการอนุมัติสิทธิ์จากผู้ดูแลระบบ</b>\n\n"
                    f"🎖️ <b>ยศ - ชื่อ:</b> {f'{rank_str} {name_str}'.strip()}\n"
                    f"🏢 <b>ตำแหน่ง/สังกัด:</b> {user_record.get('police_station') or '-'}\n"
                    f"📞 <b>เบอร์โทรศัพท์:</b> {user_record.get('phone_number') or '-'}\n\n"
                    f"<i>ข้อมูลของท่านถูกส่งถึงผู้ดูแลระบบเรียบร้อยแล้ว เมื่อได้รับการอนุมัติ ท่านจะได้รับการแจ้งเตือนและเริ่มใช้งานได้ทันทีครับ 🚀</i>"
                )
                await send_message(chat_id, pending_msg)
                return

        # 3. ได้รับอนุมัติแล้ว (is_authorized == 1): แสดง Welcome Message เฉพาะเมื่อพิมพ์ /start หรือ /help
        if text in ["/start", "/help"]:
            await remove_telegram_menu_button(chat_id)
            rank_str = user_record.get("rank_title") or ""
            name_str = user_record.get("first_name") or first_name
            display_name = f"{rank_str} {name_str}".strip() or first_name
            welcome_msg = (
                f"👮‍♂️ สวัสดีครับ <b>{display_name}</b>!\n"
                f"สังกัด: <b>{user_record.get('police_station') or '-'}</b>\n"
                f"ยินดีต้อนรับสู่ระบบ <b>AI ตรวจสอบประวัติอาชญากรรมและหมายจับอัตโนมัติ (C.I.A.S.)</b>\n\n"
                f"📸 <b>วิธีใช้งาน:</b>\n"
                f"ส่งรูปภาพเข้ามาในแชทนี้ได้ทันทีครับ โดย AI จะทำการแยกประเภทอัตโนมัติ:\n"
                f" • 👤 <b>ใบหน้าบุคคล</b> ➔ ค้นหาเปรียบเทียบใบหน้าผู้ต้องหาตามหมายจับ (ระบบ 512D ArcFace)\n"
                f" • 🚗 <b>ป้ายทะเบียนรถ</b> ➔ ตรวจสอบรถชนแล้วหนี / รถผิดกฎหมาย / รถ พ.ร.บ ขาด (4 หมวด)\n"
                f" • 🪪 <b>บัตรประชาชน</b> ➔ ตรวจสอบเลขประจำตัว 13 หลักและชื่อผู้ต้องหา\n\n"
                f"<i>ท่านสามารถถ่ายภาพหรือแนบรูปภาพส่งเข้ามาได้ตลอดเวลาครับ 🚀</i>"
            )
            await send_message(chat_id, welcome_msg)
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

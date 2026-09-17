import os
import json
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

THAI_TZ = timezone(timedelta(hours=7))
import socket
import aiohttp
import aiomysql
from app.config import TELEGRAM_TOKEN, TELEGRAM_API, ADMIN_TELEGRAM_ID
from app.db.mysql import get_connection
from app.core.router import process_media
from .formatter import (
    format_face_result,
    format_plate_result,
    format_id_card_result,
    format_similar_candidates_list,
    format_similar_candidate_detail,
)

logger = logging.getLogger(__name__)

# แคชจัดเก็บเซสชันบุคคลโครงหน้าใกล้เคียงรองลงมา (In-Memory Session Cache)
_SIMILAR_SESSIONS: dict[str, dict] = {}



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


_telegram_session: aiohttp.ClientSession | None = None


async def get_telegram_session() -> aiohttp.ClientSession:
    """คืนค่า ClientSession แบบ Connection Pooling พร้อม Keep-Alive เพื่อความรวดเร็วสูงสุด (< 200ms)"""
    global _telegram_session
    if _telegram_session is None or _telegram_session.closed:
        connector = aiohttp.TCPConnector(family=socket.AF_INET, limit=30, keepalive_timeout=60, enable_cleanup_closed=True)
        timeout = aiohttp.ClientTimeout(total=60, connect=25)
        _telegram_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _telegram_session


async def fetch_file_path(file_id: str) -> str:
    """ดึง URL เส้นทางไฟล์จาก Telegram API"""
    session = await get_telegram_session()
    url = f"{TELEGRAM_API}/getFile?file_id={file_id}"
    async with session.get(url) as resp:
        data = await resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram getFile error: {data}")
        return data["result"]["file_path"]


async def download_file(file_path: str) -> bytes:
    """ดาวน์โหลดรูปภาพจาก Telegram Server"""
    session = await get_telegram_session()
    url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
    async with session.get(url) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Download file failed: HTTP {resp.status}")
        return await resp.read()


async def send_message(chat_id: int, text: str, reply_markup: dict = None):
    """ส่งข้อความ HTML ไปยัง Telegram Chat"""
    try:
        session = await get_telegram_session()
        url = f"{TELEGRAM_API}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if not data.get("ok"):
                logger.error(f"sendMessage Error (chat_id: {chat_id}): {data}")
            return data
    except Exception as e:
        logger.error(f"send_message error: {e}")
        return {"ok": False, "error": str(e)}


async def answer_callback_query(callback_query_id: str, text: str = "", show_alert: bool = False):
    """ตอบรับ Callback Query จาก Inline Buttons (หากไม่ระบุ text จะไม่มี Popup เด้งขึ้นมา)"""
    try:
        session = await get_telegram_session()
        url = f"{TELEGRAM_API}/answerCallbackQuery"
        payload = {
            "callback_query_id": callback_query_id,
        }
        if text:
            payload["text"] = text
            payload["show_alert"] = show_alert
        await session.post(url, json=payload)
    except Exception as e:
        logger.error(f"answer_callback_query error: {e}")



async def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict = None):
    """แก้ไขข้อความเดิมใน Telegram Chat พร้อมดักจับข้อผิดพลาด"""
    try:
        session = await get_telegram_session()
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


async def send_photo(chat_id: int, photo_path: str, caption: str, reply_markup: dict = None):
    """ส่งรูปภาพพร้อม Caption และปุ่ม Inline Keyboard ไปยัง Telegram (รองรับ Cross-Platform Windows & Linux Docker)"""
    try:
        from app.modules.face.matcher import normalize_path
        actual_path = normalize_path(photo_path) or photo_path
        if not os.path.exists(actual_path) or not os.path.isfile(actual_path):
            logger.error(f"[Telegram] send_photo file not found: {photo_path} (resolved: {actual_path})")
            await send_message(chat_id, caption, reply_markup=reply_markup)
            return {"ok": False, "error": "file_not_found"}

        with open(actual_path, "rb") as f:
            photo_bytes = f.read()

        ext = os.path.splitext(actual_path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"

        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))
        form.add_field("caption", caption)
        form.add_field("parse_mode", "HTML")
        if reply_markup:
            form.add_field("reply_markup", json.dumps(reply_markup))
        form.add_field("photo", photo_bytes, filename=f"photo{ext}", content_type=mime)

        session = await get_telegram_session()
        url = f"{TELEGRAM_API}/sendPhoto"
        async with session.post(url, data=form) as resp:
            res_data = await resp.json()
            if not res_data.get("ok"):
                logger.error(f"[Telegram] send_photo returned not ok: {res_data}")
                await send_message(chat_id, caption, reply_markup=reply_markup)
            return res_data
    except Exception as e:
        logger.error(f"send_photo error: {e}")
        await send_message(chat_id, caption, reply_markup=reply_markup)
        return {"ok": False, "error": str(e)}



async def delete_message(chat_id: int, message_id: int) -> bool:
    """ลบข้อความ เช่น ข้อความแจ้งเตือนสถานะชั่วคราว"""
    try:
        url = f"{TELEGRAM_API}/deleteMessage"
        payload = {"chat_id": chat_id, "message_id": message_id}
        session = await get_telegram_session()
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            data = await resp.json()
            return data.get("ok", False)
    except Exception as e:
        logger.debug(f"delete_message note: {e}")
        return False


def create_composite_warrant_image(photo_path: str, warrant_path: str) -> str | None:
    """รวมภาพถ่ายหน้าตรงผู้ต้องหากับภาพเอกสารหมายจับจริงจากศาลเป็นภาพเดียว (Side-by-Side Composite)"""
    try:
        from PIL import Image
        import tempfile

        if not os.path.exists(photo_path) or not os.path.exists(warrant_path):
            return None

        im1 = Image.open(photo_path).convert("RGB")
        im2 = Image.open(warrant_path).convert("RGB")

        target_h = max(im1.height, im2.height, 1000)
        target_h = min(target_h, 1400)

        w1 = int(im1.width * (target_h / im1.height))
        im1_resized = im1.resize((w1, target_h), Image.Resampling.LANCZOS)

        w2 = int(im2.width * (target_h / im2.height))
        im2_resized = im2.resize((w2, target_h), Image.Resampling.LANCZOS)

        divider_w = 10
        total_w = w1 + divider_w + w2

        composite = Image.new("RGB", (total_w, target_h), (25, 30, 40))
        composite.paste(im1_resized, (0, 0))
        composite.paste(im2_resized, (w1 + divider_w, 0))

        os.makedirs("data/temp", exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", dir="data/temp", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        composite.save(temp_path, "JPEG", quality=90)
        return temp_path
    except Exception as e:
        logger.error(f"create_composite_warrant_image error: {e}")
        return None


async def send_media_group(chat_id: int, photo_paths: list[str], caption: str = ""):
    """ส่งรูปภาพเป็นอัลบั้มคู่ (sendMediaGroup) เช่น รูปใบหน้าตรงในฐานข้อมูลคู่กับหมายศาล"""
    try:
        from app.modules.face.matcher import normalize_path
        valid_paths = []
        for p in photo_paths:
            norm_p = normalize_path(p) or p
            if os.path.exists(norm_p) and os.path.isfile(norm_p):
                valid_paths.append(norm_p)

        if not valid_paths:
            logger.warning("[Telegram] send_media_group: No valid files found")
            await send_message(chat_id, caption)
            return {"ok": False}

        if len(valid_paths) == 1:
            return await send_photo(chat_id, valid_paths[0], caption)

        url = f"{TELEGRAM_API}/sendMediaGroup"
        form = aiohttp.FormData()
        form.add_field("chat_id", str(chat_id))

        media_items = []
        for idx, p in enumerate(valid_paths):
            attach_key = f"photo_{idx}"
            media_obj = {
                "type": "photo",
                "media": f"attach://{attach_key}"
            }
            if idx == 0 and caption:
                media_obj["caption"] = caption
                media_obj["parse_mode"] = "HTML"
            media_items.append(media_obj)
            with open(p, "rb") as f:
                p_bytes = f.read()
            ext = os.path.splitext(p)[1].lower()
            mime = "image/png" if ext == ".png" else "image/jpeg"
            form.add_field(attach_key, p_bytes, filename=f"photo_{idx}{ext}", content_type=mime)

        form.add_field("media", json.dumps(media_items))

        session = await get_telegram_session()
        async with session.post(url, data=form) as resp:
            res_data = await resp.json()
            if res_data.get("ok"):
                return res_data
            logger.warning(f"sendMediaGroup returned not ok: {res_data}")

        # Fallback หาก Telegram API ตอบกลับ not ok ให้ส่งแบบเดี่ยวเรียงกัน
        logger.info("[Telegram] Falling back to sequential send_photo...")
        await send_photo(chat_id, valid_paths[0], caption)
        if len(valid_paths) > 1:
            await send_photo(chat_id, valid_paths[1], "📄 <b>หมายศาลประกอบคดี (เอกสารหมายจับจริง)</b>")
    except Exception as e:
        logger.error(f"send_media_group error: {e}")
        if photo_paths:
            await send_photo(chat_id, photo_paths[0], caption)
            if len(photo_paths) > 1:
                await send_photo(chat_id, photo_paths[1], "📄 <b>หมายศาลประกอบคดี (เอกสารหมายจับจริง)</b>")
        else:
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
        session = await get_telegram_session()
        menu_url = f"{TELEGRAM_API}/setChatMenuButton"
        payload = {"menu_button": {"type": "default"}}
        if chat_id:
            payload["chat_id"] = chat_id
        await session.post(menu_url, json=payload, timeout=aiohttp.ClientTimeout(total=5))

        del_cmd_url = f"{TELEGRAM_API}/deleteMyCommands"
        await session.post(del_cmd_url, json={}, timeout=aiohttp.ClientTimeout(total=5))
    except Exception as e:
        logger.debug(f"remove_telegram_menu_button note: {e}")



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
            now_str = datetime.now(THAI_TZ).strftime("%d/%m/%Y %H:%M:%S")
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
                f" • 🚗 <b>ค้นหาป้ายทะเบียน</b> ➔ ส่งภาพรถเพื่อตรวจจับป้ายทะเบียน (รองรับป้ายขาวรถยนต์และรถจักรยานยนต์)\n"
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
            now_str = datetime.now(THAI_TZ).strftime("%d/%m/%Y %H:%M:%S")
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

        elif data.startswith("sim_list_"):
            session_id = data.replace("sim_list_", "")
            session_data = _SIMILAR_SESSIONS.get(session_id)
            if not session_data:
                await answer_callback_query(cb_id)
                await send_message(chat_id, "ℹ️ ข้อมูลเซสชันหมดอายุแล้ว กรุณาส่งภาพใหม่อีกครั้งครับ")
                return

            candidates = session_data.get("candidates", [])
            # ตามคำสั่งของผู้ใช้: ตัดป๊อปอัปออก ไม่ต้องมีป๊อปอัปเด้ง แต่ส่งตรงไปยังแชททันที
            if not candidates:
                await answer_callback_query(cb_id)
                await send_message(chat_id, "ℹ️ <b>ไม่มีบุคคลหน้าคล้าย</b> (ไม่มีบุคคลอื่นที่มีความคล้ายคลึงถึงเกณฑ์ 80% ในระบบ)")
                return

            await answer_callback_query(cb_id)
            list_text = format_similar_candidates_list(candidates)

            cand_buttons = []
            for c in candidates:
                rank_num = c.get("rank", 1)
                c_name = c.get("person_name", "-")
                c_score = c.get("score", 0.0)
                cand_buttons.append([
                    {
                        "text": f"👤 ดูภาพอันดับ {rank_num}: {c_name} ({c_score:.1f}%)",
                        "callback_data": f"sim_view_{session_id}_{rank_num}"
                    }
                ])
            cand_markup = {"inline_keyboard": cand_buttons}
            await send_message(chat_id, list_text, reply_markup=cand_markup)

        elif data.startswith("sim_view_"):
            parts = data.replace("sim_view_", "").split("_")
            if len(parts) < 2:
                await answer_callback_query(cb_id)
                await send_message(chat_id, "❌ คำขอไม่ถูกต้อง")
                return
            session_id = parts[0]
            target_rank = parts[1]

            session_data = _SIMILAR_SESSIONS.get(session_id)
            if not session_data:
                await answer_callback_query(cb_id)
                await send_message(chat_id, "ℹ️ ข้อมูลเซสชันหมดอายุแล้ว")
                return

            candidates = session_data.get("candidates", [])
            target_candidate = None
            for c in candidates:
                if str(c.get("rank")) == str(target_rank):
                    target_candidate = c
                    break

            if not target_candidate:
                await answer_callback_query(cb_id)
                await send_message(chat_id, "❌ ไม่พบข้อมูลบุคคลนี้ในระบบ")
                return

            await answer_callback_query(cb_id)
            detail_caption = format_similar_candidate_detail(target_candidate)

            photo_file = target_candidate.get("photo_url")
            warrant_file = target_candidate.get("warrant_url")

            from app.modules.face.matcher import normalize_path
            actual_p = normalize_path(photo_file) if photo_file else None
            actual_w = normalize_path(warrant_file) if warrant_file else None

            p_exists = actual_p and os.path.exists(actual_p)
            w_exists = actual_w and os.path.exists(actual_w)

            back_markup = {
                "inline_keyboard": [
                    [
                        {"text": "⬅️ ย้อนกลับไปดูรายชื่อโครงหน้าใกล้เคียง", "callback_data": f"sim_list_{session_id}"}
                    ]
                ]
            }

            if p_exists and w_exists:
                await send_media_group(chat_id, [actual_p, actual_w], detail_caption)
                await send_message(chat_id, "<i>เลือกดำเนินการ:</i>", reply_markup=back_markup)
            elif p_exists:
                await send_photo(chat_id, actual_p, detail_caption, reply_markup=back_markup)
            elif w_exists:
                await send_photo(chat_id, actual_w, detail_caption, reply_markup=back_markup)
            else:
                await send_message(chat_id, detail_caption, reply_markup=back_markup)



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
                f" • 🚗 <b>ป้ายทะเบียนรถ</b> ➔ ตรวจสอบรถชนแล้วหนี / รถผิดกฎหมาย / รถ พ.ร.บ ขาด (ป้ายขาวรถยนต์และรถจักรยานยนต์)\n"
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

    ack_res = await send_message(chat_id, "⏳ <b>ได้รับรูปภาพแล้ว</b> AI กำลังจำแนกประเภทและตรวจสอบกับฐานข้อมูลหมายจับ...")
    ack_msg_id = ack_res.get("result", {}).get("message_id") if isinstance(ack_res, dict) else None

    try:
        file_path = await fetch_file_path(file_id)
        image_bytes = await download_file(file_path)
    except Exception as ex_down:
        logger.error(f"Error downloading photo {file_id}: {ex_down}")
        await send_message(chat_id, f"❌ ไม่สามารถดาวน์โหลดรูปภาพจาก Telegram ได้ กรุณาลองส่งใหม่อีกครั้งครับ ({ex_down})")
        if request_id:
            try:
                async with await get_connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("UPDATE media_requests SET status = 'failed' WHERE id = %s", (request_id,))
            except Exception:
                pass
        return

    detected_at = datetime.now(THAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
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

    # ลบข้อความชั่วคราวออก เพื่อรวมการแสดงผลเป็นการตอบกลับครั้งเดียว
    if ack_msg_id:
        try:
            await delete_message(chat_id, ack_msg_id)
        except Exception:
            pass

    if not result_data.get("found"):
        custom_reason = result_data.get("message")
        if custom_reason:
            not_found_msg = (
                f"ℹ️ <b>ผลการตรวจสอบ</b>\n"
                f"🔍 <b>ประเภทภาพที่ AI ตรวจพบ:</b> {detected_type_label}\n\n"
                f"{custom_reason}"
            )
        else:
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
            photo_file = item.get("photo_url")
            warrant_file = item.get("warrant_url")
            person_name = item.get("person_name", "")
            secondary_candidates = item.get("similar_candidates", [])

            # บันทึกเซสชันสำหรับการกดดูบุคคลหน้าใกล้เคียงรองลงไป
            import time
            now_ts = int(time.time())
            session_id = f"{chat_id}_{now_ts}"
            _SIMILAR_SESSIONS[session_id] = {
                "candidates": secondary_candidates,
                "created_at": now_ts,
                "best_name": person_name,
            }

            similar_btn_markup = {
                "inline_keyboard": [
                    [
                        {"text": "👥 กดดูบุคคลหน้าใกล้เคียงเพิ่มเติม", "callback_data": f"sim_list_{session_id}"}
                    ]
                ]
            }

            # ตรวจสอบและ resolve เส้นทางรูปถ่ายและหมายจับให้สมบูรณ์ (Safety Fallback)
            if not warrant_file or not os.path.exists(warrant_file):
                try:
                    from app.modules.face.matcher import resolve_warrant_path
                    resolved_w = resolve_warrant_path(person_name, photo_file, warrant_file)
                    if resolved_w:
                        warrant_file = resolved_w
                        item["warrant_url"] = resolved_w
                except Exception as ex_w:
                    logger.debug(f"resolve_warrant_path fallback note: {ex_w}")

            if not photo_file or not os.path.exists(photo_file):
                try:
                    from app.modules.face.matcher import resolve_photo_path
                    resolved_p = resolve_photo_path(person_name, photo_file)
                    if resolved_p:
                        photo_file = resolved_p
                        item["photo_url"] = resolved_p
                except Exception as ex_p:
                    logger.debug(f"resolve_photo_path fallback note: {ex_p}")

            caption = format_face_result(item, detected_at)

            from app.modules.face.matcher import normalize_path
            actual_p = normalize_path(photo_file) if photo_file else None
            actual_w = normalize_path(warrant_file) if warrant_file else None

            p_exists = actual_p and os.path.exists(actual_p)
            w_exists = actual_w and os.path.exists(actual_w)

            if p_exists and w_exists:
                # ส่งเป็นเซ็ทอัลบั้มภาพคู่ 2 ภาพ (รูปหน้าตรง + รูปเอกสารหมายจับจริง) ในเซ็ทข้อความเดียว
                await send_media_group(chat_id, [actual_p, actual_w], caption)
                await send_message(
                    chat_id,
                    "👥 <b>บุคคลโครงหน้าใกล้เคียงเพิ่มเติม</b>",
                    reply_markup=similar_btn_markup,
                )

            elif p_exists:
                await send_photo(chat_id, actual_p, caption, reply_markup=similar_btn_markup)
            elif w_exists:
                await send_photo(chat_id, actual_w, caption, reply_markup=similar_btn_markup)
            else:
                await send_message(chat_id, caption, reply_markup=similar_btn_markup)


        elif item_type == "plate":
            plate_msg = format_plate_result(item, detected_at)
            await send_message(chat_id, plate_msg)

        elif item_type == "id_card":
            id_msg = format_id_card_result(item, detected_at)
            await send_message(chat_id, id_msg)

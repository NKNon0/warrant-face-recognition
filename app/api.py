import os
import json
import hmac
import hashlib
from urllib.parse import parse_qsl
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, Header, HTTPException
from app.db import get_connection
from app.ai_processor import process_media
import aiomysql

router = APIRouter(prefix="/api")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")


def verify_telegram_init_data(init_data: str) -> dict | None:
    if not init_data or not TELEGRAM_TOKEN:
        return None
    try:
        parsed_data = dict(parse_qsl(init_data))
        if "hash" not in parsed_data:
            return None
        hash_val = parsed_data.pop("hash")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if calculated_hash == hash_val:
            return json.loads(parsed_data.get("user", "{}"))
    except Exception:
        pass
    return None


@router.post("/upload")
async def upload_file_from_miniapp(
    file: UploadFile = File(...),
    mode: str = Form("all"),
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"),
):
    user_info = None
    if x_telegram_init_data:
        user_info = verify_telegram_init_data(x_telegram_init_data)

    ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
    user_db_id = None
    if user_info:
        telegram_id = user_info.get("id")
        username = user_info.get("username", "")
        first_name = user_info.get("first_name", "")
        is_admin = (ADMIN_TELEGRAM_ID and telegram_id == ADMIN_TELEGRAM_ID)

        async with await get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                row = await cur.fetchone()
                if not row:
                    role = 'admin' if is_admin else 'police'
                    await cur.execute(
                        "INSERT INTO users (telegram_id, username, first_name, is_authorized, role) VALUES (%s, %s, %s, 1, %s)",
                        (telegram_id, username, first_name, role)
                    )
                    user_db_id = cur.lastrowid
                else:
                    if is_admin and not row.get("is_authorized"):
                        await cur.execute("UPDATE users SET is_authorized = 1 WHERE id = %s", (row["id"],))
                    user_db_id = row["id"]

    image_bytes = await file.read()

    # บันทึกไฟล์รูปถ่ายสดที่ถ่ายส่งเข้ามาลงโฟลเดอร์ uploads
    uploads_dir = os.path.join(os.getcwd(), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    captured_filename = f"captured_{int(datetime.now().timestamp())}_{file.filename or 'scan.jpg'}"
    captured_path = os.path.join(uploads_dir, captured_filename)
    with open(captured_path, "wb") as f:
        f.write(image_bytes)

    # บันทึก media_request ชั่วคราว
    request_id = None
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO media_requests (user_id, media_type, status) VALUES (%s, %s, %s)",
                (user_db_id, f"photo_miniapp_{mode}", "received"),
            )
            request_id = cur.lastrowid

    result = await process_media(request_id, image_bytes, mode=mode)

    # แนบไฟล์ภาพถ่ายสดที่ถ่ายจากมือถือเข้าในผลลัพธ์
    if isinstance(result, dict) and result.get("found") and result.get("results"):
        for res_item in result["results"]:
            res_item["captured_photo_url"] = captured_path

    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE media_requests SET status = %s WHERE id = %s",
                ("processed", request_id),
            )

    return result


from pydantic import BaseModel

class SendToChatRequest(BaseModel):
    chat_id: int | None = None
    result: dict


@router.post("/send_to_chat")
async def send_result_to_chat(
    req: SendToChatRequest,
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data"),
):
    from app.telegram_bot import send_message, send_photo, format_face_result, ADMIN_TELEGRAM_ID

    target_chat_id = req.chat_id
    if x_telegram_init_data:
        user_info = verify_telegram_init_data(x_telegram_init_data)
        if user_info and user_info.get("id"):
            target_chat_id = user_info.get("id")

    if not target_chat_id:
        target_chat_id = ADMIN_TELEGRAM_ID

    if not target_chat_id:
        raise HTTPException(status_code=400, detail="ไม่พบ Chat ID สำหรับส่งข้อมูล")

    res_data = req.result
    res_type = res_data.get("type", "face")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # กำหนดไฟล์ภาพถ่ายสด หรือไฟล์ภาพประวัติในฐานข้อมูล
    photo_path = res_data.get("captured_photo_url") or res_data.get("photo_url")

    if res_type == "face":
        caption = (
            f"🚨 <b>ผลการสแกนตรวจพบหมายจับจาก Mini App</b> 📱\n\n"
            + format_face_result(res_data, now_str)
        )
    elif res_type == "plate":
        caption = (
            f"🚨 <b>ผลการสแกนตรวจพบป้ายทะเบียนเฝ้าระวัง!</b> 🚗\n\n"
            f"🚗 <b>ป้ายทะเบียน:</b> {res_data.get('plate_text', '-')}\n"
            f"📍 <b>จังหวัด:</b> {res_data.get('province', '-')}\n"
            f"🚨 <b>หมวดหมู่:</b> {res_data.get('category', '-')}\n"
            f"📋 <b>รายละเอียดข้อหา:</b> {res_data.get('detail', '-')}\n"
            f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {res_data.get('station', '-')}\n"
            f"🎯 <b>ความถูกต้อง:</b> {res_data.get('score', 95):.2f}%\n"
            f"🕐 <b>เวลาที่สแกน:</b> {now_str}"
        )
    elif res_type == "id_card":
        caption = (
            f"🚨 <b>ผลการสแกนตรวจพบบัตรประชาชนเป้าหมาย!</b> 🪪\n\n"
            f"👤 <b>ชื่อ-สกุล:</b> {res_data.get('person_name') or res_data.get('name') or '-'}\n"
            f"🪪 <b>เลขบัตรประชาชน:</b> {res_data.get('id_number', '-')}\n"
            f"📋 <b>รายละเอียดข้อหา:</b> {res_data.get('detail', '-')}\n"
            f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {res_data.get('station', '-')}\n"
            f"⚖️ <b>ศาลที่ออกหมายจับ:</b> {res_data.get('court', '-')}\n"
            f"🎯 <b>ความถูกต้อง:</b> {res_data.get('score', 99):.2f}%\n"
            f"🕐 <b>เวลาที่สแกน:</b> {now_str}"
        )
    else:
        caption = f"📱 <b>ผลการสแกนจาก Mini App ({now_str}):</b>\n\n{res_data}"

    # ส่งไฟล์รูปถ่ายพร้อมคำอธิบายแบบสวยงามเข้า Telegram Chat
    if photo_path and os.path.exists(photo_path):
        await send_photo(target_chat_id, photo_path, caption)
    else:
        await send_message(target_chat_id, caption)

    return {"ok": True, "message": "ส่งข้อมูลเข้าแชทบอทสำเร็จ!"}

import os
import json
import hmac
import hashlib
from urllib.parse import parse_qsl
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

    user_db_id = None
    if user_info:
        telegram_id = user_info.get("id")
        async with await get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                row = await cur.fetchone()
                if row and not row.get("is_authorized"):
                    raise HTTPException(status_code=403, detail="คุณยังไม่ได้รับการอนุมัติสิทธิ์การใช้งาน")
                if row:
                    user_db_id = row["id"]

    image_bytes = await file.read()

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
    from datetime import datetime

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

    if res_type == "face":
        caption = (
            f"🚨 <b>ผลการสแกนตรวจสอบหมายจับจาก Mini App</b> 📱\n\n"
            + format_face_result(res_data, now_str)
        )
        photo_path = res_data.get("photo_url")
        if photo_path and os.path.exists(photo_path):
            await send_photo(target_chat_id, photo_path, caption)
        else:
            await send_message(target_chat_id, caption)
    else:
        caption = f"📱 <b>ผลการตรวจสอบจาก Mini App:</b>\n\n<code>{json.dumps(res_data, ensure_ascii=False, indent=2)}</code>"
        await send_message(target_chat_id, caption)

    return {"ok": True, "message": "ส่งข้อมูลเข้าแชทบอทสำเร็จ!"}

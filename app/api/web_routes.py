import os
import logging
from pathlib import Path
from urllib.parse import quote_plus
from datetime import datetime, timezone, timedelta

THAI_TZ = timezone(timedelta(hours=7))
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import aiomysql

from app.config import ADMIN_TELEGRAM_ID
from app.db.mysql import get_connection
from app.bot.bot_service import send_message, set_user_authorization, get_user

logger = logging.getLogger("cias.web_routes")

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/register", response_class=HTMLResponse)
async def get_registration_page(
    request: Request,
    tid: str = "",
    name: str = "",
    username: str = "",
):
    """แสดงแบบฟอร์มลงทะเบียนสำหรับเจ้าหน้าที่ผู้ใช้งานใหม่ผ่าน Localhost"""
    # ล้างค่า tid ให้เหลือเฉพาะตัวเลข ป้องกัน 422 Unprocessable Content
    clean_tid = "".join([c for c in str(tid) if c.isdigit()])
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "telegram_id": clean_tid if clean_tid else "",
            "default_name": name,
            "username": username,
        },
    )


@router.post("/register", response_class=HTMLResponse)
async def handle_registration(
    request: Request,
    telegram_id: int = Form(...),
    username: str = Form(""),
    rank_title: str = Form(...),
    first_name: str = Form(...),
    police_station: str = Form(...),
    phone_number: str = Form(...),
):
    """รับข้อมูลลงทะเบียน บันทึกลงฐานข้อมูล MySQL (is_authorized=0) และแจ้งเตือน Admin"""
    try:
        async with await get_connection() as conn:
            async with conn.cursor() as cur:
                sql = """
                    INSERT INTO users (telegram_id, username, first_name, rank_title, police_station, phone_number, is_authorized, role)
                    VALUES (%s, %s, %s, %s, %s, %s, 0, 'police')
                    ON DUPLICATE KEY UPDATE 
                        username = VALUES(username),
                        first_name = VALUES(first_name),
                        rank_title = VALUES(rank_title),
                        police_station = VALUES(police_station),
                        phone_number = VALUES(phone_number),
                        is_authorized = 0
                """
                await cur.execute(
                    sql,
                    (
                        telegram_id,
                        username,
                        first_name.strip(),
                        rank_title.strip(),
                        police_station.strip(),
                        phone_number.strip(),
                    ),
                )
                await conn.commit()
    except Exception as e:
        logger.error(f"Error saving user registration: {e}")

    # ส่งข้อความแจ้งเตือนหา Admin ใน Telegram ทันที
    try:
        now_str = datetime.now(THAI_TZ).strftime("%d/%m/%Y %H:%M:%S")
        admin_text = (
            f"🚨 <b>มีคำขอลงทะเบียนเข้าใช้งานระบบใหม่! (C.I.A.S.)</b>\n\n"
            f"🎖️ <b>ยศ - ชื่อ:</b> {rank_title} {first_name}\n"
            f"🏢 <b>ตำแหน่ง/สังกัด:</b> {police_station}\n"
            f"📞 <b>เบอร์โทรศัพท์:</b> {phone_number}\n"
            f"🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>"
            + (f" (@{username})" if username else "")
            + f"\n🕒 <b>เวลาลงทะเบียน:</b> {now_str}"
            + "\n\n<i>กรุณาพิจารณาอนุมัติหรือปฏิเสธสิทธิ์การเข้าใช้งาน:</i>"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ อนุมัติสิทธิ์", "callback_data": f"approve_{telegram_id}"},
                    {"text": "❌ ปฏิเสธ", "callback_data": f"reject_{telegram_id}"},
                ]
            ]
        }
        await send_message(ADMIN_TELEGRAM_ID, admin_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error notifying admin via Telegram: {e}")

    return templates.TemplateResponse(
        request=request,
        name="register_success.html",
        context={
            "telegram_id": telegram_id,
            "rank_title": rank_title,
            "first_name": first_name,
            "police_station": police_station,
            "phone_number": phone_number,
        },
    )


@router.get("/admin/users", response_class=HTMLResponse)
async def get_admin_users_dashboard(
    request: Request,
    msg: str = "",
    name: str = "",
):
    """หน้า Dashboard สำหรับ Admin ตรวจสอบและอนุมัติผู้ใช้งานบน Localhost"""
    users = []
    total_count = 0
    pending_count = 0
    approved_count = 0

    try:
        async with await get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT * FROM users ORDER BY created_at DESC")
                users = await cur.fetchall()
                total_count = len(users)
                for u in users:
                    if u.get("role") == "admin" or u.get("is_authorized") == 1:
                        approved_count += 1
                    else:
                        pending_count += 1
    except Exception as e:
        logger.error(f"Error fetching users for admin: {e}")

    return templates.TemplateResponse(
        request=request,
        name="admin_users.html",
        context={
            "users": users,
            "total_count": total_count,
            "pending_count": pending_count,
            "approved_count": approved_count,
            "action_msg": msg,
            "action_name": name,
        },
    )


@router.post("/admin/users/{target_id}/approve")
async def approve_user_web(target_id: int):
    """API สำหรับ Admin กดอนุมัติผู้ใช้งานจากหน้าเว็บ"""
    await set_user_authorization(target_id, True)
    user_info = await get_user(target_id)
    rank = user_info.get("rank_title", "") if user_info else ""
    name = user_info.get("first_name", "") if user_info else ""
    display_name = f"{rank} {name}".strip() or str(target_id)

    try:
        await send_message(
            target_id,
            f"🎉 <b>ยินดีด้วยครับ! บัญชีของคุณได้รับการอนุมัติให้ใช้งานระบบเรียบร้อยแล้ว</b>\n\n"
            f"🎖️ <b>ยศ - ชื่อ:</b> {display_name}\n"
            f"✅ <b>ท่านได้รับสิทธิ์เข้าใช้งานระบบสืบค้น AI เต็มรูปแบบ</b>\n"
            f"📸 <b>วิธีใช้งาน:</b>\n"
            f"ท่านสามารถส่งรูปภาพ (ใบหน้า / ป้ายทะเบียนรถ / บัตรประชาชน) เข้ามาในแชทนี้ได้โดยตรง ระบบ AI จะวิเคราะห์และตรวจสอบให้ทันทีครับ! 🚀",
        )
    except Exception as e:
        logger.error(f"Error sending approval notification to user: {e}")

    return RedirectResponse(url=f"/admin/users?msg=approved&name={quote_plus(display_name)}", status_code=303)


@router.post("/admin/users/{target_id}/reject")
async def reject_user_web(target_id: int):
    """API สำหรับ Admin กดระงับ/ปฏิเสธสิทธิ์ผู้ใช้งานจากหน้าเว็บ"""
    await set_user_authorization(target_id, False)
    user_info = await get_user(target_id)
    rank = user_info.get("rank_title", "") if user_info else ""
    name = user_info.get("first_name", "") if user_info else ""
    display_name = f"{rank} {name}".strip() or str(target_id)

    try:
        await send_message(
            target_id,
            "⚠️ <b>คำขอเข้าใช้งานระบบของคุณถูกระงับสิทธิ์ชั่วคราว</b>\n"
            "กรุณาติดต่อผู้ดูแลระบบเพื่อขอเปิดใช้งานสิทธิ์ครับ",
        )
    except Exception as e:
        logger.error(f"Error sending reject notification to user: {e}")

    return RedirectResponse(url=f"/admin/users?msg=rejected&name={quote_plus(display_name)}", status_code=303)

import os
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.db import get_connection
from app.ai_processor import process_media
import aiomysql

router = APIRouter(prefix="/api")


@router.post("/scan")
async def scan_media_direct(
    file: UploadFile = File(...),
    mode: str = Form("auto"),
):
    """
    Direct Multi-Modal AI Scan API
    รองรับการอัปโหลดไฟล์รูปภาพโดยตรงเพื่อวิเคราะห์ (ใบหน้า, ป้ายทะเบียน, บัตรประชาชน)
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูลรูปภาพ")

    # บันทึกประวัติการเรียกค้น
    request_id = None
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO media_requests (user_id, media_type, status) VALUES (%s, %s, %s)",
                (None, f"api_direct_{mode}", "received"),
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


@router.get("/status")
async def get_system_status():
    """ตรวจสอบสถานะระบบและจำนวนข้อมูลในฐานข้อมูล"""
    face_count = 0
    plate_count = 0
    warrant_count = 0

    try:
        async with await get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM face_profiles")
                r = await cur.fetchone()
                face_count = r[0] if r else 0

                await cur.execute("SELECT COUNT(*) FROM license_plates")
                r = await cur.fetchone()
                plate_count = r[0] if r else 0

                await cur.execute("SELECT COUNT(*) FROM warrants")
                r = await cur.fetchone()
                warrant_count = r[0] if r else 0
    except Exception as e:
        return {"status": "degraded", "error": str(e)}

    return {
        "status": "online",
        "architecture": "Warrant & AI Direct Recognition Bot (No MiniApp)",
        "database": {
            "face_profiles": face_count,
            "license_plates": plate_count,
            "warrants": warrant_count,
        }
    }


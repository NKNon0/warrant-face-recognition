import logging
import asyncio
import cv2
import pytesseract
import aiomysql
from app.db.mysql import get_connection
from app.modules.face.detector import cv2_imread_unicode
from .enhancer import enhance_id_card_contrast
from .parser import extract_id_number, extract_thai_name, validate_thai_id_checksum

logger = logging.getLogger(__name__)


async def find_warrant_by_id_number(id_num: str) -> dict | None:
    """ค้นหาข้อมูลหมายจับจากเลขบัตรประชาชน 13 หลัก"""
    clean_id = id_num.replace(" ", "").replace("-", "").strip()
    if not clean_id or len(clean_id) != 13:
        return None

    try:
        async with await get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                # 1. ค้นหาในตาราง warrants
                await cur.execute(
                    "SELECT id, id_number, person_name, detail, station, court FROM warrants WHERE id_number = %s",
                    (clean_id,),
                )
                res = await cur.fetchone()
                if res:
                    return {
                        "type": "id_card",
                        "id": res["id"],
                        "id_number": res.get("id_number", "-"),
                        "person_name": res.get("person_name", "-"),
                        "detail": res.get("detail", "-"),
                        "station": res.get("station", "-"),
                        "court": res.get("court", "-"),
                        "score": 99.85,
                        "match_method": "Exact 13-Digit ID Checksum",
                    }

                # 2. ค้นหาในตาราง face_profiles (ถ้ามี id_number บันทึกไว้)
                await cur.execute(
                    "SELECT id, id_number, person_name, detail, station, court FROM face_profiles WHERE id_number = %s",
                    (clean_id,),
                )
                res_fp = await cur.fetchone()
                if res_fp:
                    return {
                        "type": "id_card",
                        "id": res_fp["id"],
                        "id_number": res_fp.get("id_number", "-"),
                        "person_name": res_fp.get("person_name", "-"),
                        "detail": res_fp.get("detail", "-"),
                        "station": res_fp.get("station", "-"),
                        "court": res_fp.get("court", "-"),
                        "score": 99.50,
                        "match_method": "Face Profile ID Match",
                    }
        return None
    except Exception as e:
        logger.error(f"[ID Matcher] find_warrant_by_id_number error: {e}")
        return None


async def find_warrant_by_name(person_name: str) -> dict | None:
    """ค้นหาข้อมูลหมายจับจากชื่อ-นามสกุล"""
    if not person_name or len(person_name.strip()) < 3:
        return None

    clean_name = person_name.strip()
    words = clean_name.split()
    first_name = words[0]
    last_name = words[1] if len(words) > 1 else ""

    try:
        async with await get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                # 1. Exact Name Match ใน warrants
                await cur.execute(
                    "SELECT id, id_number, person_name, detail, station, court FROM warrants WHERE person_name LIKE %s",
                    (f"%{first_name}%",),
                )
                rows = await cur.fetchall()
                for r in rows:
                    db_name = r.get("person_name", "")
                    if first_name in db_name and (not last_name or last_name in db_name):
                        return {
                            "type": "id_card",
                            "id": r["id"],
                            "id_number": r.get("id_number", "-"),
                            "person_name": r.get("person_name", "-"),
                            "detail": r.get("detail", "-"),
                            "station": r.get("station", "-"),
                            "court": r.get("court", "-"),
                            "score": 98.50,
                            "match_method": "Thai Name Warrant Match",
                        }
        return None
    except Exception as e:
        logger.error(f"[ID Matcher] find_warrant_by_name error: {e}")
        return None


async def search_id_card(image_path: str) -> dict | None:
    """
    ระบบค้นหาข้อมูลจากบัตรประชาชน (Thai ID Card Deep OCR & Warrant Matcher)
    """
    try:
        image = cv2_imread_unicode(image_path)
        if image is None:
            return None

        # ย่อขนาดรูปภาพให้เหมาะสมกับการทำ OCR (Max Width 1200px)
        h, w = image.shape[:2]
        if w > 1200:
            scale = 1200.0 / w
            image = cv2.resize(image, (1200, int(h * scale)), interpolation=cv2.INTER_AREA)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enhanced_gray = enhance_id_card_contrast(gray)

        # ----------------------------------------------------
        # Multi-Pass OCR: Original Gray & Faded Text Enhanced
        # ----------------------------------------------------
        for target_img in [enhanced_gray, gray]:
            for psm_mode in [6, 4]:
                def _ocr_call(img_in, psm):
                    try:
                        return pytesseract.image_to_string(img_in, lang="tha+eng", config=f"--psm {psm} --dpi 200")
                    except Exception:
                        return ""

                ocr_result = await asyncio.to_thread(_ocr_call, target_img, psm_mode)
                if not ocr_result:
                    continue

                # 1. ตรวจสอบเลขประจำตัวประชาชน 13 หลัก
                id_num = extract_id_number(ocr_result)
                if id_num:
                    warrant = await find_warrant_by_id_number(id_num)
                    if warrant:
                        return warrant

                # 2. ตรวจสอบชื่อ-นามสกุล
                detected_name = extract_thai_name(ocr_result)
                if detected_name:
                    warrant_name = await find_warrant_by_name(detected_name)
                    if warrant_name:
                        return warrant_name

        return None
    except Exception as e:
        logger.error(f"[ID Matcher] search_id_card error: {e}")
        return None

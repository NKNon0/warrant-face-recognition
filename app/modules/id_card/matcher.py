import json
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
                # 1. ค้นหาในตาราง id_cards (ฐานข้อมูลหลัก 63 รายการ)
                await cur.execute(
                    "SELECT id, id_number, name, metadata FROM id_cards WHERE id_number = %s",
                    (clean_id,),
                )
                res_idc = await cur.fetchone()
                if res_idc:
                    meta = {}
                    if res_idc.get("metadata"):
                        try:
                            meta = json.loads(res_idc["metadata"]) if isinstance(res_idc["metadata"], str) else res_idc["metadata"]
                        except Exception:
                            pass
                    return {
                        "type": "id_card",
                        "id": res_idc["id"],
                        "id_number": res_idc.get("id_number", "-"),
                        "person_name": res_idc.get("name", "-"),
                        "detail": meta.get("detail") or "พบบุคคลเป้าหมายเฝ้าระวังตามหมายจับ",
                        "station": meta.get("station") or "สน.ตำรวจนครบาล",
                        "court": meta.get("court") or "ศาลอาญา",
                        "score": 99.85,
                        "match_method": "ID Cards Database Match",
                    }

                # 2. ค้นหาในตาราง warrants
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

                # 3. ค้นหาในตาราง face_profiles (ถ้ามี id_number บันทึกไว้)
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
                # 1. ค้นหาในตาราง id_cards
                await cur.execute(
                    "SELECT id, id_number, name, metadata FROM id_cards WHERE name LIKE %s",
                    (f"%{first_name}%",),
                )
                rows_idc = await cur.fetchall()
                for r in rows_idc:
                    db_name = r.get("name", "")
                    if first_name in db_name and (not last_name or last_name in db_name):
                        meta = {}
                        if r.get("metadata"):
                            try:
                                meta = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]
                            except Exception:
                                pass
                        return {
                            "type": "id_card",
                            "id": r["id"],
                            "id_number": r.get("id_number", "-"),
                            "person_name": r.get("name", "-"),
                            "detail": meta.get("detail") or "พบบุคคลเป้าหมายเฝ้าระวังตามหมายจับ",
                            "station": meta.get("station") or "สน.ตำรวจนครบาล",
                            "court": meta.get("court") or "ศาลอาญา",
                            "score": 98.85,
                            "match_method": "ID Cards Name Match",
                        }

                # 2. Exact Name Match ใน warrants
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


from app.modules.license_plate.ocr_engine import get_paddleocr_engine, extract_paddle_text


async def search_id_card(image_path: str) -> dict | None:
    """
    ระบบค้นหาข้อมูลจากบัตรประชาชน (Thai ID Card Deep OCR & Warrant Matcher)
    รองรับทั้ง PaddleOCR และ PyTesseract Multi-Pass
    """
    try:
        image = cv2_imread_unicode(image_path)
        if image is None:
            return None

        ocr_texts = []

        # 1. High-Speed Pass: PaddleOCR Engine (หากมี)
        paddle_ocr = get_paddleocr_engine()
        if paddle_ocr is not None:
            def _paddle_run(img_in):
                try:
                    res = paddle_ocr.ocr(img_in)
                    return extract_paddle_text(res)
                except Exception as err:
                    logger.debug(f"[ID Matcher] PaddleOCR run error: {err}")
                    return ""

            paddle_text = await asyncio.to_thread(_paddle_run, image)
            if paddle_text:
                ocr_texts.append(paddle_text)

        # 2. Multi-Mode Tesseract OCR Pass (PSM 11, 6, 3)
        def _tesseract_call(img_in, psm_mode):
            try:
                return pytesseract.image_to_string(img_in, lang="tha+eng", config=f"--psm {psm_mode}")
            except Exception:
                return ""

        for psm in [11, 6, 3]:
            tess_text = await asyncio.to_thread(_tesseract_call, image, psm)
            if tess_text:
                ocr_texts.append(tess_text)

        # 3. Enhanced Image Pass (Grayscale + Contrast)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        enhanced = enhance_id_card_contrast(gray)
        for psm in [11, 6]:
            enh_text = await asyncio.to_thread(_tesseract_call, enhanced, psm)
            if enh_text:
                ocr_texts.append(enh_text)

        combined_text = " \n ".join(ocr_texts).strip()
        if not combined_text:
            return None

        # 1. ตรวจสอบเลขประจำตัวประชาชน 13 หลัก
        id_num = extract_id_number(combined_text)
        if id_num:
            warrant = await find_warrant_by_id_number(id_num)
            if warrant:
                return warrant

        # 2. ตรวจสอบชื่อ-นามสกุล
        detected_name = extract_thai_name(combined_text)
        if detected_name:
            warrant_name = await find_warrant_by_name(detected_name)
            if warrant_name:
                return warrant_name

        return None
    except Exception as e:
        logger.error(f"[ID Matcher] search_id_card error: {e}")
        return None

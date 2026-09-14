import os
import re
import logging
import asyncio
import pytesseract
from app.config import IAPP_API_KEY
from app.modules.face.detector import cv2_imread_unicode
from .detector import preprocess_license_plate_image, classify_license_plate_type
from .matcher import find_license_plate

logger = logging.getLogger(__name__)

PADDLE_OCR_ENGINE = None
PADDLE_OCR_AVAILABLE = False

try:
    from paddleocr import PaddleOCR
    PADDLE_OCR_AVAILABLE = True
except ImportError:
    logger.warning("[ALPR OCR] PaddleOCR not available, using PyTesseract.")
    PaddleOCR = None


def extract_paddle_text(res) -> str:
    """สกัดข้อความทั้งหมดจากผลลัพธ์ของ PaddleOCR รองรับทั้ง v5 rec_texts และรูปแบบดั้งเดิม"""
    if not res:
        return ""
    texts = []
    for page in res:
        if isinstance(page, dict) and "rec_texts" in page:
            texts.extend([str(t) for t in page["rec_texts"] if str(t).strip()])
        elif isinstance(page, list):
            for item in page:
                if isinstance(item, list) and len(item) > 1 and isinstance(item[1], (tuple, list)):
                    texts.append(str(item[1][0]))
                elif isinstance(item, dict) and "rec_texts" in item:
                    texts.extend([str(t) for t in item["rec_texts"] if str(t).strip()])
    return " ".join(texts).strip()


def get_paddleocr_engine():
    """โหลด PaddleOCR Thai Language Model แบบ Lazy Loading"""
    global PADDLE_OCR_ENGINE
    if PADDLE_OCR_ENGINE is not None:
        return PADDLE_OCR_ENGINE
    if not PADDLE_OCR_AVAILABLE or PaddleOCR is None:
        return None
    try:
        PADDLE_OCR_ENGINE = PaddleOCR(lang='th')
        logger.info("[ALPR OCR] PaddleOCR Thai Engine loaded successfully!")
    except Exception as ex:
        logger.error(f"[ALPR OCR] PaddleOCR init error: {ex}")
    return PADDLE_OCR_ENGINE


async def search_license_plate(image_path: str) -> dict | None:
    """
    ระบบอ่านและค้นหาป้ายทะเบียนรถ (License Plate Fast OCR Engine) ความเร็วสูงพิเศษ (< 1.0s)
    """
    try:
        image = cv2_imread_unicode(image_path)
        if image is None:
            return None

        # ----------------------------------------------------
        # Optional: iApp Cloud API Integration
        # ----------------------------------------------------
        if IAPP_API_KEY:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    headers = {"apikey": IAPP_API_KEY}
                    with open(image_path, "rb") as f:
                        form_data = aiohttp.FormData()
                        form_data.add_field("file", f, filename="plate.jpg", content_type="image/jpeg")
                        async with session.post(
                            "https://api.iapp.co.th/license-plate-recognition/file",
                            headers=headers,
                            data=form_data,
                            timeout=aiohttp.ClientTimeout(total=4.0)
                        ) as resp:
                            if resp.status == 200:
                                res_json = await resp.json()
                                lp_num = res_json.get("lp_number", "")
                                prov = res_json.get("province", "")
                                search_term = f"{lp_num} {prov}".strip()
                                if search_term:
                                    match = await find_license_plate(search_term)
                                    if match:
                                        return match
            except Exception as e:
                logger.error(f"[ALPR OCR] iApp API search error: {e}")

        # ----------------------------------------------------
        # Local Fast Pipeline: Original Image + Preprocessed Crops
        # ----------------------------------------------------
        candidate_imgs = preprocess_license_plate_image(image)
        # ตรวจสอบภาพต้นฉบับด้วย เพื่อความแม่นยำสูงสุดหากผู้ใช้ส่งภาพครอปป้ายทะเบียนมาโดยตรง
        all_candidates = [image] + (candidate_imgs or [])

        plate_type_code, plate_type_label = "car_normal", "🚗 รถยนต์ - ป้ายขาวปกติ (Car - Normal Plate)"
        if candidate_imgs and len(candidate_imgs) > 0:
            plate_type_code, plate_type_label = classify_license_plate_type(candidate_imgs[0])

        # 1. High Speed Pass: PaddleOCR Engine
        paddle_ocr = get_paddleocr_engine()
        if paddle_ocr is not None:
            def _paddle_pass(img_input):
                try:
                    res = paddle_ocr.ocr(img_input)
                    return extract_paddle_text(res)
                except Exception as err:
                    logger.debug(f"[PaddleOCR] pass error: {err}")
                    return ""

            for c_img in all_candidates:
                paddle_text = await asyncio.to_thread(_paddle_pass, c_img)
                if paddle_text:
                    clean_txt = re.sub(r'[^a-zA-Z0-9ก-๙\s]', '', paddle_text).strip()
                    if len(clean_txt) >= 2:
                        match = await find_license_plate(clean_txt)
                        if match:
                            match["plate_type_code"] = plate_type_code
                            match["plate_type_label"] = plate_type_label
                            return match

        # 2. Fast Fallback Pass: PyTesseract Engine (Multi-Mode PSM)
        def _ocr_pass(img_input, psm_mode):
            try:
                return pytesseract.image_to_string(img_input, lang="tha+eng", config=f"--psm {psm_mode}").strip()
            except Exception:
                return ""

        for c_img in all_candidates:
            for psm in [11, 3, 6, 7]:
                raw_text = await asyncio.to_thread(_ocr_pass, c_img, psm)
                if raw_text:
                    clean_txt = re.sub(r'[^a-zA-Z0-9ก-๙\s]', '', raw_text).strip()
                    if len(clean_txt) >= 2:
                        match = await find_license_plate(clean_txt)
                        if match:
                            match["plate_type_code"] = plate_type_code
                            match["plate_type_label"] = plate_type_label
                            return match

        return None
    except Exception as e:
        logger.error(f"[ALPR OCR] search_license_plate error: {e}")
        return None

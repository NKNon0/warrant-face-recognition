import os
import logging
import asyncio
import pytesseract
from app.modules.face.detector import cv2_imread_unicode
from app.config import IAPP_API_KEY
from .detector import preprocess_license_plate_image
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


def get_paddleocr_engine():
    """โหลด PaddleOCR Thai Language Model แบบ Lazy Loading"""
    global PADDLE_OCR_ENGINE
    if PADDLE_OCR_ENGINE is not None:
        return PADDLE_OCR_ENGINE
    if not PADDLE_OCR_AVAILABLE or PaddleOCR is None:
        return None
    try:
        PADDLE_OCR_ENGINE = PaddleOCR(use_angle_cls=False, lang='th', show_log=False)
        print("[ALPR OCR] ✅ PaddleOCR Thai Engine loaded successfully!")
    except Exception as ex:
        print(f"[ALPR OCR] PaddleOCR init error: {ex}")
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
        # Local Fast Pipeline: 2-Candidate Crop
        # ----------------------------------------------------
        candidate_imgs = preprocess_license_plate_image(image)

        # 1. High Speed Pass: PaddleOCR Engine (cls=False)
        paddle_ocr = get_paddleocr_engine()
        if paddle_ocr is not None:
            def _paddle_pass(img_input):
                try:
                    res = paddle_ocr.ocr(img_input, cls=False)
                    text_str = ""
                    if res and res[0]:
                        for line in res[0]:
                            text_str += line[1][0] + " "
                    return text_str.strip()
                except Exception:
                    return ""

            for c_img in candidate_imgs:
                paddle_text = await asyncio.to_thread(_paddle_pass, c_img)
                if paddle_text:
                    clean_txt = "".join(ch for ch in paddle_text if ch.isalnum() or ch in " กขคฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
                    if len(clean_txt) >= 2:
                        match = await find_license_plate(clean_txt)
                        if match:
                            return match

        # 2. Fast Fallback Pass: PyTesseract Engine
        def _ocr_pass(img_input, psm_mode):
            try:
                return pytesseract.image_to_string(img_input, lang="tha+eng", config=f"--psm {psm_mode}").strip()
            except Exception:
                return ""

        for c_img in candidate_imgs:
            for psm in [7, 6]:
                raw_text = await asyncio.to_thread(_ocr_pass, c_img, psm)
                if raw_text:
                    clean_txt = "".join(ch for ch in raw_text if ch.isalnum() or ch in " กขคฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
                    if len(clean_txt) >= 2:
                        match = await find_license_plate(clean_txt)
                        if match:
                            return match

        return None
    except Exception as e:
        logger.error(f"[ALPR OCR] search_license_plate error: {e}")
        return None

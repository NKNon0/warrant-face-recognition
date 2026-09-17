import logging
import re
import cv2
import numpy as np
import pytesseract
from app.modules.face.detector import cv2_imread_unicode, get_insightface_app, detect_and_crop_face
from app.modules.license_plate.detector import get_yolo_plate_model
from app.modules.license_plate.ocr_engine import get_paddleocr_engine, extract_paddle_text
from app.modules.id_card.parser import extract_id_number

logger = logging.getLogger(__name__)

# รายชื่อจังหวัดของไทยสำหรับระบุป้ายทะเบียน
THAI_PROVINCES = [
    "กรุงเทพ", "กรุงเทพมหานคร", "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น",
    "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ", "ชุมพร", "เชียงราย", "เชียงใหม่",
    "ตรัง", "ตราด", "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา", "นครศรีธรรมราช",
    "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน", "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์",
    "ปราจีนบุรี", "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง", "พิจิตร", "พิษณุโลก",
    "เพชรบุรี", "เพชรบูรณ์", "แพร่", "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร",
    "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี", "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ",
    "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม", "สมุทรสาคร", "สระแก้ว", "สระบุรี",
    "สิงห์บุรี", "สุโขทัย", "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู",
    "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี", "อุบลราชธานี"
]


def extract_quick_ocr_text(img: np.ndarray) -> str:
    """สกัดข้อความความเร็วสูงสำหรับวิเคราะห์จำแนกประเภทของรูปภาพ (< 0.2s)"""
    extracted_texts = []

    # 1. ลองใช้ PaddleOCR หากมีติดตั้ง
    paddle = get_paddleocr_engine()
    if paddle is not None:
        try:
            res = paddle.ocr(img)
            p_text = extract_paddle_text(res)
            if p_text:
                extracted_texts.append(p_text)
        except Exception:
            pass

    # 2. ใช้ PyTesseract (Tha + Eng)
    try:
        h, w = img.shape[:2]
        max_d = 900
        if max(h, w) > max_d:
            scale = max_d / float(max(h, w))
            small = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        else:
            small = img

        t_text = pytesseract.image_to_string(small, lang="tha+eng", config="--psm 11")
        if t_text:
            extracted_texts.append(t_text)

        # หากเป็นภาพขนาดใหญ่ ให้ลองอ่านแบบเดิมเสริม
        if small is not img:
            t_orig = pytesseract.image_to_string(img, lang="tha+eng", config="--psm 11")
            if t_orig:
                extracted_texts.append(t_orig)
    except Exception as e:
        logger.debug(f"[Classifier] PyTesseract error: {e}")

    return " \n ".join(extracted_texts).strip()


def classify_image_type(image_path: str) -> tuple[str, float]:
    """
    AI Multi-Modal Image Classifier:
    วิเคราะห์และจำแนกประเภทของรูปภาพที่ส่งเข้ามาโดยอัตโนมัติ ออกเป็น 3 ส่วนชัดเจน:
    1. 'idcard' -> 🪪 บัตรประจำตัวประชาชน
    2. 'plate'  -> 🚗 ป้ายทะเบียนรถยนต์/รถจักรยานยนต์
    3. 'face'   -> 👤 ใบหน้าบุคคลต้องสงสัย
    คืนค่าเป็น (predicted_type, confidence_score)
    """
    try:
        img = cv2_imread_unicode(image_path)
        if img is None:
            return "face", 0.50

        h_orig, w_orig = img.shape[:2]
        aspect_ratio = float(w_orig) / float(h_orig) if h_orig > 0 else 1.0

        # สกัดข้อความในภาพอย่างรวดเร็ว
        ocr_text = extract_quick_ocr_text(img)

        # =========================================================================
        # ส่วนที่ 1: ตรวจสอบบัตรประจำตัวประชาชน (Thai National ID Card)
        # =========================================================================
        id_keywords = [
            "บัตรประจำตัวประชาชน", "บัตรประจําตัวประชาชน", "Thai National ID Card",
            "National ID", "ประจำตัวประชาชน", "ประจําตัวประชาชน", "เกิดวันที่",
            "ศาสนา", "ที่อยู่", "ชื่อตัวและชื่อสกุล", "วันออกบัตร", "วันบัตรหมดอายุ",
            "Identification Number", "Date of Birth", "Date of Issue", "Date of Expiry"
        ]
        has_id_keyword = any(k in ocr_text for k in id_keywords)
        has_13_digits = bool(extract_id_number(ocr_text))

        # หากมีคีย์เวิร์ดบัตรประชาชนโดยตรง เช่น บัตรประจำตัวประชาชน, วันออกบัตร, เกิดวันที่ -> เป็น ID Card ทันที
        if has_id_keyword:
            return "idcard", 0.99

        # =========================================================================
        # ส่วนที่ 2: ตรวจสอบป้ายทะเบียนรถ (License Plate)
        # =========================================================================
        has_province = any(prov in ocr_text for prov in THAI_PROVINCES)
        plate_text_clean = "".join(ch for ch in ocr_text if ch.isalnum() or ch in " กขคฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
        digits_in_text = re.findall(r"\d+", plate_text_clean)
        thai_in_text = re.findall(r"[ก-ฮ]+", plate_text_clean)

        # ตรวจหาแพทเทิร์นป้ายทะเบียนไทย เช่น 1กย 889, กย 889, ขนษ 660, 4กฆ 1819, 3กฒ 161
        plate_pattern_match = bool(re.search(r'[0-9]?[ก-ฮ]{1,3}\s*[0-9]{1,4}', ocr_text))

        # ก) ตรวจสอบจากข้อความ OCR (มีจังหวัด + ตัวเลข หรือ ตรงตามแพทเทิร์นป้าย)
        if (has_province and digits_in_text) or (plate_pattern_match and digits_in_text):
            return "plate", 0.96

        # ข) ตรวจสอบด้วยโมเดล YOLO Plate Detector
        yolo = get_yolo_plate_model()
        if yolo is not None:
            try:
                y_res = yolo.predict(img, verbose=False, conf=0.35)
                if y_res and len(y_res) > 0 and len(y_res[0].boxes) > 0:
                    box = y_res[0].boxes[0]
                    conf = float(box.conf[0])
                    bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                    bw = max(1, bx2 - bx1)
                    bh = max(1, by2 - by1)
                    box_ratio = float(bw) / float(bh)
                    if box_ratio >= 1.2:
                        return "plate", round(max(0.85, conf), 2)
            except Exception:
                pass

        if has_province and thai_in_text:
            return "plate", 0.92

        # หากไม่มีลักษณะของป้ายทะเบียนรถ แต่พบเลข 13 หลักที่ถูกต้องตามโครงสร้าง
        if has_13_digits:
            return "idcard", 0.95

        # =========================================================================
        # ส่วนที่ 3: ตรวจสอบใบหน้าบุคคล (Face Recognition)
        # =========================================================================
        has_face = False
        face_conf = 0.0
        iface_app = get_insightface_app()
        if iface_app is not None:
            try:
                faces = iface_app.get(img)
                if faces and len(faces) > 0:
                    best_face = max(faces, key=lambda f: float(f.det_score))
                    face_conf = float(best_face.det_score)
                    if face_conf >= 0.45:
                        has_face = True
            except Exception:
                pass

        if not has_face and detect_and_crop_face(image_path) is not None:
            has_face = True
            face_conf = 0.80

        if has_face:
            return "face", round(max(0.85, face_conf), 2)

        # =========================================================================
        # Fallback Heuristics สำหรับภาพขอบเขตพิเศษ
        # =========================================================================
        if aspect_ratio >= 1.8:
            return "plate", 0.75
        elif 1.30 <= aspect_ratio <= 1.90 and len(ocr_text) >= 10:
            return "idcard", 0.70

        if digits_in_text and len(plate_text_clean) <= 15:
            return "plate", 0.75

        return "face", 0.50
    except Exception as e:
        logger.error(f"[Classifier] classify_image_type error: {e}")
        return "face", 0.50

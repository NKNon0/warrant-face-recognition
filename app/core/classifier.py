import logging
import re
import cv2
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


def classify_image_type(image_path: str) -> tuple[str, float]:
    """
    AI Multi-Modal Image Classifier:
    วิเคราะห์และจำแนกประเภทของรูปภาพที่ส่งเข้ามาโดยอัตโนมัติ (ความเร็วสูงพิเศษ):
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

        # ปรับขนาดภาพสำหรับการจำแนกประเภทความเร็วสูง (Max Dim 640px)
        max_dim = 640
        if max(h_orig, w_orig) > max_dim:
            scale = float(max_dim) / float(max(h_orig, w_orig))
            quick_img = cv2.resize(img, (int(w_orig * scale), int(h_orig * scale)), interpolation=cv2.INTER_AREA)
        else:
            quick_img = img

        # --- 1. ตรวจสอบข้อความด้วย PaddleOCR ก่อน ---
        paddle_ocr = get_paddleocr_engine()
        ocr_text = ""
        if paddle_ocr is not None:
            try:
                res = paddle_ocr.ocr(quick_img)
                ocr_text = extract_paddle_text(res)
            except Exception as e:
                logger.debug(f"[Classifier] PaddleOCR check note: {e}")

        # ก) ตรวจสอบบัตรประชาชน (Thai ID Card)
        id_keywords = [
            "บัตรประจำตัวประชาชน", "Thai National ID Card", "ประจำตัวประชาชน", "เกิดวันที่",
            "ศาสนา", "ที่อยู่", "ชื่อตัวและชื่อสกุล", "วันออกบัตร", "วันบัตรหมดอายุ",
            "Identification Number", "Date of Birth", "Date of Issue", "Date of Expiry"
        ]
        has_id_keyword = any(k in ocr_text for k in id_keywords)
        has_13_digits = bool(extract_id_number(ocr_text))

        if has_id_keyword or has_13_digits:
            return "idcard", 0.98

        # ข) ตรวจสอบป้ายทะเบียนรถ (License Plate) จากข้อความ
        has_province = any(prov in ocr_text for prov in THAI_PROVINCES)
        plate_text_clean = "".join(ch for ch in ocr_text if ch.isalnum() or ch in " กขคฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ")
        digits_in_text = re.findall(r"\d+", plate_text_clean)
        thai_in_text = re.findall(r"[ก-ฮ]+", plate_text_clean)

        is_plate_by_text = False
        if has_province and (digits_in_text or thai_in_text):
            is_plate_by_text = True
        elif digits_in_text and thai_in_text:
            if len(plate_text_clean) <= 25 and len(digits_in_text[0]) <= 4:
                is_plate_by_text = True

        if is_plate_by_text:
            return "plate", 0.96

        # ค) ตรวจสอบด้วย YOLO License Plate Detector (ถ้ามี)
        yolo = get_yolo_plate_model()
        if yolo is not None:
            try:
                y_res = yolo.predict(quick_img, verbose=False, conf=0.30)
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

        # --- 2. ตรวจสอบ ใบหน้าบุคคล (Face Detection) ---
        has_face = False
        face_conf = 0.0
        iface_app = get_insightface_app()
        if iface_app is not None:
            try:
                faces = iface_app.get(quick_img)
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
            if 1.35 <= aspect_ratio <= 1.85 and (len(ocr_text) > 10):
                return "idcard", 0.85
            return "face", round(max(0.85, face_conf), 2)

        # --- 3. กฎสัดส่วนภาพและลักษณะเฉพาะ (Fallback Heuristics) ---
        if aspect_ratio >= 1.8:
            return "plate", 0.75
        elif 1.35 <= aspect_ratio <= 1.85:
            if len(ocr_text) >= 5:
                return "idcard", 0.70
            return "plate", 0.65

        if digits_in_text and len(plate_text_clean) <= 15:
            return "plate", 0.75

        return "face", 0.50
    except Exception as e:
        logger.error(f"[Classifier] classify_image_type error: {e}")
        return "face", 0.50

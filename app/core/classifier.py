import logging
import cv2
import pytesseract
from app.modules.face.detector import cv2_imread_unicode, get_insightface_app, detect_and_crop_face
from app.modules.license_plate.detector import get_yolo_plate_model
from app.modules.id_card.parser import extract_id_number

logger = logging.getLogger(__name__)


def classify_image_type(image_path: str) -> tuple[str, float]:
    """
    AI Multi-Modal Image Classifier:
    วิเคราะห์และจำแนกประเภทของรูปภาพที่ส่งเข้ามาโดยอัตโนมัติ (ความเร็วสูงพิเศษ < 100ms):
    1. 'face'   -> 👤 ใบหน้าบุคคลต้องสงสัย
    2. 'idcard' -> 🪪 บัตรประจำตัวประชาชน
    3. 'plate'  -> 🚗 ป้ายทะเบียนรถยนต์/รถจักรยานยนต์
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

        full_gray = cv2.cvtColor(quick_img, cv2.COLOR_BGR2GRAY)

        # --- 1. ตรวจสอบ ใบหน้าบุคคล (Face Detection) ---
        has_face = False
        face_conf = 0.0
        iface_app = get_insightface_app()
        if iface_app is not None:
            try:
                faces = iface_app.get(quick_img)
                if faces and len(faces) > 0:
                    best_face = max(faces, key=lambda f: float(f.det_score))
                    face_conf = float(best_face.det_score)
                    if face_conf >= 0.50:
                        has_face = True
            except Exception:
                pass

        if not has_face and detect_and_crop_face(image_path) is not None:
            has_face = True
            face_conf = 0.80

        # --- 2. ตรวจสอบ บัตรประชาชน (Thai ID Card Detection) ---
        is_idcard = False
        idcard_conf = 0.0
        if 1.20 <= aspect_ratio <= 1.95:
            try:
                quick_text = pytesseract.image_to_string(full_gray, lang="tha+eng", config="--psm 6").strip()
                id_keywords = ["บัตรประจำตัวประชาชน", "Thai National ID Card", "ประจำตัวประชาชน", "เกิดวันที่", "ศาสนา", "ที่อยู่", "ชื่อตัวและชื่อสกุล", "วันออกบัตร", "วันบัตรหมดอายุ"]
                keyword_matches = sum(1 for kw in id_keywords if kw in quick_text)

                id_num_match = extract_id_number(quick_text)
                if id_num_match or keyword_matches >= 2:
                    is_idcard = True
                    idcard_conf = 0.95
                elif keyword_matches == 1:
                    is_idcard = True
                    idcard_conf = 0.85
            except Exception:
                pass

        if is_idcard:
            return "idcard", idcard_conf

        if has_face:
            return "face", round(max(0.85, face_conf), 2)

        # --- 3. ตรวจสอบ ป้ายทะเบียนรถ (License Plate Detection) ---
        yolo = get_yolo_plate_model()
        if yolo is not None:
            try:
                y_res = yolo.predict(quick_img, verbose=False, conf=0.35)
                if y_res and len(y_res) > 0 and len(y_res[0].boxes) > 0:
                    box = y_res[0].boxes[0]
                    conf = float(box.conf[0])
                    bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                    bw = max(1, bx2 - bx1)
                    bh = max(1, by2 - by1)
                    box_ratio = float(bw) / float(bh)
                    if box_ratio >= 1.5:
                        return "plate", round(max(0.85, conf), 2)
            except Exception:
                pass

        # --- 4. กฎสัดส่วนภาพ (Fallback Heuristics) ---
        if aspect_ratio >= 2.0:
            return "plate", 0.70
        elif 1.35 <= aspect_ratio <= 1.85:
            return "idcard", 0.65

        return "face", 0.60
    except Exception as e:
        logger.error(f"[Classifier] classify_image_type error: {e}")
        return "face", 0.50

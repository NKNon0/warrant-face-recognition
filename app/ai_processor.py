import json
import tempfile
import shutil
import os
import re
import numpy as np
from PIL import Image
import pytesseract
import cv2
import aiomysql
from datetime import datetime
from app.db import get_connection

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DeepFace = None
    DEEPFACE_AVAILABLE = False

INSIGHTFACE_AVAILABLE = False
INSIGHTFACE_APP = None
_INSIGHTFACE_INITIALIZED = False

try:
    import insightface
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    insightface = None
    FaceAnalysis = None
    INSIGHTFACE_AVAILABLE = False


def get_insightface_app():
    """โหลด InsightFace แบบ Lazy Loading เพื่อให้ Uvicorn เริ่มทำงานได้ทันที"""
    global INSIGHTFACE_APP, _INSIGHTFACE_INITIALIZED
    if _INSIGHTFACE_INITIALIZED:
        return INSIGHTFACE_APP
    _INSIGHTFACE_INITIALIZED = True
    if not INSIGHTFACE_AVAILABLE or FaceAnalysis is None:
        return None
    try:
        app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        app.prepare(ctx_id=0, det_size=(640, 640))
        INSIGHTFACE_APP = app
        print("[AI Process] InsightFace (buffalo_l / ResNet50) loaded successfully!")
    except Exception as ex:
        print(f"[AI Process] InsightFace init note: {ex}")
    return INSIGHTFACE_APP


def cv2_imread_unicode(image_path: str):
    """อ่านรูปภาพ fail-safe รองรับภาษาไทยและทุก OS"""
    try:
        img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            return img
    except Exception:
        pass
    return cv2.imread(image_path)


def is_valid_image(image_path: str) -> tuple[bool, str]:
    """ตรวจสอบภาพว่าเป็นภาพสีดำ/มืดเกินไป/ภาพเปล่าหรือไม่"""
    try:
        img = cv2_imread_unicode(image_path)
        if img is None:
            return False, "ไม่สามารถอ่านไฟล์รูปภาพได้"

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean_val = float(np.mean(gray))
        std_val = float(np.std(gray))

        # หากค่าความสว่างเฉลี่ย < 15 หรือความแปรปรวน < 5 (ภาพมืดสนิท/ภาพสีดำ)
        if mean_val < 15 or std_val < 5:
            return False, "ภาพถ่ายเป็นสีดำ มืดเกินไป หรือไม่มีรายละเอียดใบหน้าเพียงพอ"

        return True, ""
    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการตรวจสอบรูปภาพ: {e}"


async def process_media(request_id: int, image_bytes: bytes, mode: str = "all") -> dict:
    """
    ประมวลผลรูปภาพและค้นหาข้อมูลจากฐานข้อมูลตามโหมดที่ระบุ
    mode: 'face', 'idcard', 'plate', 'all'
    """
    image_path = save_temp_image(image_bytes)
    try:
        # ตรวจสอบภาพสีดำ / ภาพมืดเกินไปก่อนส่งให้ AI
        is_valid, err_msg = is_valid_image(image_path)
        if not is_valid:
            return {"found": False, "message": err_msg}

        results = []

        if mode in ["all", "face"]:
            face_result = await search_face(image_path)
            if face_result:
                if face_result.get("type") == "no_face":
                    return {"found": False, "message": face_result.get("message", "ไม่พบใบหน้าบุคคลในภาพถ่าย")}
                results.append(face_result)
                await save_search_result(
                    request_id=request_id,
                    result_type="face",
                    match_score=face_result.get("score", 0.0),
                    matched_record_id=face_result.get("id"),
                    details=face_result,
                )

        if mode in ["all", "plate"]:
            plate_result = await search_license_plate(image_path)
            if plate_result:
                results.append({"type": "plate", "plate_text": plate_result})
                await save_search_result(
                    request_id=request_id,
                    result_type="license_plate",
                    match_score=1.0,
                    matched_record_id=None,
                    details={"plate_text": plate_result},
                )

        if mode in ["all", "idcard"]:
            id_card_result = await search_id_card(image_path)
            if id_card_result:
                results.append({"type": "id_card", **id_card_result})
                await save_search_result(
                    request_id=request_id,
                    result_type="id_card",
                    match_score=1.0,
                    matched_record_id=id_card_result.get("id"),
                    details=id_card_result,
                )

        if not results:
            mode_names = {"face": "ใบหน้า", "idcard": "บัตรประชาชน", "plate": "ป้ายทะเบียน"}
            mode_text = mode_names.get(mode, "ข้อมูล")
            return {"found": False, "message": f"ไม่พบข้อมูล{mode_text}ที่ตรงกับฐานข้อมูลหมายจับ"}

        return {"found": True, "results": results}
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


def save_temp_image(image_bytes: bytes) -> str:
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp_file.write(image_bytes)
    temp_file.close()
    return temp_file.name


FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.40"))


def _safe_ascii_image_path(image_path: str) -> str:
    """สร้าง temp ASCII copy และ resize ภาพเป็นความกว้างไม่เกิน 800px เพื่อให้ประมวลผลเร็วขึ้น 10 เท่า"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="df_proc_")
    tmp_path = tmp.name
    tmp.close()

    try:
        # อ่านรูปภาพด้วย imdecode เพื่อรองรับภาษาไทย และ resize
        img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            h, w = img.shape[:2]
            max_dim = 800
            if max(h, w) > max_dim:
                scale = max_dim / float(max(h, w))
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
            cv2.imwrite(tmp_path, img)
            return tmp_path
    except Exception:
        pass

    shutil.copy2(image_path, tmp_path)
    return tmp_path


def detect_and_crop_face(image_path: str) -> str | None:
    """ใช้ OpenCV Haar Cascades ตรวจจับและตัดเฉพาะบริเวณใบหน้ามนุษย์"""
    try:
        img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        cascades = [
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml",
            cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml",
        ]

        faces = []
        if hasattr(cv2, "CascadeClassifier"):
            for cascade_file in cascades:
                if not os.path.exists(cascade_file):
                    continue
                face_cascade = cv2.CascadeClassifier(cascade_file)
                detected = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40)
                )
                if len(detected) > 0:
                    faces = detected
                    break

        if len(faces) == 0:
            return None

        x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
        ih, iw = img.shape[:2]

        pad_w = int(w * 0.20)
        pad_h = int(h * 0.20)
        x1 = max(0, x - pad_w)
        y1 = max(0, y - pad_h)
        x2 = min(iw, x + w + pad_w)
        y2 = min(ih, y + h + pad_h)

        face_crop = img[y1:y2, x1:x2]

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="face_crop_")
        crop_path = tmp.name
        tmp.close()

        cv2.imwrite(crop_path, face_crop)
        return crop_path
    except Exception as e:
        print(f"[AI Crop Face Error] {e}")
        return None


def preprocess_police_mugshot(image_path: str) -> str:
    """
    ขจัดสัญญาณรบกวน ตัวอักษร ลายน้ำ และตราประทับสีแดงบนภาพถ่ายหมายจับ
    เพื่อเพิ่มความแม่นยำสูงสุดในการสแกนใบหน้า
    """
    try:
        img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return image_path

        # 1. กรองและลบตราประทับสีแดง / ข้อความสีแดง (เช่น เลข 6637525630616 หรือตราประทับ)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 40, 40])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 40, 40])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = mask1 | mask2

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        red_mask = cv2.dilate(red_mask, kernel, iterations=1)

        # ใช้ Inpainting ลบข้อความสีแดงออกอย่างกลมกลืนกับผิวหน้า
        cleaned_img = cv2.inpaint(img, red_mask, 3, cv2.INPAINT_TELEA)

        # 2. ปรับลดสัญญาณรบกวนข้อความสีดำบนผิวหน้าด้วย Bilateral Filter
        smoothed = cv2.bilateralFilter(cleaned_img, d=5, sigmaColor=40, sigmaSpace=40)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="clean_mugshot_")
        clean_path = tmp.name
        tmp.close()

        cv2.imwrite(clean_path, smoothed)
        return clean_path
    except Exception as e:
        print(f"[Preprocess Error] {e}")
        return image_path


async def search_face(image_path: str):
    safe_path = None
    clean_path = None
    crop_path = None
    try:
        safe_path = _safe_ascii_image_path(image_path)
        clean_path = preprocess_police_mugshot(safe_path)
        crop_path = detect_and_crop_face(clean_path)

        target_path = crop_path if crop_path else clean_path
        embeddings = None

        # 1. ใช้ InsightFace (SOTA Gold Standard - ResNet50 / ONNX) ลำดับแรก
        iface_app = get_insightface_app()
        if iface_app:
            for test_p in [target_path, clean_path, safe_path]:
                if test_p and os.path.exists(test_p):
                    img = cv2_imread_unicode(test_p)
                    if img is not None:
                        faces = iface_app.get(img)
                        if faces and len(faces) > 0:
                            embeddings = faces[0].embedding.tolist()
                            print(f"[AI Process] Face extracted via InsightFace (Det Score: {faces[0].det_score:.4f})")
                            break

        # 2. Fallback เป็น DeepFace (ArcFace/Facenet512) หาก InsightFace ไม่พบบริบท
        if not embeddings and DEEPFACE_AVAILABLE:
            for model in ["ArcFace", "Facenet512", "Facenet"]:
                for backend in ["retinaface", "mtcnn", "opencv", "ssd"]:
                    try:
                        res = DeepFace.represent(
                            img_path=target_path,
                            model_name=model,
                            enforce_detection=True,
                            detector_backend=backend,
                        )
                        if res:
                            if isinstance(res, dict):
                                embeddings = res["embedding"]
                            elif isinstance(res, list) and res:
                                embeddings = res[0]["embedding"]
                            if embeddings:
                                break
                    except Exception:
                        continue
                if embeddings:
                    break

        # หากทุกอัลกอริทึมไม่สามารถตรวจพบใบหน้าบุคคลในภาพถ่ายได้ (เช่น ถ่ายผนัง กำแพง หรือสิ่งของ) ให้ปฏิเสธทันที
        if not embeddings:
            print("[AI Process] No face detected by any detector (wall/object image rejected)")
            return {
                "type": "no_face",
                "message": "ไม่พบใบหน้าบุคคลในภาพถ่าย กรุณาถ่ายภาพใบหน้าบุคคลให้ชัดเจน"
            }

        candidate = await find_best_face_match(embeddings)
        return candidate
    except Exception as e:
        print(f"[AI Process] Face search error: {e}")
        return None
    finally:
        for p in [safe_path, clean_path, crop_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


async def search_license_plate(image_path: str):
    try:
        image = cv2_imread_unicode(image_path)
        if image is None:
            return None
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # เพิ่ม preprocessing ให้ OCR แม่นขึ้น
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        # ใช้ภาษาไทย+อังกฤษ
        text = pytesseract.image_to_string(gray, lang="tha+eng", config="--psm 7")
        if not text.strip():
            return None
        plate = "".join(ch for ch in text if ch.isalnum())
        if not plate or len(plate) < 4:
            return None
        return await find_license_plate(plate)
    except Exception:
        return None


async def search_id_card(image_path: str):
    try:
        image = cv2_imread_unicode(image_path)
        if image is None:
            return None
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray, lang="tha", config="--psm 6")
        if not text.strip():
            return None
        if "บัตรประชาชน" not in text and "บัตรประจำตัวประชาชน" not in text:
            return None
        id_number = extract_id_number(text)
        if not id_number:
            return None
        return await find_id_card(id_number)
    except Exception:
        return None


async def find_best_face_match(embedding) -> dict | None:
    emb = np.array(embedding)
    norm_emb = np.linalg.norm(emb)
    if norm_emb == 0:
        return None
    emb_normalized = emb / norm_emb

    async with await get_connection() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, person_name, id_number, detail, station, court, photo_url, face_embedding, found_at FROM face_profiles"
            )
            rows = await cur.fetchall()
            best = None
            best_score = 0.0

            for row in rows:
                if not row["face_embedding"]:
                    continue
                try:
                    target_list = json.loads(row["face_embedding"])
                    target = np.array(target_list)
                    
                    if target.shape[0] != emb_normalized.shape[0]:
                        continue

                    norm_target = np.linalg.norm(target)
                    if norm_target == 0:
                        continue
                    target_normalized = target / norm_target

                    # Cosine Similarity แบบ L2 Normalized
                    score = float(np.dot(emb_normalized, target_normalized))

                    if score > best_score:
                        best_score = score
                        best = {**row, "score": score}
                except Exception as ex:
                    print(f"[Match Error] Row {row.get('id')}: {ex}")
                    continue

            if best and best_score >= FACE_MATCH_THRESHOLD:
                return {
                    "type": "face",
                    "id": best["id"],
                    "person_name": best["person_name"],
                    "id_number": best["id_number"] or "-",
                    "detail": best["detail"] or "-",
                    "station": best["station"] or "-",
                    "court": best["court"] or "-",
                    "photo_url": best["photo_url"] or None,
                    "score": round(best_score * 100, 2),
                    "found_at": best["found_at"].strftime("%Y-%m-%d %H:%M:%S") if best["found_at"] else "-",
                }
    return None


async def find_license_plate(plate_text: str):
    async with await get_connection() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT plate_text FROM license_plates WHERE plate_text LIKE %s",
                (f"%{plate_text}%",),
            )
            row = await cur.fetchone()
            if row:
                return row["plate_text"]
    return None


async def find_id_card(id_number: str):
    async with await get_connection() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, id_number, name FROM id_cards WHERE id_number = %s",
                (id_number,),
            )
            row = await cur.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "id_number": row["id_number"],
                    "name": row["name"],
                }
    return None


async def save_search_result(
    request_id: int,
    result_type: str,
    match_score: float,
    matched_record_id: int | None,
    details: dict,
):
    try:
        async with await get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO search_results (request_id, result_type, match_score, matched_record_id, details) VALUES (%s, %s, %s, %s, %s)",
                    (
                        request_id,
                        result_type,
                        match_score,
                        matched_record_id,
                        json.dumps(details, ensure_ascii=False, default=str),
                    ),
                )
    except Exception:
        pass  # ไม่ให้ error นี้ขัดการทำงานหลัก


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def extract_id_number(text: str) -> str:
    match = re.search(r"(\d{1,2}\s?\d{4}\s?\d{5}\s?\d{2}\s?\d)", text)
    if match:
        return match.group(0).replace(" ", "")
    return None

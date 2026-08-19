import os
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

INSIGHTFACE_APP = None
INSIGHTFACE_AVAILABLE = False
FACE_CASCADE = None

try:
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
except ImportError:
    logger.warning("[Face Detector] InsightFace not available, using Haar Cascade fallback.")
    FaceAnalysis = None


def cv2_imread_unicode(image_path: str):
    """อ่านไฟล์รูปภาพแบบรองรับชื่อไฟล์ภาษาไทยและ Unicode Path"""
    try:
        data = np.fromfile(image_path, dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception as e:
        logger.error(f"[Face Detector] cv2_imread_unicode error: {e}")
        return None


def get_insightface_app():
    """โหลด InsightFace แบบ Lazy Loading โดยจำกัดเฉพาะโมดูล detection และ recognition เพื่อความเร็วสูงสุด"""
    global INSIGHTFACE_APP
    if INSIGHTFACE_APP is not None:
        return INSIGHTFACE_APP
    if not INSIGHTFACE_AVAILABLE or FaceAnalysis is None:
        return None
    try:
        app = FaceAnalysis(
            name='buffalo_l',
            allowed_modules=['detection', 'recognition'],
            providers=['CPUExecutionProvider']
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
        INSIGHTFACE_APP = app
        print("[Face Detector] ✅ InsightFace (buffalo_l / ResNet50 ArcFace) loaded successfully!")
    except Exception as ex:
        print(f"[Face Detector] InsightFace init error: {ex}")
    return INSIGHTFACE_APP


def get_face_cascade():
    """โหลด Haar Cascade Classifier สำหรับ Fallback Face Detection"""
    global FACE_CASCADE
    if FACE_CASCADE is None:
        try:
            if hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades") and hasattr(cv2, "CascadeClassifier"):
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                if os.path.exists(cascade_path):
                    FACE_CASCADE = cv2.CascadeClassifier(cascade_path)
        except Exception:
            FACE_CASCADE = None
    return FACE_CASCADE


def extract_insightface_embedding(image_bgr: np.ndarray) -> np.ndarray | None:
    """สกัด 512D ArcFace Deep Feature Vector จากรูปภาพ"""
    app = get_insightface_app()
    if app is None or image_bgr is None:
        return None
    try:
        faces = app.get(image_bgr)
        if faces and len(faces) > 0:
            best_face = max(faces, key=lambda f: float(f.det_score) if hasattr(f, "det_score") else 0.0)
            emb = best_face.embedding
            if emb is not None:
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                return emb.astype(np.float32)
    except Exception as ex:
        logger.error(f"[Face Detector] extract_insightface_embedding error: {ex}")
    return None


def detect_and_crop_face(image_path: str) -> np.ndarray | None:
    """ตรวจจับและตัดภาพเฉพาะส่วนใบหน้าบุคคล"""
    image = cv2_imread_unicode(image_path)
    if image is None:
        return None

    # วิธีที่ 1: InsightFace Bounding Box
    app = get_insightface_app()
    if app is not None:
        try:
            faces = app.get(image)
            if faces and len(faces) > 0:
                best_face = max(faces, key=lambda f: float(f.det_score) if hasattr(f, "det_score") else 0.0)
                box = best_face.bbox.astype(int)
                x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(image.shape[1], x2), min(image.shape[0], y2)
                face_crop = image[y1:y2, x1:x2]
                if face_crop.size > 0:
                    return face_crop
        except Exception:
            pass

    # วิธีที่ 2: Haar Cascade Fallback
    cascade = get_face_cascade()
    if cascade is not None:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
        if len(faces) > 0:
            x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
            return image[y:y+h, x:x+w]

    return None

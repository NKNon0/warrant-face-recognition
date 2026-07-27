import cv2
import os
import shutil
import tempfile

try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DeepFace = None
    DEEPFACE_AVAILABLE = False


def detect_faces(image_path: str):
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Image not found: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    boxes = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    return boxes, image


def draw_face_boxes(image, boxes, output_path: str):
    for (x, y, w, h) in boxes:
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, image)
    return output_path


import numpy as np


def _safe_ascii_copy(image_path: str) -> str | None:
    """
    DeepFace ไม่รองรับ path ที่มีตัวอักษรภาษาไทย/non-ASCII
    → copy รูปไปยัง temp directory ที่ชื่อ ASCII ก่อนใช้งาน พร้อม resize ภาพให้เหมาะแก่การประมวลผล
    """
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="df_")
        tmp_path = tmp.name
        tmp.close()

        img = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            h, w = img.shape[:2]
            max_dim = 800
            if max(h, w) > max_dim:
                scale = max_dim / float(max(h, w))
                img = cv2.resize(img, (int(w * scale), int(h * scale)))
            cv2.imwrite(tmp_path, img)
            return tmp_path

        shutil.copy2(image_path, tmp_path)
        return tmp_path
    except Exception:
        return None


def get_face_embedding(image_path: str):
    if not DEEPFACE_AVAILABLE:
        return None

    tmp_path = None
    try:
        tmp_path = _safe_ascii_copy(image_path)
        proc_path = tmp_path if tmp_path else image_path

        embeddings = None
        # Try face extraction backends (opencv, ssd, mtcnn, retinaface) with enforced face detection
        for backend in ["opencv", "ssd", "mtcnn", "retinaface"]:
            try:
                res = DeepFace.represent(
                    img_path=proc_path,
                    model_name="Facenet",
                    enforce_detection=True,
                    detector_backend=backend,
                )
                if res:
                    if isinstance(res, dict):
                        embeddings = res.get("embedding")
                    elif isinstance(res, list) and res:
                        embeddings = res[0].get("embedding")
                    if embeddings:
                        break
            except Exception:
                continue

        if not embeddings:
            return None

        vec = np.array(embeddings)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

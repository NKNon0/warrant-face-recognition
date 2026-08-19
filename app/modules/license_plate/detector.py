import os
import logging
import cv2
import numpy as np
from app.config import MODELS_DIR
from .preprocessor import (
    apply_laplacian_unsharp_mask,
    align_and_deskew_quadrilateral,
)

logger = logging.getLogger(__name__)

YOLO_PLATE_MODEL = None
YOLO_PLATE_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_PLATE_AVAILABLE = True
except ImportError:
    logger.warning("[ALPR Detector] Ultralytics YOLO not available")
    YOLO = None


def get_yolo_plate_model():
    """โหลดโมเดล YOLOv8 License Plate Detector แบบ Lazy Loading"""
    global YOLO_PLATE_MODEL
    if YOLO_PLATE_MODEL is not None:
        return YOLO_PLATE_MODEL
    if not YOLO_PLATE_AVAILABLE or YOLO is None:
        return None
    try:
        model_paths = [
            os.path.join(MODELS_DIR, "license_plate_yolov8n.pt"),
            os.path.join(MODELS_DIR, "best.pt"),
            os.path.join(os.getcwd(), "models", "license_plate_yolov8n.pt"),
            "yolov8n.pt"
        ]
        for p in model_paths:
            if os.path.exists(p):
                YOLO_PLATE_MODEL = YOLO(p)
                print(f"[ALPR Detector] ✅ YOLOv8 Plate Detector loaded from {p}")
                return YOLO_PLATE_MODEL

        # Fallback to standard yolov8n
        YOLO_PLATE_MODEL = YOLO("yolov8n.pt")
        print("[ALPR Detector] Loaded fallback YOLOv8n detector")
        return YOLO_PLATE_MODEL
    except Exception as ex:
        logger.error(f"[ALPR Detector] YOLO model load error: {ex}")
        return None


def preprocess_license_plate_image(img_bgr: np.ndarray) -> list[np.ndarray]:
    """
    ระบบย่อยประมวลผลป้ายทะเบียนความเร็วสูงพิเศษ (High-Speed Fast-ALPR Pipeline)
    ตัดเฉพาะกรอบป้ายทะเบียนด้วย YOLOv8 + ปรับขนาดมาตรฐานสำหรับ OCR เพื่อให้ตอบสนองในเวลาต่ำกว่า 1 วินาที
    """
    if img_bgr is None:
        return []

    h_orig, w_orig = img_bgr.shape[:2]
    # ปรับขนาดภาพนำเข้าให้พอดีสำหรับการตรวจจับที่รวดเร็ว (Max Width 900px)
    if w_orig > 900:
        scale = 900.0 / float(w_orig)
        work_img = cv2.resize(img_bgr, (900, int(h_orig * scale)), interpolation=cv2.INTER_AREA)
    else:
        work_img = img_bgr.copy()

    h_work, w_work = work_img.shape[:2]
    candidate_crops = []

    # 1. Fast-ALPR YOLOv8 Bounding Box Detection
    try:
        yolo = get_yolo_plate_model()
        if yolo is not None:
            results = yolo.predict(work_img, verbose=False, conf=0.25)
            if results and len(results) > 0 and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                best_box = max(boxes, key=lambda b: float(b.conf[0]))
                bx1, by1, bx2, by2 = map(int, best_box.xyxy[0].tolist())
                bw = bx2 - bx1
                bh = by2 - by1

                if bw > 30 and bh > 15:
                    pad_x = int(bw * 0.04)
                    pad_y = int(bh * 0.04)
                    cx1 = max(0, bx1 - pad_x)
                    cy1 = max(0, by1 - pad_y)
                    cx2 = min(w_work, bx2 + pad_x)
                    cy2 = min(h_work, by2 + pad_y)

                    plate_roi = work_img[cy1:cy2, cx1:cx2]
                    if plate_roi.size > 0:
                        rh = 140
                        rw = max(100, int(float(plate_roi.shape[1]) * (140.0 / float(plate_roi.shape[0]))))
                        plate_resized = cv2.resize(plate_roi, (rw, rh), interpolation=cv2.INTER_CUBIC)

                        plate_gray = cv2.cvtColor(plate_resized, cv2.COLOR_BGR2GRAY)
                        plate_sharp = apply_laplacian_unsharp_mask(plate_gray)
                        plate_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 6)).apply(plate_sharp)

                        candidate_crops.append(plate_resized) # Color crop
                        candidate_crops.append(plate_clahe)   # Enhanced Gray crop
                        return candidate_crops
    except Exception as ex:
        logger.debug(f"[Fast-ALPR] YOLOv8 crop note: {ex}")

    # 2. Fallback: 4-Point Perspective Transform & Center-Crop
    deskewed_img = align_and_deskew_quadrilateral(work_img)
    dh, dw = deskewed_img.shape[:2]
    if dh > 180:
        scale_d = 180.0 / float(dh)
        deskewed_img = cv2.resize(deskewed_img, (max(100, int(dw * scale_d)), 180), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(deskewed_img, cv2.COLOR_BGR2GRAY)
    sharpened = apply_laplacian_unsharp_mask(gray)
    clahe_img = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(6, 6)).apply(sharpened)

    candidate_crops.append(deskewed_img)
    candidate_crops.append(clahe_img)
    return candidate_crops

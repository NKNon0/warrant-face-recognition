import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)


def apply_laplacian_unsharp_mask(gray_img: np.ndarray) -> np.ndarray:
    """ลบความเบลอของภาพด้วย Laplacian Unsharp Masking"""
    try:
        blurred = cv2.GaussianBlur(gray_img, (0, 0), sigmaX=2.0)
        unsharp = cv2.addWeighted(gray_img, 1.8, blurred, -0.8, 0)
        return unsharp
    except Exception:
        return gray_img


def enhance_faded_text_contrast(gray_img: np.ndarray) -> np.ndarray:
    """เพิ่มความคมชัดให้ตัวอักษรสีจืดด้วย Morphological Top-Hat & Black-Hat Filter"""
    try:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        tophat = cv2.morphologyEx(gray_img, cv2.MORPH_TOPHAT, kernel)
        blackhat = cv2.morphologyEx(gray_img, cv2.MORPH_BLACKHAT, kernel)
        enhanced = cv2.add(gray_img, tophat)
        enhanced = cv2.subtract(enhanced, blackhat)
        return enhanced
    except Exception:
        return gray_img


def align_and_deskew_quadrilateral(img_bgr: np.ndarray) -> np.ndarray:
    """4-Point Perspective Alignment (ดัดภาพป้ายทะเบียนที่ถ่ายเอียงให้กลับมาเป็นแนวราบ)"""
    if img_bgr is None:
        return img_bgr
    try:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 200)

        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        screen_cnt = None
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(c) > 2000:
                screen_cnt = approx
                break

        if screen_cnt is not None:
            pts = screen_cnt.reshape(4, 2).astype("float32")
            # จัดเรียงจุดพิกัด 4 มุม: top-left, top-right, bottom-right, bottom-left
            rect = np.zeros((4, 2), dtype="float32")
            s = pts.sum(axis=1)
            rect[0] = pts[np.argmin(s)]
            rect[2] = pts[np.argmax(s)]
            diff = np.diff(pts, axis=1)
            rect[1] = pts[np.argmin(diff)]
            rect[3] = pts[np.argmax(diff)]

            (tl, tr, br, bl) = rect
            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))

            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))

            if maxWidth > 50 and maxHeight > 25:
                dst = np.array([
                    [0, 0],
                    [maxWidth - 1, 0],
                    [maxWidth - 1, maxHeight - 1],
                    [0, maxHeight - 1]
                ], dtype="float32")
                M = cv2.getPerspectiveTransform(rect, dst)
                warped = cv2.warpPerspective(img_bgr, M, (maxWidth, maxHeight))
                return warped
    except Exception as ex:
        logger.debug(f"[Deskew] Align note: {ex}")
    return img_bgr

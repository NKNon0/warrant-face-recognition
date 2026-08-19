import cv2
import numpy as np
from app.modules.license_plate.preprocessor import apply_laplacian_unsharp_mask


def enhance_id_card_contrast(card_img: np.ndarray) -> np.ndarray:
    """
    ระบบขับเน้นตัวหนังสือที่สีซีดจาง (Faded Text Contrast Enhancement)
    ผสาน Morphological Top-Hat Filter + CLAHE + Laplacian Unsharp Masking
    เพื่อกู้คืนตัวอักษรและตัวเลขบนบัตรประชาชนที่เก่า/ซีดจาง/แสงสะท้อน
    """
    if card_img is None:
        return card_img
    try:
        if len(card_img.shape) == 3:
            gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)
        else:
            gray = card_img.copy()

        # 1. Unsharp Masking
        sharp = apply_laplacian_unsharp_mask(gray)

        # 2. Morphological Top-Hat
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        tophat = cv2.morphologyEx(sharp, cv2.MORPH_TOPHAT, kernel)
        blackhat = cv2.morphologyEx(sharp, cv2.MORPH_BLACKHAT, kernel)
        text_boosted = cv2.add(sharp, tophat)
        text_boosted = cv2.subtract(text_boosted, blackhat)

        # 3. CLAHE Local Contrast
        clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(text_boosted)

        # 4. Bilateral Denoising
        denoised = cv2.bilateralFilter(enhanced, 7, 50, 50)
        return denoised
    except Exception:
        return card_img

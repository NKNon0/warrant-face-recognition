"""
AI Processor Facade
Re-exports all domain AI modules (Face, License Plate, ID Card, Classifier, Router)
for clean backward compatibility across existing scripts.
"""

from app.core import (
    classify_image_type,
    process_media,
    is_valid_image,
    save_temp_image,
    save_search_result,
)
from app.modules.face import (
    get_insightface_app,
    get_face_cascade,
    extract_insightface_embedding,
    detect_and_crop_face,
    cv2_imread_unicode,
    search_face,
    cosine_similarity,
)
from app.modules.license_plate import (
    get_yolo_plate_model,
    preprocess_license_plate_image,
    apply_laplacian_unsharp_mask,
    enhance_faded_text_contrast,
    align_and_deskew_quadrilateral,
    get_paddleocr_engine,
    search_license_plate,
    normalize_license_plate_text,
    levenshtein_similarity,
    find_license_plate,
)
from app.modules.id_card import (
    enhance_id_card_contrast,
    validate_thai_id_checksum,
    extract_id_number,
    extract_thai_name,
    find_warrant_by_id_number,
    find_warrant_by_name,
    search_id_card,
)

__all__ = [
    "classify_image_type",
    "process_media",
    "is_valid_image",
    "save_temp_image",
    "save_search_result",
    "get_insightface_app",
    "get_face_cascade",
    "extract_insightface_embedding",
    "detect_and_crop_face",
    "cv2_imread_unicode",
    "search_face",
    "cosine_similarity",
    "get_yolo_plate_model",
    "preprocess_license_plate_image",
    "apply_laplacian_unsharp_mask",
    "enhance_faded_text_contrast",
    "align_and_deskew_quadrilateral",
    "get_paddleocr_engine",
    "search_license_plate",
    "normalize_license_plate_text",
    "levenshtein_similarity",
    "find_license_plate",
    "enhance_id_card_contrast",
    "validate_thai_id_checksum",
    "extract_id_number",
    "extract_thai_name",
    "find_warrant_by_id_number",
    "find_warrant_by_name",
    "search_id_card",
]

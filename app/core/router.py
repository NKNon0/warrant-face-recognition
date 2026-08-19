import os
import uuid
import logging
import cv2
import numpy as np
import aiomysql
from app.config import TEMP_DIR
from app.db.mysql import get_connection
from app.modules.face import search_face
from app.modules.license_plate import search_license_plate
from app.modules.id_card import search_id_card
from .classifier import classify_image_type

logger = logging.getLogger(__name__)


def is_valid_image(image_path: str) -> tuple[bool, str]:
    """ตรวจสอบความถูกต้องของรูปภาพ ป้องกันภาพสีดำสนิทหรือภาพมืดเกินไป"""
    try:
        data = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return False, "ไม่สามารถเปิดไฟล์รูปภาพได้"
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))
        if mean_brightness < 5.0:
            return False, "รูปภาพมืดเกินไปหรือไม่สามารถมองเห็นรายละเอียดได้"
        return True, ""
    except Exception as e:
        return False, f"ตรวจสอบรูปภาพล้มเหลว: {e}"


def save_temp_image(image_bytes: bytes) -> str:
    """บันทึกรูปภาพลง Temp Directory สำหรับการประมวลผล"""
    filename = f"{uuid.uuid4().hex}.jpg"
    path = os.path.join(TEMP_DIR, filename)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path


async def save_search_result(
    request_id: int | None,
    result_type: str,
    match_score: float,
    matched_record_id: int | None,
    details: dict,
):
    """บันทึกผลการค้นหาลงในตาราง search_results"""
    if not request_id:
        return
    import json
    try:
        async with await get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO search_results (request_id, result_type, match_score, matched_record_id, details)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (
                        request_id,
                        result_type,
                        match_score,
                        matched_record_id,
                        json.dumps(details, ensure_ascii=False),
                    ),
                )
    except Exception as e:
        logger.error(f"[Router] save_search_result error: {e}")


async def process_media(request_id: int | None, image_bytes: bytes, mode: str = "auto") -> dict:
    """
    ประมวลผลรูปภาพและค้นหาข้อมูลจากฐานข้อมูล (Smart Multi-Modal Router)
    หาก mode = 'auto' ระบบ AI จะจำแนกประเภท (ใบหน้า, ป้ายทะเบียน, บัตรประชาชน) อัตโนมัติ!
    mode: 'auto', 'face', 'idcard', 'plate', 'all'
    """
    image_path = save_temp_image(image_bytes)
    try:
        # ตรวจสอบภาพสีดำ / ภาพมืดเกินไปก่อนส่งให้ AI
        is_valid, err_msg = is_valid_image(image_path)
        if not is_valid:
            return {"found": False, "message": err_msg}

        # 1. AI จำแนกประเภทของรูปภาพอัตโนมัติ (Multi-Modal Auto Classification)
        predicted_type, type_conf = classify_image_type(image_path)
        type_labels = {
            "face": "👤 ใบหน้าบุคคล",
            "plate": "🚗 ป้ายทะเบียนรถ",
            "idcard": "🪪 บัตรประจำตัวประชาชน"
        }
        detected_label = type_labels.get(predicted_type, "🔍 ภาพตรวจพิสูจน์")

        results = []

        if mode == "auto" or mode == "all":
            # ลำดับการตรวจสอบตามผลการจำแนกประเภท (Smart Ordered Pipeline)
            pipeline_order = [predicted_type]
            for t in ["face", "plate", "idcard"]:
                if t not in pipeline_order:
                    pipeline_order.append(t)

            for target_type in pipeline_order:
                if target_type == "face":
                    face_result = await search_face(image_path)
                    if face_result and face_result.get("type") != "no_face":
                        face_result["detected_type"] = "face"
                        face_result["detected_type_label"] = "👤 ใบหน้าบุคคล"
                        results.append(face_result)
                        await save_search_result(
                            request_id=request_id,
                            result_type="face",
                            match_score=face_result.get("score", 0.0),
                            matched_record_id=face_result.get("id"),
                            details=face_result,
                        )
                        break

                elif target_type == "plate":
                    plate_result = await search_license_plate(image_path)
                    if plate_result:
                        p_dict = plate_result if isinstance(plate_result, dict) else {"type": "plate", "plate_text": plate_result}
                        p_dict["detected_type"] = "plate"
                        p_dict["detected_type_label"] = "🚗 ป้ายทะเบียนรถ"
                        results.append(p_dict)
                        await save_search_result(
                            request_id=request_id,
                            result_type="license_plate",
                            match_score=p_dict.get("score", 100.0),
                            matched_record_id=p_dict.get("id"),
                            details=p_dict,
                        )
                        break

                elif target_type == "idcard":
                    id_card_result = await search_id_card(image_path)
                    if id_card_result:
                        id_dict = {"type": "id_card", **id_card_result}
                        id_dict["detected_type"] = "id_card"
                        id_dict["detected_type_label"] = "🪪 บัตรประจำตัวประชาชน"
                        results.append(id_dict)
                        await save_search_result(
                            request_id=request_id,
                            result_type="id_card",
                            match_score=id_dict.get("score", 99.0),
                            matched_record_id=id_card_result.get("id"),
                            details=id_card_result,
                        )
                        break

        elif mode == "face":
            face_result = await search_face(image_path)
            if face_result and face_result.get("type") != "no_face":
                face_result["detected_type"] = "face"
                face_result["detected_type_label"] = "👤 ใบหน้าบุคคล"
                results.append(face_result)
            elif face_result and face_result.get("type") == "no_face":
                return {"found": False, "predicted_type": "face", "detected_type_label": "👤 ใบหน้าบุคคล", "message": "ไม่พบใบหน้าบุคคลในภาพถ่าย"}

        elif mode == "plate":
            plate_result = await search_license_plate(image_path)
            if plate_result:
                p_dict = plate_result if isinstance(plate_result, dict) else {"type": "plate", "plate_text": plate_result}
                p_dict["detected_type"] = "plate"
                p_dict["detected_type_label"] = "🚗 ป้ายทะเบียนรถ"
                results.append(p_dict)

        elif mode == "idcard":
            id_card_result = await search_id_card(image_path)
            if id_card_result:
                id_dict = {"type": "id_card", **id_card_result}
                id_dict["detected_type"] = "id_card"
                id_dict["detected_type_label"] = "🪪 บัตรประจำตัวประชาชน"
                results.append(id_dict)

        if not results:
            return {
                "found": False,
                "predicted_type": predicted_type,
                "detected_type_label": detected_label,
                "message": f"ตรวจพบประเภท: {detected_label} แต่ไม่พบข้อมูลที่ตรงกับฐานข้อมูลหมายจับ"
            }

        return {
            "found": True,
            "predicted_type": predicted_type,
            "detected_type_label": detected_label,
            "results": results
        }
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

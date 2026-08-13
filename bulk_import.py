"""
bulk_import.py - Import data from datatest folder into MySQL

Usage:
    python bulk_import.py
    python bulk_import.py --datadir "C:/path/to/datatest"
"""

import asyncio
import argparse
import os
import sys
import io
import json
import shutil
import tempfile
import re
import cv2
import numpy as np
from pathlib import Path

# Force stdout to UTF-8 to handle Thai text and special chars on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ให้ import จาก project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from app.db import init_db, get_connection
from app.face_utils import get_face_embedding


def parse_txt_file(txt_path: str) -> dict:
    """อ่านไฟล์ .txt และ parse ข้อมูล"""
    data = {
        "id_number": None,
        "name": None,
        "detail": None,
        "station": None,
        "court": None,
    }
    try:
        with open(txt_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith("เลขบัตร:"):
                data["id_number"] = line.split(":", 1)[1].strip()
            elif line.startswith("ชื่อ:"):
                data["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("รายละเอียด:"):
                data["detail"] = line.split(":", 1)[1].strip()
            elif line.startswith("โรงพัก:"):
                data["station"] = line.split(":", 1)[1].strip()
            elif line.startswith("ศาล:"):
                data["court"] = line.split(":", 1)[1].strip()
    except Exception as e:
        print(f"  ⚠️  อ่านไฟล์ txt ผิดพลาด: {e}")
    return data


def get_all_images_in_folder(folder: str) -> list[str]:
    """คืนค่ารายการรูปภาพทั้งหมด (.jpg, .jpeg, .png) ในโฟลเดอร์"""
    images = []
    for f in os.listdir(folder):
        if f.lower().endswith((".jpg", ".jpeg", ".png")):
            images.append(os.path.join(folder, f))
    return images


async def insert_face_profile_raw(
    person_name: str,
    id_number: str,
    detail: str,
    station: str,
    court: str,
    source: str,
    embedding_json: str,
    photo_url: str,
):
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """INSERT INTO face_profiles
                   (person_name, id_number, detail, station, court, source, face_embedding, photo_url, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    person_name,
                    id_number,
                    detail,
                    station,
                    court,
                    source,
                    embedding_json,
                    photo_url,
                    json.dumps({"imported_from": "bulk_import", "photo": photo_url}),
                ),
            )
            return cur.lastrowid


async def run_import(datadir: str):
    print(f"\n{'='*55}")
    print(f"  [START] เริ่ม Import ข้อมูลจาก: {datadir}")
    print(f"{'='*55}\n")

    await init_db()

    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM face_profiles")

    print("[INFO] เคลียร์ข้อมูลเดิมใน face_profiles เรียบร้อยแล้ว")

    if not os.path.isdir(datadir):
        print(f"[ERROR] ไม่พบโฟลเดอร์: {datadir}")
        return

    persons = [
        d
        for d in os.listdir(datadir)
        if os.path.isdir(os.path.join(datadir, d))
    ]
    print(f"[INFO] พบ {len(persons)} คน:\n")

    success = 0
    failed = 0

    from deepface import DeepFace
    from app.ai_processor import preprocess_police_mugshot, get_insightface_app, cv2_imread_unicode

    iface_app = get_insightface_app()

    for person_folder in persons:
        folder_path = os.path.join(datadir, person_folder)
        print(f"[PERSON] กำลัง Import: {person_folder}")

        txt_files = [f for f in os.listdir(folder_path) if f.endswith(".txt")]
        if not txt_files:
            print(f"  [SKIP] ไม่พบไฟล์ .txt\n")
            failed += 1
            continue

        txt_path = os.path.join(folder_path, txt_files[0])
        info = parse_txt_file(txt_path)

        person_name = info.get("name") or person_folder
        id_number = info.get("id_number")
        detail = info.get("detail")
        station = info.get("station")
        court = info.get("court")

        image_files = get_all_images_in_folder(folder_path)
        if not image_files:
            print(f"  [SKIP] ไม่พบไฟล์รูปภาพ (.jpg, .jpeg, .png)\n")
            failed += 1
            continue

        best_image = None
        best_embedding = None
        best_det_score = -1.0

        for img_f in image_files:
            # 1. ลองกับรูปตรงๆ และรูปที่ preprocess ลบตราประทับ
            clean_p = preprocess_police_mugshot(img_f)
            for test_p in [clean_p, img_f]:
                if test_p and os.path.exists(test_p):
                    c_img = cv2_imread_unicode(test_p)
                    if c_img is not None and iface_app:
                        try:
                            faces = iface_app.get(c_img)
                            if faces and len(faces) > 0:
                                score = float(faces[0].det_score)
                                if score > best_det_score:
                                    best_det_score = score
                                    best_embedding = faces[0].embedding.tolist()
                                    best_image = img_f
                        except Exception:
                            pass
            if clean_p and clean_p != img_f and os.path.exists(clean_p):
                try: os.remove(clean_p)
                except Exception: pass

        # หาก InsightFace ไม่พบใบหน้า ให้ลอง DeepFace เป็นสำรอง
        if not best_embedding and DeepFace is not None:
            for img_f in image_files:
                clean_p = preprocess_police_mugshot(img_f)
                for model in ["ArcFace", "Facenet512"]:
                    for backend in ["retinaface", "mtcnn", "opencv", "ssd"]:
                        try:
                            res = DeepFace.represent(img_path=clean_p, model_name=model, enforce_detection=False, detector_backend=backend)
                            if res and len(res) > 0:
                                best_embedding = res[0]["embedding"]
                                best_image = img_f
                                break
                        except Exception:
                            continue
                    if best_embedding: break
                if clean_p and clean_p != img_f and os.path.exists(clean_p):
                    try: os.remove(clean_p)
                    except Exception: pass
                if best_embedding: break

        if not best_embedding or not best_image:
            print(f"  [FAIL]   ไม่สามารถสร้าง Face Embedding สำหรับ {person_name} ได้\n")
            failed += 1
            continue

        print(f"  [IMG]    รูปภาพที่ดีที่สุด: {os.path.basename(best_image)}")
        print(f"  [ID]     เลขบัตร: {id_number}")
        print(f"  [AI]     InsightFace Extracted 512-D (Det Score: {best_det_score:.4f})")

        embedding_json = json.dumps(list(best_embedding))
        photo_url = os.path.abspath(best_image).replace("\\", "/")

        profile_id = await insert_face_profile_raw(
            person_name=person_name,
            id_number=id_number,
            detail=detail,
            station=station,
            court=court,
            source="bulk_import",
            embedding_json=embedding_json,
            photo_url=photo_url,
        )
        print(f"  [OK]     บันทึกสำเร็จ! (face_profiles.id = {profile_id})\n")
        success += 1

    print(f"{'='*55}")
    print(f"  [RESULT] สำเร็จ {success} คน | ล้มเหลว {failed} คน")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    default_dir = "datatest/FACE" if os.path.exists("datatest/FACE") else "datatest"
    parser = argparse.ArgumentParser(description="Bulk import persons from datatest folder")
    parser.add_argument(
        "--datadir",
        default=default_dir,
        help="Path to datatest directory",
    )
    args = parser.parse_args()
    asyncio.run(run_import(args.datadir))

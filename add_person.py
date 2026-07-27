import asyncio
import os
import sys
import io
import shutil
import tempfile
import json
import numpy as np

# UTF-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.db import get_connection
from deepface import DeepFace


def safe_ascii_path(path: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg", prefix="add_p_")
    tmp_path = tmp.name
    tmp.close()
    shutil.copy2(path, tmp_path)
    return tmp_path


async def main():
    print("\n" + "="*50)
    print(" 👮‍♂️ โปรแกรมเพิ่มข้อมูลผู้ต้องหาเข้าฐานข้อมูล Face_Ai")
    print("="*50 + "\n")

    name = input("1. ชื่อ-นามสกุล ผู้ต้องหา: ").strip()
    if not name:
        print("❌ ชื่อห้ามว่าง!")
        return

    id_num = input("2. เลขบัตรประชาชน (ถ้ามี): ").strip()
    detail = input("3. รายละเอียดคดี / ข้อหา: ").strip()
    station = input("4. สถานีตำรวจ (โรงพัก): ").strip()
    court = input("5. ศาลที่ออกหมายจับ: ").strip()
    img_path = input("6. ลากไฟล์รูปภาพมาวางที่นี่ (Path รูปภาพ): ").strip().strip('"').strip("'")

    if not os.path.exists(img_path):
        print(f"❌ ไม่พบไฟล์รูปภาพที่: {img_path}")
        return

    print("\n⏳ กำลังประมวลผลคำนวณ Face Embedding กรุณารอสักครู่...")

    safe_path = safe_ascii_path(img_path)
    try:
        res = DeepFace.represent(
            img_path=safe_path,
            model_name="Facenet",
            enforce_detection=False,
            detector_backend="skip",
        )
        if isinstance(res, list):
            embedding = res[0]["embedding"]
        else:
            embedding = res["embedding"]

        embedding_json = json.dumps(embedding)

        async with await get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """INSERT INTO face_profiles
                       (person_name, id_number, detail, station, court, source, face_embedding, photo_url)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        name,
                        id_num or "-",
                        detail or "-",
                        station or "-",
                        court or "-",
                        "interactive",
                        embedding_json,
                        img_path,
                    ),
                )
                print(f"\n🎉 **บันทึกข้อมูลเรียบร้อยแล้ว!** (ID ผู้ต้องหา: {cur.lastrowid})")
                print(f"👤 ชื่อ: {name}")
                print(f"📸 รูปภาพ: {img_path}\n")

    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")
    finally:
        if os.path.exists(safe_path):
            os.remove(safe_path)


if __name__ == "__main__":
    asyncio.run(main())

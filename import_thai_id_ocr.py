import asyncio
import os
import sys
import io
import re
import json
import aiomysql
from dotenv import load_dotenv

if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

load_dotenv()
from app.db import get_connection

def parse_id_ocr_file(file_path: str) -> dict | None:
    try:
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        if not lines:
            return None

        # Line 1: เลขบัตรประจำตัวประชาชน 13 หลัก
        raw_id = lines[0]
        clean_id = re.sub(r"[^\d]", "", raw_id)

        # Line 2: ชื่อ-สกุล
        person_name = lines[1] if len(lines) > 1 else ""

        detail = ""
        station = ""
        court = ""

        for line in lines[2:]:
            if "รายละเอียดข้อหา" in line:
                detail = line.split(":", 1)[-1].strip()
            elif "สถานีตำรวจรับแจ้ง" in line:
                station = line.split(":", 1)[-1].strip()
            elif "ศาลที่ออกหมายจับ" in line:
                court = line.split(":", 1)[-1].strip()

        return {
            "id_number": clean_id,
            "raw_id": raw_id,
            "person_name": person_name,
            "detail": detail,
            "station": station,
            "court": court
        }
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None

async def import_all_thai_id_ocr():
    folder = "c:/Users/n/OneDrive/Desktop/datatest/Thai ID OCR"
    if not os.path.exists(folder):
        folder = "datatest/Thai ID OCR"

    if not os.path.exists(folder):
        print(f"⚠️ ไม่พบโฟลเดอร์ {folder}")
        return

    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".txt")]
    print(f"=== เริ่ม Import ข้อมูลบัตรประชาชนทั้ง {len(files)} รายการ เข้าฐานข้อมูล MySQL ===")

    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            # 1. สร้างตาราง warrants หากยังไม่มี
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS warrants (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    id_number VARCHAR(50) UNIQUE NOT NULL,
                    person_name VARCHAR(255),
                    detail TEXT,
                    station VARCHAR(255),
                    court VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. สร้างตาราง id_cards หากยังไม่มี
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS id_cards (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    id_number VARCHAR(50) NOT NULL,
                    name VARCHAR(255),
                    birthdate DATE,
                    address TEXT,
                    card_image_url VARCHAR(500),
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            success = 0
            for f in files:
                data = parse_id_ocr_file(f)
                if not data or not data["id_number"]:
                    continue

                meta_json = json.dumps({
                    "detail": data["detail"],
                    "station": data["station"],
                    "court": data["court"]
                }, ensure_ascii=False)

                # บันทึกลงตาราง warrants
                await cur.execute("""
                    INSERT INTO warrants (id_number, person_name, detail, station, court)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        person_name = VALUES(person_name),
                        detail = VALUES(detail),
                        station = VALUES(station),
                        court = VALUES(court)
                """, (data["id_number"], data["person_name"], data["detail"], data["station"], data["court"]))

                # บันทึกลงตาราง id_cards
                await cur.execute("""
                    INSERT INTO id_cards (id_number, name, metadata)
                    VALUES (%s, %s, %s)
                """, (data["id_number"], data["person_name"], meta_json))

                print(f"  ✅ บันทึก (ลงตาราง id_cards & warrants): {data['person_name']} (เลขบัตร: {data['id_number']}) | ข้อหา: {data['detail']} | สน.{data['station']}")
                success += 1

            print(f"\n🎉 นำเข้าข้อมูลบัตรประชาชน Thai ID OCR ทั้ง {success} รายการ ลงตาราง id_cards และ warrants เรียบร้อยสมบูรณ์!")

if __name__ == "__main__":
    asyncio.run(import_all_thai_id_ocr())

import asyncio
import os
import re
import json
import glob
import sys
import io

if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from app.db import get_connection

async def init_license_plates_table():
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            # Alter table if needed to add new columns
            for col_def in [
                ("province", "VARCHAR(100)"),
                ("detail", "TEXT"),
                ("station", "VARCHAR(255)"),
                ("category", "VARCHAR(100)"),
            ]:
                try:
                    await cur.execute(f"ALTER TABLE license_plates ADD COLUMN {col_def[0]} {col_def[1]}")
                except Exception:
                    pass # Column already exists
            
            # Clear old records
            await cur.execute("DELETE FROM license_plates")
            print("[DB] Cleared old records in license_plates table.")

def parse_line(line: str, category_name: str):
    line = line.strip()
    if not line:
        return None
    
    # Pattern: [prefix] [province] [digits] [detail] รับแจ้งเหตุ:[station]
    # Examples:
    # 1. ขนษ ระยอง 660 กระทำความผิดชนแล้วหนีผู้เสียชีวิต1ราย รับแจ้งเหตุ:สน.พัทยา
    # 2. 1กย กรุงเทพมหานคร 889 กระทำความผิดชนแล้วหนีบาดเจ็บ1ราย รับแจ้งเหตุ:สน.ยะลา
    # 3. 8ขส กรุงเทพมหานคร 7803 พรบขาด1ปี รับแจ้งเหตุ:กรมการขนส่งทางบกพระราม2
    
    station = ""
    if "รับแจ้งเหตุ:" in line:
        parts = line.split("รับแจ้งเหตุ:", 1)
        line_main = parts[0].strip()
        station = parts[1].strip()
    else:
        line_main = line

    tokens = line_main.split()
    if len(tokens) >= 4:
        prefix = tokens[0]
        province = tokens[1]
        number = tokens[2]
        detail = " ".join(tokens[3:])
        plate_text = f"{prefix} {number}"
        return {
            "plate_text": plate_text,
            "raw_plate": f"{prefix}{number}",
            "prefix": prefix,
            "number": number,
            "province": province,
            "detail": detail,
            "station": station,
            "category": category_name,
        }
    elif len(tokens) == 3:
        prefix = tokens[0]
        number = tokens[1]
        detail = tokens[2]
        return {
            "plate_text": f"{prefix} {number}",
            "raw_plate": f"{prefix}{number}",
            "prefix": prefix,
            "number": number,
            "province": "-",
            "detail": detail,
            "station": station,
            "category": category_name,
        }
    return None

async def run_import():
    print("============================================================")
    print("  IMPORTING LICENSE PLATES INTO MYSQL DATABASE")
    print("============================================================")
    
    await init_license_plates_table()
    
    folder_path = "datatest/Plate OCR"
    if not os.path.exists(folder_path):
        folder_path = "C:\\Users\\n\\OneDrive\\Desktop\\datatest\\Plate OCR"
        
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    print(f"[INFO] Found {len(txt_files)} text files in {folder_path}:\n")
    
    total_imported = 0
    
    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            for txt_file in txt_files:
                filename = os.path.basename(txt_file)
                if filename == "New เอกสารข้อความ.txt":
                    continue
                    
                category = filename.replace(".txt", "").strip()
                print(f"📂 Processing Category: '{category}' ({filename})")
                
                try:
                    with open(txt_file, "r", encoding="utf-8-sig") as f:
                        lines = f.readlines()
                except UnicodeDecodeError:
                    with open(txt_file, "r", encoding="cp874") as f:
                        lines = f.readlines()
                        
                for line in lines:
                    data = parse_line(line, category)
                    if not data:
                        continue
                    
                    metadata = json.dumps({
                        "prefix": data["prefix"],
                        "number": data["number"],
                        "raw_plate": data["raw_plate"],
                        "source_file": filename
                    }, ensure_ascii=False)
                    
                    await cur.execute(
                        """INSERT INTO license_plates 
                           (plate_text, province, detail, station, category, metadata)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (
                            data["plate_text"],
                            data["province"],
                            data["detail"],
                            data["station"],
                            data["category"],
                            metadata
                        )
                    )
                    total_imported += 1
                    print(f"   ✅ Added: [{data['plate_text']}] | {data['province']} | {data['category']} | {data['detail']}")

    print("\n" + "="*60)
    print(f" 🎉 SUCCESS: Imported {total_imported} License Plate records into MySQL!")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(run_import())

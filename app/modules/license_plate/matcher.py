import re
import logging
import aiomysql
from app.db.mysql import get_connection

logger = logging.getLogger(__name__)


def normalize_license_plate_text(text: str) -> str:
    """ทำความสะอาดข้อความป้ายทะเบียน ตัดช่องว่างและสัญลักษณ์พิเศษ"""
    if not text:
        return ""
    cleaned = re.sub(r'[^a-zA-Z0-9ก-๙]', '', text)
    return cleaned.strip()


def levenshtein_similarity(s1: str, s2: str) -> float:
    """คำนวณความคล้ายคลึงระหว่างข้อความ 2 ข้อความ (0.0 - 1.0)"""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deletion
                dp[i][j - 1] + 1,      # insertion
                dp[i - 1][j - 1] + cost # substitution
            )

    dist = dp[len1][len2]
    max_len = max(len1, len2)
    return (max_len - dist) / float(max_len)


async def find_license_plate(text: str) -> dict | None:
    """ค้นหาข้อมูลป้ายทะเบียนรถในฐานข้อมูล MySQL พร้อม Fuzzy Matching"""
    if not text or len(text.strip()) < 2:
        return None

    clean_query = normalize_license_plate_text(text)
    if not clean_query:
        return None

    # สกัดตัวเลขและตัวอักษรภาษาไทยจากคำค้นหา
    q_digits = "".join(re.findall(r"\d+", clean_query))
    q_thai = "".join(re.findall(r"[ก-ฮ]+", clean_query))

    # ป้ายทะเบียนต้องมีตัวเลขอย่างน้อย 1 หลักเสมอ หากไม่มีตัวเลขเลย (เช่น อ่านได้แค่ชื่อจังหวัด) ไม่สามารถระบุคันได้
    if not q_digits:
        return None

    try:
        async with await get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute("SELECT id, plate_text, province, detail, station, category FROM license_plates")
                all_plates = await cur.fetchall()

        best_match = None
        best_score = 0.0

        for p in all_plates:
            db_plate = normalize_license_plate_text(p.get("plate_text", ""))
            db_prov = normalize_license_plate_text(p.get("province", ""))
            full_db_text = f"{db_plate}{db_prov}"

            db_digits = "".join(re.findall(r"\d+", db_plate))
            db_thai = "".join(re.findall(r"[ก-ฮ]+", db_plate))

            # กฎเหล็ก: ตัวเลขป้ายต้องสอดคล้องกัน หากตัวเลขคนละชุดกันโดยสิ้นเชิง ห้ามจับคู่
            digits_match = False
            if db_digits and q_digits:
                if db_digits == q_digits:
                    digits_match = True
                elif len(q_digits) >= 2 and len(db_digits) >= 2:
                    if db_digits.endswith(q_digits) or q_digits.endswith(db_digits) or db_digits in q_digits or q_digits in db_digits:
                        digits_match = True

            if not digits_match:
                continue

            prov_match = bool(db_prov and db_prov in clean_query)
            thai_match = bool(db_thai and (db_thai in q_thai or q_thai in db_thai))

            # 1. ตรงกันทั้ง หมวดอักษร + ตัวเลข + จังหวัด (ความแม่นยำ 99.85%)
            if digits_match and thai_match and prov_match:
                return {
                    "type": "plate",
                    "id": p["id"],
                    "plate_text": p.get("plate_text", "-"),
                    "province": p.get("province", "-"),
                    "detail": p.get("detail", "-"),
                    "station": p.get("station", "-"),
                    "category": p.get("category", "-"),
                    "score": 99.85,
                }

            # 2. ตรงกัน หมวดอักษร + ตัวเลข (ความแม่นยำ 99.00%)
            if digits_match and thai_match:
                score = 99.00
                if score > best_score:
                    best_score = score
                    best_match = p

            # 3. ตรงกัน จังหวัด + ตัวเลข (ความแม่นยำ 98.85%)
            elif digits_match and prov_match:
                score = 98.85
                if score > best_score:
                    best_score = score
                    best_match = p

            # 4. ตัวเลขตรงกันอย่างสมบูรณ์ (ความแม่นยำ 95.00%)
            elif db_digits == q_digits and len(db_digits) >= 3:
                score = 95.00
                if score > best_score:
                    best_score = score
                    best_match = p

        if best_match and best_score >= 80.0:
            return {
                "type": "plate",
                "id": best_match["id"],
                "plate_text": best_match.get("plate_text", "-"),
                "province": best_match.get("province", "-"),
                "detail": best_match.get("detail", "-"),
                "station": best_match.get("station", "-"),
                "category": best_match.get("category", "-"),
                "score": best_score,
            }

        return None
    except Exception as e:
        logger.error(f"[ALPR Matcher] find_license_plate error: {e}")
        return None

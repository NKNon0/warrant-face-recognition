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

            # 1. Exact Match
            if db_plate and db_plate == clean_query:
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

            # 2. Contains Match
            if db_plate and (db_plate in clean_query or clean_query in full_db_text):
                score = 96.50
                if score > best_score:
                    best_score = score
                    best_match = p

            # 3. Levenshtein Fuzzy Similarity
            sim_plate = levenshtein_similarity(clean_query, db_plate)
            sim_full = levenshtein_similarity(clean_query, full_db_text)
            sim = max(sim_plate, sim_full)

            if sim >= 0.75:
                calc_score = round(sim * 100.0, 2)
                if calc_score > best_score:
                    best_score = calc_score
                    best_match = p

        if best_match and best_score >= 75.0:
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

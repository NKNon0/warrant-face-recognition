import json
import logging
import numpy as np
import aiomysql
from app.db.mysql import get_connection
from app.db.vector_db import search_similar_faces
from .detector import cv2_imread_unicode, extract_insightface_embedding, detect_and_crop_face

logger = logging.getLogger(__name__)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """คำนวณ Cosine Similarity ระหว่าง Vector 2 ตัว"""
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


async def search_face(image_path: str) -> dict | None:
    """
    ระบบค้นหาเปรียบเทียบใบหน้าบุคคลกับฐานข้อมูลหมายจับ (Face Matcher Engine)
    Pass 1: ค้นหาผ่าน Qdrant HNSW Vector Search 512D (< 5ms)
    Pass 2: Fallback ค้นหาผ่าน MySQL Face Embeddings
    """
    try:
        image = cv2_imread_unicode(image_path)
        if image is None:
            return None

        # สกัด 512D Feature Vector
        query_embedding = extract_insightface_embedding(image)
        if query_embedding is None:
            # ลองตัดหน้าก่อนแล้วสกัดอีกรอบ
            face_crop = detect_and_crop_face(image_path)
            if face_crop is not None:
                query_embedding = extract_insightface_embedding(face_crop)

        if query_embedding is None:
            return {"type": "no_face", "message": "ไม่สามารถตรวจจับใบหน้าบุคคลในภาพได้"}

        # ----------------------------------------------------
        # Pass 1: Qdrant HNSW Vector Search (ความเร็วสูงพิเศษ)
        # ----------------------------------------------------
        vector_results = search_similar_faces(query_embedding.tolist(), limit=1, score_threshold=0.45)
        if vector_results:
            top_hit = vector_results[0]
            score_sim = top_hit["score"]
            profile_id = top_hit["id"]
            payload = top_hit.get("payload", {})

            # ปรับสเกลคะแนนความคล้ายคลึงให้อ่านเข้าใจง่าย (0.50 -> 75%, 0.70 -> 99%)
            display_score = round(min(99.95, max(60.0, (score_sim - 0.35) / 0.35 * 40.0 + 60.0)), 2)

            return {
                "type": "face",
                "id": profile_id,
                "person_name": payload.get("person_name", "-"),
                "id_number": payload.get("id_number", "-"),
                "detail": payload.get("detail", "-"),
                "station": payload.get("station", "-"),
                "court": payload.get("court", "-"),
                "photo_url": payload.get("photo_url", ""),
                "score": display_score,
                "engine": "Qdrant HNSW 512D ArcFace",
            }

        # ----------------------------------------------------
        # Pass 2: Fallback MySQL Database Sequential Search
        # ----------------------------------------------------
        async with await get_connection() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT id, person_name, id_number, detail, station, court, photo_url, face_embedding FROM face_profiles WHERE face_embedding IS NOT NULL"
                )
                profiles = await cur.fetchall()

        best_profile = None
        best_similarity = -1.0

        for p in profiles:
            raw_emb = p.get("face_embedding")
            if not raw_emb:
                continue
            try:
                if isinstance(raw_emb, str):
                    db_vec = np.array(json.loads(raw_emb), dtype=np.float32)
                elif isinstance(raw_emb, bytes):
                    db_vec = np.frombuffer(raw_emb, dtype=np.float32)
                else:
                    db_vec = np.array(raw_emb, dtype=np.float32)

                sim = cosine_similarity(query_embedding, db_vec)
                if sim > best_similarity:
                    best_similarity = sim
                    best_profile = p
            except Exception:
                continue

        if best_profile and best_similarity >= 0.45:
            display_score = round(min(99.95, max(60.0, (best_similarity - 0.35) / 0.35 * 40.0 + 60.0)), 2)
            return {
                "type": "face",
                "id": best_profile["id"],
                "person_name": best_profile.get("person_name", "-"),
                "id_number": best_profile.get("id_number", "-"),
                "detail": best_profile.get("detail", "-"),
                "station": best_profile.get("station", "-"),
                "court": best_profile.get("court", "-"),
                "photo_url": best_profile.get("photo_url", ""),
                "score": display_score,
                "engine": "MySQL ArcFace Cosine",
            }

        return None
    except Exception as e:
        logger.error(f"[Face Matcher] search_face error: {e}")
        return None

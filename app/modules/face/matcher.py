import os
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


CACHE_FILE_PATH = "data/face_embeddings_cache.npz"

_CACHE_MATRIX: np.ndarray | None = None
_CACHE_METADATA: dict | None = None


def get_face_cache():
    """โหลดและแคชเวกเตอร์ใบหน้าทั้งหมดขึ้น RAM เป็น NumPy Matrix เพื่อค้นหาในระดับ 1 มิลลิวินาที"""
    global _CACHE_MATRIX, _CACHE_METADATA
    if _CACHE_MATRIX is not None and _CACHE_METADATA is not None:
        return _CACHE_MATRIX, _CACHE_METADATA

    if os.path.exists(CACHE_FILE_PATH):
        try:
            data = np.load(CACHE_FILE_PATH, allow_pickle=True)
            _CACHE_MATRIX = data["matrix"].astype(np.float32)
            _CACHE_METADATA = {
                "names": data["names"],
                "ids": data["ids"],
                "id_numbers": data["id_numbers"] if "id_numbers" in data else np.array(["-"] * len(data["names"])),
                "details": data["details"],
                "stations": data["stations"],
                "courts": data["courts"],
                "photo_urls": data["photo_urls"],
                "warrant_urls": data["warrant_urls"] if "warrant_urls" in data else np.array([""] * len(data["names"])),
            }
            logger.info(f"[Face Cache] ✅ โหลดเวกเตอร์ใบหน้า {len(_CACHE_MATRIX)} รายการขึ้น RAM พร้อมค้นหาใน 1ms!")
            return _CACHE_MATRIX, _CACHE_METADATA
        except Exception as e:
            logger.error(f"[Face Cache] ไม่สามารถโหลด {CACHE_FILE_PATH}: {e}")

    return None, None


def rebuild_face_cache_sync(profiles: list[dict]):
    """สร้างไฟล์ data/face_embeddings_cache.npz ใหม่จากข้อมูลโปรไฟล์ในระบบ"""
    global _CACHE_MATRIX, _CACHE_METADATA
    os.makedirs("data", exist_ok=True)
    embeddings = []
    names = []
    ids = []
    id_numbers = []
    details = []
    stations = []
    courts = []
    photo_urls = []
    warrant_urls = []

    for r in profiles:
        raw_emb = r.get("face_embedding")
        if not raw_emb:
            continue
        try:
            if isinstance(raw_emb, str):
                vec = np.array(json.loads(raw_emb), dtype=np.float32)
            elif isinstance(raw_emb, bytes):
                vec = np.frombuffer(raw_emb, dtype=np.float32)
            else:
                vec = np.array(raw_emb, dtype=np.float32)

            if vec.shape == (512,):
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec_norm = vec / norm
                    embeddings.append(vec_norm)
                    names.append(str(r.get("person_name", "-")))
                    ids.append(int(r.get("id", 0)))
                    id_numbers.append(str(r.get("id_number", "-")))
                    details.append(str(r.get("detail", "-")))
                    stations.append(str(r.get("station", "-")))
                    courts.append(str(r.get("court", "-")))
                    photo_urls.append(str(r.get("photo_url", "")))
                    warrant_urls.append(str(r.get("warrant_url", "")))
        except Exception:
            continue

    if embeddings:
        _CACHE_MATRIX = np.vstack(embeddings).astype(np.float32)
        _CACHE_METADATA = {
            "names": np.array(names),
            "ids": np.array(ids),
            "id_numbers": np.array(id_numbers),
            "details": np.array(details),
            "stations": np.array(stations),
            "courts": np.array(courts),
            "photo_urls": np.array(photo_urls),
            "warrant_urls": np.array(warrant_urls),
        }
        np.savez_compressed(
            CACHE_FILE_PATH,
            matrix=_CACHE_MATRIX,
            names=_CACHE_METADATA["names"],
            ids=_CACHE_METADATA["ids"],
            id_numbers=_CACHE_METADATA["id_numbers"],
            details=_CACHE_METADATA["details"],
            stations=_CACHE_METADATA["stations"],
            courts=_CACHE_METADATA["courts"],
            photo_urls=_CACHE_METADATA["photo_urls"],
            warrant_urls=_CACHE_METADATA["warrant_urls"],
        )
        logger.info(f"[Face Cache] ✅ สร้างและบันทึกไฟล์แคชเวกเตอร์ {len(names)} รายการเรียบร้อยแล้ว!")
        return _CACHE_MATRIX, _CACHE_METADATA

    return None, None


async def search_face(image_path: str) -> dict | None:
    """
    ระบบค้นหาเปรียบเทียบใบหน้าบุคคลกับฐานข้อมูลหมายจับ (High-Performance Vectorized Face Matcher)
    Pass 1: Qdrant Vector DB HNSW (< 5ms) หากเปิดใช้งาน
    Pass 2: In-Memory NumPy Vectorized Matrix (< 1ms) ป้องกันการอ่านดิสก์ซ้ำซ้อน และกำจัดปัญหา AI เพี้ยน
    """
    try:
        image = cv2_imread_unicode(image_path)
        if image is None:
            return None

        # สกัด 512D ArcFace Feature Vector
        query_embedding = extract_insightface_embedding(image)
        if query_embedding is None:
            face_crop = detect_and_crop_face(image_path)
            if face_crop is not None:
                query_embedding = extract_insightface_embedding(face_crop)

        if query_embedding is None:
            return {"type": "no_face", "message": "ไม่สามารถตรวจจับใบหน้าบุคคลในภาพได้"}

        # Normalize query vector
        q_norm_val = np.linalg.norm(query_embedding)
        if q_norm_val == 0:
            return {"type": "no_face", "message": "เวกเตอร์ใบหน้าไม่ถูกต้อง"}
        query_norm = (query_embedding / q_norm_val).astype(np.float32)

        # ----------------------------------------------------
        # Pass 1: Qdrant HNSW Vector Search (ถ้ามี Container เปิดอยู่)
        # ----------------------------------------------------
        try:
            vector_results = search_similar_faces(query_norm.tolist(), limit=1, score_threshold=0.65)
            if vector_results:
                top_hit = vector_results[0]
                score_sim = top_hit["score"]
                profile_id = top_hit["id"]
                payload = top_hit.get("payload", {})
                display_score = round(min(99.95, max(85.0, (score_sim - 0.50) / 0.50 * 20.0 + 80.0)), 2)

                return {
                    "found": True,
                    "type": "face",
                    "id": profile_id,
                    "person_name": payload.get("person_name", "-"),
                    "id_number": payload.get("id_number", "-"),
                    "detail": payload.get("detail", "-"),
                    "station": payload.get("station", "-"),
                    "court": payload.get("court", "-"),
                    "photo_url": payload.get("photo_url", ""),
                    "warrant_url": payload.get("warrant_url", ""),
                    "score": display_score,
                    "engine": "Qdrant HNSW 512D ArcFace",
                }
        except Exception as q_ex:
            logger.debug(f"[Face Matcher] Qdrant note: {q_ex}")

        # ----------------------------------------------------
        # Pass 2: High-Speed In-Memory NumPy Vectorized Matrix (< 1ms)
        # ----------------------------------------------------
        matrix, metadata = get_face_cache()

        if matrix is None:
            # ดึงจาก MySQL ครั้งเดียวเพื่อสร้างแคช
            try:
                async with await get_connection() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute(
                            "SELECT id, person_name, id_number, detail, station, court, photo_url, warrant_url, face_embedding FROM face_profiles WHERE face_embedding IS NOT NULL"
                        )
                        rows = await cur.fetchall()
                        matrix, metadata = rebuild_face_cache_sync(rows)
            except Exception as db_err:
                logger.error(f"[Face Matcher] MySQL cache rebuild error: {db_err}")

        if matrix is not None and metadata is not None and len(matrix) > 0:
            # คำนวณ Cosine Similarity พร้อมกันทั้งตารางใน 1 คำสั่ง (< 1 มิลลิวินาที)
            sim_scores = np.dot(matrix, query_norm)
            best_idx = int(np.argmax(sim_scores))
            best_sim = float(sim_scores[best_idx])

            # เกณฑ์ความคล้ายคลึงมาตรฐาน ArcFace (Threshold >= 0.48):
            # มีความแม่นยำสูงมาก ตัดคนไม่เกี่ยว (ความคล้าย < 0.35) และจับคู่ผู้ต้องหาจริงได้อย่างแม่นยำสูง
            if best_sim >= 0.48:
                display_score = round(min(99.95, max(75.0, (best_sim - 0.40) / 0.60 * 24.95 + 75.0)), 2)
                return {
                    "found": True,
                    "type": "face",
                    "id": int(metadata["ids"][best_idx]),
                    "person_name": str(metadata["names"][best_idx]),
                    "id_number": str(metadata["id_numbers"][best_idx]) if "id_numbers" in metadata else "-",
                    "detail": str(metadata["details"][best_idx]),
                    "station": str(metadata["stations"][best_idx]),
                    "court": str(metadata["courts"][best_idx]),
                    "photo_url": str(metadata["photo_urls"][best_idx]),
                    "warrant_url": str(metadata["warrant_urls"][best_idx]) if "warrant_urls" in metadata else "",
                    "score": display_score,
                    "engine": "InsightFace ResNet50 ArcFace (Vectorized 1ms)",
                }

            # ตรวจพบใบหน้าบุคคลในภาพ แต่คะแนนไม่ถึงเกณฑ์หมายจับ (คนบริสุทธิ์)
            return {
                "found": False,
                "type": "face",
                "detected_face": True,
                "message": "ตรวจพบใบหน้าบุคคล แต่ไม่พบข้อมูลประวัติหมายจับในฐานข้อมูล"
            }

        return None
    except Exception as e:
        logger.error(f"[Face Matcher] search_face error: {e}")
        return None


import logging
from typing import List, Dict, Any, Optional
from app.config import QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION_NAME

logger = logging.getLogger(__name__)

QDRANT_AVAILABLE = False
QdrantClient = None
models = None

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    QDRANT_AVAILABLE = True
except ImportError:
    logger.warning("[Qdrant] qdrant-client library not installed, using MySQL fallback.")

qdrant_client_instance = None
_qdrant_checked = False
_qdrant_available_status = False


def get_qdrant_client():
    """เชื่อมต่อกับ Qdrant Vector Database"""
    global qdrant_client_instance, _qdrant_checked, _qdrant_available_status
    if not QDRANT_AVAILABLE or QdrantClient is None:
        return None
    if _qdrant_checked and not _qdrant_available_status:
        return None
    if qdrant_client_instance is not None:
        return qdrant_client_instance
    try:
        qdrant_client_instance = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=2.0, check_compatibility=False)
        # Test connection
        _ = qdrant_client_instance.get_collections()
        _qdrant_checked = True
        _qdrant_available_status = True
        return qdrant_client_instance
    except Exception as e:
        logger.debug(f"[Qdrant] Note: {e}")
        _qdrant_checked = True
        _qdrant_available_status = False
        qdrant_client_instance = None
        return None


def init_qdrant_collection() -> bool:
    """สร้าง Collection สำหรับ 512D ArcFace Cosine Distance ถ้ายังไม่มี"""
    client = get_qdrant_client()
    if client is None:
        return False
    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        if QDRANT_COLLECTION_NAME not in collection_names:
            client.create_collection(
                collection_name=QDRANT_COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=512,
                    distance=models.Distance.COSINE,
                    on_disk=False,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000,
                ),
            )
            print(f"[Qdrant] ✅ Created collection '{QDRANT_COLLECTION_NAME}' (512D Cosine HNSW)")
        return True
    except Exception as e:
        logger.warning(f"[Qdrant] Init collection failed: {e}")
        return False


def upsert_face_embedding(profile_id: int, embedding: List[float], payload: Dict[str, Any]) -> bool:
    """บันทึกหรืออัปเดต Face Vector Embedding 512D ลงใน Qdrant"""
    client = get_qdrant_client()
    if client is None:
        return False
    try:
        init_qdrant_collection()
        point = models.PointStruct(
            id=profile_id,
            vector=embedding,
            payload=payload,
        )
        client.upsert(collection_name=QDRANT_COLLECTION_NAME, points=[point])
        return True
    except Exception as e:
        logger.error(f"[Qdrant] Error upserting vector for profile {profile_id}: {e}")
        return False


def search_similar_faces(query_embedding: List[float], limit: int = 5, score_threshold: float = 0.50) -> List[Dict[str, Any]]:
    """ค้นหาใบหน้าบุคคลที่คล้ายคลึงที่สุดในระดับมิลลิวินาทีด้วย HNSW Index"""
    client = get_qdrant_client()
    if client is None:
        return []
    try:
        init_qdrant_collection()
        if hasattr(client, "search"):
            search_results = client.search(
                collection_name=QDRANT_COLLECTION_NAME,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )
        elif hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=QDRANT_COLLECTION_NAME,
                query=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
            )
            search_results = response.points
        else:
            search_results = []

        results = []
        for hit in search_results:
            results.append({
                "id": hit.id,
                "score": float(hit.score),
                "payload": hit.payload,
            })
        return results
    except Exception as e:
        logger.debug(f"[Qdrant] Search note: {e}")
        return []

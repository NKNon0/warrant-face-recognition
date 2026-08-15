"""
High-Performance Vector Database Module (Qdrant HNSW Indexing)
Supports sub-millisecond similarity search across millions of 512D ArcFace facial embeddings.
"""

import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

QDRANT_CLIENT = None
COLLECTION_NAME = "face_warrants"
VECTOR_SIZE = 512

def get_qdrant_client():
    """Lazy loader for Qdrant Client"""
    global QDRANT_CLIENT
    if QDRANT_CLIENT is not None:
        return QDRANT_CLIENT
    try:
        from qdrant_client import QdrantClient
        host = os.getenv("QDRANT_HOST", "qdrant")
        port = int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(host=host, port=port, timeout=5.0)
        
        # Ensure collection exists
        from qdrant_client.models import Distance, VectorParams
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        if not exists:
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info(f"[Vector DB] Initialized Qdrant collection '{COLLECTION_NAME}' (512D, Cosine)")

        QDRANT_CLIENT = client
    except Exception as e:
        logger.debug(f"[Vector DB] Qdrant not active or failed to connect: {e}")
        QDRANT_CLIENT = None
    return QDRANT_CLIENT


def upsert_face_vector(person_id: int, embedding: List[float], payload: Dict[str, Any]) -> bool:
    """Insert or update a 512D ArcFace facial embedding in Qdrant Vector DB"""
    client = get_qdrant_client()
    if client is None:
        return False
    try:
        from qdrant_client.models import PointStruct
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(id=person_id, vector=embedding, payload=payload)
            ]
        )
        return True
    except Exception as e:
        logger.error(f"[Vector DB] Error upserting vector for person {person_id}: {e}")
        return False


def search_face_vector(query_embedding: List[float], score_threshold: float = 0.70, limit: int = 1) -> Optional[Dict[str, Any]]:
    """Search for the most similar facial vector in Qdrant sub-millisecond HNSW index"""
    client = get_qdrant_client()
    if client is None:
        return None
    try:
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold
        )
        if results and len(results) > 0:
            top = results[0]
            score_pct = round(top.score * 100.0, 2)
            payload = top.payload or {}
            return {
                "id": top.id,
                "score": score_pct,
                "person_name": payload.get("person_name", "Unknown"),
                "id_number": payload.get("id_number", "-"),
                "detail": payload.get("detail", "-"),
                "station": payload.get("station", "-"),
                "court": payload.get("court", "-"),
                "photo_url": payload.get("photo_url", "-"),
                "engine": "qdrant_hnsw_vector"
            }
    except Exception as e:
        logger.error(f"[Vector DB] Search error: {e}")
    return None

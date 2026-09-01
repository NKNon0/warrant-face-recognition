import logging
import aiomysql
from app.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

logger = logging.getLogger(__name__)

pool = None
_mysql_checked = False
_mysql_available_status = False


async def init_db():
    """สร้าง MySQL Connection Pool (ขยายขนาดเป็น 20 ช่อง ป้องกันการค้าง)"""
    global pool, _mysql_checked, _mysql_available_status
    if pool is not None:
        return pool
    try:
        pool = await aiomysql.create_pool(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            db=MYSQL_DB,
            autocommit=True,
            minsize=1,
            maxsize=20,
            connect_timeout=3,
        )
        _mysql_checked = True
        _mysql_available_status = True
        return pool
    except Exception as e:
        logger.debug(f"[MySQL] Connection Note: {e}")
        _mysql_checked = True
        _mysql_available_status = False
        pool = None
        return None


async def get_connection():
    """ดึง Connection จาก Pool"""
    global pool
    if pool is None:
        await init_db()
    if pool is None:
        raise ConnectionError(f"Cannot connect to MySQL server at {MYSQL_HOST}:{MYSQL_PORT}")
    return pool.acquire()

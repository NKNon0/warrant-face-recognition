import aiomysql
from app.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

pool = None


async def init_db():
    """สร้าง MySQL Connection Pool (ขยายขนาดเป็น 20 ช่อง ป้องกันการค้าง)"""
    global pool
    if pool is not None:
        return pool
    pool = await aiomysql.create_pool(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        autocommit=True,
        minsize=2,
        maxsize=20,
        connect_timeout=10,
    )
    return pool


async def get_connection():
    """ดึง Connection จาก Pool"""
    if pool is None:
        await init_db()
    return pool.acquire()

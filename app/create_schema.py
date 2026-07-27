import asyncio
import os
from dotenv import load_dotenv
import aiomysql

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "Face_Ai")

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")

async def create_schema():
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = await aiomysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        autocommit=True,
    )

    try:
        async with conn.cursor() as cur:
            for statement in schema_sql.split(";"):
                sql = statement.strip()
                if not sql:
                    continue
                await cur.execute(sql)
            print("Schema created successfully.")
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(create_schema())

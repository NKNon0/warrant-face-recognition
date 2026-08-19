# Re-export for backward compatibility
from app.db.mysql import init_db, get_connection, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, pool

__all__ = ["init_db", "get_connection", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DB", "pool"]

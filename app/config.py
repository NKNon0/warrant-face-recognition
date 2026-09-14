import os
import socket
from pathlib import Path
from dotenv import load_dotenv

# ป้องกัน Docker IPv6 Blackhole Timeout: บังคับใช้ IPv4 เท่านั้นสำหรับการเชื่อมต่อเครือข่ายทั้งหมด
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _ipv4_getaddrinfo

os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "False"
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database Settings
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "Face_Ai")

# Qdrant Vector Database
QDRANT_HOST = os.getenv("QDRANT_HOST", "127.0.0.1")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION_NAME = "face_warrants"

# Telegram Bot Settings
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# External API Keys (Optional)
IAPP_API_KEY = os.getenv("IAPP_API_KEY", "").strip()

# AI Models Directories & Settings
MODELS_DIR = os.getenv("MODELS_DIR", str(BASE_DIR / "models"))
TEMP_DIR = str(BASE_DIR / "temp")
UPLOADS_DIR = str(BASE_DIR / "uploads")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

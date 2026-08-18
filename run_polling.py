import asyncio
import aiohttp
import os
import sys
import io
from pathlib import Path
from dotenv import load_dotenv

# Force stdout to UTF-8 to handle Thai characters in logs with immediate flushing
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

load_dotenv()

from app.telegram_bot import handle_telegram_update
from app.db import init_db

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

async def main():
    # Initialize DB connection pool
    await init_db()

    print("[AI Warmup] Preloading InsightFace, YOLOv8, and PaddleOCR models into memory...")
    try:
        from app.ai_processor import get_insightface_app, get_yolo_plate_model, get_paddleocr_engine
        await asyncio.to_thread(get_insightface_app)
        await asyncio.to_thread(get_yolo_plate_model)
        await asyncio.to_thread(get_paddleocr_engine)
        print("[AI Warmup] ✅ All AI models warm in memory (Zero latency)!")
    except Exception as e:
        print(f"[AI Warmup Note]: {e}")
    
    print("\n" + "="*50)
    print(" 🤖 Telegram Bot Polling Mode Started... (กำลังทำงาน)")
    print(" บอทจะคอยดึงข้อความจาก Telegram มาประมวลผลทันที")
    print(" (ไม่จำเป็นต้องใช้ ngrok หรือตั้งค่า Webhook URL)")
    print("="*50 + "\n")
    
    async with aiohttp.ClientSession() as session:
        # Delete webhook first (otherwise getUpdates will fail)
        print("[INFO] ลบการตั้งค่า Webhook เก่าเพื่อให้ใช้ Polling ได้...")
        async with session.get(f"{TELEGRAM_API}/deleteWebhook") as resp:
            data = await resp.json()
            print(f"[INFO] ลบ Webhook: {data.get('description', 'สำเร็จ')}")
            
        offset = 0
        while True:
            try:
                # Long Polling (timeout 10 วินาที เพื่อไม่ให้ค้างนานเกินไป)
                url = f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=10"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        if res.get("ok"):
                            for update in res.get("result", []):
                                offset = update["update_id"] + 1
                                print(f"[RECEIVED] ได้รับข้อความใหม่! Update ID: {update.get('update_id')}")
                                
                                # Wrapper เพื่อดักจับและแสดงผล Error ของแต่ละข้อความ
                                async def run_and_log(upd):
                                    try:
                                        await handle_telegram_update(upd)
                                        print(f"[SUCCESS] ประมวลผล Update ID: {upd.get('update_id')} เสร็จสิ้น")
                                    except Exception as ex:
                                        print(f"[ERROR] ประมวลผล Update ID: {upd.get('update_id')} ล้มเหลว: {ex}")
                                
                                asyncio.create_task(run_and_log(update))
            except Exception as e:
                print(f"[ERROR] เกิดข้อผิดพลาดใน Polling loop: {e}")
            
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 ปิดการทำงาน Polling Mode.")

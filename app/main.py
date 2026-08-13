import asyncio
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.telegram_bot import handle_telegram_update, set_telegram_menu_button, set_telegram_webhook
from app.db import init_db
from app.api import router as api_router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Telegram AI Search Service")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(api_router)

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(STATIC_DIR / "index.html")

async def auto_train_datasets_on_startup():
    """
    เทรนและซิงค์ข้อมูล AI อัตโนมัติทุกครั้งเมื่อเซิร์ฟเวอร์เปิดใช้งาน
    (Auto-Train & Ingest All 3 Datasets on Server Startup)
    """
    try:
        from import_license_plates import run_import as import_plates
        from import_thai_id_ocr import import_all_thai_id_ocr
        from scratch.master_train_all_ai import master_train

        print("[Auto-Train] Starting background AI dataset training & vector sync...")
        await master_train()
        print("[Auto-Train] ✅ All 3 AI Engines trained & synced automatically on startup!")
    except Exception as e:
        print(f"[Auto-Train] Note: {e}")

@app.on_event("startup")
async def startup_event():
    await init_db()
    await set_telegram_menu_button()
    await set_telegram_webhook()
    # เรียกทำงาน Auto-Train AI อัตโนมัติทุกครั้งที่เปิดเซิร์ฟเวอร์
    asyncio.create_task(auto_train_datasets_on_startup())

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(handle_telegram_update, payload)
    return {"ok": True}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

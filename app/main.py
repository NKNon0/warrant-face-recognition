import asyncio
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.telegram_bot import handle_telegram_update
from app.db import init_db
from app.api import router as api_router

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Telegram AI Search Service")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(api_router)

@app.get("/", include_in_schema=False)
async def root():
    return {"status": "online", "service": "Warrant AI Recognition Direct Bot"}

async def auto_train_datasets_on_startup():
    """
    โหลดโมเดล AI ทั้งหมดให้อุ่นในหน่วยความจำทันที และซิงค์ฐานข้อมูล
    """
    try:
        from app.ai_processor import get_insightface_app, get_yolo_plate_model, get_paddleocr_engine
        print("[AI Warmup] Preloading InsightFace, YOLOv8, and PaddleOCR into memory...")
        await asyncio.to_thread(get_insightface_app)
        await asyncio.to_thread(get_yolo_plate_model)
        await asyncio.to_thread(get_paddleocr_engine)
        print("[AI Warmup] ✅ All AI Models warmed up in memory (Zero cold-start delay)!")

        from scratch.master_train_all_ai import master_train
        print("[Auto-Train] Starting background AI dataset training & vector sync...")
        await master_train()
        print("[Auto-Train] ✅ All 3 AI Engines trained & synced automatically on startup!")
    except Exception as e:
        print(f"[Auto-Train/Warmup] Note: {e}")

@app.on_event("startup")
async def startup_event():
    await init_db()
    asyncio.create_task(auto_train_datasets_on_startup())

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(handle_telegram_update, payload)
    return {"ok": True}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

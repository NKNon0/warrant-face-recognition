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

@app.on_event("startup")
async def startup_event():
    await init_db()
    await set_telegram_menu_button()
    await set_telegram_webhook()

@app.post("/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(handle_telegram_update, payload)
    return {"ok": True}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

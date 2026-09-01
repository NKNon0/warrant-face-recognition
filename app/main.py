import asyncio
import aiohttp
from fastapi import FastAPI, Request, BackgroundTasks
from app.config import TELEGRAM_TOKEN, TELEGRAM_API
from app.bot import handle_telegram_update, remove_telegram_menu_button
from app.db import init_db
from app.api import router as api_router
from app.modules.face import get_insightface_app
from app.modules.license_plate import get_yolo_plate_model, get_paddleocr_engine

app = FastAPI(title="Warrant AI Recognition Direct Bot Service")
app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root():
    return {"status": "online", "service": "Warrant AI Recognition Direct Bot (Modular Architecture)"}


async def auto_train_datasets_on_startup():
    """
    โหลดโมเดล AI ทั้งหมดให้อุ่นในหน่วยความจำทันที (Zero Latency) และซิงค์ฐานข้อมูล
    """
    try:
        print("[AI Warmup] Preloading InsightFace, YOLOv8, and PaddleOCR into memory...")
        await asyncio.to_thread(get_insightface_app)
        await asyncio.to_thread(get_yolo_plate_model)
        await asyncio.to_thread(get_paddleocr_engine)
        print("[AI Warmup] ✅ All AI Models warmed up in memory (Zero cold-start delay)!")

        try:
            from scratch.master_train_all_ai import master_train
            print("[Auto-Train] Starting background AI dataset training & vector sync...")
            await master_train()
            print("[Auto-Train] ✅ All 3 AI Engines trained & synced automatically on startup!")
        except Exception as ex:
            print(f"[Auto-Train] Note: {ex}")
    except Exception as e:
        print(f"[AI Warmup Note]: {e}")


async def start_telegram_polling():
    """
    Background worker สำหรับดึงข้อความ Long Polling จาก Telegram Bot อัตโนมัติ (Direct Chat)
    """
    if not TELEGRAM_TOKEN:
        print("[Telegram Polling] ⚠️ TELEGRAM_TOKEN is not set. Polling worker skipped.")
        return

    try:
        await remove_telegram_menu_button()
    except Exception as e:
        print(f"[Telegram Menu Note]: {e}")

    print("\n" + "="*55)
    print(" 🤖 Telegram Bot Background Polling Worker Started!")
    print(" พร้อมรับรูปภาพและข้อความจากแชทบอทโดยตรง (Direct Chat)")
    print("="*55 + "\n")

    async with aiohttp.ClientSession() as session:
        # ล้าง Webhook เก่าออกเพื่อให้ Polling ทำงานได้
        try:
            async with session.get(f"{TELEGRAM_API}/deleteWebhook") as resp:
                data = await resp.json()
                print(f"[Telegram Polling] Webhook status: {data.get('description', 'OK')}")
        except Exception as e:
            print(f"[Telegram Polling] deleteWebhook note: {e}")

        offset = 0
        while True:
            try:
                url = f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=10"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        res = await resp.json()
                        if res.get("ok"):
                            for update in res.get("result", []):
                                offset = update["update_id"] + 1
                                print(f"[Telegram Polling] 📩 Received Update ID: {update.get('update_id')}")

                                async def run_and_log(upd):
                                    try:
                                        await handle_telegram_update(upd)
                                        print(f"[Telegram Polling] ✅ Processed Update ID: {upd.get('update_id')}")
                                    except Exception as ex:
                                        print(f"[Telegram Polling] ❌ Error in Update ID {upd.get('update_id')}: {ex}")

                                asyncio.create_task(run_and_log(update))
            except Exception as e:
                await asyncio.sleep(2)
            await asyncio.sleep(0.5)


@app.on_event("startup")
async def startup_event():
    await init_db()
    asyncio.create_task(auto_train_datasets_on_startup())
    asyncio.create_task(start_telegram_polling())


@app.post("/telegram-webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(handle_telegram_update, payload)
    return {"ok": True}


@app.get("/health")
async def health_check():
    return {"status": "ok"}

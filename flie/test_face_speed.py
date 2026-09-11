import asyncio
import time
import os
from app.core.router import process_media

async def main():
    test_cases = [
        ("Suspect 1 (อรอุมา)", r"datatest/FACE/น.ส.อรอุมา ขุนไชย/สกรีนช็อต 2026-07-21 142628.png"),
        ("Suspect 2 (สุภัสสร)", r"datatest/FACE/นางสาวสุภัสสร ชุมภูทอง/สกรีนช็อต 2026-07-21 143231.png"),
        ("Suspect 3 (มูฮำหมัด)", r"datatest/FACE/นาย มูฮำหมัดซัยดีนาอาลี อิ/สกรีนช็อต 2026-07-21 142205.png"),
    ]

    for label, path in test_cases:
        if not os.path.exists(path):
            print(f"Skipping {label}: path not found")
            continue
        with open(path, "rb") as f:
            img_bytes = f.read()

        t0 = time.perf_counter()
        res = await process_media(request_id=None, image_bytes=img_bytes, mode="auto")
        dt = time.perf_counter() - t0

        print(f"=== {label} ===")
        print(f"Time: {dt:.3f}s")
        print(f"Found: {res.get('found')}")
        print(f"Predicted type: {res.get('predicted_type')}")
        for r in res.get("results", []):
            print(f"  Person: {r.get('person_name')}")
            print(f"  Score: {r.get('score')}%")
            print(f"  Photo exists: {os.path.exists(r.get('photo_url', ''))} ({r.get('photo_url')})")
            print(f"  Warrant exists: {os.path.exists(r.get('warrant_url', ''))} ({r.get('warrant_url')})")
        print()

if __name__ == "__main__":
    asyncio.run(main())

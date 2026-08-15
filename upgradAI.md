# 🚀 AI Upgrade & System Architecture Evolution Guide (upgradAI.md)

คู่มือการอัปเกรดระบบ AI, Backend, Frontend และการประมวลผลเชิงลึกแบบทีละขั้นตอน (Step-by-Step Execution Guide) สำหรับระบบตรวจจับใบหน้าบุคคลเป้าหมาย, ป้ายทะเบียนรถเฝ้าระวัง, และบัตรประชาชนหมายจับ

---

## 📑 สารบัญ (Table of Contents)

1. [ภาพรวมสถาปัตยกรรมและสถานะปัจจุบัน (Current Baseline)](#1-ภาพรวมสถาปัตยกรรมและสถานะปัจจุบัน)
2. [เฟสที่ 1: การอัปเกรด Computer Vision & Dual OCR Engine (เสร็จสมบูรณ์)](#2-เฟสที่-1-การอัปเกรด-computer-vision--dual-ocr-engine)
3. [เฟสที่ 2: การอัปเกรดฐานข้อมูลเวกเตอร์ระดับ 10 ล้านข้อมูล (Milvus / Qdrant)](#3-เฟสที่-2-การอัปเกรดฐานข้อมูลเวกเตอร์)
4. [เฟสที่ 3: การอัปเกรด Frontend ด้วย Edge AI & กล้องจัดตำแหน่งอัตโนมัติ](#4-เฟสที่-3-การอัปเกรด-frontend-ด้วย-edge-ai)
5. [เฟสที่ 4: การอัปเกรดสู่ Multimodal Vision-Language AI (Qwen2-VL) & CCTV สตรีมสด](#5-เฟสที่-4-การอัปเกรดสู่-multimodal-vlm--cctv)
6. [คำสั่งและขั้นตอนการทดสอบระบบ (Verification & Testing Guide)](#6-คำสั่งและขั้นตอนการทดสอบระบบ)

---

## 1. ภาพรวมสถาปัตยกรรมและสถานะปัจจุบัน

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CURRENT 3-TIER PRODUCTION STACK                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ 👤 Face Engine    : InsightFace ArcFace (512D Vector) + Cosine Similarity   │
│ 🚗 Plate Engine   : YOLOv8 + OpenCV Deskew/TopHat + PaddleOCR Thai Neural  │
│ 🪪 ID Card Engine : Top-Right ROI Crop + Faded Text Filter + Name Detection │
│ 🛢️ Database Engine: MySQL 8.0 Async Pool (face_profiles, plates, warrants)   │
│ 🌐 Mobile Frontend: Telegram Mini App (Glassmorphism Dark Mode)             │
│ 🔒 Tunnel Security: Cloudflare Quick Tunnel (HTTPS Webhook)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. เฟสที่ 1: การอัปเกรด Computer Vision & Dual OCR Engine (เสร็จสมบูรณ์)

### 2.1 ปัญหาในโลกความเป็นจริงและแนวทางแก้ไข (Real-World Image Challenges)

| ปัญหาภาพถ่ายจริง | อัลกอริทึมที่นำมาใช้แก้ไข | ผลลัพธ์ที่ได้ |
| :--- | :--- | :--- |
| **ภาพเบลอ / ไม่โฟกัส** | **Laplacian Unsharp Masking** | เพิ่มความต่างขอบอักษรและจุดสำคัญบนใบหน้า |
| **ตัวหนังสือสีซีด / บัตรเก่า** | **Morphological Top-Hat & Black-Hat Filter** | ดึงความเข้มของเส้นอักษรที่จางให้กลับมาดำชัดเจน |
| **ป้ายทะเบียน / บัตรเอียง** | **4-Point Homography Perspective Transform** | ดัดภาพที่ถ่ายมุมเฉียงให้กลับมาเป็นระนาบตรง 100% |
| **กรอบการ์ตูน / โดเรม่อนบัง** | **Inner Text ROI Crop (ตัดขอบ 88%)** | กำจัดสิ่งบดบังลายการ์ตูนขอบป้ายทะเบียน |
| **เลขบัตรโดนนิ้วมือบัง** | **Thai Name/Surname Detection + Fuzzy Match** | ค้นหาด้วยชื่อ-นามสกุลทดแทนเลขบัตรที่เสียหาย |

### 2.2 โค้ดตัวอย่างการใช้งานใน `app/ai_processor.py`:
* **การขับเน้นตัวหนังสือซีดจาง:** `enhance_id_card_contrast(img)`
* **การตรวจจับชื่อ-นามสกุล:** `extract_thai_name_from_card(text)`
* **การค้นหาเชิงลึกจากชื่อ:** `find_id_card_by_name(name_query)`
* **เอนจินคู่ OCR:** รัน **PaddleOCR (`lang='th'`)** เป็น Pass หลัก และ **PyTesseract** เป็น Pass สำรอง

---

## 3. เฟสที่ 2: การอัปเกรดฐานข้อมูลเวกเตอร์ระดับ 10 ล้านข้อมูล (Milvus / Qdrant)

### 🎯 เป้าหมาย:
เปลี่ยนจากการวนลูปคำนวณ `Cosine Similarity` บน MySQL มาใช้ **Dedicated Vector Database (Qdrant / Milvus)** ซึ่งใช้ดัชนีเวกเตอร์แบบ **HNSW (Hierarchical Navigable Small World)** รองรับการค้นหาใบหน้าระดับ **10,000,000+ หมายจับ ในเวลาเพียง 3–5 มิลลิวินาที**

### 🛠️ ขั้นตอนการติดตั้งและใช้งาน:

#### Step 1: เพิ่ม Qdrant ลงใน `docker-compose.yml`
```yaml
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant-ai
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_storage:/qdrant/storage
    restart: always
```

#### Step 2: สร้างคอลเลกชันเวกเตอร์ 512 มิติ (`app/vector_db.py`)
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

client = QdrantClient(host="qdrant", port=6333)

# สร้าง Collection ขนาด 512 มิติ (ArcFace Vector Size)
client.recreate_collection(
    collection_name="face_warrants",
    vectors_config=VectorParams(size=512, distance=Distance.COSINE),
)

def insert_face_vector(person_id: int, embedding: list, payload: dict):
    client.upsert(
        collection_name="face_warrants",
        points=[
            PointStruct(id=person_id, vector=embedding, payload=payload)
        ]
    )

def search_face_vector(query_embedding: list, limit: int = 1):
    results = client.search(
        collection_name="face_warrants",
        query_vector=query_embedding,
        limit=limit,
        score_threshold=0.70
    )
    return results
```

---

## 4. เฟสที่ 3: การอัปเกรด Frontend ด้วย Edge AI & กล้องจัดตำแหน่งอัตโนมัติ

### 🎯 เป้าหมาย:
ติดตั้ง **Google MediaPipe Face Mesh** หรือ **TensorFlow.js** บนหน้าจอ **Telegram Mini App** เพื่อช่วยจัดตำแหน่งใบหน้าและแผ่นป้ายทะเบียนก่อนกดถ่ายภาพ ลดปัญหาภาพสั่นและภาพเอียงตั้งแต่ต้นทาง

### 🛠️ ขั้นตอนการพัฒนาบน `app/static/index.html`:

```html
<!-- นำเข้า MediaPipe ผ่าน CDN -->
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/face_mesh.js"></script>

<script>
// ตรวจจับตำแหน่งใบหน้าบนกล้องแบบ Real-time
const faceMesh = new FaceMesh({locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`});
faceMesh.setOptions({maxNumFaces: 1, refineLandmarks: true, minDetectionConfidence: 0.7});

faceMesh.onResults((results) => {
    if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
        // วาดกรอบไกด์สีเขียว
        drawGuideBox("green", "✅ ใบหน้าอยู่ในตำแหน่งที่เหมาะสม");
        // สั่งถ่ายภาพอัตโนมัติเมื่อใบหน้านิ่งเกิน 1.5 วินาที
        triggerAutoCapture();
    } else {
        drawGuideBox("red", "⚠️ กรุณาขยับใบหน้าให้อยู่ในกรอบ");
    }
});
</script>
```

---

## 5. เฟสที่ 4: การอัปเกรดสู่ Multimodal Vision-Language AI (Qwen2-VL) & CCTV สตรีมสด

### 🎯 เป้าหมาย:
1. ใช้งานโมเดล **Qwen2-VL-7B-Instruct (Vision-Language Multimodal)** สำหรับอ่านบัตรประชาชนและป้ายทะเบียนที่ชำรุดรุนแรงแบบ Zero-Shot JSON Extraction
2. รองรับการเชื่อมต่อสตรีมกล้องสายตรวจ **RTSP / WebRTC Video Stream**

### 🛠️ สถาปัตยกรรม CCTV Real-time Processing:

```text
[ กล้อง CCTV / RTSP Stream (25 FPS) ]
                 │
                 ▼
[ Video Frame Sampler (ดึง 3-5 FPS) ]
                 │
                 ▼
[ YOLO11 Fast Bounding Box Detector (GPU) ]
                 │
                 ▼
[ InsightFace & PaddleOCR Batch Processing ]
                 │
                 ▼
[ Qdrant Vector Match (< 5ms) ]
                 │
                 ▼
[ Telegram Bot Push Notification เมื่อพบคนร้ายทันที! ]
```

---

## 6. คำสั่งและขั้นตอนการทดสอบระบบ (Verification & Testing Guide)

### 6.1 คำสั่งเปิดใช้งานระบบทั้งหมด:
```cmd
# 1. เปิดคอนเทนเนอร์เซิร์ฟเวอร์
docker compose up -d

# 2. เปิดอุโมงค์ Cloudflare Tunnel
cloudflared.exe tunnel --url http://127.0.0.1:8000

# 3. ลงทะเบียน Webhook และ Menu Button
docker compose exec web python scratch/register_telegram.py

# 4. สั่งเทรนและซิงค์ชุดข้อมูลทั้งหมดเข้า MySQL
docker compose exec web python scratch/master_train_all_ai.py
```

### 6.2 คำสั่งรันชุดทดสอบระบบ AI ทุกโหมด (Automated Test Suite):
```cmd
# รันการทดสอบระบบสแกนบัตรประชาชน Deep Search & Name Detection
docker compose exec web python scratch/test_deep_idcard_search.py

# รันการทดสอบระบบรวมทั้ง 3 โหมด (ใบหน้า, ป้ายทะเบียน, บัตรประชาชน)
docker compose exec web python scratch/verify_system_all_modes.py
```

---

*เอกสารฉบับนี้อัปเดตล่าสุดสำหรับการพัฒนาและอัปเกรดระบบ Warrant & AI Recognition System อย่างต่อเนื่องครับ* 🟢🚀

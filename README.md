# 👮‍♂️ Warrant & AI Recognition Direct Bot 🤖
> **ระบบ AI ตรวจสอบประวัติอาชญากรรมและหมายจับอัตโนมัติ (Multi-Modal Auto-Classification)**  
> ผสานขุมพลัง **InsightFace (ResNet50 ArcFace 512D)**, **Qdrant Vector Database**, **Fast-ALPR YOLOv8**, **PaddleOCR**, และ **Thai ID Card Modulo 11 Checksum** ใช้งานผ่าน Telegram Chat โดยตรง

---

## 🌟 จุดเด่นของระบบ (Core Features)

1. **🧠 Auto Multi-Modal AI Classifier (< 100ms):**
   * วิเคราะห์และจำแนกประเภทของภาพถ่ายที่ส่งเข้ามาโดยอัตโนมัติ ไม่ต้องกดเลือกโหมด:
     * 👤 **ใบหน้าบุคคล (Face):** ตรวจสอบเปรียบเทียบใบหน้าผู้ต้องหาตามหมายจับ
     * 🚗 **ป้ายทะเบียนรถ (License Plate):** ตรวจสอบรถเฝ้าระวัง / รถชนแล้วหนี / รถผิดกฎหมาย
     * 🪪 **บัตรประชาชน (Thai ID Card):** ตรวจสอบเลขประจำตัว 13 หลัก และชื่อผู้ต้องหา
2. **👤 Face Recognition Engine (ArcFace 512D + Qdrant HNSW):**
   * สกัด Deep Feature Vectors 512 มิติ และค้นหาผ่าน **Qdrant Vector Database** ดัชนี HNSW ในระดับ **< 5 มิลลิวินาที** (พร้อมระบบ MySQL Cosine Fallback)
3. **🚗 License Plate Engine (Fast-ALPR YOLOv8 + PaddleOCR Fast Mode):**
   * เจาะครอปเฉพาะกรอบป้ายทะเบียนด้วย **YOLOv8** ตัดขอบกรอบลายการ์ตูนออก 
   * อ่านข้อความภาษาไทยด้วย **PaddleOCR (`cls=False`)** ตอบสนองรวดเร็วทันใจ **< 1.0 วินาที**
4. **🪪 Thai ID Card Deep Search (Faded Text Enhancer + Modulo 11):**
   * กู้คืนตัวอักษรและตัวเลขที่ซีดจางด้วย **Morphological Top-Hat Filter + CLAHE**
   * ตรวจสอบความถูกต้องของเลข 13 หลักด้วยอัลกอริทึม **Modulo 11 Checksum**
5. **🤖 Pure Direct Chat Telegram Bot:**
   * ส่งรูปภาพเข้าแชทบอท **`@Nontdanu_bot`** ได้โดยตรง ไม่ต้องผ่านหน้าเว็บหรือ MiniApp ที่โหลดช้า

---

## 🏗️ โครงสร้างสถาปัตยกรรม (Domain-Driven Modular Architecture)

```
projectnew/
├── app/
│   ├── config.py                   # ⚙️ รวมการตั้งค่าระบบ (Database, Tokens, Paths)
│   ├── main.py                     # 🚀 จุดเริ่มต้น FastAPI Server, Lifespan & Startup Warmup
│   │
│   ├── core/                       # 🧠 แกนกลางระบบ AI (Core Classifier & Router)
│   │   ├── classifier.py           # ระบบวิเคราะห์และจำแนกประเภทภาพอัตโนมัติ (< 100ms)
│   │   └── router.py               # Smart-Ordered Pipeline จัดคิวส่งภาพเข้า AI แต่ละตัว
│   │
│   ├── modules/                    # 📦 โมดูล AI แต่ละด้าน (แยกอิสระ 100%)
│   │   ├── face/                   # 1. 👤 ระบบตรวจจับและค้นหาใบหน้าบุคคล (Face Engine)
│   │   │   ├── detector.py         # InsightFace ResNet50 (ArcFace 512D Embeddings)
│   │   │   └── matcher.py          # ค้นหาด้วย Qdrant HNSW Vector Search + Cosine
│   │   │
│   │   ├── license_plate/          # 2. 🚗 ระบบตรวจจับและอ่านป้ายทะเบียนรถ (License Plate)
│   │   │   ├── detector.py         # YOLOv8 Fast-ALPR Box & ROI Detection
│   │   │   ├── ocr_engine.py       # PaddleOCR (cls=False) + Fast PyTesseract
│   │   │   ├── preprocessor.py     # ดัดภาพเอียง (Deskewing) + Laplacian Unsharp
│   │   │   └── matcher.py          # ค้นหา Fuzzy String Matching ในฐานข้อมูล
│   │   │
│   │   └── id_card/                # 3. 🪪 ระบบตรวจจับและอ่านบัตรประชาชน (Thai ID Card)
│   │       ├── enhancer.py         # ขับเน้นตัวหนังสือซีดจาง (Morphological Top-Hat + CLAHE)
│   │       ├── parser.py           # สกัดเลข 13 หลักพร้อม Modulo 11 Checksum + ชื่อ-สกุล
│   │       └── matcher.py          # ค้นหาฐานข้อมูลหมายจับตามเลขบัตรประชาชน
│   │
│   ├── db/                         # 🛢️ การจัดการฐานข้อมูล (Database Layer)
│   │   ├── mysql.py                # จัดการ MySQL Connection Pool (20 ช่อง)
│   │   └── vector_db.py            # จัดการ Qdrant HNSW Vector Search Client
│   │
│   ├── bot/                        # 🤖 การทำงานของ Telegram Bot (Direct Chat Layer)
│   │   ├── bot_service.py          # รับข้อความ, ดาวน์โหลดรูป, ตรวจสอบสิทธิ์
│   │   └── formatter.py            # จัดรูปแบบข้อความรายงานผล HTML สวยงาม
│   │
│   └── api/                        # 🌐 REST API Layer
│       └── routes.py               # เส้นทาง API (/api/scan, /api/status)
│
├── run_polling.py                  # 🔄 สคริปต์รัน Telegram Polling Mode แบบ Standalone
├── docker-compose.yml              # 🐳 คอนฟิกบริการ Docker ทั้งหมด
└── requirements.txt                # 📦 รายการ Dependency ทั้งหมด
```

---

## 🚀 การติดตั้งและเริ่มต้นใช้งาน (Getting Started)

### 1. โคลนโปรเจกต์และเตรียม Environment:
```bash
git clone https://github.com/NKNon0/warrant-face-recognition.git
cd warrant-face-recognition
cp .env.example .env
```
*(แก้ไขค่า `TELEGRAM_TOKEN` และ `ADMIN_TELEGRAM_ID` ในไฟล์ `.env`)*

### 2. เปิดใช้งานผ่าน Docker Compose:
```bash
docker compose up -d
```
ระบบจะเปิดบริการทั้งหมดขึ้นมาโดยอัตโนมัติ:
* **`projectnew-web-1` (FastAPI + AI Engine):** พอร์ต `8000`
* **`mysql-ai` (MySQL 8.0 Database):** พอร์ต `3306`
* **`qdrant-ai` (Qdrant Vector Database):** พอร์ต `6333`
* **`phpmyadmin-ai` (Database UI):** พอร์ต `8080`

### 3. รัน Telegram Bot Polling Mode:
```bash
docker compose exec -d web python run_polling.py
```

---

## 📊 ตารางฐานข้อมูล (Database Architecture)

1. **`face_profiles`**: ข้อมูลประวัติหมายจับบุคคลและ Face Embedding Vector (512D ArcFace)
2. **`license_plates`**: ข้อมูลป้ายทะเบียนรถเฝ้าระวัง, จังหวัด, หมวดหมู่ข้อหา, สถานีตำรวจ
3. **`warrants`**: ข้อมูลหมายจับตามเลขบัตรประชาชน 13 หลัก, ชื่อ-นามสกุล, ข้อหา, ศาลที่ออกหมายจับ
4. **`users`**: ข้อมูลผู้ใช้งาน Telegram และสิทธิ์การเข้าใช้งานระบบ (`admin` / `police`)
5. **`media_requests` & `search_results`**: บันทึกประวัติการส่งรูปภาพและผลการตรวจสอบย้อนหลัง

---

## 🌐 รายการ REST API Endpoints

* `POST /api/scan` ➔ อัปโหลดรูปภาพเพื่อตรวจจับและค้นหาข้อมูลอัตโนมัติ (รับไฟล์ `file` และ `mode="auto"`)
* `GET /api/status` ➔ ตรวจสอบสถานะระบบและจำนวนข้อมูลในฐานข้อมูล
* `GET /health` ➔ ตรวจสอบความพร้อมการทำงานของเซิร์ฟเวอร์ (Health Check)
* `POST /telegram-webhook` ➔ รองรับ Webhook จาก Telegram API

---

## 🛡️ มาตรการความปลอดภัยและคุ้มครองข้อมูล (PDPA)
* โฟลเดอร์และไฟล์ภาพถ่ายทดสอบจริง (`datatest/`) ได้รับการยกเว้นใน `.gitignore` ไม่มีการอัปโหลดข้อมูลส่วนบุคคลขึ้นสู่ Public Repository
* ระบบมีกลไกตรวจสอบสิทธิ์ผู้ใช้งาน (Authorization System) โดยแอดมินสามารถอนุมัติหรือปฏิเสธคำขอได้ทันทีผ่านแชท Telegram

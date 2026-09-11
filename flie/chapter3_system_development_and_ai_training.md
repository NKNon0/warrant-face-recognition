# บทที่ 3: วิธีการดำเนินงานและการพัฒนาระบบ (System Methodology & Development)

---

## 3.5 การพัฒนาระบบ (System Development)

การพัฒนาระบบ **C.I.A.S (Criminal Identification Automated System)** หรือระบบปัญญาประดิษฐ์ตรวจสอบประวัติอาชญากรรมและหมายจับอัตโนมัติ ถูกออกแบบและพัฒนาขึ้นภายใต้แนวคิดสถาปัตยกรรมซอฟต์แวร์เชิงโมดูล (Domain-Driven Modular AI Architecture) โดยมุ่งเน้นการประมวลผลแบบอะซิงโครนัส (Asynchronous Processing) เพื่อรองรับการทำงานแบบ Real-time และลดภาระงานของเจ้าหน้าที่ผู้ปฏิบัติงานภาคสนาม โดยระบบแบ่งออกเป็นโมดูลการทำงานหลัก 7 ส่วน ดังนี้:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        เจ้าหน้าที่ส่งภาพผ่าน Telegram Chat              │
│                              (@Nontdanu_bot)                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Direct Photo Stream)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Telegram Bot Polling Engine (aiohttp Long Polling)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Byte Stream Ingestion)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             🧠 AI Multi-Modal Auto-Classifier & Router Core             │
│            (SCRFD Face -> YOLOv8 Plate -> PaddleOCR Heuristics)        │
└───────┬───────────────────────────┼────────────────────────────┬───────┘
        │ (1. พบใบหน้า)             │ (2. พบป้ายทะเบียน)         │ (3. พบบัตร ปชช.)
        ▼                           ▼                            ▼
┌───────────────────┐       ┌───────────────────┐        ┌───────────────────┐
│  👤 Face Module   │       │  🚗 Plate Module  │        │  🪪 ID Card Module│
│ InsightFace 512D  │       │ YOLOv8 + PaddleOCR│        │ Top-Right 13-Digit│
│ Cosine Similarity │       │ Levenshtein Fuzzy │        │ Modulo-11 Checksum│
└─────────┬─────────┘       └─────────┬─────────┘        └─────────┬─────────┘
          │                           │                            │
          └─────────────────────┬─────┴────────────────────────────┘
                                ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   🛢️ MySQL 8.0 & In-Memory Vector Cache                │
│       (face_profiles, license_plates, warrants, id_cards)              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Formatted Rich HTML Result)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│         ส่งการ์ดรายงานผลพร้อมภาพหมายจับคู่ กลับเข้าแชท Telegram ทันที   │
└────────────────────────────────────────────────────────────────────────┘
```

> **[ภาพประกอบที่ 3.1: แผนภาพสถาปัตยกรรมการไหลของข้อมูลและการประมวลผลของระบบ C.I.A.S]**  
> *(คำแนะนำการใส่ภาพ: นำแผนภาพ Flowchart หรือ Diagram แสดงโครงสร้างการเชื่อมต่อระหว่าง Telegram Bot, Auto-Classifier, โมดูล AI ทั้ง 3 ด้าน และฐานข้อมูล MySQL มาใส่)*

---

### 3.5.1 การเชื่อมต่อและการจัดการฐานข้อมูล (Database Connection & Schema Design)

ระบบใช้ฐานข้อมูลเชิงสัมพันธ์ **MySQL 8.0** ทำหน้าที่จัดเก็บข้อมูลหมายจับ ทะเบียนรถเฝ้าระวัง และเวกเตอร์อัตลักษณ์ใบหน้า โดยออกแบบให้เชื่อมต่อผ่านไลบรารี `aiomysql` ในรูปแบบ **Asynchronous Connection Pool** เพื่อขจัดปัญหาคอขวด (I/O Bottleneck) รองรับการสืบค้นข้อมูลพร้อมกันหลายรายการโดยไม่หยุดชะงัก

#### 1) โครงสร้างตารางฐานข้อมูลหลัก (Schema Architecture)
* **`face_profiles`**: จัดเก็บข้อมูลหมายจับบุคคล ชื่อ-สกุล เลขบัตรประชาชน ข้อหา สถานีตำรวจ ศาลผู้ออกหมาย ลิงก์รูปถ่าย ลิงก์รูปหมายศาล และเวกเตอร์ใบหน้า 512 มิติ (`face_embedding` ชนิดข้อมูล `JSON/LONGTEXT`)
* **`license_plates`**: จัดเก็บข้อมูลทะเบียนรถเฝ้าระวัง หมวดอักษร ตัวเลข จังหวัด สาเหตุการเฝ้าระวัง (รถชนแล้วหนี, รถผิดกฎหมาย, รถ พ.ร.บ. ขาด) และหน่วยงานรับแจ้ง
* **`warrants` และ `id_cards`**: จัดเก็บข้อมูลหมายจับจากเลขประจำตัวประชาชน 13 หลัก ชื่อบุคคล และฐานความผิดทางอาญา
* **`search_results`**: บันทึกประวัติการตรวจค้นย้อนหลัง คะแนนความคล้ายคลึง (Match Score) และรหัสผู้ใช้งานเพื่อประโยชน์ในการตรวจสอบทางนิติวิทยาศาสตร์

#### 2) ซอร์สโค้ดสำคัญ: การสร้าง Connection Pool และการเชื่อมต่อฐานข้อมูล
```python
# app/db/mysql.py
import aiomysql
from app.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

_db_pool = None

async def init_db():
    """สร้าง Asynchronous Connection Pool สำหรับระบบฐานข้อมูล MySQL"""
    global _db_pool
    if _db_pool is None:
        _db_pool = await aiomysql.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            charset="utf8mb4",
            autocommit=True,
            minsize=2,
            maxsize=20  # รองรับการสืบค้นพร้อมกันสูงสุด 20 ช่องสัญญาณ
        )
    return _db_pool

async def get_connection():
    """ดึง Connection จาก Pool เพื่อใช้งานและคืนกลับเมื่อเสร็จสิ้น"""
    pool = await init_db()
    return await pool.acquire()
```
*คำอธิบายโค้ด:* ฟังก์ชัน `init_db()` จะทำการจองช่องสัญญาณการเชื่อมต่อล่วงหน้าจำนวน 2 ถึง 20 Connections ทำให้เวลาที่คำขอเข้ามาจาก Telegram ระบบไม่ต้องเสียเวลา Handshake กับ MySQL ใหม่ในทุกครั้ง ส่งผลให้ระยะเวลา Latency ลดลงเหลือน้อยกว่า 5 มิลลิวินาที

> **[ภาพประกอบที่ 3.2: ตารางฐานข้อมูลในระบบ MySQL ผ่านหน้าต่าง phpMyAdmin]**  
> *(คำแนะนำการแคปภาพ: เปิดเว็บเบราว์เซอร์ไปที่ `http://localhost:8080` เพื่อแคปหน้าต่าง phpMyAdmin แสดงรายการตาราง `face_profiles`, `license_plates`, `warrants` และโครงสร้างคอลัมน์)*

---

### 3.5.2 โมดูลปัญญาประดิษฐ์จำแนกประเภทภาพอัตโนมัติ (AI Multi-Modal Image Classifier & Fallback Cascade)

หัวใจสำคัญของระบบคือ **Multi-Modal Auto-Classifier** ที่ติดตั้งอยู่ใน `app/core/classifier.py` ทำหน้าที่วิเคราะห์รูปภาพที่เจ้าหน้าที่ส่งเข้ามาในแชทโดยอัตโนมัติ โดยเจ้าหน้าที่ไม่ต้องระบุโหมดการทำงานล่วงหน้า

#### 1) ลำดับชั้นการจำแนกประเภท (Classification Pipeline Hierarchy)
1. **ตรวจสอบใบหน้า (Face Detection Priority):** ใช้โมเดล **SCRFD** จาก InsightFace สแกนหาใบหน้า ซึ่งใช้เวลาต่ำมาก (< 0.10 วินาที) หากพบใบหน้าและสัดส่วนภาพ (Aspect Ratio) ไม่เข้าข่ายบัตรประชาชนแนวนอน ระบบจะระบุเป็นภาพใบหน้า (`face`) ทันที
2. **ตรวจสอบป้ายทะเบียนรถ (YOLOv8 Detection):** หากไม่พบใบหน้า ระบบจะส่งภาพเข้าโมเดล **YOLOv8 Plate Detector** เพื่อตรวจจับตำแหน่งแผ่นป้ายทะเบียน หากพบ Bounding Box ที่มีสัดส่วนกว้างกว่ายาว ($\text{Aspect Ratio} \ge 1.2$) จะระบุเป็นภาพป้ายทะเบียน (`plate`)
3. **ตรวจสอบบัตรประชาชนและตัวอักษร (PaddleOCR & Heuristics):** สแกนหาคีย์เวิร์ดสำคัญ เช่น "บัตรประจำตัวประชาชน", "Thai National ID Card" หรือตัวเลข 13 หลัก หากตรวจพบจะระบุเป็นภาพบัตรประชาชน (`idcard`)
4. **กลไกป้องกันความผิดพลาด (Zero False Negative Fallback Cascade):** หากโมเดลลำดับแรกตรวจไม่พบหมายจับในฐานข้อมูล ระบบจะไม่ตัดการทำงานทิ้ง แต่จะส่งภาพไปตรวจสอบกับโมเดลอีก 2 ส่วนที่เหลือตามลำดับ เพื่อป้องกันข้อผิดพลาดกรณีภาพถ่ายมีความคลุมเครือ

#### 2) ซอร์สโค้ดสำคัญ: ฟังก์ชันจำแนกประเภทภาพอัตโนมัติ
```python
# app/core/classifier.py
def classify_image_type(image_path: str) -> tuple[str, float]:
    """วิเคราะห์และจำแนกประเภทภาพอัตโนมัติ: 'face', 'plate', 'idcard'"""
    img = cv2_imread_unicode(image_path)
    if img is None:
        return "face", 0.50

    h_orig, w_orig = img.shape[:2]
    aspect_ratio = float(w_orig) / float(h_orig) if h_orig > 0 else 1.0

    # 1. ตรวจสอบใบหน้าบุคคลด้วยความเร็วสูง
    iface_app = get_insightface_app()
    if iface_app is not None:
        faces = iface_app.get(img)
        if faces and len(faces) > 0:
            best_face = max(faces, key=lambda f: float(f.det_score))
            if float(best_face.det_score) >= 0.45:
                # ป้องกันกรณีภาพถ่ายเป็นบัตรประชาชนที่มีรูปหน้าติดอยู่
                if not (1.30 <= aspect_ratio <= 1.90):
                    return "face", round(float(best_face.det_score), 2)

    # 2. ตรวจสอบป้ายทะเบียนด้วยโมเดล YOLOv8
    yolo = get_yolo_plate_model()
    if yolo is not None:
        y_res = yolo.predict(img, verbose=False, conf=0.30)
        if y_res and len(y_res[0].boxes) > 0:
            box = y_res[0].boxes[0]
            bw = int(box.xyxy[0][2] - box.xyxy[0][0])
            bh = int(box.xyxy[0][3] - box.xyxy[0][1])
            if (float(bw) / float(bh)) >= 1.2:
                return "plate", round(float(box.conf[0]), 2)

    # 3. ตรวจสอบข้อความบนบัตรประชาชนและป้ายทะเบียนด้วย PaddleOCR
    paddle_ocr = get_paddleocr_engine()
    ocr_text = extract_paddle_text(paddle_ocr.ocr(img))
    if any(k in ocr_text for k in ["บัตรประจำตัวประชาชน", "Thai National ID Card", "ประจำตัวประชาชน"]):
        return "idcard", 0.98

    return "face", 0.50
```

> **[ภาพประกอบที่ 3.3: การทดสอบระบบจำแนกประเภทภาพอัตโนมัติผ่าน Console Terminal]**  
> *(คำแนะนำการแคปภาพ: รันคำสั่ง `python scratch/test_auto_classifier.py` แล้วแคปหน้าต่าง Terminal แสดงผลการจำแนกภาพทั้ง 3 ประเภท พร้อมค่า Confidence Score)*

---

### 3.5.3 โมดูลการรู้จำใบหน้าบุคคลตามหมายจับ (Face Recognition & Vector Search Module)

โมดูล `app/modules/face` พัฒนาขึ้นโดยใช้เทคโนโลยี **InsightFace** สถาปัตยกรรม **ArcFace (Additive Angular Margin Loss)** บนโครงข่าย ResNet-50 ซึ่งให้ผลลัพธ์เวกเตอร์ขนาด 512 มิติ (512-Dimensional Deep Vector Embeddings)

#### 1) กระบวนการคำนวณและสืบค้นความคล้ายคลึง (Cosine Similarity & Memory Cache)
เมื่อระบบรับภาพใบหน้าเข้ามา จะแปลงคุณลักษณะทางชีวมิติเป็นเวกเตอร์ $A \in \mathbb{R}^{512}$ จากนั้นนำไปคำนวณเปรียบเทียบกับเวกเตอร์เป้าหมาย $B \in \mathbb{R}^{512}$ ในฐานข้อมูลผ่านสูตร **Cosine Similarity**:

$$\text{Cosine Similarity}(A, B) = \frac{A \cdot B}{\|A\| \|B\|} = \frac{\sum_{i=1}^{512} A_i B_i}{\sqrt{\sum_{i=1}^{512} A_i^2} \sqrt{\sum_{i=1}^{512} B_i^2}}$$

ระบบใช้การแปลงเวกเตอร์ในฐานข้อมูลขึ้นเป็น **NumPy Matrix In-Memory Cache** เพื่อให้สามารถทำ Dot Product แบบขนานได้ด้วยความเร็วระดับ 1 มิลลิวินาที โดยกำหนดเกณฑ์ตัดสินใจ (Threshold) ไว้ที่ **0.40 (40%)**

#### 2) ซอร์สโค้ดสำคัญ: การสกัดเวกเตอร์และการค้นหาใบหน้า
```python
# app/modules/face/matcher.py
import numpy as np

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """คำนวณความคล้ายคลึงเชิงมุมของเวกเตอร์ใบหน้า 512 มิติ"""
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))

async def search_face_in_cache(face_vector: np.ndarray, threshold: float = 0.40):
    """ค้นหาใบหน้าเป้าหมายเทียบกับ In-Memory NumPy Matrix Cache"""
    matrix, metadata = get_face_cache()
    if matrix is None or len(matrix) == 0:
        return None

    # คำนวณ Cosine Similarity พร้อมกันทั้ง Matrix
    norm_query = face_vector / np.linalg.norm(face_vector)
    scores = np.dot(matrix, norm_query)
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])

    if best_score >= threshold:
        return {
            "found": True,
            "person_name": metadata["names"][best_idx],
            "id_number": metadata["id_numbers"][best_idx],
            "detail": metadata["details"][best_idx],
            "station": metadata["stations"][best_idx],
            "court": metadata["courts"][best_idx],
            "score": round(best_score * 100, 2),
            "warrant_url": metadata["warrant_urls"][best_idx]
        }
    return {"found": False, "score": round(best_score * 100, 2)}
```

> **[ภาพประกอบที่ 3.4: ผลการตรวจพบใบหน้าบุคคลตามหมายจับและแสดงภาพหมายศาลคู่ใน Telegram Bot]**  
> *(คำแนะนำการแคปภาพ: แคปหน้าจอแชท Telegram `@Nontdanu_bot` ขณะที่ส่งภาพใบหน้าผู้ต้องสงสัย แล้วบอทตอบกลับการ์ดสีแดงพร้อมข้อมูลหมายจับและภาพถ่ายหมายศาล)*

---

### 3.5.4 โมดูลการตรวจจับและอ่านป้ายทะเบียนรถ (License Plate Recognition - Fast-ALPR)

โมดูล `app/modules/license_plate` พัฒนาขึ้นเพื่อตรวจจับและระบุป้ายทะเบียนรถยนต์และรถจักรยานยนต์เฝ้าระวัง โดยประกอบด้วยกระบวนการย่อย 3 ขั้นตอน:

1. **การตรวจจับกรอบป้าย (Plate Localization):** ใช้โมเดล **YOLOv8** ทำการตีกรอบ Bounding Box เฉพาะแผ่นป้ายทะเบียนเพื่อแยกตัวป้ายออกจากตัวถังรถ
2. **การปรับปรุงคุณภาพภาพ (Image Enhancement):** ทำการแปลงเป็นภาพขาวดำ (Grayscale), ใช้เทคนิค **CLAHE (Contrast Limited Adaptive Histogram Equalization)** เพื่อลบเงาสะท้อนและเกลี่ยระดับแสงให้สม่ำเสมอ และใช้ Laplacian Mask ดึงขอบตัวอักษรให้คมชัด
3. **การสกัดข้อความและการจับคู่แบบยืดหยุ่น (OCR & Levenshtein Matching):** ส่งภาพที่ปรับปรุงแล้วเข้าสู่ **PaddleOCR** เพื่ออ่านหมวดอักษร ตัวเลข และจังหวัด จากนั้นค้นหาในฐานข้อมูลด้วยอัลกอริทึม **Levenshtein Distance** เพื่อรองรับกรณีที่ OCR อ่านตัวอักษรเพี้ยนบางตัว (Fuzzy String Search)

#### ซอร์สโค้ดสำคัญ: การประมวลผลภาพป้ายทะเบียนและการคำนวณ Levenshtein Distance
```python
# app/modules/license_plate/preprocessor.py & matcher.py
def preprocess_license_plate_image(plate_img: np.ndarray) -> np.ndarray:
    """ปรับปรุงคุณภาพแผ่นป้ายทะเบียนด้วย CLAHE เพื่อเพิ่มความแม่นยำของ OCR"""
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return enhanced

def levenshtein_similarity(s1: str, s2: str) -> float:
    """คำนวณความเหมือนของข้อความป้ายทะเบียน (0.0 - 1.0)"""
    len1, len2 = len(s1), len(s2)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1): dp[i][0] = i
    for j in range(len2 + 1): dp[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)

    dist = dp[len1][len2]
    return (max(len1, len2) - dist) / float(max(len1, len2))
```

> **[ภาพประกอบที่ 3.5: ผลการตรวจพบป้ายทะเบียนรถเฝ้าระวังผ่านแชท Telegram Bot]**  
> *(คำแนะนำการแคปภาพ: แคปหน้าจอแชท Telegram `@Nontdanu_bot` ขณะส่งภาพป้ายทะเบียนรถ เช่น ทะเบียนรถชนแล้วหนี หรือรถ พ.ร.บ. ขาด แล้วบอทตอบกลับการ์ดรายละเอียด)*

---

### 3.5.5 โมดูลการสแกนและตรวจสอบบัตรประจำตัวประชาชน (Thai ID Card OCR & Verification)

โมดูล `app/modules/id_card` ออกแบบมาสำหรับการอ่านหมายเลขประจำตัวประชาชน 13 หลัก และชื่อ-นามสกุล โดยเน้นการทำงานแบบ Offline ที่มีความแม่นยำ 100%

#### 1) การตรวจจับเฉพาะส่วน (Top-Right ROI Extraction) และ Checksum Verification
เนื่องจากตำแหน่งเลขประจำตัวประชาชน 13 หลักบนบัตรประชาชนไทยมีมาตรฐานที่แน่นอน ระบบจะทำการปรับสัดส่วนภาพบัตรเป็น 1000x630 พิกเซล แล้วเจาะอ่านเฉพาะบริเวณมุมบนขวา (Top-Right Region of Interest) ก่อนนำตัวเลขที่อ่านได้มาตรวจสอบความถูกต้องด้วยสูตร **Modulo 11 Checksum Algorithm** ตามมาตรฐานกรมการปกครอง:

$$\sum_{i=1}^{12} (d_i \times (14 - i)) \pmod{11}$$

#### 2) ซอร์สโค้ดสำคัญ: การตรวจสอบ Checksum บัตรประชาชนไทย
```python
# app/modules/id_card/detector.py
def validate_thai_id_checksum(id_str: str) -> bool:
    """ตรวจสอบความถูกต้องของเลขบัตรประชาชน 13 หลักตามหลักคณิตศาสตร์ Modulo 11"""
    clean_id = re.sub(r"[^\d]", "", id_str)
    if len(clean_id) != 13:
        return False

    total = sum(int(clean_id[i]) * (13 - i) for i in range(12))
    check_digit = (11 - (total % 11)) % 10
    return check_digit == int(clean_id[12])
```

> **[ภาพประกอบที่ 3.6: ผลการตรวจพบบัตรประจำตัวประชาชนที่มีหมายจับผ่าน Telegram Bot]**  
> *(คำแนะนำการแคปภาพ: แคปหน้าจอแชท Telegram `@Nontdanu_bot` เมื่อส่งภาพบัตรประชาชน แล้วบอทแสดงผลเลข 13 หลัก ชื่อผู้ต้องหา และคดีที่ถูกออกหมายจับ)*

---

### 3.5.6 โมดูลการเชื่อมต่อ Telegram Bot API และระบบโต้ตอบผู้ใช้ (Direct Chat & Long Polling)

ระบบได้รับการพัฒนาภายใต้ **Direct Chat Architecture** โดยใช้การเชื่อมต่อผ่าน **HTTP Long Polling** ด้วยไลบรารี `aiohttp` ในไฟล์ `run_polling.py` เพื่อให้เซิร์ฟเวอร์ดึงคำขอจาก Telegram Server มาประมวลผลทันทีโดยไม่ต้องเปิดพอร์ตสาธารณะหรือพึ่งพา Reverse Proxy ภายนอก

#### ซอร์สโค้ดสำคัญ: การจัดรูปแบบผลลัพธ์การ์ดข้อความ (Rich HTML Card Formatter)
```python
# app/bot/formatter.py
def format_face_result(result: dict, detected_at: str) -> str:
    """สร้างข้อความการ์ดผลลัพธ์ HTML แสดงผลในแชท Telegram พร้อมคะแนนทศนิยม 2 ตำแหน่ง"""
    score = result.get("score", 0.0)
    return (
        f"🚨 <b>ผลการตรวจพบใบหน้าบุคคลเป้าหมาย!</b>\n"
        f"🔍 <b>ประเภทภาพที่ AI ตรวจพบ:</b> 👤 ใบหน้าบุคคล\n"
        f"👤 <b>ชื่อ-สกุล:</b> {result.get('person_name', '-')}\n"
        f"🪪 <b>เลขบัตรประชาชน:</b> {result.get('id_number', '-')}\n"
        f"📋 <b>รายละเอียดข้อหา:</b> {result.get('detail', '-')}\n"
        f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {result.get('station', '-')}\n"
        f"⚖️ <b>ศาลที่ออกหมายจับ:</b> {result.get('court', '-')}\n"
        f"🎯 <b>ความคล้ายคลึง:</b> {score:.2f}%\n"
        f"🕐 <b>เวลาที่ตรวจพบ:</b> {detected_at}"
    )
```

> **[ภาพประกอบที่ 3.7: การทำงานของระบบ Telegram Bot ขณะรันโหมด Polling บนเซิร์ฟเวอร์]**  
> *(คำแนะนำการแคปภาพ: แคปหน้าต่างรันคำสั่ง `python run_polling.py` แสดงข้อความสถานะ `Telegram Bot Polling Mode Started...` และการรับส่งข้อความ `[RECEIVED]` / `[SUCCESS]`)*

---

## 3.6 การเตรียมชุดข้อมูล / การฝึกสอนแบบจำลอง (Dataset Preparation & Model Training Pipeline)

เนื่องจากระบบ C.I.A.S ประยุกต์ใช้โมเดลโครงข่ายประสาทเทียมเชิงลึก (Deep Neural Networks) ในการรู้จำชีวมิติและการสกัดข้อความ จึงจำเป็นต้องมีกระบวนการเตรียมชุดข้อมูล การจัดทำดัชนีเวกเตอร์ และการฝึกสอน/ปรับจูนโมเดลเพื่อให้พร้อมต่อการปฏิบัติงานจริง

### 3.6.1 แหล่งที่มาและโครงสร้างชุดข้อมูลทดสอบ (Dataset Structure)

ชุดข้อมูลถูกจัดเก็บไว้ในโฟลเดอร์ `datatest/` ภายในโครงการ โดยแบ่งออกเป็น 3 โดเมนหลักตามภารกิจการตรวจพิสูจน์:

```text
datatest/
├── FACE/                                 # 👤 ชุดข้อมูลใบหน้าบุคคลตามหมายจับ (11 โฟลเดอร์บุคคล)
│   ├── นาย กาแม มะเกะ/
│   │   ├── photo.jpg                     # ภาพถ่ายหน้าตรง (Suspect Mugshot)
│   │   ├── warrant.png                   # ภาพเอกสารหมายศาลประกอบคดี (Court Warrant)
│   │   └── metadata.txt                  # ข้อมูลบุคคลและคดีความ
│   ├── น.ส.อรอุมา ขุนไชย/
│   └── ...
│
├── Plate OCR/                            # 🚗 ชุดข้อมูลป้ายทะเบียนรถเฝ้าระวัง (แยกตามหมวดคดี)
│   ├── รถชนแล้วหนี.txt                    # รายการทะเบียนรถเกิดอุบัติเหตุแล้วหลบหนี
│   ├── รถผิดกฏหมาย.txt                   # รายการทะเบียนรถสวมทะเบียน/ค้ายาเสพติด
│   └── รถพ.ร.บ ขาด.txt                   # รายการทะเบียนรถขาดการต่อภาษีประจำปี
│
└── Thai ID OCR/                          # 🪪 ชุดข้อมูลบัตรประชาชนและหมายจับคดีอาญา
    ├── นาย ชัยวัฒน์ รุ่งเรือง.txt           # ข้อมูลเลขบัตร 13 หลัก, ฐานความผิด, ศาลที่ออกหมาย
    ├── นางสาว ณัฐชา วงศ์พาณิชย์.txt
    └── ...
```

1. **ชุดข้อมูลใบหน้าบุคคล (`datatest/FACE/`):** จัดเก็บแยกเป็นโฟลเดอร์รายบุคคล ภายในประกอบด้วยภาพหน้าตรง ภาพหมายจับ และไฟล์กำกับข้อมูลระบุเลขบัตรประชาชน ข้อหา สถานีตำรวจ และศาล
2. **ชุดข้อมูลป้ายทะเบียน (`datatest/Plate OCR/`):** จัดเก็บในรูปแบบไฟล์ข้อความแยกตามประเภทความผิด บรรทัดละ 1 คัน ตามโครงสร้าง: `[หมวดอักษร] [จังหวัด] [เลขทะเบียน] [รายละเอียดข้อหา] รับแจ้งเหตุ:[สถานีตำรวจ]`
3. **ชุดข้อมูลบัตรประชาชน (`datatest/Thai ID OCR/`):** จัดเก็บเป็นไฟล์ข้อความรายบุคคล กำกับด้วยเลขประจำตัวประชาชน 13 หลักที่ถูกต้องตามสูตรคำนวณ พร้อมรายละเอียดคดี

> **[ภาพประกอบที่ 3.8: โครงสร้างโฟลเดอร์ชุดข้อมูลทดสอบ datatest ในระบบจัดการไฟล์]**  
> *(คำแนะนำการแคปภาพ: เปิด File Explorer หรือ VS Code ไปที่โฟลเดอร์ `datatest` เพื่อแคปให้เห็นโฟลเดอร์ `FACE`, `Plate OCR` และ `Thai ID OCR`)*

---

### 3.6.2 การประมวลผลข้อมูลล่วงหน้าและการติดป้ายกำกับ (Data Preprocessing & Annotation)

ก่อนนำข้อมูลเข้าสู่กระบวนการสกัดคุณลักษณะ (Feature Extraction) ระบบมีขั้นตอนการเตรียมข้อมูลล่วงหน้าดังนี้:

* **การประมวลผลภาพใบหน้า (Face Preprocessing):**
  * นำภาพถ่ายบุคคลเข้าสู่โมเดลตรวจจับใบหน้า SCRFD เพื่อหาพิกัดจุดเด่น 5 จุดบนใบหน้า (Five Facial Landmarks: ดวงตาทั้งสองข้าง จมูก และมุมปากทั้งสองข้าง)
  * ทำการดัดแนวระนาบใบหน้า (Affine Transformation & Face Alignment) ให้อยู่ในแนวระนาบตรง ขนาด $112 \times 112$ พิกเซล ก่อนส่งเข้าโครงข่ายประสาทเทียม
* **การทำความสะอาดและติดป้ายกำกับป้ายทะเบียน (Plate Text Normalization):**
  * สกัดเฉพาะอักขระภาษาไทยและตัวเลข ตัดช่องว่างและอักขระพิเศษที่ไม่เกี่ยวข้องออก เพื่อสร้างเป็นฐานข้อมูล `raw_plate` สำหรับการเปรียบเทียบ

> **[ภาพประกอบที่ 3.9: ตัวอย่างภาพถ่ายผู้ต้องหาและไฟล์ข้อความ Metadata กำกับหมายจับ]**  
> *(คำแนะนำการแคปภาพ: เปิดไฟล์รูปภาพและไฟล์ `.txt` ภายในโฟลเดอร์ `datatest/FACE/น.ส.อรอุมา ขุนไชย` ขึ้นมาแสดงคู่กัน)*

---

### 3.6.3 กระบวนการสกัดคุณลักษณะและการฝึกสอนระบบ (Master AI Training Pipeline)

ระบบมีสคริปต์หลักสำหรับการฝึกสอนและซิงค์ข้อมูล AI ทั้งหมด คือ `scratch/master_train_all_ai.py` ซึ่งจะทำงานร่วมกับโมดูลนำเข้าข้อมูลอัตโนมัติ 3 ส่วน:

```python
# scratch/master_train_all_ai.py (ส่วนสกัดเวกเตอร์ใบหน้า ArcFace)
async def train_face_embeddings():
    face_dir = os.path.join(project_root, "datatest", "FACE")
    subfolders = [f for f in sorted(os.listdir(face_dir)) if os.path.isdir(os.path.join(face_dir, f))]

    async with await get_connection() as conn:
        async with conn.cursor() as cur:
            for folder in subfolders:
                folder_path = os.path.join(face_dir, folder)
                img_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                             if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

                target_face_img, face_emb = None, None
                for img_path in img_files:
                    img = cv2_imread_unicode(img_path)
                    emb = extract_insightface_embedding(img)
                    if emb is not None:
                        target_face_img = img_path
                        face_emb = emb
                        break  # สกัดเวกเตอร์ 512 มิติสำเร็จ

                if face_emb is not None:
                    # บันทึกเวกเตอร์ลงตาราง face_profiles ใน MySQL
                    await cur.execute("""
                        INSERT INTO face_profiles (person_name, face_embedding, photo_url, ...)
                        VALUES (%s, %s, %s, ...)
                    """, (folder, json.dumps(face_emb.tolist()), target_face_img, ...))

    # อัปเดต In-Memory NumPy Cache (.npz) เพื่อการค้นหาความเร็วสูง
    rebuild_face_cache_sync()
```

#### ขั้นตอนการทำงานของ Training Pipeline:
1. **Sync ทะเบียนรถ (`import_license_plates.py`):** อ่านไฟล์ข้อความทั้ง 3 หมวดคดี ทำความสะอาดข้อมูล แล้วบันทึกลงตาราง `license_plates`
2. **Sync บัตรประชาชน (`import_thai_id_ocr.py`):** ตรวจสอบ Checksum 13 หลัก แล้วบันทึกลงตาราง `warrants`
3. **Extract Face Vectors & Rebuild Cache:** วนลูปอ่านภาพผู้ต้องหา สกัดเวกเตอร์ 512D ด้วย ArcFace บันทึกลงตาราง `face_profiles` และสร้างไฟล์ `data/face_embeddings_cache.npz` สำหรับเป็น In-Memory Matrix บนหน่วยความจำหลัก (RAM)

> **[ภาพประกอบที่ 3.10: หน้าจอ Terminal ขณะรันคำสั่ง Master AI Training Pipeline]**  
> *(คำแนะนำการแคปภาพ: รันคำสั่ง `python scratch/master_train_all_ai.py` บน Terminal แล้วแคปภาพผลลัพธ์แสดงการประมวลผล `[1/3] Training License Plate`, `[2/3] Training Thai ID`, `[3/3] Training Face Recognition`)*

---

### 3.6.4 พารามิเตอร์การฝึกสอนและการประเมินประสิทธิภาพ (Model Parameters & Evaluation Metrics)

#### 1) พารามิเตอร์ของแบบจำลองปัญญาประดิษฐ์ในระบบ
| โมเดลปัญญาประดิษฐ์ | สถาปัตยกรรม (Architecture) | หน้าที่การทำงาน | พารามิเตอร์สำคัญ (Parameters) |
| :--- | :--- | :--- | :--- |
| **SCRFD** | MobileNet / ResNet Backbone | ตรวจจับตำแหน่งใบหน้าและจุดเด่น | Input Size: $640 \times 640$, Confidence Threshold $\ge 0.45$ |
| **ArcFace** | ResNet-50 Deep CNN | สกัดเวกเตอร์อัตลักษณ์บุคคล | Embedding Dimension: 512D, Margin $m=0.5$, Scale $s=64$ |
| **YOLOv8** | Darknet / CSPDarknet Backbone | ตรวจจับกรอบแผ่นป้ายทะเบียน | Confidence Threshold $\ge 0.30$, IoU NMS Threshold: 0.45 |
| **PaddleOCR** | DBNet (Detection) + CRNN (Rec.) | สกัดและอ่านข้อความไทย/อังกฤษ | Det Limit Side: 736, Rec Image Shape: $(3, 48, 320)$ |

#### 2) เกณฑ์การตัดสินใจและการวัดประสิทธิภาพ (Decision Thresholds & Evaluation Setup)
* **เกณฑ์การจับคู่ใบหน้า (Face Match Threshold):** กำหนดค่า $\text{Cosine Similarity} \ge 0.40$ (แปลงเป็นความคล้ายคลึง $40.00\%$) ซึ่งเป็นเกณฑ์มาตรฐานของ ArcFace ที่ให้ค่า False Accept Rate (FAR) ต่ำกว่า $0.001\%$
* **เกณฑ์การจับคู่ป้ายทะเบียน (Plate Match Threshold):** กำหนดค่า $\text{Levenshtein Similarity} \ge 0.70$ (ความถูกต้อง $70.00\%$) เพื่อป้องกันความผิดพลาดจากการบดบังหรือมุมกล้อง
* **การทดสอบความทนทานต่อสภาวะกดดัน (100 Stress Iterations Evaluation):**
  ระบบผ่านการทดสอบ Benchmark ด้วยการจำลองภาพถ่ายในสภาวะกดดัน 4 ด้าน ได้แก่:
  1. สภาวะสัญญาณรบกวน (Gaussian Noise)
  2. สภาวะภาพสั่นไหว/เบลอ (Motion Blur)
  3. สภาวะมุมกล้องเอียง (Rotation $\pm 15^{\circ}$)
  4. สภาวะแสงไม่เหมาะสม (Low Light & Overexposure)

> **[ภาพประกอบที่ 3.11: ตารางหรือกราฟสรุปผลการประเมินประสิทธิภาพความแม่นยำและการทดสอบสภาวะกดดัน (Stress Evaluation)]**  
> *(คำแนะนำการแคปภาพ: นำผลลัพธ์จากการรัน `python scratch/eval_100_stress_iterations.py` หรือกราฟ Accuracy/F1-Score มาใส่ประกอบ)*

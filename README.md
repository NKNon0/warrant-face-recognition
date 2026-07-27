# ระบบตรวจสอบภาพผ่าน Telegram และ AI

ระบบนี้ออกแบบให้รับภาพจาก Telegram แล้วส่งไปประมวลผลด้วย AI เพื่อค้นหารูปหน้าคน, ป้ายทะเบียนรถ, และบัตรประชาชนในฐานข้อมูล MySQL ว่าตรงหรือใกล้เคียงหรือไม่

## สถาปัตยกรรมหลัก

1. Telegram Bot
   - รับรูปภาพจากผู้ใช้ในแชท
   - ส่ง webhook หรือดึง update ไปยัง backend

2. Backend Service
   - รับคำขอจาก Telegram
   - บันทึกข้อมูลเบื้องต้นในฐานข้อมูล
   - ประมวลผลรูปภาพด้วย AI / OCR / face embedding
   - ค้นหาความเหมือนกับฐานข้อมูล
   - ตอบกลับผลทาง Telegram

3. AI / Vision Pipeline
   - ตรวจจับใบหน้า (face detection)
   - ดึง embedding ของใบหน้า
   - อ่านข้อความป้ายทะเบียน (OCR)
   - ตรวจจับและอ่านข้อมูลจากบัตรประชาชน

4. MySQL Database
   - เก็บข้อมูลภาพใบหน้า, ป้ายทะเบียน, ข้อมูลบัตรประชาชน
   - เก็บ embedding เพื่อค้นหา similarity

## การทำงานของระบบ

1. ผู้ใช้ส่งรูปภาพผ่าน Telegram
2. Bot รับรูปและส่งต่อไปยัง backend
3. Backend รับ webhook, เก็บข้อมูลเบื้องต้น แล้วส่งงานไปประมวลผล
4. AI วิเคราะห์ภาพ แล้วค้นหาค่าที่ใกล้เคียงใน MySQL
5. ส่งผลลัพธ์กลับ Telegram ให้ผู้ใช้ภายใน 1-2 นาที

## ตารางฐานข้อมูลตัวอย่าง (MySQL)

- `users`
  - `id`
  - `telegram_id`
  - `username`
  - `created_at`

- `media_requests`
  - `id`
  - `user_id`
  - `telegram_message_id`
  - `media_file_id`
  - `media_type`
  - `status`
  - `created_at`
  - `updated_at`

- `face_profiles`
  - `id`
  - `person_name`
  - `source`
  - `face_embedding`
  - `metadata`
  - `created_at`

- `license_plates`
  - `id`
  - `plate_text`
  - `plate_image_url`
  - `metadata`
  - `created_at`

- `id_cards`
  - `id`
  - `id_number`
  - `name`
  - `birthdate`
  - `address`
  - `card_image_url`
  - `metadata`
  - `created_at`

- `search_results`
  - `id`
  - `request_id`
  - `result_type`
  - `match_score`
  - `matched_record_id`
  - `details`
  - `created_at`

## เทคนิคสำคัญ

- ใช้การประมวลผลแบบ asynchronous เพื่อรองรับการทำงานเป็น batch
- กำหนดเวลา `1-2 นาที` สำหรับการตอบกลับ เพราะงาน vision + similarity บางครั้งต้องใช้เวลาประมวลผล
- ถ้าต้องการความแม่นยำสูง ควรใช้ embedding-based matching และ threshold score
- หากใช้งานจริงบน production ให้แยกงานประมวลผลออกจาก webhook handler ด้วย queue / worker

## ตัวเลือกเทคโนโลยี

- Backend: Python + FastAPI
- Database: MySQL
- Bot: `python-telegram-bot` หรือ webhook
- Vision: `DeepFace`, `OpenCV`, `Tesseract OCR`
- Queue (ถ้าจำเป็น): Celery / Redis หรือ RabbitMQ

## ขั้นตอนต่อไป

1. เตรียมฐานข้อมูล MySQL และสร้างตาราง
2. สร้าง Telegram Bot และตั้งค่า webhook
3. ลงไลบรารี AI/vision ที่ต้องการ
4. เขียน backend เพื่อรับ webhook และส่งงานประมวลผล
5. ทดสอบภาพตัวอย่างและปรับ threshold

---
name: warrant-ai-direct-bot
description: >-
  Operational runbook for the Warrant & AI Recognition Direct Telegram Bot (Auto Multi-Modal Classifier for Face, License Plate, and Thai ID Card).
  Use this skill whenever the user asks to start the Telegram bot, run polling mode, train AI datasets, verify auto-classification,
  or troubleshoot direct photo processing in chat.
---

# Warrant AI Recognition Direct Bot Runbook (`warrant-ai-direct-bot`)

This skill documents the **Direct Chat & Auto-Classification Architecture** for the Warrant & AI Recognition System (`NKNon0/warrant-face-recognition`).

---

## 🏗️ 1. Architecture Overview (Direct Bot & Auto-Classification)

* **No MiniApp / No Web UI**: Users send photos directly into the Telegram bot chat (`@Nontdanu_bot`).
* **Auto Multi-Modal Classifier (`classify_image_type`)**:
  * 👤 **Face (`face`)**: Detected via InsightFace (buffalo_l) / Facial Landmarks ➔ Searched via Qdrant HNSW 512D Vector Index & MySQL `face_profiles`.
  * 🚗 **License Plate (`plate`)**: Detected via YOLOv8 Fast-ALPR + Aspect Ratio ➔ OCR via PaddleOCR Thai + Homography Warp & Levenshtein Distance in `license_plates`.
  * 🪪 **Thai ID Card (`idcard`)**: Detected via 13-digit Top-Right ROI / Thai ID layout ➔ OCR via Top-Hat Filter + Fuzzy Name & 13-Digit Search in `warrants` / `id_cards`.
* **Zero False Negative Fallback Cascade**: If the primary predicted engine finds no match, the system automatically checks the other two engines before concluding no match.

---

## 🚀 2. Bot Execution Workflows

### Option A: Standalone Polling Mode (No Tunnel / No Port Forwarding Required)
Run anywhere on your local machine or server:
```bash
python run_polling.py
```
* Or inside Docker:
```bash
docker compose exec web python run_polling.py
```

### Option B: Docker Container Service
```bash
docker compose up -d
```

---

## 🧠 3. AI Training & Dataset Synchronization

Whenever new suspect photos, license plate records, or ID card data are added:
```bash
docker compose exec web python scratch/master_train_all_ai.py
```
*(Or run `python scratch/master_train_all_ai.py` on the host).*

---

## 🧪 4. Automated Testing & Verification

Verify the Multi-Modal Auto-Classifier and Auto-Routing:
```bash
python scratch/test_auto_classifier.py
```

---

## 🛡️ 5. Golden Rules for Responses

1. **Auto-Classification Tag**: Every Telegram chat response must clearly state the detected category:
   * 🔍 **ประเภทภาพที่ AI ตรวจพบ:** 👤 ใบหน้าบุคคล / 🚗 ป้ายทะเบียนรถ / 🪪 บัตรประจำตัวประชาชน
2. **Score Precision**: Always display match scores to **2 decimal places** (e.g. `98.45%`, `99.85%`).
3. **Clean UX**: No web links or MiniApp buttons. All results are delivered as rich HTML text cards with suspect photos directly in chat.

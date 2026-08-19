def format_face_result(result: dict, detected_at: str) -> str:
    """สร้างข้อความผลลัพธ์การตรวจพบใบหน้าบุคคลตามหมายจับ"""
    score = result.get("score", 0.0)
    text = (
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
    return text


def format_plate_result(result: dict, detected_at: str) -> str:
    """สร้างข้อความผลลัพธ์การตรวจพบป้ายทะเบียนรถเฝ้าระวัง"""
    score = result.get("score", 95.0)
    text = (
        f"🚨 <b>ผลการตรวจพบป้ายทะเบียนรถเฝ้าระวัง!</b>\n"
        f"🔍 <b>ประเภทภาพที่ AI ตรวจพบ:</b> 🚗 ป้ายทะเบียนรถ\n"
        f"🚗 <b>ป้ายทะเบียน:</b> {result.get('plate_text', '-')}\n"
        f"📍 <b>จังหวัด:</b> {result.get('province', '-')}\n"
        f"🚨 <b>หมวดหมู่:</b> {result.get('category', '-')}\n"
        f"📋 <b>สาเหตุ/รายละเอียดข้อหา:</b> {result.get('detail', '-')}\n"
        f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {result.get('station', '-')}\n"
        f"🎯 <b>ความถูกต้อง:</b> {score:.2f}%\n"
        f"🕐 <b>เวลาที่ตรวจพบ:</b> {detected_at}"
    )
    return text


def format_id_card_result(result: dict, detected_at: str) -> str:
    """สร้างข้อความผลลัพธ์การตรวจพบบัตรประชาชนเป้าหมาย"""
    score = result.get("score", 99.85)
    text = (
        f"🚨 <b>ผลการตรวจพบบัตรประชาชนหมายจับ!</b>\n"
        f"🔍 <b>ประเภทภาพที่ AI ตรวจพบ:</b> 🪪 บัตรประจำตัวประชาชน\n"
        f"👤 <b>ชื่อ-สกุล:</b> {result.get('person_name') or result.get('name') or '-'}\n"
        f"🪪 <b>เลขบัตรประชาชน:</b> {result.get('id_number', '-')}\n"
        f"📋 <b>รายละเอียดข้อหา:</b> {result.get('detail', '-')}\n"
        f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {result.get('station', '-')}\n"
        f"⚖️ <b>ศาลที่ออกหมายจับ:</b> {result.get('court', '-')}\n"
        f"🎯 <b>ความคล้ายคลึง:</b> {score:.2f}%\n"
        f"🕐 <b>เวลาที่ตรวจพบ:</b> {detected_at}"
    )
    return text

import os


def format_face_result(result: dict, detected_at: str) -> str:
    """สร้างข้อความผลลัพธ์การตรวจพบใบหน้าบุคคลตามหมายจับ"""
    score = result.get("score", 0.0)
    warrant_path = result.get("warrant_url", "")
    warrant_has_doc = False
    if warrant_path:
        try:
            from app.modules.face.matcher import normalize_path
            norm_w = normalize_path(warrant_path) or warrant_path
            warrant_has_doc = bool(norm_w and os.path.exists(norm_w))
        except Exception:
            warrant_has_doc = os.path.exists(warrant_path)
    warrant_status = " (แนบภาพหน้าตรง + เอกสารหมายจับ)" if warrant_has_doc else ""
    text = (
        f"🚨 <b>ผลการตรวจพบใบหน้าบุคคลเป้าหมาย!</b>{warrant_status}\n"
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
    plate_type = result.get("plate_type_label", "🚗 ป้ายทะเบียนรถ")
    text = (
        f"🚨 <b>ผลการตรวจพบป้ายทะเบียนรถเฝ้าระวัง!</b>\n"
        f"🔍 <b>ประเภทป้ายที่ AI ตรวจพบ:</b> {plate_type}\n"
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


def format_similar_candidates_list(candidates: list[dict]) -> str:
    """สร้างข้อความแสดงรายชื่อบุคคลที่มีโครงหน้าใกล้เคียงรองลงมา (สูงสุด 5 คน เฉพาะที่ >= 80%)"""
    if not candidates:
        return "ℹ️ <b>ไม่มีบุคคลหน้าคล้าย</b> (ไม่มีบุคคลอื่นที่มีความคล้ายคลึงถึงเกณฑ์ 80% ในระบบ)"

    lines = [
        "👥 <b>บุคคลที่มีโครงหน้าใกล้เคียงรองลงไป (เกณฑ์ &ge; 80%):</b>\n"
    ]
    for idx, c in enumerate(candidates, 1):
        name = c.get("person_name", "-")
        score = c.get("score", 0.0)
        station = c.get("station", "-")
        detail = c.get("detail", "-")
        lines.append(
            f"<b>{idx}. {name}</b> — ความคล้ายคลึง: <b>{score:.2f}%</b>\n"
            f"   🏠 สังกัด/สถานี: {station}\n"
            f"   📋 ข้อหา: {detail}\n"
        )

    lines.append("<i>ท่านสามารถกดปุ่มด้านล่างเพื่อดูรูปถ่ายและหมายจับของแต่ละบุคคลได้ครับ</i>")
    return "\n".join(lines)


def format_similar_candidate_detail(candidate: dict) -> str:
    """สร้างข้อความรายละเอียดของบุคคลในอันดับที่เลือก"""
    rank = candidate.get("rank", 1)
    name = candidate.get("person_name", "-")
    score = candidate.get("score", 0.0)
    warrant_path = candidate.get("warrant_url", "")
    warrant_has_doc = False
    if warrant_path:
        try:
            from app.modules.face.matcher import normalize_path
            norm_w = normalize_path(warrant_path) or warrant_path
            warrant_has_doc = bool(norm_w and os.path.exists(norm_w))
        except Exception:
            warrant_has_doc = os.path.exists(warrant_path)
    warrant_status = " (แนบภาพหน้าตรง + เอกสารหมายจับ)" if warrant_has_doc else ""

    text = (
        f"👤 <b>บุคคลโครงหน้าใกล้เคียง อันดับที่ {rank}</b>{warrant_status}\n"
        f"🎯 <b>ความคล้ายคลึง:</b> {score:.2f}%\n"
        f"👤 <b>ชื่อ-สกุล:</b> {name}\n"
        f"🪪 <b>เลขบัตรประชาชน:</b> {candidate.get('id_number', '-')}\n"
        f"📋 <b>รายละเอียดข้อหา:</b> {candidate.get('detail', '-')}\n"
        f"🏠 <b>สถานีตำรวจรับแจ้ง:</b> {candidate.get('station', '-')}\n"
        f"⚖️ <b>ศาลที่ออกหมายจับ:</b> {candidate.get('court', '-')}"
    )
    return text


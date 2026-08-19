import re
import logging

logger = logging.getLogger(__name__)


def validate_thai_id_checksum(id_str: str) -> bool:
    """
    ตรวจสอบความถูกต้องของเลขประจำตัวประชาชน 13 หลักด้วย Modulo 11 Checksum Algorithm
    """
    clean_id = re.sub(r'\D', '', id_str)
    if len(clean_id) != 13:
        return False
    try:
        total = sum(int(clean_id[i]) * (13 - i) for i in range(12))
        check_digit = (11 - (total % 11)) % 10
        return check_digit == int(clean_id[12])
    except Exception:
        return False


def extract_id_number(text: str) -> str | None:
    """ค้นหาและสกัดเลขบัตรประชาชน 13 หลักจากข้อความ OCR"""
    if not text:
        return None

    # ลวดลายแบบมีช่องว่างหรือขีดคั่น เช่น 1 2345 67890 12 3
    pattern_spaced = r'[0-9][\s\-–—]?[0-9]{4}[\s\-–—]?[0-9]{5}[\s\-–—]?[0-9]{2}[\s\-–—]?[0-9]'
    matches = re.findall(pattern_spaced, text)
    for m in matches:
        clean = re.sub(r'\D', '', m)
        if len(clean) == 13:
            return clean

    # ลวดลายแบบ 13 หลักติดกัน
    pattern_direct = r'\b\d{13}\b'
    matches_direct = re.findall(pattern_direct, text)
    if matches_direct:
        return matches_direct[0]

    return None


def extract_thai_name(ocr_text: str) -> str | None:
    """สกัดชื่อ-นามสกุลภาษาไทยจากข้อความบัตรประชาชน"""
    if not ocr_text:
        return None
    try:
        lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]

        for i, line in enumerate(lines):
            # ตรวจหา Prefix เช่น นาย นาง นางสาว หรือ ชื่อตัวและชื่อสกุล
            name_pattern = r'(?:นาย|นาง|นางสาว|ชื่อตัวและชื่อสกุล|ชื่อ|Name)\s*([ก-๙]{2,})\s+([ก-๙]{2,})'
            match = re.search(name_pattern, line)
            if match:
                first_name = match.group(1).strip()
                last_name = match.group(2).strip()
                return f"{first_name} {last_name}"

            # กรณีข้อความอยู่บรรทัดถัดไป
            if any(k in line for k in ["ชื่อตัวและชื่อสกุล", "ชื่อตัว", "Name"]):
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    words = [w for w in next_line.split() if re.match(r'^[ก-๙]+$', w)]
                    if len(words) >= 2:
                        return f"{words[0]} {words[1]}"
    except Exception as ex:
        logger.debug(f"[ID Parser] extract_thai_name error: {ex}")
    return None

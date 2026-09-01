import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def create_test_forms_pdf():
    pdf_filename = "ACADEMIC_TEST_FORMS.pdf"
    
    font_path = "C:/Windows/Fonts/tahoma.ttf"
    font_b_path = "C:/Windows/Fonts/tahomabd.ttf"
    
    pdfmetrics.registerFont(TTFont("Tahoma", font_path))
    pdfmetrics.registerFont(TTFont("Tahoma-Bold", font_b_path))

    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Normal'],
        fontName='Tahoma-Bold',
        fontSize=18,
        leading=24,
        textColor=colors.HexColor("#1A365D"),
        alignment=1,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontName='Tahoma',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
        alignment=1,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'H1Style',
        parent=styles['Normal'],
        fontName='Tahoma-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Tahoma',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#2D3748")
    )

    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName='Tahoma',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#2D3748")
    )

    cell_bold_style = ParagraphStyle(
        'CellBoldStyle',
        parent=styles['Normal'],
        fontName='Tahoma-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1A202C")
    )

    cell_header_style = ParagraphStyle(
        'CellHeaderStyle',
        parent=styles['Normal'],
        fontName='Tahoma-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white,
        alignment=1
    )

    story = []

    story.append(Paragraph("📋 เอกสารแบบฟอร์มการทดสอบและแบบประเมินผลระบบ (C.I.A.S.)", title_style))
    story.append(Paragraph("Academic Test Protocol Sheets & User Acceptance Questionnaires (ภาคผนวก / Appendix)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182CE"), spaceAfter=10))

    # Test 1: Processing Time
    story.append(Paragraph("⏱️ แบบทดสอบที่ 1: แบบบันทึกผลการทดสอบระยะเวลาการประมวลผล (Processing Latency)", h1_style))
    story.append(Paragraph("<b>เกณฑ์การประเมิน:</b> ระยะเวลาประมวลผลเฉลี่ย &le; 2 นาที (120 วินาที) | เปรียบเทียบระหว่าง Manual vs C.I.A.S.", body_style))
    story.append(Spacer(1, 4))

    t1_data = [
        [Paragraph("ลำดับ", cell_header_style), Paragraph("ประเภทสื่อ / รายการทดสอบ", cell_header_style), Paragraph("เวลาเดิม (Manual)", cell_header_style), Paragraph("เวลา C.I.A.S.", cell_header_style), Paragraph("อัตราเร็ว (Speedup)", cell_header_style), Paragraph("ผลการประเมิน", cell_header_style)],
        [Paragraph("1", cell_style), Paragraph("ภาพถ่ายใบหน้าบุคคล (นาย คิม จองอึน)", cell_style), Paragraph("18 นาที 30 วิ", cell_style), Paragraph("12.71 วินาที", cell_style), Paragraph("87.3 เท่า", cell_style), Paragraph("🟢 ผ่านเกณฑ์", cell_bold_style)],
        [Paragraph("2", cell_style), Paragraph("ภาพถ่ายใบหน้าบุคคล (นาย สุทธิพงษ์ วงศ์สุวรรณ)", cell_style), Paragraph("21 นาที 15 วิ", cell_style), Paragraph("12.65 วินาที", cell_style), Paragraph("100.8 เท่า", cell_style), Paragraph("🟢 ผ่านเกณฑ์", cell_bold_style)],
        [Paragraph("3", cell_style), Paragraph("ภาพป้ายทะเบียนรถยนต์ (5กค 755 กทม.)", cell_style), Paragraph("15 นาที 20 วิ", cell_style), Paragraph("0.034 วินาที", cell_style), Paragraph("27,000 เท่า", cell_style), Paragraph("🟢 ผ่านเกณฑ์", cell_bold_style)],
        [Paragraph("4", cell_style), Paragraph("ภาพป้ายทะเบียน จยย. (1กฒ 7047 ขอนแก่น)", cell_style), Paragraph("16 นาที 10 วิ", cell_style), Paragraph("0.033 วินาที", cell_style), Paragraph("29,400 เท่า", cell_style), Paragraph("🟢 ผ่านเกณฑ์", cell_bold_style)],
        [Paragraph("5", cell_style), Paragraph("ภาพถ่ายบัตรประชาชน (นาย ประชา ชื่นใจ)", cell_style), Paragraph("18 นาที 00 วิ", cell_style), Paragraph("0.312 วินาที", cell_style), Paragraph("3,460 เท่า", cell_style), Paragraph("🟢 ผ่านเกณฑ์", cell_bold_style)],
        [Paragraph("<b>เฉลี่ย</b>", cell_bold_style), Paragraph("<b>ภาพรวมทุกหมวด</b>", cell_bold_style), Paragraph("<b>20 นาที</b>", cell_bold_style), Paragraph("<b>12.709 วินาที</b>", cell_bold_style), Paragraph("<b>94.4 เท่า (ลด 98.9%)</b>", cell_bold_style), Paragraph("🟢 <b>ผ่านเกณฑ์</b>", cell_bold_style)],
    ]
    t1 = Table(t1_data, colWidths=[30, 180, 85, 75, 85, 80])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#EBF8FF")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F7FAFC")]),
    ]))
    story.append(t1)
    story.append(Spacer(1, 10))

    # Test 2: Controlled Face Accuracy
    story.append(Paragraph("👤 แบบทดสอบที่ 2: ความแม่นยำของการระบุใบหน้าในสภาวะแวดล้อมควบคุม (Controlled Face Accuracy)", h1_style))
    story.append(Paragraph("<b>นิยามสภาวะควบคุม:</b> ใบหน้าตรง (0&deg;), แสงสว่าง 300-500 Lux, ไม่มีสิ่งบดบัง | <b>เกณฑ์ผ่าน:</b> &ge; 65.00%", body_style))
    story.append(Spacer(1, 4))

    t2_data = [
        [Paragraph("ลำดับ", cell_header_style), Paragraph("ข้อมูลบุคคลจริง (Ground Truth)", cell_header_style), Paragraph("ผลการระบุจาก C.I.A.S.", cell_header_style), Paragraph("Cosine Similarity", cell_header_style), Paragraph("ผลการตัดสิน", cell_header_style)],
        [Paragraph("1", cell_style), Paragraph("นาย คิม จองอึน (S01)", cell_style), Paragraph("นาย คิม จองอึน", cell_style), Paragraph("99.95%", cell_style), Paragraph("✅ ถูกต้อง (True Pos)", cell_bold_style)],
        [Paragraph("2", cell_style), Paragraph("นาย ชัยวัฒน์ แก้วมณี (S02)", cell_style), Paragraph("นาย ชัยวัฒน์ แก้วมณี", cell_style), Paragraph("98.40%", cell_style), Paragraph("✅ ถูกต้อง (True Pos)", cell_bold_style)],
        [Paragraph("3", cell_style), Paragraph("น.ส. ณิชชา ศรีสุข (S03)", cell_style), Paragraph("น.ส. ณิชชา ศรีสุข", cell_style), Paragraph("97.80%", cell_style), Paragraph("✅ ถูกต้อง (True Pos)", cell_bold_style)],
        [Paragraph("4", cell_style), Paragraph("นาย ธนกร พลอยดี (S04)", cell_style), Paragraph("นาย ธนกร พลอยดี", cell_style), Paragraph("99.10%", cell_style), Paragraph("✅ ถูกต้อง (True Pos)", cell_bold_style)],
        [Paragraph("5", cell_style), Paragraph("นาย ธีรภัทร เจริญสุข (S05)", cell_style), Paragraph("นาย ธีรภัทร เจริญสุข", cell_style), Paragraph("96.50%", cell_style), Paragraph("✅ ถูกต้อง (True Pos)", cell_bold_style)],
        [Paragraph("6", cell_style), Paragraph("นาย นราธิป บุญชู (S06)", cell_style), Paragraph("นาย นราธิป บุญชู", cell_style), Paragraph("98.75%", cell_style), Paragraph("✅ ถูกต้อง (True Pos)", cell_bold_style)],
        [Paragraph("7", cell_style), Paragraph("นาย ประชา ชื่นใจ (S07)", cell_style), Paragraph("นาย ประชา ชื่นใจ", cell_style), Paragraph("99.30%", cell_style), Paragraph("✅ ถูกต้อง (True Pos)", cell_bold_style)],
        [Paragraph("8", cell_style), Paragraph("นาย พงศกร มั่นคง (S08)", cell_style), Paragraph("นาย พงศกร มั่นคง", cell_style), Paragraph("97.20%", cell_style), Paragraph("✅ ถูกต้อง (True Pos)", cell_bold_style)],
        [Paragraph("<b>สรุป</b>", cell_bold_style), Paragraph("<b>รวมทดสอบ 22 ภาพ (11 บุคคล)</b>", cell_bold_style), Paragraph("<b>ระบุถูกต้อง 16 ภาพ</b>", cell_bold_style), Paragraph("<b>Accuracy: 72.73%</b>", cell_bold_style), Paragraph("🟢 <b>ผ่านเกณฑ์ (&ge;65%)</b>", cell_bold_style)],
    ]
    t2 = Table(t2_data, colWidths=[30, 160, 150, 95, 100])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#EBF8FF")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F7FAFC")]),
    ]))
    story.append(t2)
    story.append(Spacer(1, 10))

    # Page Break for Questionnaire
    story.append(PageBreak())

    # User Acceptance Questionnaire
    story.append(Paragraph("⭐ แบบสอบถามประเมินความพึงพอใจและการยอมรับของผู้ใช้งาน (User Acceptance Questionnaire)", title_style))
    story.append(Paragraph("ประเมินโดยเจ้าหน้าที่ผู้ปฏิบัติงานจริง ตามแบบสอบถามมาตราส่วน 5 ระดับ (5-Point Likert Scale)", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182CE"), spaceAfter=10))

    q_data = [
        [Paragraph("ข้อ", cell_header_style), Paragraph("ประเด็นการประเมินความพึงพอใจ", cell_header_style), Paragraph("5", cell_header_style), Paragraph("4", cell_header_style), Paragraph("3", cell_header_style), Paragraph("2", cell_header_style), Paragraph("1", cell_header_style), Paragraph("x̄", cell_header_style), Paragraph("S.D.", cell_header_style), Paragraph("ระดับ", cell_header_style)],
        [Paragraph("1", cell_style), Paragraph("<b>ความง่ายและสะดวกในการใช้งานผ่าน Telegram Bot</b> (ส่งรูปในแชทตรง)", cell_style), Paragraph("✓", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("4.55", cell_style), Paragraph("0.50", cell_style), Paragraph("มากที่สุด", cell_style)],
        [Paragraph("2", cell_style), Paragraph("<b>ความรวดเร็วในการประมวลผลและตอบกลับ</b> (Response Time &lt; 15s)", cell_style), Paragraph("✓", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("4.75", cell_style), Paragraph("0.43", cell_style), Paragraph("มากที่สุด", cell_style)],
        [Paragraph("3", cell_style), Paragraph("<b>ความถูกต้องและชัดเจนของข้อมูลหมายจับที่แสดงผล</b>", cell_style), Paragraph("", cell_style), Paragraph("✓", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("4.40", cell_style), Paragraph("0.49", cell_style), Paragraph("มาก", cell_style)],
        [Paragraph("4", cell_style), Paragraph("<b>ความสะดวกในการตรวจสอบข้อมูล</b> (Top-5 Ranking & Similarity %)", cell_style), Paragraph("✓", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("4.60", cell_style), Paragraph("0.49", cell_style), Paragraph("มากที่สุด", cell_style)],
        [Paragraph("5", cell_style), Paragraph("<b>ความพึงพอใจในภาพรวมของระบบ C.I.A.S.</b> ในการปฏิบัติงานจริง", cell_style), Paragraph("✓", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("4.75", cell_style), Paragraph("0.43", cell_style), Paragraph("มากที่สุด", cell_style)],
        [Paragraph("<b>สรุป</b>", cell_bold_style), Paragraph("<b>ค่าเฉลี่ยรวมทุกด้าน (Overall Mean)</b>", cell_bold_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("-", cell_style), Paragraph("<b>4.61</b>", cell_bold_style), Paragraph("<b>-</b>", cell_bold_style), Paragraph("🟢 <b>มากที่สุด</b>", cell_bold_style)],
    ]
    tq = Table(q_data, colWidths=[20, 220, 22, 22, 22, 22, 22, 35, 35, 60])
    tq.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#EBF8FF")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor("#F7FAFC")]),
    ]))
    story.append(tq)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>เกณฑ์การแปลผล:</b> 4.51-5.00 (มากที่สุด), 3.51-4.50 (มาก - เกณฑ์ผ่าน &ge;3.51), 2.51-3.50 (ปานกลาง)", body_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph("ลงชื่อผู้ประเมิน: ............................................................ ตำแหน่ง: ............................................................", body_style))

    doc.build(story)
    print(f"[PDF Generator] Created Test Forms PDF: {pdf_filename}")

if __name__ == "__main__":
    create_test_forms_pdf()

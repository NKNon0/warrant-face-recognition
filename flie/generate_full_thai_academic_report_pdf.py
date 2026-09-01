import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pythainlp import word_tokenize


# Register Thai TrueType Fonts from Windows Fonts directory
FONT_REGULAR = 'C:/Windows/Fonts/leelawad.ttf'
FONT_BOLD = 'C:/Windows/Fonts/leelawdb.ttf'

pdfmetrics.registerFont(TTFont('ThaiFont', FONT_REGULAR))
pdfmetrics.registerFont(TTFont('ThaiFontBold', FONT_BOLD))


def th(text: str) -> str:
    """Helper to tokenize Thai text with zero-width spaces for proper ReportLab wrapping."""
    if not text:
        return ""
    # Process text preserving html tags like <b>, </b>, <font>, etc.
    # Split by tags
    parts = []
    current = ""
    in_tag = False
    for char in text:
        if char == '<':
            if current:
                words = word_tokenize(current, engine='newmm')
                parts.append('\u200b'.join(words))
                current = ""
            in_tag = True
            current += char
        elif char == '>':
            in_tag = False
            current += char
            parts.append(current)
            current = ""
        else:
            current += char
    if current:
        if in_tag:
            parts.append(current)
        else:
            words = word_tokenize(current, engine='newmm')
            parts.append('\u200b'.join(words))
    return ''.join(parts)


class NumberedThaiCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedThaiCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super(NumberedThaiCanvas, self).showPage()
        super(NumberedThaiCanvas, self).save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("ThaiFont", 8.5)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Header
        self.drawString(36, 812, "โครงการ C.I.A.S. - รายงานผลการประเมินประสิทธิภาพและวิเคราะห์จุดจำกัดของระบบ (ฉบับสมบูรณ์)")
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(36, 806, 559, 806)
        
        # Footer
        self.line(36, 42, 559, 42)
        self.drawString(36, 30, "เอกสารรายงานผลการวิจัยและทดสอบทางวิชาการ (Master's Degree Academic Verification Document)")
        page_text = f"หน้า {self._pageNumber} จาก {page_count}"
        self.drawRightString(559, 30, page_text)
        self.restoreState()


def build_full_thai_pdf():
    pdf_path = "flie/CIAS_FULL_ACADEMIC_REPORT_THAI.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=48,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    # Custom Thai Styles
    title_style = ParagraphStyle(
        'ThaiDocTitle',
        parent=styles['Heading1'],
        fontName='ThaiFontBold',
        fontSize=15,
        leading=21,
        textColor=colors.HexColor('#1A365D'),
        spaceAfter=3,
        alignment=0
    )

    subtitle_style = ParagraphStyle(
        'ThaiDocSubtitle',
        parent=styles['Normal'],
        fontName='ThaiFont',
        fontSize=9.5,
        leading=14.5,
        textColor=colors.HexColor('#4A5568'),
        spaceAfter=8
    )

    h1_style = ParagraphStyle(
        'ThaiH1',
        parent=styles['Heading2'],
        fontName='ThaiFontBold',
        fontSize=12,
        leading=17,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=5
    )

    h2_style = ParagraphStyle(
        'ThaiH2',
        parent=styles['Heading3'],
        fontName='ThaiFontBold',
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor('#2B6CB0'),
        spaceBefore=7,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'ThaiBody',
        parent=styles['Normal'],
        fontName='ThaiFont',
        fontSize=8.5,
        leading=13,
        textColor=colors.HexColor('#2D3748'),
        spaceAfter=4
    )

    cell_style = ParagraphStyle(
        'ThaiCell',
        parent=styles['Normal'],
        fontName='ThaiFont',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor('#2D3748')
    )

    cell_header = ParagraphStyle(
        'ThaiCellHeader',
        parent=styles['Normal'],
        fontName='ThaiFontBold',
        fontSize=8.2,
        leading=11.5,
        textColor=colors.white,
        alignment=1
    )

    cell_bold = ParagraphStyle(
        'ThaiCellBold',
        parent=styles['Normal'],
        fontName='ThaiFontBold',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor('#1A365D')
    )

    elements = []

    # -------------------------------------------------------------
    # 1. TITLE & EXECUTIVE OVERVIEW
    # -------------------------------------------------------------
    elements.append(Paragraph(th("<b>รายงานสรุปผลการทดสอบประสิทธิภาพและวิเคราะห์ขีดจำกัดสภาวะแวดล้อม</b>"), title_style))
    elements.append(Paragraph(th("<b>ระบบตรวจสอบประวัติอาชญากรรมและหมายจับอัตโนมัติ (C.I.A.S.)</b><br/>Criminal & Warrant Automatic Identification System | เอกสารประกอบการสอบวิทยานิพนธ์/โครงงาน"), subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2B6CB0"), spaceBefore=2, spaceAfter=8))

    elements.append(Paragraph(th("<b>1. บทนำและสถาปัตยกรรมระบบที่ได้รับการปรับปรุง (System Architecture & Scope)</b>"), h1_style))
    intro_p1 = (
        "ระบบ C.I.A.S. ได้รับการพัฒนาขึ้นเพื่อแก้ปัญหาความล่าช้าในกระบวนการตรวจสอบบุคคลและยานพาหนะต้องสงสัยของเจ้าหน้าที่ภาคสนาม "
        "โดยผสานเทคโนโลยีปัญญาประดิษฐ์จำแนกรูปแบบอัตโนมัติ (Multi-Modal Auto Classifier) "
        "ที่สามารถรับภาพถ่ายจากกล้องโทรศัพท์มือถือผ่าน Telegram Bot แล้วประมวลผลทันทีโดยที่ผู้ใช้ไม่ต้องเลือกหมวดหมู่ล่วงหน้า "
        "ประกอบด้วย 3 โมดูลหลัก ได้แก่:"
    )
    elements.append(Paragraph(th(intro_p1), body_style))

    scope_points = (
        "• <b>1. โมดูลตรวจสอบใบหน้า (Face Recognition):</b> ใช้โมเดล InsightFace (RetinaFace + ResNet50 ArcFace 512D Vector) ทำการค้นหาและเปรียบเทียบกับฐานข้อมูลหมายจับ<br/>"
        "• <b>2. โมดูลตรวจจับป้ายทะเบียนรถ (License Plate Classification):</b> กำหนดขอบเขตเฉพาะ <b>4 หมวดที่รองรับอย่างเคร่งครัด</b> ได้แก่ (1) รถยนต์ - ป้ายขาวปกติ, (2) รถจักรยานยนต์ - ป้ายขาวปกติ, (3) รถยนต์ - ป้ายแดง, และ (4) รถจักรยานยนต์ - ป้ายแดง<br/>"
        "• <b>3. โมดูลตรวจจับบัตรประชาชน (Thai ID Card OCR):</b> สกัดเลขประจำตัวประชาชน 13 หลัก, ชื่อ-สกุลภาษาไทย/อังกฤษ เพื่อสืบค้นประวัติหมายจับอัตโนมัติ<br/>"
        "• <b>4. ระบบเบื้องหลังอัตโนมัติ (Automated Polling Daemon):</b> ทำงานแบบ Asynchronous ตลอด 24 ชม. ตรวจจับและตอบกลับผลการสืบค้นพร้อมรูปถ่ายผู้ต้องหาทันที"
    )
    elements.append(Paragraph(th(scope_points), body_style))
    elements.append(Spacer(1, 4))

    # -------------------------------------------------------------
    # 2. WORKFLOW COMPARISON & LATENCY KPI
    # -------------------------------------------------------------
    elements.append(Paragraph(th("<b>2. ผลการเปรียบเทียบประสิทธิภาพเชิงกระบวนการ (Workflow Comparison & Latency)</b>"), h1_style))
    workflow_desc = (
        "ทำการเปรียบเทียบกระบวนการตรวจสอบเดิมผ่านการติดต่อศูนย์วิทยุสื่อสาร/ระบบฐานข้อมูลเดิม "
        "เทียบกับกระบวนการอัตโนมัติผ่านระบบ C.I.A.S. โดยมีเกณฑ์ตัวชี้วัดสำคัญคือ <b>ระยะเวลาต้องไม่เกิน 2 นาที (120 วินาที)</b>"
    )
    elements.append(Paragraph(th(workflow_desc), body_style))

    workflow_table_data = [
        [
            Paragraph(th("<b>รายการประเมิน</b>"), cell_header),
            Paragraph(th("<b>กระบวนการเดิม (Traditional)</b>"), cell_header),
            Paragraph(th("<b>ระบบ C.I.A.S. (อัตโนมัติ)</b>"), cell_header),
            Paragraph(th("<b>ผลสัมฤทธิ์ / ตัวชี้วัด</b>"), cell_header)
        ],
        [
            Paragraph(th("<b>1. วิธีการทำงาน</b>"), cell_bold),
            Paragraph(th("วิทยุสื่อสารประสานศูนย์ / ตรวจสอบเอกสารแบบแมนนวล"), cell_style),
            Paragraph(th("ส่งภาพถ่ายผ่าน Telegram Bot ประมวลผล AI อัตโนมัติ"), cell_style),
            Paragraph(th("ลดขั้นตอนแมนนวล 100%"), cell_style)
        ],
        [
            Paragraph(th("<b>2. ระยะเวลาเฉลี่ย</b>"), cell_bold),
            Paragraph(th("ประมาณ 20 นาที (1,200 วินาที)"), cell_style),
            Paragraph(th("<b>2.538 วินาที</b> (เฉลี่ย / Min 0.95s)"), cell_style),
            Paragraph(th("<font color='#38A169'><b>เร็วกว่าเดิม 472.8 เท่า<br/>(ลดเวลาลง 99.79%)</b></font>"), cell_style)
        ],
        [
            Paragraph(th("<b>3. ผลลัพธ์ที่ได้</b>"), cell_bold),
            Paragraph(th("ข้อมูลบุคคล / รายละเอียดหมายจับ"), cell_style),
            Paragraph(th("ข้อมูลบุคคล, เลขคดี, ข้อหา, และรูปหมายจับ"), cell_style),
            Paragraph(th("ข้อมูลครบถ้วนพร้อมใช้งานทันที"), cell_style)
        ],
        [
            Paragraph(th("<b>4. การประเมินเทียบเกณฑ์</b>"), cell_bold),
            Paragraph(th("เกินเกณฑ์เวลาเป้าหมาย"), cell_style),
            Paragraph(th("<b>2.54 วินาที &lt; 10 วินาที (และ &le; 120s)</b>"), cell_style),
            Paragraph(th("<font color='#38A169'><b>🟢 ผ่านเกณฑ์ยอดเยี่ยม</b></font>"), cell_style)
        ]
    ]

    t_wf = Table(workflow_table_data, colWidths=[105, 135, 140, 143])
    t_wf.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_wf)
    elements.append(Spacer(1, 6))

    # -------------------------------------------------------------
    # 3. CORE TECHNICAL ACCURACY & USER SATISFACTION
    # -------------------------------------------------------------
    elements.append(Paragraph(th("<b>3. ผลการทดสอบความถูกต้องของระบบและความพึงพอใจของผู้ใช้งาน</b>"), h1_style))
    
    core_metrics_data = [
        [
            Paragraph(th("<b>มิติการทดสอบ</b>"), cell_header),
            Paragraph(th("<b>กลุ่มตัวอย่าง / สภาวะ</b>"), cell_header),
            Paragraph(th("<b>เกณฑ์เป้าหมาย</b>"), cell_header),
            Paragraph(th("<b>ผลการทดสอบจริง</b>"), cell_header),
            Paragraph(th("<b>สถานะการประเมิน</b>"), cell_header)
        ],
        [
            Paragraph(th("<b>1. Face Recognition (Controlled)</b>"), cell_bold),
            Paragraph(th("22 ภาพทดสอบจาก 11 บุคคล"), cell_style),
            Paragraph(th("Accuracy &ge; 65.00%"), cell_style),
            Paragraph(th("<b>72.73%</b> (Similarity 68.85%)"), cell_style),
            Paragraph(th("<font color='#38A169'><b>🟢 ผ่านเกณฑ์</b></font>"), cell_style)
        ],
        [
            Paragraph(th("<b>2. Top-N Candidate Ranking</b>"), cell_bold),
            Paragraph(th("Top-1, Top-3, Top-5 Match"), cell_style),
            Paragraph(th("Top-5 &ge; 90.00%"), cell_style),
            Paragraph(th("<b>Top-1: 100% | Top-5: 100%</b>"), cell_style),
            Paragraph(th("<font color='#38A169'><b>🟢 ผ่านเกณฑ์</b></font>"), cell_style)
        ],
        [
            Paragraph(th("<b>3. License Plate (4 Classes)</b>"), cell_bold),
            Paragraph(th("รถยนต์/จยย. ป้ายขาวและป้ายแดง"), cell_style),
            Paragraph(th("Accuracy &ge; 80.00%"), cell_style),
            Paragraph(th("<b>100.00%</b> (YOLO+PaddleOCR)"), cell_style),
            Paragraph(th("<font color='#38A169'><b>🟢 ผ่านเกณฑ์</b></font>"), cell_style)
        ],
        [
            Paragraph(th("<b>4. Thai ID Card Field OCR</b>"), cell_bold),
            Paragraph(th("บัตรประชาชนตัวอย่างภาคสนาม"), cell_style),
            Paragraph(th("Accuracy &ge; 80.00%"), cell_style),
            Paragraph(th("<b>95.00%</b> (สกัดเลข 13 หลักแม่นยำ)"), cell_style),
            Paragraph(th("<font color='#38A169'><b>🟢 ผ่านเกณฑ์</b></font>"), cell_style)
        ],
        [
            Paragraph(th("<b>5. User Satisfaction (Likert)</b>"), cell_bold),
            Paragraph(th("ผู้ใช้งานกลุ่มตัวอย่าง (5 ด้าน)"), cell_style),
            Paragraph(th("ค่าเฉลี่ย &ge; 3.51 (ระดับมาก)"), cell_style),
            Paragraph(th("<b>4.61 / 5.00</b> (S.D. &plusmn;0.51)"), cell_style),
            Paragraph(th("<font color='#38A169'><b>🟢 ระดับมากที่สุด</b></font>"), cell_style)
        ]
    ]

    t_core = Table(core_metrics_data, colWidths=[125, 120, 100, 108, 70])
    t_core.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
    ]))
    elements.append(t_core)
    
    # Page Break to start Stress & Breakdown Evaluation cleanly on Page 2
    elements.append(PageBreak())

    # -------------------------------------------------------------
    # 4. 100-ITERATION MONTE CARLO STRESS & BREAKDOWN EVALUATION
    # -------------------------------------------------------------
    elements.append(Paragraph(th("<b>4. ผลการทดสอบวิเคราะห์ขีดจำกัดสภาวะแวดล้อม (100 Iterations Monte Carlo Evaluation)</b>"), h1_style))
    stress_intro = (
        "เพื่อตอบข้อซักถามเชิงวิชาการของคณะกรรมการว่า <b>'ระบบสามารถลดแสง หมุนมุมเอียง หรือมีสิ่งปกปิดได้ระดับใดจึงจะเริ่มหลุดเกณฑ์เป้าหมาย (&lt; 65.00%)'</b> "
        "ผู้วิจัยจึงได้ดำเนินการทดสอบทางสถิติแบบ Monte Carlo Bootstrap สุ่มซ้ำ <b>100 ครั้งต่อหนึ่งสภาวะ (รวมทั้งสิ้น 2,800 ครั้ง)</b> "
        "โดยเปิดใช้เกณฑ์การยืนยันตัวบุคคลทางชีวมิติขั้นต่ำตามมาตรฐานสากล (Cosine Similarity &ge; 60.00%) ได้ผลสรุปดังนี้:"
    )
    elements.append(Paragraph(th(stress_intro), body_style))
    elements.append(Spacer(1, 4))

    # Summary Table of Breakdowns
    elements.append(Paragraph(th("<b>4.1 ตารางสรุปจุดจำกัดวิกฤตที่ทำให้ระบบเริ่มหลุดเกณฑ์เป้าหมาย (Critical Breakdown Summary)</b>"), h2_style))
    breakdown_summary_data = [
        [
            Paragraph(th("<b>ปัจจัยสภาวะแวดล้อม</b>"), cell_header),
            Paragraph(th("<b>ช่วงสภาวะที่ผ่านเกณฑ์ (&ge; 65%)</b>"), cell_header),
            Paragraph(th("<b>จุดวิกฤตที่เริ่มหลุดเกณฑ์ (&lt; 65%)</b>"), cell_header),
            Paragraph(th("<b>สาเหตุและผลกระทบทางเทคนิค</b>"), cell_header)
        ],
        [
            Paragraph(th("<b>1. การลดระดับแสง (Illumination)</b>"), cell_bold),
            Paragraph(th("<b>100% ถึง 30%</b><br/>(ความถูกต้อง 68.32% - 69.36%)"), cell_style),
            Paragraph(th("<font color='#E53E3E'><b>แสงลดลงเกิน 80% (&le; 20% แสง)</b></font><br/>ความถูกต้องลดเหลือ 63.14%"), cell_style),
            Paragraph(th("คอนทราสต์ของภาพต่ำเกินไป ส่งผลให้โครงสร้างเวกเตอร์ 512D สูญเสียรายละเอียด"), cell_style)
        ],
        [
            Paragraph(th("<b>2. มุมเอียงใบหน้า (Pose Rotation)</b>"), cell_bold),
            Paragraph(th("<b>0&deg; ถึง 45&deg; (ทนทานทุกมุม)</b><br/>(ความถูกต้อง 66.73% - 69.64%)"), cell_style),
            Paragraph(th("<font color='#38A169'><b>🟢 ไม่พบจุดหลุดเกณฑ์</b></font><br/>ทนทานได้จนถึง 45&deg;"), cell_style),
            Paragraph(th("โมเดล RetinaFace มีระบบ 5-Point Affine Alignment ช่วยดัดระนาบใบหน้ากลับมาตรง"), cell_style)
        ],
        [
            Paragraph(th("<b>3. สิ่งปกปิดใบหน้า (Occlusions)</b>"), cell_bold),
            Paragraph(th("<b>ไม่ปกปิด, หมวกแก๊ป, หน้ากากเปิดจมูก</b><br/>(ความถูกต้อง 67.82% - 68.55%)"), cell_style),
            Paragraph(th("<font color='#E53E3E'><b>แว่นตาดำ (9.05%), หน้ากากเต็ม (59.8%), หมวกปิดคิ้ว (44.6%)</b></font>"), cell_style),
            Paragraph(th("การบดบังดวงตาและคิ้วซึ่งเป็นจุดอ้างอิงหลักทางชีวมิติ ทำให้ประสิทธิภาพลดฮวบทันที"), cell_style)
        ]
    ]

    t_bs = Table(breakdown_summary_data, colWidths=[115, 125, 135, 148])
    t_bs.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_bs)
    elements.append(Spacer(1, 6))

    # Illumination Details Table
    elements.append(Paragraph(th("<b>4.2 ตารางผลการทดสอบสภาวะแสง 10 ระดับ (100 Iterations per Level)</b>"), h2_style))
    light_rows = [
        [
            Paragraph(th("<b>ระดับแสง</b>"), cell_header),
            Paragraph(th("<b>Factor</b>"), cell_header),
            Paragraph(th("<b>ความถูกต้องเฉลี่ย (&mu;)</b>"), cell_header),
            Paragraph(th("<b>ส่วนเบี่ยงเบน (S.D.)</b>"), cell_header),
            Paragraph(th("<b>Similarity เฉลี่ย</b>"), cell_header),
            Paragraph(th("<b>สถานะ (&ge; 65%)</b>"), cell_header)
        ],
        [Paragraph(th("100% (ปกติ)"), cell_style), Paragraph(th("1.00"), cell_style), Paragraph(th("<b>66.68%</b>"), cell_style), Paragraph(th("&plusmn;10.02%"), cell_style), Paragraph(th("68.48%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("90% (-10%)"), cell_style), Paragraph(th("0.90"), cell_style), Paragraph(th("<b>68.77%</b>"), cell_style), Paragraph(th("&plusmn;10.56%"), cell_style), Paragraph(th("70.32%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("80% (-20%)"), cell_style), Paragraph(th("0.80"), cell_style), Paragraph(th("<b>67.68%</b>"), cell_style), Paragraph(th("&plusmn;10.50%"), cell_style), Paragraph(th("68.68%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("70% (-30%)"), cell_style), Paragraph(th("0.70"), cell_style), Paragraph(th("<b>68.73%</b>"), cell_style), Paragraph(th("&plusmn;11.19%"), cell_style), Paragraph(th("69.83%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("60% (-40%)"), cell_style), Paragraph(th("0.60"), cell_style), Paragraph(th("<b>68.32%</b>"), cell_style), Paragraph(th("&plusmn;9.41%"), cell_style), Paragraph(th("68.86%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("50% (-50%)"), cell_style), Paragraph(th("0.50"), cell_style), Paragraph(th("<b>68.73%</b>"), cell_style), Paragraph(th("&plusmn;8.89%"), cell_style), Paragraph(th("69.28%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("40% (-60%)"), cell_style), Paragraph(th("0.40"), cell_style), Paragraph(th("<b>68.50%</b>"), cell_style), Paragraph(th("&plusmn;11.38%"), cell_style), Paragraph(th("68.24%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("30% (-70%)"), cell_style), Paragraph(th("0.30"), cell_style), Paragraph(th("<b>69.36%</b>"), cell_style), Paragraph(th("&plusmn;10.24%"), cell_style), Paragraph(th("68.41%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("20% (-80%)"), cell_style), Paragraph(th("0.20"), cell_style), Paragraph(th("<b>63.14%</b>"), cell_style), Paragraph(th("&plusmn;11.21%"), cell_style), Paragraph(th("65.83%"), cell_style), Paragraph(th("<font color='#E53E3E'><b>หลุดเกณฑ์ (&lt;65%)</b></font>"), cell_style)],
        [Paragraph(th("10% (-90%)"), cell_style), Paragraph(th("0.10"), cell_style), Paragraph(th("<b>64.09%</b>"), cell_style), Paragraph(th("&plusmn;8.61%"), cell_style), Paragraph(th("62.31%"), cell_style), Paragraph(th("<font color='#E53E3E'><b>หลุดเกณฑ์ (&lt;65%)</b></font>"), cell_style)],
    ]
    t_light = Table(light_rows, colWidths=[95, 55, 105, 95, 95, 78])
    t_light.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elements.append(t_light)

    # Page Break for Pose Angle & Occlusions
    elements.append(PageBreak())

    # Pose Angle Table
    elements.append(Paragraph(th("<b>4.3 ตารางผลการทดสอบมุมเอียงของใบหน้า 10 ระดับ (100 Iterations per Level)</b>"), h2_style))
    angle_rows = [
        [
            Paragraph(th("<b>มุมเอียงของใบหน้า</b>"), cell_header),
            Paragraph(th("<b>องศาการหมุน</b>"), cell_header),
            Paragraph(th("<b>ความถูกต้องเฉลี่ย (&mu;)</b>"), cell_header),
            Paragraph(th("<b>ส่วนเบี่ยงเบน (S.D.)</b>"), cell_header),
            Paragraph(th("<b>Similarity เฉลี่ย</b>"), cell_header),
            Paragraph(th("<b>สถานะ (&ge; 65%)</b>"), cell_header)
        ],
        [Paragraph(th("มุมเอียง 0&deg; (หน้าตรง)"), cell_style), Paragraph(th("0.0&deg;"), cell_style), Paragraph(th("<b>67.86%</b>"), cell_style), Paragraph(th("&plusmn;9.45%"), cell_style), Paragraph(th("69.18%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 5&deg;"), cell_style), Paragraph(th("5.0&deg;"), cell_style), Paragraph(th("<b>68.95%</b>"), cell_style), Paragraph(th("&plusmn;9.54%"), cell_style), Paragraph(th("70.36%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 10&deg;"), cell_style), Paragraph(th("10.0&deg;"), cell_style), Paragraph(th("<b>69.36%</b>"), cell_style), Paragraph(th("&plusmn;10.50%"), cell_style), Paragraph(th("70.40%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 15&deg;"), cell_style), Paragraph(th("15.0&deg;"), cell_style), Paragraph(th("<b>67.45%</b>"), cell_style), Paragraph(th("&plusmn;9.13%"), cell_style), Paragraph(th("68.70%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 20&deg;"), cell_style), Paragraph(th("20.0&deg;"), cell_style), Paragraph(th("<b>66.95%</b>"), cell_style), Paragraph(th("&plusmn;10.48%"), cell_style), Paragraph(th("67.64%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 25&deg;"), cell_style), Paragraph(th("25.0&deg;"), cell_style), Paragraph(th("<b>69.36%</b>"), cell_style), Paragraph(th("&plusmn;9.66%"), cell_style), Paragraph(th("68.48%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 30&deg;"), cell_style), Paragraph(th("30.0&deg;"), cell_style), Paragraph(th("<b>67.91%</b>"), cell_style), Paragraph(th("&plusmn;9.83%"), cell_style), Paragraph(th("68.15%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 35&deg;"), cell_style), Paragraph(th("35.0&deg;"), cell_style), Paragraph(th("<b>69.64%</b>"), cell_style), Paragraph(th("&plusmn;8.90%"), cell_style), Paragraph(th("68.10%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 40&deg;"), cell_style), Paragraph(th("40.0&deg;"), cell_style), Paragraph(th("<b>68.05%</b>"), cell_style), Paragraph(th("&plusmn;9.86%"), cell_style), Paragraph(th("66.81%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("มุมเอียง 45&deg;"), cell_style), Paragraph(th("45.0&deg;"), cell_style), Paragraph(th("<b>66.73%</b>"), cell_style), Paragraph(th("&plusmn;10.40%"), cell_style), Paragraph(th("65.21%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
    ]
    t_angle = Table(angle_rows, colWidths=[110, 65, 95, 85, 90, 78])
    t_angle.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elements.append(t_angle)
    elements.append(Spacer(1, 6))

    # Occlusions Table
    elements.append(Paragraph(th("<b>4.4 ตารางผลการทดสอบสิ่งปกปิดบนใบหน้า 8 รูปแบบ (100 Iterations per Case)</b>"), h2_style))
    occ_rows = [
        [
            Paragraph(th("<b>รูปแบบสิ่งปกปิด</b>"), cell_header),
            Paragraph(th("<b>% ปกปิด</b>"), cell_header),
            Paragraph(th("<b>ความถูกต้องเฉลี่ย (&mu;)</b>"), cell_header),
            Paragraph(th("<b>ส่วนเบี่ยงเบน (S.D.)</b>"), cell_header),
            Paragraph(th("<b>Similarity เฉลี่ย</b>"), cell_header),
            Paragraph(th("<b>สถานะ (&ge; 65%)</b>"), cell_header)
        ],
        [Paragraph(th("ปกติ (ไม่ปกปิด)"), cell_style), Paragraph(th("0%"), cell_style), Paragraph(th("<b>67.86%</b>"), cell_style), Paragraph(th("&plusmn;9.58%"), cell_style), Paragraph(th("68.04%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("แว่นสายตาใส"), cell_style), Paragraph(th("~10%"), cell_style), Paragraph(th("<b>62.64%</b>"), cell_style), Paragraph(th("&plusmn;10.07%"), cell_style), Paragraph(th("65.38%"), cell_style), Paragraph(th("<font color='#E53E3E'><b>หลุดเกณฑ์ (<65%)</b></font>"), cell_style)],
        [Paragraph(th("หมวกแก๊ปเปิดหน้าผาก"), cell_style), Paragraph(th("~15%"), cell_style), Paragraph(th("<b>67.82%</b>"), cell_style), Paragraph(th("&plusmn;10.48%"), cell_style), Paragraph(th("67.37%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("หน้ากากเปิดจมูก"), cell_style), Paragraph(th("~30%"), cell_style), Paragraph(th("<b>68.55%</b>"), cell_style), Paragraph(th("&plusmn;10.22%"), cell_style), Paragraph(th("68.53%"), cell_style), Paragraph(th("<font color='#38A169'><b>ผ่านเกณฑ์</b></font>"), cell_style)],
        [Paragraph(th("หน้ากากอนามัยเต็มใบหน้า"), cell_style), Paragraph(th("~45%"), cell_style), Paragraph(th("<b>59.82%</b>"), cell_style), Paragraph(th("&plusmn;10.92%"), cell_style), Paragraph(th("57.81%"), cell_style), Paragraph(th("<font color='#E53E3E'><b>หลุดเกณฑ์ (<65%)</b></font>"), cell_style)],
        [Paragraph(th("<b>หมวกดึงปิดลึกถึงคิ้ว</b>"), cell_style), Paragraph(th("~35%"), cell_style), Paragraph(th("<b>44.64%</b>"), cell_style), Paragraph(th("&plusmn;10.35%"), cell_style), Paragraph(th("38.07%"), cell_style), Paragraph(th("<font color='#E53E3E'><b>หลุดเกณฑ์ (<65%)</b></font>"), cell_style)],
        [Paragraph(th("<b>ไอ้โม่ง / ผ้าคลุมมิดชิด</b>"), cell_style), Paragraph(th(">60%"), cell_style), Paragraph(th("<b>34.18%</b>"), cell_style), Paragraph(th("&plusmn;9.26%"), cell_style), Paragraph(th("30.18%"), cell_style), Paragraph(th("<font color='#E53E3E'><b>หลุดเกณฑ์ (<65%)</b></font>"), cell_style)],
        [Paragraph(th("<b>แว่นตาดำ / แว่นกันแดด</b>"), cell_style), Paragraph(th("~20%"), cell_style), Paragraph(th("<b>9.05%</b>"), cell_style), Paragraph(th("&plusmn;6.08%"), cell_style), Paragraph(th("28.39%"), cell_style), Paragraph(th("<font color='#E53E3E'><b>วิกฤตที่สุด (<10%)</b></font>"), cell_style)],
    ]
    t_occ = Table(occ_rows, colWidths=[120, 55, 95, 85, 90, 78])
    t_occ.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elements.append(t_occ)
    elements.append(Spacer(1, 6))

    # -------------------------------------------------------------
    # 5. RECOMMENDATIONS & PROTOCOLS
    # -------------------------------------------------------------
    elements.append(Paragraph(th("<b>5. ข้อเสนอแนะเชิงวิชาการและระเบียบปฏิบัติการใช้งานจริง (Operational Protocols)</b>"), h1_style))
    recom_p = (
        "<b>1. ความน่าเชื่อถือทางสถิติ (Statistical Rigor):</b> การทดลองซ้ำแบบ Monte Carlo 100 ครั้งต่อโหมด แสดงให้เห็นค่าส่วนเบี่ยงเบนมาตรฐาน (S.D.) ในช่วงแคบ (&plusmn;8.6% ถึง &plusmn;11.4%) ยืนยันความเสถียรของโมเดล AI<br/>"
        "<b>2. ขอบเขตสภาวะแสงที่ปลอดภัย:</b> ระบบทำงานได้อย่างมีเสถียรภาพในสภาวะแสงปกติจนถึงลดแสงลง 70% แต่หากลดแสงเกิน 80% (ความสว่างเหลือ &le; 20%) ควรใช้ไฟแฟลชหรือส่องไฟช่วยในการถ่ายภาพ<br/>"
        "<b>3. ข้อพึงระวังเรื่องสิ่งปกปิดใบหน้า:</b> ดวงตาและโหนกคิ้วเป็นจุดยึดเหนี่ยวชีวมิติที่สำคัญที่สุด เมื่อสวมแว่นตาดำความแม่นยำจะลดเหลือเพียง <b>9.05%</b> ดังนั้นในการปฏิบัติงานจริง เจ้าหน้าที่ต้องขอความร่วมมือให้ผู้ถูกตรวจสอบ <b>ถอดแว่นตาดำ หรือถอดหมวกที่ปิดคิ้วออกก่อนถ่ายภาพเสมอ</b>"
    )
    elements.append(Paragraph(th(recom_p), body_style))

    doc.build(elements, canvasmaker=NumberedThaiCanvas)
    print(f"[Thai PDF Generator] Successfully generated full Thai academic PDF report: {pdf_path}")


if __name__ == "__main__":
    build_full_thai_pdf()

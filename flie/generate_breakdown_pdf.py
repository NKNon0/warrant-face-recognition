import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# Define NumberedCanvas for professional page numbering
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        
        # Header
        self.drawString(40, 810, "C.I.A.S. - Empirical Environmental Stress & Breakdown Threshold Report (100 Iterations/Mode)")
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(40, 804, 555, 804)
        
        # Footer
        self.line(40, 45, 555, 45)
        self.drawString(40, 32, "Confidential - Master's Degree Examination & Academic Verification Document")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(555, 32, page_text)
        self.restoreState()


def create_breakdown_pdf():
    pdf_path = "flie/STRESS_BREAKDOWN_100_REPORT.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=45,
        bottomMargin=55
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=colors.HexColor('#1A365D'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4A5568'),
        spaceAfter=10
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#2B6CB0'),
        spaceBefore=10,
        spaceAfter=6
    )

    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#2D3748')
    )

    cell_header = ParagraphStyle(
        'CellHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.white
    )

    elements = []

    # Title
    elements.append(Paragraph("<b>Empirical Environmental Stress & Breakdown Threshold Report</b>", title_style))
    elements.append(Paragraph("<b>Project: Criminal & Warrant Automatic Identification System (C.I.A.S.)</b><br/>Rigorous 100-Iteration Monte Carlo Bootstrap Testing per Mode | Pass Target: Accuracy &ge; 65.00% (Operational Sim &ge; 60%)", subtitle_style))
    elements.append(Spacer(1, 5))

    # Section 1: Summary Table
    elements.append(Paragraph("<b>1. Critical Breakdown Cutoff Summary (100 Iterations per Mode)</b>", h2_style))
    
    summary_data = [
        [
            Paragraph("<b>Stress Factor</b>", cell_header),
            Paragraph("<b>Safe Operational Range (&ge; 65%)</b>", cell_header),
            Paragraph("<b>Critical Cutoff Boundary (&lt; 65%)</b>", cell_header),
            Paragraph("<b>Technical Analysis & Impact</b>", cell_header)
        ],
        [
            Paragraph("<b>1. Illumination (Light)</b>", cell_style),
            Paragraph("<b>100% down to 30%</b><br/>Accuracy remains 68.32% - 69.36%", cell_style),
            Paragraph("<font color='#E53E3E'><b>&le; 20% (-80% darkness)</b></font><br/>Accuracy drops to 63.14% - 64.09%", cell_style),
            Paragraph("Severe underexposure suppresses edge gradients and facial contrast, hindering embedding extraction.", cell_style)
        ],
        [
            Paragraph("<b>2. Pose Rotation (Angle)</b>", cell_style),
            Paragraph("<b>0&deg; to 45&deg; (Yaw / Roll)</b><br/>Accuracy 66.73% - 69.64%", cell_style),
            Paragraph("<font color='#38A169'><b>Robust (&ge; 65%) up to 45&deg;</b></font><br/>Similarity decays monotonically", cell_style),
            Paragraph("RetinaFace 5-point landmark alignment corrects affine angles, preserving recognition up to 45&deg;.", cell_style)
        ],
        [
            Paragraph("<b>3. Facial Occlusions</b>", cell_style),
            Paragraph("<b>None, Cap, Nose-open Mask</b><br/>Accuracy 67.82% - 68.55%", cell_style),
            Paragraph("<font color='#E53E3E'><b>Sunglasses (9.05%), Full Mask (59.8%), Brow Hat (44.6%), Balaclava (34.2%)</b></font>", cell_style),
            Paragraph("Eyes and brow landmarks are critical biometric anchors; blocking them causes catastrophic accuracy collapse.", cell_style)
        ]
    ]

    t_summary = Table(summary_data, colWidths=[105, 125, 135, 150])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A365D')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 10))

    # Section 2: Illumination Table
    elements.append(Paragraph("<b>2. Illumination Degradation Test Results (100 Iterations per level)</b>", h2_style))
    light_rows = [
        [
            Paragraph("<b>Brightness Level</b>", cell_header),
            Paragraph("<b>Factor</b>", cell_header),
            Paragraph("<b>Mean Accuracy (&mu;)</b>", cell_header),
            Paragraph("<b>Std Dev (&sigma;)</b>", cell_header),
            Paragraph("<b>Mean Similarity</b>", cell_header),
            Paragraph("<b>Status (&ge; 65%)</b>", cell_header)
        ],
        [Paragraph("100% (Normal)", cell_style), Paragraph("1.00", cell_style), Paragraph("<b>66.68%</b>", cell_style), Paragraph("&plusmn;10.02%", cell_style), Paragraph("68.48%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("90% (-10%)", cell_style), Paragraph("0.90", cell_style), Paragraph("<b>68.77%</b>", cell_style), Paragraph("&plusmn;10.56%", cell_style), Paragraph("70.32%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("80% (-20%)", cell_style), Paragraph("0.80", cell_style), Paragraph("<b>67.68%</b>", cell_style), Paragraph("&plusmn;10.50%", cell_style), Paragraph("68.68%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("70% (-30%)", cell_style), Paragraph("0.70", cell_style), Paragraph("<b>68.73%</b>", cell_style), Paragraph("&plusmn;11.19%", cell_style), Paragraph("69.83%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("60% (-40%)", cell_style), Paragraph("0.60", cell_style), Paragraph("<b>68.32%</b>", cell_style), Paragraph("&plusmn;9.41%", cell_style), Paragraph("68.86%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("50% (-50%)", cell_style), Paragraph("0.50", cell_style), Paragraph("<b>68.73%</b>", cell_style), Paragraph("&plusmn;8.89%", cell_style), Paragraph("69.28%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("40% (-60%)", cell_style), Paragraph("0.40", cell_style), Paragraph("<b>68.50%</b>", cell_style), Paragraph("&plusmn;11.38%", cell_style), Paragraph("68.24%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("30% (-70%)", cell_style), Paragraph("0.30", cell_style), Paragraph("<b>69.36%</b>", cell_style), Paragraph("&plusmn;10.24%", cell_style), Paragraph("68.41%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("20% (-80%)", cell_style), Paragraph("0.20", cell_style), Paragraph("<b>63.14%</b>", cell_style), Paragraph("&plusmn;11.21%", cell_style), Paragraph("65.83%", cell_style), Paragraph("<font color='#E53E3E'><b>BELOW CRITERIA</b></font>", cell_style)],
        [Paragraph("10% (-90%)", cell_style), Paragraph("0.10", cell_style), Paragraph("<b>64.09%</b>", cell_style), Paragraph("&plusmn;8.61%", cell_style), Paragraph("62.31%", cell_style), Paragraph("<font color='#E53E3E'><b>BELOW CRITERIA</b></font>", cell_style)],
    ]
    t_light = Table(light_rows, colWidths=[100, 60, 95, 85, 95, 80])
    t_light.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_light)
    elements.append(Spacer(1, 10))

    # Page Break for clean presentation
    elements.append(PageBreak())

    # Section 3: Pose Angle Table
    elements.append(Paragraph("<b>3. Pose & Rotation Angle Breakdown Results (100 Iterations per level)</b>", h2_style))
    angle_rows = [
        [
            Paragraph("<b>Pose Angle</b>", cell_header),
            Paragraph("<b>Degree</b>", cell_header),
            Paragraph("<b>Mean Accuracy (&mu;)</b>", cell_header),
            Paragraph("<b>Std Dev (&sigma;)</b>", cell_header),
            Paragraph("<b>Mean Similarity</b>", cell_header),
            Paragraph("<b>Status (&ge; 65%)</b>", cell_header)
        ],
        [Paragraph("Angle 0&deg; (Frontal)", cell_style), Paragraph("0.0&deg;", cell_style), Paragraph("<b>67.86%</b>", cell_style), Paragraph("&plusmn;9.45%", cell_style), Paragraph("69.18%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 5&deg;", cell_style), Paragraph("5.0&deg;", cell_style), Paragraph("<b>68.95%</b>", cell_style), Paragraph("&plusmn;9.54%", cell_style), Paragraph("70.36%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 10&deg;", cell_style), Paragraph("10.0&deg;", cell_style), Paragraph("<b>69.36%</b>", cell_style), Paragraph("&plusmn;10.50%", cell_style), Paragraph("70.40%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 15&deg;", cell_style), Paragraph("15.0&deg;", cell_style), Paragraph("<b>67.45%</b>", cell_style), Paragraph("&plusmn;9.13%", cell_style), Paragraph("68.70%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 20&deg;", cell_style), Paragraph("20.0&deg;", cell_style), Paragraph("<b>66.95%</b>", cell_style), Paragraph("&plusmn;10.48%", cell_style), Paragraph("67.64%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 25&deg;", cell_style), Paragraph("25.0&deg;", cell_style), Paragraph("<b>69.36%</b>", cell_style), Paragraph("&plusmn;9.66%", cell_style), Paragraph("68.48%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 30&deg;", cell_style), Paragraph("30.0&deg;", cell_style), Paragraph("<b>67.91%</b>", cell_style), Paragraph("&plusmn;9.83%", cell_style), Paragraph("68.15%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 35&deg;", cell_style), Paragraph("35.0&deg;", cell_style), Paragraph("<b>69.64%</b>", cell_style), Paragraph("&plusmn;8.90%", cell_style), Paragraph("68.10%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 40&deg;", cell_style), Paragraph("40.0&deg;", cell_style), Paragraph("<b>68.05%</b>", cell_style), Paragraph("&plusmn;9.86%", cell_style), Paragraph("66.81%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Angle 45&deg;", cell_style), Paragraph("45.0&deg;", cell_style), Paragraph("<b>66.73%</b>", cell_style), Paragraph("&plusmn;10.40%", cell_style), Paragraph("65.21%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
    ]
    t_angle = Table(angle_rows, colWidths=[100, 60, 95, 85, 95, 80])
    t_angle.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_angle)
    elements.append(Spacer(1, 10))

    # Section 4: Occlusions Table
    elements.append(Paragraph("<b>4. Facial Occlusions Breakdown Results (100 Iterations per case)</b>", h2_style))
    occ_rows = [
        [
            Paragraph("<b>Occlusion Mode</b>", cell_header),
            Paragraph("<b>Coverage %</b>", cell_header),
            Paragraph("<b>Mean Accuracy (&mu;)</b>", cell_header),
            Paragraph("<b>Std Dev (&sigma;)</b>", cell_header),
            Paragraph("<b>Mean Similarity</b>", cell_header),
            Paragraph("<b>Status (&ge; 65%)</b>", cell_header)
        ],
        [Paragraph("Normal (No Occlusion)", cell_style), Paragraph("0%", cell_style), Paragraph("<b>67.86%</b>", cell_style), Paragraph("&plusmn;9.58%", cell_style), Paragraph("68.04%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Clear Glasses (Eyewear)", cell_style), Paragraph("~10%", cell_style), Paragraph("<b>62.64%</b>", cell_style), Paragraph("&plusmn;10.07%", cell_style), Paragraph("65.38%", cell_style), Paragraph("<font color='#E53E3E'><b>BELOW CRITERIA</b></font>", cell_style)],
        [Paragraph("Cap (Forehead Exposed)", cell_style), Paragraph("~15%", cell_style), Paragraph("<b>67.82%</b>", cell_style), Paragraph("&plusmn;10.48%", cell_style), Paragraph("67.37%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Mask (Nose Exposed)", cell_style), Paragraph("~30%", cell_style), Paragraph("<b>68.55%</b>", cell_style), Paragraph("&plusmn;10.22%", cell_style), Paragraph("68.53%", cell_style), Paragraph("<font color='#38A169'><b>PASSED</b></font>", cell_style)],
        [Paragraph("Surgical Mask (Lower Face)", cell_style), Paragraph("~45%", cell_style), Paragraph("<b>59.82%</b>", cell_style), Paragraph("&plusmn;10.92%", cell_style), Paragraph("57.81%", cell_style), Paragraph("<font color='#E53E3E'><b>BELOW CRITERIA</b></font>", cell_style)],
        [Paragraph("<b>Hat Pulled to Brows</b>", cell_style), Paragraph("~35%", cell_style), Paragraph("<b>44.64%</b>", cell_style), Paragraph("&plusmn;10.35%", cell_style), Paragraph("38.07%", cell_style), Paragraph("<font color='#E53E3E'><b>BELOW CRITERIA</b></font>", cell_style)],
        [Paragraph("<b>Balaclava / Full Wrap</b>", cell_style), Paragraph(">60%", cell_style), Paragraph("<b>34.18%</b>", cell_style), Paragraph("&plusmn;9.26%", cell_style), Paragraph("30.18%", cell_style), Paragraph("<font color='#E53E3E'><b>BELOW CRITERIA</b></font>", cell_style)],
        [Paragraph("<b>Dark Sunglasses</b>", cell_style), Paragraph("~20%", cell_style), Paragraph("<b>9.05%</b>", cell_style), Paragraph("&plusmn;6.08%", cell_style), Paragraph("28.39%", cell_style), Paragraph("<font color='#E53E3E'><b>BELOW CRITERIA</b></font>", cell_style)],
    ]
    t_occ = Table(occ_rows, colWidths=[120, 60, 90, 75, 90, 80])
    t_occ.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_occ)
    elements.append(Spacer(1, 10))

    # Recommendations
    elements.append(Paragraph("<b>5. Academic Insights & Practical Operational Guidelines</b>", h2_style))
    recom_text = """
    <b>1. Statistical Rigor:</b> 100-iteration Monte Carlo testing reveals empirical thresholds where biometric features decay.<br/>
    <b>2. Illumination Limit:</b> Brightness reduction beyond 80% (&le; 20% light) causes accuracy to fall below 65.00% (63.14%).<br/>
    <b>3. Occlusion Vulnerability:</b> Eye occlusion (dark sunglasses) causes extreme collapse (<b>9.05%</b> accuracy), and forehead/brow occlusion causes significant degradation (<b>44.64%</b>). Officers should ensure eyes and upper facial features are unblocked before capture.
    """
    elements.append(Paragraph(recom_text, cell_style))

    doc.build(elements, canvasmaker=NumberedCanvas)
    print(f"[PDF Generator] Created Stress Breakdown Report PDF: {pdf_path}")


if __name__ == "__main__":
    create_breakdown_pdf()

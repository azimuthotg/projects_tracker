"""
ReportLab PDF utilities — Thai font registration + common helpers.
"""
import os
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Font Registration ────────────────────────────────────────────────────────

FONTS_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts')

_FONTS_REGISTERED = False


def _register_fonts():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    try:
        pdfmetrics.registerFont(TTFont('THSarabunNew', os.path.join(FONTS_DIR, 'THSarabunNew.ttf')))
        pdfmetrics.registerFont(TTFont('THSarabunNew-Bold', os.path.join(FONTS_DIR, 'THSarabunNew_Bold.ttf')))
        pdfmetrics.registerFont(TTFont('THSarabunNew-Italic', os.path.join(FONTS_DIR, 'THSarabunNew_Italic.ttf')))
        pdfmetrics.registerFont(TTFont('THSarabunNew-BoldItalic', os.path.join(FONTS_DIR, 'THSarabunNew_BoldItalic.ttf')))
        pdfmetrics.registerFontFamily(
            'THSarabunNew',
            normal='THSarabunNew',
            bold='THSarabunNew-Bold',
            italic='THSarabunNew-Italic',
            boldItalic='THSarabunNew-BoldItalic',
        )
        _FONTS_REGISTERED = True
    except Exception as e:
        # Fall back to Helvetica if font files are missing
        pass


# ── Colour Palette ───────────────────────────────────────────────────────────

C_HEADER_BG  = colors.HexColor('#1e3a5f')   # dark blue
C_HEADER_FG  = colors.white
C_SUBHEAD_BG = colors.HexColor('#dbeafe')   # light blue
C_SUBHEAD_FG = colors.HexColor('#1e3a5f')
C_ALT_ROW    = colors.HexColor('#f8faff')
C_TOTAL_BG   = colors.HexColor('#dbeafe')
C_BORDER     = colors.HexColor('#d1d5db')
C_RED        = colors.HexColor('#dc2626')
C_AMBER      = colors.HexColor('#d97706')
C_EMERALD    = colors.HexColor('#059669')
C_BLUE       = colors.HexColor('#1d4ed8')
C_GRAY       = colors.HexColor('#6b7280')

# ── Style Factory ────────────────────────────────────────────────────────────

def make_styles():
    """Return a dict of ParagraphStyles for the report."""
    _register_fonts()
    base = 'THSarabunNew'

    return {
        'title': ParagraphStyle('title', fontName=f'{base}-Bold', fontSize=16,
                                leading=20, textColor=C_HEADER_FG, alignment=TA_LEFT),
        'subtitle': ParagraphStyle('subtitle', fontName=base, fontSize=11,
                                   leading=14, textColor=colors.HexColor('#bfdbfe'),
                                   alignment=TA_LEFT),
        'org': ParagraphStyle('org', fontName=base, fontSize=9,
                              leading=12, textColor=colors.HexColor('#93c5fd'),
                              alignment=TA_LEFT),
        'body': ParagraphStyle('body', fontName=base, fontSize=10, leading=13),
        'body_r': ParagraphStyle('body_r', fontName=base, fontSize=10,
                                 leading=13, alignment=TA_RIGHT),
        'body_c': ParagraphStyle('body_c', fontName=base, fontSize=10,
                                 leading=13, alignment=TA_CENTER),
        'bold': ParagraphStyle('bold', fontName=f'{base}-Bold', fontSize=10, leading=13),
        'bold_r': ParagraphStyle('bold_r', fontName=f'{base}-Bold', fontSize=10,
                                 leading=13, alignment=TA_RIGHT),
        'small': ParagraphStyle('small', fontName=base, fontSize=9,
                                leading=11, textColor=C_GRAY),
        'small_r': ParagraphStyle('small_r', fontName=base, fontSize=9,
                                  leading=11, textColor=C_GRAY, alignment=TA_RIGHT),
        'th': ParagraphStyle('th', fontName=f'{base}-Bold', fontSize=9,
                             leading=11, textColor=C_HEADER_FG, alignment=TA_CENTER),
        'th_r': ParagraphStyle('th_r', fontName=f'{base}-Bold', fontSize=9,
                               leading=11, textColor=C_HEADER_FG, alignment=TA_RIGHT),
        'td': ParagraphStyle('td', fontName=base, fontSize=9, leading=11),
        'td_r': ParagraphStyle('td_r', fontName=base, fontSize=9,
                               leading=11, alignment=TA_RIGHT),
        'td_c': ParagraphStyle('td_c', fontName=base, fontSize=9,
                               leading=11, alignment=TA_CENTER),
        'td_bold_r': ParagraphStyle('td_bold_r', fontName=f'{base}-Bold', fontSize=9,
                                    leading=11, alignment=TA_RIGHT),
        'td_bold': ParagraphStyle('td_bold', fontName=f'{base}-Bold', fontSize=9, leading=11),
        'footer': ParagraphStyle('footer', fontName=base, fontSize=8,
                                 leading=10, textColor=C_GRAY),
    }


# ── Formatting Helpers ───────────────────────────────────────────────────────

_THAI_MONTHS = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
                'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


def thaidate(d):
    if not d:
        return '—'
    return f"{d.day} {_THAI_MONTHS[d.month]} {d.year + 543}"


def fmt_currency(val):
    """Format number as Thai currency string e.g. 1,234,567.89"""
    try:
        f = float(val or 0)
        return f"{f:,.2f}"
    except Exception:
        return "0.00"


def pct_color(pct):
    """Return colour based on budget usage percentage."""
    if pct >= 90:
        return C_RED
    if pct >= 70:
        return C_AMBER
    return C_BLUE


# ── Document Builder ─────────────────────────────────────────────────────────

def build_document(buffer, title, page_size=A4):
    """Create a SimpleDocTemplate for a PDF report."""
    _register_fonts()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=title,
    )
    return doc


def header_block(styles, title_text, subtitle_text='', org_text='สำนักวิทยบริการ มหาวิทยาลัยนครพนม', page_width=None):
    """Return a blue header table for the top of the PDF."""
    from reportlab.platypus import Table, TableStyle
    width = page_width if page_width is not None else A4[0] - 3 * cm

    inner = []
    if org_text:
        inner.append(Paragraph(org_text, styles['org']))
    inner.append(Paragraph(title_text, styles['title']))
    if subtitle_text:
        inner.append(Paragraph(subtitle_text, styles['subtitle']))

    tbl = Table([[inner]], colWidths=[width])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_HEADER_BG),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING',   (0, 0), (-1, -1), 14),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 14),
    ]))
    return tbl


def summary_card_row(styles, cards, page_width=None):
    """Render a row of (label, value, unit) summary cards."""
    if page_width is None:
        page_width = A4[0] - 3 * cm
    n = len(cards)
    col_w = page_width / n
    cells = []
    for label, value, unit in cards:
        cell = [
            Paragraph(label, styles['small']),
            Paragraph(value, ParagraphStyle('cv', fontName='THSarabunNew-Bold',
                                            fontSize=13, leading=16,
                                            textColor=C_HEADER_BG)),
            Paragraph(unit, styles['small']),
        ]
        cells.append(cell)

    tbl = Table([cells], colWidths=[col_w] * n)
    tbl.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('LINEAFTER',     (0, 0), (-2, -1), 0.5, C_BORDER),
        ('BOX',           (0, 0), (-1, -1), 0.5, C_BORDER),
    ]))
    return tbl


def table_header_style(col_count, extra=None):
    """Return base TableStyle commands for a data table."""
    cmds = [
        ('BACKGROUND',    (0, 0), (-1, 0), C_HEADER_BG),
        ('TEXTCOLOR',     (0, 0), (-1, 0), C_HEADER_FG),
        ('FONTNAME',      (0, 0), (-1, 0), 'THSarabunNew-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), 9),
        ('TOPPADDING',    (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('GRID',          (0, 0), (-1, -1), 0.25, C_BORDER),
        ('FONTNAME',      (0, 1), (-1, -1), 'THSarabunNew'),
        ('FONTSIZE',      (0, 1), (-1, -1), 9),
        ('TOPPADDING',    (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]
    if extra:
        cmds.extend(extra)
    return TableStyle(cmds)

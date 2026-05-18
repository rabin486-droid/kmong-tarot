"""
intro_pages.py
===============
일간/주간/월간 PDF 공용 도입 페이지 모듈.

페이지 구성:
- p1: 표지 (식물 수채화 톤, 운세의 정원 로고, 고객 이름, 날짜)
- p2: 목차 + 카드 덱 소개 + 상품 안내 + 구매/상담 링크 (한 페이지에 통합)

다른 make_*.py에서 import 해서 사용:
    from intro_pages import build_cover_page, build_intro_page

제작자: 루밍 (looming)
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
    KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.colors import HexColor

BASE_DIR = Path(__file__).parent.resolve()
IMAGES_DIR = BASE_DIR / 'images'

# 색상 팔레트 (make_daily.py 와 동일)
C = {
    'CREAM':  HexColor('#FDF6EC'),
    'GOLD':   HexColor('#C9963A'),
    'DG':     HexColor('#8B6520'),
    'SAGE':   HexColor('#7A9E7E'),
    'DSG':    HexColor('#6B8F71'),
    'LSG':    HexColor('#EAF2EA'),
    'BROWN':  HexColor('#5C3D2E'),
    'INDIGO': HexColor('#4A4580'),
    'LI':     HexColor('#F0EFF8'),
    'PURPLE': HexColor('#6B4C93'),
    'LP':     HexColor('#F3EEFB'),
    'EARTH':  HexColor('#7A6040'),
    'LE':     HexColor('#F5EFE6'),
    'TEAL':   HexColor('#3D7A8A'),
    'LT':     HexColor('#EBF5F7'),
    'RUST':   HexColor('#C07A5A'),
    'LR':     HexColor('#FDF0EA'),
    'NIGHT':  HexColor('#2C2A4A'),
}


# ============================================================
# 폰트 헬퍼
# ============================================================

def _get_fonts():
    """등록된 한글 폰트 가져오기. 없으면 Helvetica."""
    registered = pdfmetrics.getRegisteredFontNames()
    main_font = 'NanumGothic' if 'NanumGothic' in registered else 'Helvetica'
    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in registered else 'Helvetica-Bold'
    myeongjo = 'NanumMyeongjoBold' if 'NanumMyeongjoBold' in registered else bold_font
    return main_font, bold_font, myeongjo


def _kt(items):
    return KeepTogether(items)


def _sp(h=6):
    return Spacer(1, h)


# ============================================================
# 표지 페이지 (p1)
# ============================================================

def build_cover_page(story, customer, pdf_type='일간', date_str='', subtitle_extra=''):
    """
    표지 페이지를 만든다.
    
    Parameters
    ----------
    story : list
        ReportLab story (만들 페이지 요소 리스트)
    customer : dict
        {'name': '홍길동', ...}
    pdf_type : str
        '일간', '주간', '월간' 중 하나
    date_str : str
        '2026년 5월 17일' 같은 형태
    subtitle_extra : str
        예: 'Day 1 / 7' (주간/월간 부제용)
    """
    main_font, bold_font, myeongjo_font = _get_fonts()
    
    # ─── 상단 여백 ───
    story.append(_sp(30))
    
    # ─── "운세의 정원" 로고 텍스트 (큰 제목) ───
    logo_style = ParagraphStyle(
        'cover_logo', fontName=myeongjo_font, fontSize=42, leading=52,
        alignment=TA_CENTER, textColor=C['DSG'], spaceBefore=0, spaceAfter=8,
    )
    story.append(Paragraph('운 세 의  정 원', logo_style))
    
    # ─── 영문 부제 ───
    en_style = ParagraphStyle(
        'cover_en', fontName=main_font, fontSize=11, leading=14,
        alignment=TA_CENTER, textColor=C['EARTH'], spaceAfter=4,
    )
    story.append(Paragraph('Fortune Garden', en_style))
    
    # ─── 장식선 (구분자) ───
    divider_style = ParagraphStyle(
        'cover_divider', fontName=main_font, fontSize=14, leading=18,
        alignment=TA_CENTER, textColor=C['GOLD'], spaceBefore=12, spaceAfter=12,
    )
    story.append(Paragraph('— ✦ —', divider_style))
    
    # ─── 주문 정보 영역 (배경 정원문 위에 자연스럽게 얹기) ───
    product_name = {
        '일간': '일일 운세 PDF',
        '주간': '주간 운세 PDF',
        '월간': '월간 운세 PDF',
    }.get(pdf_type, '운세 PDF')
    
    # 이름 (홍길동님) — 두 배 크기 32pt
    name_style = ParagraphStyle(
        'cover_name', fontName=bold_font, fontSize=32, leading=42,
        alignment=TA_CENTER, textColor=C['INDIGO'], spaceAfter=24,
    )
    # 상품명 (월간 운세 PDF) — 두 배 크기 32pt
    product_style = ParagraphStyle(
        'cover_product', fontName=bold_font, fontSize=32, leading=42,
        alignment=TA_CENTER, textColor=C['INDIGO'], spaceAfter=28,
    )
    # 날짜 — 두 배 크기 24pt
    order_date_style = ParagraphStyle(
        'cover_order_date', fontName=main_font, fontSize=24, leading=32,
        alignment=TA_CENTER, textColor=C['BROWN'],
    )
    
    order_info_elements = [
        Paragraph(f"{customer['name']}님", name_style),
        Paragraph(product_name, product_style),
    ]
    if subtitle_extra:
        order_info_elements.append(
            Paragraph(f"{date_str}<br/><font size='18' color='#7A6040'>{subtitle_extra}</font>",
                      order_date_style))
    else:
        order_info_elements.append(Paragraph(date_str, order_date_style))
    
    # 단일 셀 테이블 — 배경/테두리 제거 (정원문 배경이 그대로 보이도록)
    cover_table = Table(
        [[order_info_elements]],
        colWidths=[160*mm],
        rowHeights=[100*mm],
    )
    cover_table.setStyle(TableStyle([
        # BACKGROUND, BOX 제거 — 배경 이미지 그대로 보이도록 투명 처리
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
    ]))
    story.append(cover_table)
    
    # ─── 하단 인용 문구 (가독성을 위해 BROWN으로 변경 + bold) ───
    story.append(_sp(30))
    quote_style = ParagraphStyle(
        'cover_quote', fontName=bold_font, fontSize=12, leading=20,
        alignment=TA_CENTER, textColor=C['BROWN'], spaceBefore=0,
        leftIndent=20*mm, rightIndent=20*mm,
    )
    story.append(Paragraph(
        '<i>"카드는 정답을 알려주지 않습니다. <br/>'
        '당신 안의 답을 비추는 거울일 뿐이에요."</i>',
        quote_style
    ))
    
    story.append(PageBreak())


# ============================================================
# 도입 페이지 (p2) — 목차 + 카드 덱 소개 + 상품 안내 + 링크
# ============================================================

def build_intro_page(story, pdf_type='일간', store_link='', counsel_link='',
                     toc_items=None, customer=None, date_str=''):
    """
    p2 도입 페이지를 만든다.
    
    구성:
    1. 목차 (toc_items)
    2. 카드 덱 소개 (4줄 + 대표카드 이미지 + 세루나루밍 제작)
    3. 운세 PDF 안내 (4종)
    4. 카드 덱 + 풍수용품 안내 (구매처 링크)
    5. 타로 상담 안내 (상담 링크)
    
    Parameters
    ----------
    story : list
    pdf_type : str
        '일간', '주간', '월간'
    store_link : str
        운세의 정원 스토어 URL
    counsel_link : str
        타로 상담 안내 URL
    toc_items : list of (title, page) tuples
        목차 항목들. None이면 기본 목차
    customer : dict
        (사용 안 함 — 시그니처 호환 유지용. 주문 정보는 표지로 이동됨)
    date_str : str
        (사용 안 함 — 시그니처 호환 유지용)
    """
    main_font, bold_font, myeongjo_font = _get_fonts()
    
    # =========================================================
    # 1. 목차
    # =========================================================
    section_h_style = ParagraphStyle(
        'intro_section_h', fontName=bold_font, fontSize=12, leading=16,
        alignment=TA_LEFT, textColor=C['BROWN'],
        spaceBefore=8, spaceAfter=6,
    )
    story.append(Paragraph('📑 목차', section_h_style))
    
    if toc_items is None:
        toc_items = _default_toc(pdf_type)
    
    toc_cell_left = ParagraphStyle(
        'toc_l', fontName=main_font, fontSize=10, leading=14,
        alignment=TA_LEFT, textColor=C['NIGHT'],
    )
    toc_cell_right = ParagraphStyle(
        'toc_r', fontName=main_font, fontSize=10, leading=14,
        alignment=TA_LEFT, textColor=C['EARTH'],
    )
    
    toc_rows = []
    for title, page in toc_items:
        toc_rows.append([
            Paragraph(title, toc_cell_left),
            Paragraph(f"p. {page}", toc_cell_right),
        ])
    
    toc_table = Table(toc_rows, colWidths=[140*mm, 26*mm])
    toc_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, C['LSG']),
    ]))
    story.append(toc_table)
    
    # ⭐ 목차 끝 — 페이지 나누기 (p3로 이동)
    story.append(PageBreak())
    
    # =========================================================
    # 2. 카드 덱 소개 (78장, 세루나루밍 제작) — p3 시작
    # =========================================================
    story.append(Paragraph('🌿 나의 타입 타로', section_h_style))
    
    deck_body_style = ParagraphStyle(
        'deck_body', fontName=main_font, fontSize=10, leading=15,
        alignment=TA_JUSTIFY, textColor=C['NIGHT'],
    )
    deck_note_style = ParagraphStyle(
        'deck_note', fontName=main_font, fontSize=9, leading=13,
        alignment=TA_LEFT, textColor=C['EARTH'],
        spaceBefore=8,
    )
    
    deck_intro_text = (
        '<b>세루나루밍</b>에서 직접 제작한 따뜻한 식물 수채화 톤의 78장 정통 타로 덱입니다. '
        '같은 카드라도 16가지 MBTI 성격 유형에 따라 다르게 해석되어, '
        '오직 당신만을 위한 메시지를 전합니다. '
        '카드는 정답을 알려주는 것이 아니라, 당신 안의 답을 비추는 거울이에요.'
    )
    deck_note_text = (
        '<font color="#7A6040">* 운세의 정원에서 사용된 타로 카드(실물)는 '
        '운세의 정원 스토어에 업로드 예정입니다.</font>'
    )
    
    empress_path = IMAGES_DIR / 'major_03.png.jpeg'
    if not empress_path.exists():
        empress_path = IMAGES_DIR / 'major_03.png'
    
    deck_left_cell = ''
    if empress_path.exists():
        try:
            deck_left_cell = Image(str(empress_path), width=28*mm, height=48*mm)
        except Exception:
            deck_left_cell = Paragraph('', deck_body_style)
    
    deck_right_cell = [
        Paragraph(deck_intro_text, deck_body_style),
        Paragraph(deck_note_text, deck_note_style),
    ]
    
    deck_table = Table(
        [[deck_left_cell, deck_right_cell]],
        colWidths=[34*mm, 132*mm],
        rowHeights=[58*mm],
    )
    deck_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, -1), C['LE']),
    ]))
    story.append(deck_table)
    story.append(_sp(12))
    
    # =========================================================
    # 3. 다른 운세 PDF 안내 (4종 + 추천 상황)
    # =========================================================
    story.append(Paragraph('📖 다른 운세 PDF 안내', section_h_style))
    
    product_desc_style = ParagraphStyle(
        'pd', fontName=main_font, fontSize=9, leading=12,
        alignment=TA_LEFT, textColor=C['EARTH'],
    )
    
    products = [
        ('일간', '🔮 일일 운세 PDF',  '카드 1장으로 보는 오늘 하루',     '오늘 한 가지가 막막할 때'),
        ('주간', '📖 주간 운세 PDF',  '7일의 흐름을 한 권으로',        '한 주를 미리 그려보고 싶을 때'),
        ('월간', '🌙 월간 운세 PDF',  '30일의 결을 깊게',             '한 달의 큰 방향을 잡고 싶을 때'),
        ('연간', '✨ 연간 운세 PDF',  '준비 중입니다',                '곧 만나뵐 수 있도록 준비하고 있어요'),
    ]
    
    product_rows = []
    for ptype, name, desc, rec in products:
        prefix = '★ ' if ptype == pdf_type else '   '
        is_upcoming = (ptype == '연간')
        label_color = C['GOLD'] if ptype == pdf_type else (C['EARTH'] if is_upcoming else C['BROWN'])
        
        label_para = Paragraph(
            f"{prefix}<b>{name}</b>",
            ParagraphStyle(
                f'p_label_{ptype}', fontName=bold_font, fontSize=10, leading=13,
                alignment=TA_LEFT, textColor=label_color,
            )
        )
        desc_para = Paragraph(
            f"{desc}<br/><font size='8' color='#7A6040'>· {rec}</font>",
            product_desc_style
        )
        product_rows.append([label_para, desc_para])
    
    product_table = Table(product_rows, colWidths=[55*mm, 111*mm])
    product_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, C['LSG']),
    ]))
    story.append(product_table)
    story.append(_sp(12))
    
    # =========================================================
    # 4. 운세의 정원 스토어 (구매처 링크)
    # =========================================================
    story.append(Paragraph('🛍️ 운세의 정원 스토어 (리뉴얼중)', section_h_style))
    
    store_desc_style = ParagraphStyle(
        'store_desc', fontName=main_font, fontSize=10, leading=15,
        alignment=TA_LEFT, textColor=C['NIGHT'],
    )
    link_style = ParagraphStyle(
        'link', fontName=main_font, fontSize=9, leading=13,
        alignment=TA_LEFT, textColor=C['INDIGO'],
    )
    
    store_intro = (
        '타로카드 혹은 다양한 소품들을 만나보실 수 있어요.'
    )
    
    if store_link:
        store_link_html = f'🌿 <link href="{store_link}"><u><b>{store_link}</b></u></link>'
    else:
        store_link_html = '<i>아직 스토어 링크가 등록되지 않았어요.</i>'
    
    store_box = Table([
        [Paragraph(store_intro, store_desc_style)],
        [Paragraph(store_link_html, link_style)],
    ], colWidths=[166*mm])
    store_box.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), C['LE']),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.5, C['EARTH']),
        ('LINEBELOW', (0, 0), (-1, 0), 0.3, C['EARTH']),
    ]))
    story.append(store_box)
    story.append(_sp(10))
    
    # =========================================================
    # 5. 타로 상담 안내 (상담 링크)
    # =========================================================
    story.append(Paragraph('🌙 타로 상담 안내', section_h_style))
    
    counsel_intro = (
        '운세를 더 깊이 풀어보고 싶거나 구체적인 상황이 있으시다면, '
        '1:1 카드 상담으로 도움을 드릴 수 있어요. 잠못드는밤 타로상담소에서 만나뵐게요.'
    )
    
    if counsel_link:
        counsel_link_html = f'🌙 <link href="{counsel_link}"><u><b>{counsel_link}</b></u></link>'
    else:
        counsel_link_html = '<i>아직 상담 링크가 등록되지 않았어요.</i>'
    
    counsel_box = Table([
        [Paragraph(counsel_intro, store_desc_style)],
        [Paragraph(counsel_link_html, link_style)],
    ], colWidths=[166*mm])
    counsel_box.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), C['LP']),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.5, C['PURPLE']),
    ]))
    story.append(counsel_box)
    
    story.append(PageBreak())


# ============================================================
# 기본 목차 항목 (각 PDF 종류별)
# ============================================================

def _default_toc(pdf_type):
    """기본 목차 항목 — (제목, 페이지번호) 튜플 리스트."""
    if pdf_type == '일간':
        # 표지(1) → 목차(2) → 안내(3) → 본문 6p(4~9)
        return [
            ('표지', 1),
            ('목차', 2),
            ('카드 덱 · 운세 PDF · 스토어 · 상담 안내', 3),
            ('오늘의 카드', 4),
            ('나만을 위한 심층 해석', 5),
            ('이달 흐름 속 오늘의 위치', 6),
            ('별자리 · 띠 · 사주가 받쳐주는 흐름', 7),
            ('오늘의 행운 아이템 & 확언', 8),
            ('종합 리딩 — 5가지 운세가 같이 말하는 것', 9),
        ]
    elif pdf_type == '주간':
        # 표지(1) → 목차(2) → 안내(3) → 본문 7일×6p (4~45)
        return [
            ('표지', 1),
            ('목차', 2),
            ('카드 덱 · 운세 PDF · 스토어 · 상담 안내', 3),
            ('Day 1 — 첫째 날 운세', 4),
            ('Day 2 — 둘째 날 운세', 10),
            ('Day 3 — 셋째 날 운세', 16),
            ('Day 4 — 넷째 날 운세', 22),
            ('Day 5 — 다섯째 날 운세', 28),
            ('Day 6 — 여섯째 날 운세', 34),
            ('Day 7 — 일곱째 날 · 한 주 마무리', 40),
        ]
    elif pdf_type == '월간':
        # 표지(1) → 목차(2) → 안내(3) → 본문 30일×7p (4~213)
        return [
            ('표지', 1),
            ('목차', 2),
            ('카드 덱 · 운세 PDF · 스토어 · 상담 안내', 3),
            ('Day 1 ~ Day 7 (첫째 주)', 4),
            ('Day 8 ~ Day 15 (둘째 주)', 53),
            ('Day 16 ~ Day 22 (셋째 주)', 109),
            ('Day 23 ~ Day 30 (넷째 주 · 마무리)', 158),
            ('월말 정리 — 다음 달로 이어지는 것', 206),
        ]
    return [('표지', 1), ('목차', 2), ('안내', 3), ('본문', 4)]

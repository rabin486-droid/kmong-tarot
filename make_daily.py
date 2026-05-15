"""
make_daily.py
=============
크몽 MBTI 타로 운세 — 일간 PDF 생성기 (6페이지 재설계 버전)

[페이지 구조 — 6페이지]
  p1: 오늘의 카드 + 메인 톤 + 키워드
  p2: MBTI 심층 해석 (별도 페이지)
  p3: 이달 흐름과의 연결
  p4: 별자리·띠·에너지 지도 (메인 톤에 연결)
  p5: 행운 아이템 + 확언
  p6: 종합 리딩 — "5가지 운세가 같이 말하는 것"
"""

import json
import hashlib
from datetime import date, datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab.pdfgen.canvas as rl_canvas

from manse_calc import calc_profile_jisi, calc_profile
from lucky_items import get_daily_items
from astro_items import get_energy_map, get_caution
from integration import (
    get_main_tone, get_element_support,
    get_star_support, get_zod_support,
    get_mbti_card_link, get_monthly_flow,
    get_integrated_message,
    josa_i, josa_eun, josa_eul, josa_wa, josa_ira,
)

BASE_DIR  = Path(__file__).parent.resolve()
IMG_DIR   = BASE_DIR / 'images'
FONT_DIR  = BASE_DIR / 'fonts'
OUTPUT_DIR = BASE_DIR / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)
CARDS_DB_FILE = BASE_DIR / 'cards_db.json'

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


def register_fonts():
    font_map = {
        'NanumGothic':       'NanumGothic.ttf',
        'NanumGothicBold':   'NanumGothicBold.ttf',
        'NanumMyeongjo':     'NanumMyeongjo.ttf',
        'NanumMyeongjoBold': 'NanumMyeongjoBold.ttf',
    }
    registered = []
    for name, fname in font_map.items():
        path = FONT_DIR / fname
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                registered.append(name)
            except Exception as e:
                print(f"⚠️  폰트 등록 실패 {name}: {e}")
    if not registered:
        print(f"⚠️  폰트 폴더 비어있음: {FONT_DIR}. Helvetica fallback.")
    return registered


def pick_card_for_date(date_obj):
    card_ids = (
        [f'major_{i:02d}' for i in range(22)] +
        [f'wands_{i:02d}' for i in range(1, 15)] +
        [f'cups_{i:02d}' for i in range(1, 15)] +
        [f'swords_{i:02d}' for i in range(1, 15)] +
        [f'pentacles_{i:02d}' for i in range(1, 15)]
    )
    date_str = date_obj.strftime('%Y%m%d')
    digit_sum = sum(int(d) for d in date_str)
    card_idx = digit_sum % 78
    card_id = card_ids[card_idx]
    h = hashlib.md5((date_str + 'direction').encode()).hexdigest()
    is_reversed = int(h[:8], 16) % 2 == 1
    direction = 'reversed' if is_reversed else 'upright'
    return card_id, direction


def get_card_image_path(card_id):
    if card_id.startswith('major_'):
        fname = f"{card_id}.png.jpeg"
    else:
        suit, num = card_id.split('_')
        num_int = int(num)
        face_map = {1: 'A', 11: 'P', 12: 'Kn', 13: 'Q', 14: 'K'}
        suffix = face_map.get(num_int, str(num_int))
        fname = f"{suit}_{suffix}.png.jpeg"
    return IMG_DIR / fname


class NumberedCanvas(rl_canvas.Canvas):
    footer_template = '루밍의 MBTI 타로 운세  |  일간 운세  |  {name}님 전용  |  {n}/{total}'
    customer_name = '고객'
    primary_font = 'NanumGothic'
    
    def __init__(self, *args, **kwargs):
        rl_canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
    
    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()
    
    def save(self):
        total = len(self._saved_page_states)
        for i, state in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            self._draw_footer(i + 1, total)
            rl_canvas.Canvas.showPage(self)
        rl_canvas.Canvas.save(self)
    
    def _draw_footer(self, page_num, total):
        text = self.footer_template.format(name=self.customer_name, n=page_num, total=total)
        try:
            self.setFont(self.primary_font, 8)
        except Exception:
            self.setFont('Helvetica', 8)
        self.setFillColor(C['BROWN'])
        page_w, _ = A4
        self.drawCentredString(page_w / 2, 12 * mm, text)


def make_styles():
    registered = pdfmetrics.getRegisteredFontNames()
    font_main = 'NanumGothic' if 'NanumGothic' in registered else 'Helvetica'
    font_bold = 'NanumGothicBold' if 'NanumGothicBold' in registered else 'Helvetica-Bold'
    font_serif = 'NanumMyeongjo' if 'NanumMyeongjo' in registered else font_main
    
    return {
        # 큰 제목 (페이지 최상단 타이틀) — 25p
        'title': ParagraphStyle('title', fontName=font_bold, fontSize=25, leading=32,
            alignment=TA_CENTER, textColor=C['BROWN'], spaceAfter=10),
        # 부제 (날짜+프로필)
        'subtitle': ParagraphStyle('subtitle', fontName=font_main, fontSize=11, leading=15,
            alignment=TA_CENTER, textColor=C['DG'], spaceAfter=14),
        # 중간 제목 (h2) — 16p
        'h2': ParagraphStyle('h2', fontName=font_bold, fontSize=16, leading=20,
            textColor=C['INDIGO'], spaceBefore=10, spaceAfter=8),
        # 소제목 (h3) — 13p
        'h3': ParagraphStyle('h3', fontName=font_bold, fontSize=13, leading=17,
            textColor=C['BROWN'], spaceBefore=6, spaceAfter=4),
        # 본문 — 13p
        'body': ParagraphStyle('body', fontName=font_main, fontSize=13, leading=20,
            alignment=TA_LEFT, textColor=C['NIGHT']),
        'body_just': ParagraphStyle('body_just', fontName=font_main, fontSize=13, leading=20,
            alignment=TA_JUSTIFY, textColor=C['NIGHT']),
        # 인용 / 강조 — 14p
        'quote': ParagraphStyle('quote', fontName=font_serif, fontSize=14, leading=20,
            alignment=TA_CENTER, textColor=C['PURPLE'],
            spaceBefore=8, spaceAfter=8, leftIndent=10, rightIndent=10),
        # 핵심 메시지 (골드) — 15p
        'core': ParagraphStyle('core', fontName=font_bold, fontSize=15, leading=22,
            alignment=TA_CENTER, textColor=C['GOLD'],
            spaceBefore=12, spaceAfter=12, leftIndent=20, rightIndent=20),
        # 섹션 박스 헤더 (퍼플/인디고 배경 위 흰 글씨) — 16p
        'section_box': ParagraphStyle('section_box', fontName=font_bold, fontSize=16, leading=20,
            alignment=TA_LEFT, textColor=C['CREAM']),
    }


def fill(template, customer, profile):
    if not template:
        return ''
    return (template
            .replace('{NAME}',    customer['name'])
            .replace('{MBTI}',    customer['mbti'])
            .replace('{STAR}',    profile.get('STAR', ''))
            .replace('{ZOD}',     profile.get('ZOD', ''))
            .replace('{ELEMENT}', profile.get('ELEMENT', ''))
            .replace('{BIRTH}',   profile.get('BIRTH', '')))


def kt(items): return KeepTogether(items)
def sp(h=6): return Spacer(1, h)


def section_header(title_text, styles, bg_color=None):
    bg = bg_color or C['INDIGO']
    t = Table([[Paragraph(f"<b>{title_text}</b>", styles['section_box'])]], colWidths=[166*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


# ============================================================
# p1
# ============================================================

def build_page1(story, customer, profile, card_data, direction_kr, card_key, date_obj, styles):
    wd = ['월', '화', '수', '목', '금', '토', '일'][date_obj.weekday()]
    date_str = f"{date_obj.year}년 {date_obj.month}월 {date_obj.day}일 {wd}요일"
    profile_str = (
        f"{customer['mbti']} · {profile.get('STAR', '')} · "
        f"{profile.get('ZOD', '')} · {profile.get('BIRTH', '')}"
    )

    bold_font_pre = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font_pre = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'

    # ─── 메인 제목 (이름 강조) ───
    story.append(Paragraph(
        f"{customer['name']}님의 운세 리딩",
        styles['title']
    ))
    # ─── 부제 1: 일간 운세 · 날짜 ───
    story.append(Paragraph(
        f"일간 운세 · {date_str}",
        ParagraphStyle('dl_sub1', fontName=main_font_pre, fontSize=12, leading=16,
                       alignment=TA_CENTER, textColor=C['PURPLE'], spaceAfter=4)
    ))
    # ─── 부제 2: 프로필 ───
    story.append(Paragraph(
        profile_str,
        ParagraphStyle('dl_sub2', fontName=main_font_pre, fontSize=11, leading=15,
                       alignment=TA_CENTER, textColor=C['DG'], spaceAfter=12)
    ))
    story.append(sp(6))
    
    main_tone = get_main_tone(card_key)
    
    card_img_path = get_card_image_path(card_data['card_id_base'])
    if card_img_path.exists():
        card_img = Image(str(card_img_path), width=55*mm, height=90*mm)
    else:
        card_img = Paragraph(
            f"<b>{card_data['name']}</b><br/>{card_data.get('kr', '')}<br/><br/>({direction_kr})",
            styles['quote']
        )
    
    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    
    info_label = ParagraphStyle('info_label', fontName=main_font, fontSize=11, leading=15, textColor=C['DG'])
    info_card_name = ParagraphStyle('info_card', fontName=bold_font, fontSize=20, leading=25, textColor=C['BROWN'])
    info_keyword = ParagraphStyle('info_kw', fontName=main_font, fontSize=11, leading=15, textColor=C['DG'], spaceAfter=8)
    info_body = ParagraphStyle('info_body', fontName=main_font, fontSize=12, leading=18, alignment=TA_JUSTIFY, textColor=C['NIGHT'])
    info_msg_label = ParagraphStyle('info_msg', fontName=bold_font, fontSize=12, leading=16, textColor=C['BROWN'], spaceBefore=6, spaceAfter=4)
    
    keyword_text = card_data.get('keyword', '')
    right_content = [
        Paragraph("오늘의 카드", info_label),
        Paragraph(f"{card_data['name']} <font color='#8B6520'>· {card_data.get('kr', '')}</font>", info_card_name),
        Paragraph(f"키워드 : {keyword_text}", info_keyword),
        Paragraph("오늘의 메시지", info_msg_label),
        Paragraph(main_tone['main_msg'], info_body),
    ]
    
    layout = Table([[card_img, right_content]], colWidths=[60*mm, 106*mm])
    layout.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, -1), C['CREAM']),
        ('BOX', (0, 0), (-1, -1), 0.5, C['GOLD']),
    ]))
    story.append(layout)
    story.append(sp(12))
    
    story.append(Paragraph(
        f"<b>{direction_kr}</b> 카드로 등장",
        ParagraphStyle('dir', fontName=bold_font, fontSize=13, leading=17, alignment=TA_CENTER, textColor=C['PURPLE'])
    ))
    story.append(sp(8))
    story.append(Paragraph(f'"{main_tone["core"]}"', styles['core']))
    
    story.append(PageBreak())


# ============================================================
# p2
# ============================================================

def build_page2_mbti(story, customer, profile, card_data, direction, card_key, date_obj, styles):
    mbti = customer['mbti']
    
    story.append(section_header(f"{mbti}를 위한 심층 해석", styles, C['INDIGO']))
    story.append(sp(12))
    
    link = get_mbti_card_link(card_key, mbti, direction)
    
    story.append(kt([Paragraph(link['opening'], styles['body_just'])]))
    story.append(sp(10))
    
    card_body = card_data.get('body', '')
    if card_body:
        body_filled = fill(card_body, customer, profile)
        story.append(Paragraph(body_filled, styles['body_just']))
        story.append(sp(10))
    
    story.append(kt([
        Paragraph("✦ 알아두면 좋은 그림자", styles['h3']),
        Paragraph(link['shadow_msg'], styles['body_just']),
    ]))
    story.append(sp(10))
    
    main_tone = get_main_tone(card_key)
    
    if direction == 'upright':
        energy_text = (
            f"<b>정방향 에너지</b> — <b>'{main_tone['keyword']}'</b>의 에너지가 활짝 열려 있어요. "
            f"두려움 없이 이 흐름을 따라가 보세요. 준비가 완벽하지 않아도 괜찮습니다."
        )
    else:
        energy_text = (
            f"<b>역방향 기운</b> — 억지로 밀어붙이기보다 자기 돌봄에 집중해 보세요. "
            f"에너지가 막혀 있거나 과잉 상태일 수 있어요. 본인의 페이스를 지키는 것이 가장 현명한 선택입니다."
        )
    
    story.append(kt([
        Paragraph("✦ 오늘의 에너지 상태", styles['h3']),
        Paragraph(energy_text, styles['body_just']),
    ]))
    story.append(sp(10))
    
    story.append(kt([
        Paragraph("✦ 오늘의 실천", styles['h3']),
        Paragraph(f'<b>{link["tip"]}</b>', styles['quote']),
    ]))
    story.append(sp(8))
    
    core_msg = card_data.get('core', '')
    if core_msg:
        core_filled = fill(core_msg, customer, profile)
        story.append(Paragraph(f'"{core_filled}"', styles['core']))
    else:
        story.append(Paragraph(f'"{main_tone["core"]}"', styles['core']))
    
    story.append(PageBreak())


# ============================================================
# p3
# ============================================================

def _current_week_row(day):
    if day <= 7: return 1
    elif day <= 15: return 2
    elif day <= 22: return 3
    else: return 4


def build_page3_monthly_flow(story, customer, profile, card_key, date_obj, styles):
    flow = get_monthly_flow(card_key, date_obj.day)
    main_tone = get_main_tone(card_key)
    
    story.append(section_header(f"이달 흐름과의 연결 — {flow['phase_name']}", styles, C['PURPLE']))
    story.append(sp(12))
    
    story.append(kt([
        Paragraph(f"✦ {flow['phase_text']}이 흐르는 시기예요", styles['h3']),
        Paragraph(flow['guide'], styles['body_just']),
    ]))
    story.append(sp(10))
    
    story.append(kt([
        Paragraph(f"✦ 오늘 이 카드가 등장한 이유", styles['h3']),
        Paragraph(flow['connection'], styles['body_just']),
    ]))
    story.append(sp(10))
    
    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    
    is_current = lambda r: r[0] <= date_obj.day <= r[1]
    
    rows = [['시기', '에너지', '오늘 위치']]
    week_data = [
        ((1, 7),   '1주차 - 씨앗 심기',     '의도와 시작'),
        ((8, 15),  '2주차 - 성장하는 시기', '행동과 추진'),
        ((16, 22), '3주차 - 결실의 시기',   '드러남과 명료'),
        ((23, 31), '4주차 - 정리와 준비',   '내려놓기와 회복'),
    ]
    
    for r, name, energy in week_data:
        mark = '◆ 오늘' if is_current(r) else ''
        rows.append([name, energy, mark])
    
    current_row = _current_week_row(date_obj.day)
    
    flow_table = Table(rows, colWidths=[60*mm, 60*mm, 46*mm])
    flow_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), main_font),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('BACKGROUND', (0, 0), (-1, 0), C['LP']),
        ('TEXTCOLOR', (0, 0), (-1, 0), C['PURPLE']),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.3, C['PURPLE']),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, current_row), (-1, current_row), bold_font),
        ('BACKGROUND', (0, current_row), (-1, current_row), C['LE']),
        ('TEXTCOLOR', (0, current_row), (-1, current_row), C['BROWN']),
    ]))
    story.append(Paragraph("✦ 이달 큰 그림", styles['h3']))
    story.append(kt([flow_table]))
    story.append(sp(10))
    
    closing = (
        f"오늘의 작은 한 걸음이 이달 큰 흐름의 일부입니다. "
        f"{customer['name']}님이 오늘 <b>'{main_tone['keyword']}'</b>에 집중하면, "
        f"이번 달 마지막에 큰 결실로 돌아올 거예요."
    )
    story.append(Paragraph(closing, styles['body_just']))
    
    story.append(PageBreak())


# ============================================================
# p4
# ============================================================

def build_page4_astro(story, customer, profile, card_key, date_obj, styles):
    star = profile.get('STAR', '')
    zod = profile.get('ZOD', '')
    element = profile.get('ELEMENT', '')
    main_tone = get_main_tone(card_key)
    keyword = main_tone['keyword']
    
    story.append(section_header(
        f"별자리 · 띠 · 사주가 받쳐주는 '{keyword}' 흐름",
        styles, C['TEAL']
    ))
    story.append(sp(12))
    
    star_msg = get_star_support(card_key, star)
    story.append(kt([
        Paragraph(f"✦ {star}{josa_i(star)} 받쳐주는 방식", styles['h3']),
        Paragraph(star_msg, styles['body_just']),
    ]))
    story.append(sp(8))
    
    zod_msg = get_zod_support(card_key, zod)
    story.append(kt([
        Paragraph(f"✦ {zod}{josa_i(zod)} 보태는 힘", styles['h3']),
        Paragraph(zod_msg, styles['body_just']),
    ]))
    story.append(sp(8))
    
    elem_msg = get_element_support(card_key, element)
    story.append(kt([
        Paragraph(f"✦ 사주 {element} 일간의 기운", styles['h3']),
        Paragraph(
            f"{customer['name']}님의 일간은 <b>{element}</b>{josa_ira(element)} 기운이에요. {elem_msg}.",
            styles['body_just']
        ),
    ]))
    story.append(sp(12))
    
    story.append(Paragraph("✦ 오늘의 에너지 지도", styles['h2']))
    
    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    
    energy_rows = get_energy_map(card_key, date_obj)
    energy_table = Table(energy_rows, colWidths=[28*mm, 30*mm, 108*mm])
    energy_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), main_font),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('FONTNAME', (0, 0), (-1, 0), bold_font),
        ('BACKGROUND', (0, 0), (-1, 0), C['LSG']),
        ('TEXTCOLOR', (0, 0), (-1, 0), C['DSG']),
        ('ALIGN', (0, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.3, C['SAGE']),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(kt([energy_table]))
    story.append(sp(10))
    
    caution_text = fill(get_caution(card_key, date_obj), customer, profile)
    story.append(kt([
        Paragraph("✦ 오늘의 주의 포인트", styles['h3']),
        Paragraph(caution_text, styles['body_just']),
    ]))
    
    story.append(PageBreak())


# ============================================================
# p5
# ============================================================

def build_page5_lucky(story, customer, profile, lucky, card_key, styles):
    main_tone = get_main_tone(card_key)
    
    story.append(section_header(
        f"오늘의 행운 아이템 — '{main_tone['keyword']}'을 부르는 것들",
        styles, C['GOLD']
    ))
    story.append(sp(12))
    
    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    
    rows = [
        ['행운의 색',     lucky.get('행운의 색', ''),     '추천 향기',     lucky.get('추천 향기', '')],
        ['행운의 음식',   lucky.get('행운의 음식', ''),   '추천 소재',     lucky.get('추천 소재', '')],
        ['행운의 방향',   lucky.get('행운의 방향', ''),   '추천 음악',     lucky.get('추천 음악', '')],
        ['행운의 숫자',   f"{lucky.get('행운의 숫자1', '')}, {lucky.get('행운의 숫자2', '')}",
                         '황금 시간대', lucky.get('황금 시간대', '')],
        ['귀인 조우',     lucky.get('귀인 조우', ''),    '행운의 원석',   lucky.get('행운의 원석', '')],
    ]
    
    lucky_table = Table(rows, colWidths=[28*mm, 55*mm, 28*mm, 55*mm])
    lucky_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), main_font),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('FONTNAME', (0, 0), (0, -1), bold_font),
        ('FONTNAME', (2, 0), (2, -1), bold_font),
        ('BACKGROUND', (0, 0), (0, -1), C['LE']),
        ('BACKGROUND', (2, 0), (2, -1), C['LE']),
        ('TEXTCOLOR', (0, 0), (0, -1), C['EARTH']),
        ('TEXTCOLOR', (2, 0), (2, -1), C['EARTH']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, C['GOLD']),
    ]))
    story.append(kt([lucky_table]))
    story.append(sp(14))
    
    story.append(Paragraph(
        "오늘의 확언 3문장 - 아침에 소리내어 읽어보세요 (또는, 속으로 읽어보세요.)",
        ParagraphStyle('aff_title', fontName=bold_font, fontSize=16, leading=20,
                       alignment=TA_CENTER, textColor=C['INDIGO'],
                       spaceBefore=10, spaceAfter=8)
    ))
    story.append(sp(4))
    
    affirmations = [
        f"나는 오늘 <b>'{main_tone['keyword']}'</b>의 흐름을 신뢰하며 한 걸음 내딛는다.",
        f"내 안의 {profile.get('ELEMENT', '')} 기운이 오늘의 흐름을 든든히 받쳐준다.",
        f"오늘 {customer['name']}{josa_i(customer['name'])} 내리는 선택은 미래의 나에게 좋은 선물이 된다.",
    ]
    
    for aff in affirmations:
        story.append(Paragraph(f'"{aff}"', styles['quote']))
        story.append(sp(3))
    
    story.append(PageBreak())


# ============================================================
# p6 — 핵심
# ============================================================

def build_page6_integrated(story, customer, profile, card_data, direction, card_key, lucky, styles, author_info=None):
    mbti = customer['mbti']
    intg = get_integrated_message(card_key, profile, mbti, direction)
    main_tone = get_main_tone(card_key)
    
    story.append(section_header(
        f"종합 리딩 — 5가지 운세가 같이 말하는 것",
        styles, C['BROWN']
    ))
    story.append(sp(12))
    
    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    
    story.append(Paragraph(
        f"<b>오늘의 핵심 키워드</b>",
        ParagraphStyle('kw_label', fontName=main_font, fontSize=12, leading=16,
                       alignment=TA_CENTER, textColor=C['DG'])
    ))
    story.append(Paragraph(
        f'<b>{intg["keyword"]}</b>',
        ParagraphStyle('kw_big', fontName=bold_font, fontSize=28, leading=36,
                       alignment=TA_CENTER, textColor=C['GOLD'], spaceBefore=4, spaceAfter=14)
    ))
    
    # ─── 5가지 운세 통합 표 (셀을 Paragraph로 감싸 <b> 태그 렌더링) ───
    cell_label_style = ParagraphStyle(
        'cell_label', fontName=bold_font, fontSize=12, leading=16,
        alignment=TA_CENTER, textColor=C['BROWN']
    )
    cell_body_style = ParagraphStyle(
        'cell_body', fontName=main_font, fontSize=12, leading=17,
        alignment=TA_LEFT, textColor=C['NIGHT']
    )
    cell_header_style = ParagraphStyle(
        'cell_header', fontName=bold_font, fontSize=12, leading=16,
        alignment=TA_CENTER, textColor=C['CREAM']
    )

    def P(txt, style):
        return Paragraph(txt, style)

    rows = [
        [P("운세", cell_header_style),                                                  P("오늘 이 운세가 말하는 것", cell_header_style)],
        [P(f"타로 · {card_data.get('kr', card_data['name'])}", cell_label_style),       P(intg['rows']['tarot'], cell_body_style)],
        [P(f"MBTI · {mbti}", cell_label_style),                                          P(intg['rows']['mbti'],  cell_body_style)],
        [P(f"사주 · {profile.get('ELEMENT', '')} 일간", cell_label_style),               P(intg['rows']['saju'],  cell_body_style)],
        [P(f"별자리 · {profile.get('STAR', '')}", cell_label_style),                     P(intg['rows']['star'],  cell_body_style)],
        [P(f"띠 · {profile.get('ZOD', '')}", cell_label_style),                          P(intg['rows']['zod'],   cell_body_style)],
    ]
    
    summary_table = Table(rows, colWidths=[45*mm, 121*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C['BROWN']),
        ('BACKGROUND', (0, 1), (0, -1), C['LE']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.3, C['BROWN']),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(kt([summary_table]))
    story.append(sp(14))
    
    story.append(kt([
        Paragraph("✦ 5가지가 동시에 가리키는 방향", styles['h3']),
        Paragraph(intg['integration'], styles['body_just']),
    ]))
    story.append(sp(12))
    
    story.append(kt([
        Paragraph("✦ 오늘 꼭 할 것 한 가지", styles['h3']),
        Paragraph(
            f"<b>{lucky.get('황금 시간대', '오후 시간대')}</b>에 "
            f"<b>'{intg['keyword']}'</b>의 흐름을 가장 잘 받을 수 있어요. "
            f"이 시간대에 미뤄두었던 한 가지를 끝내거나, "
            f"새로운 시도 하나를 해보세요. 그 행동이 오늘 하루의 흐름을 완성시킵니다.",
            styles['quote']
        ),
    ]))
    
    # ===== 작성자 / 사업자 정보 박스 (옵션) =====
    if author_info:
        story.append(sp(20))
        
        bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
        main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        
        author_label_style = ParagraphStyle(
            'author_label', fontName=bold_font, fontSize=9, leading=12,
            alignment=TA_CENTER, textColor=C['EARTH']
        )
        author_value_style = ParagraphStyle(
            'author_value', fontName=main_font, fontSize=10, leading=14,
            alignment=TA_CENTER, textColor=C['BROWN']
        )
        
        info_rows = []
        if author_info.get('creator_name'):
            info_rows.append([
                Paragraph("작성자", author_label_style),
                Paragraph(author_info['creator_name'], author_value_style)
            ])
        if author_info.get('business_name'):
            info_rows.append([
                Paragraph("사업자 정보", author_label_style),
                Paragraph(author_info['business_name'], author_value_style)
            ])
        if author_info.get('contact'):
            info_rows.append([
                Paragraph("문의", author_label_style),
                Paragraph(author_info['contact'], author_value_style)
            ])
        if author_info.get('platform'):
            info_rows.append([
                Paragraph("판매처", author_label_style),
                Paragraph(author_info['platform'], author_value_style)
            ])
        
        if info_rows:
            author_table = Table(info_rows, colWidths=[35*mm, 131*mm])
            author_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), C['LE']),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.3, C['EARTH']),
            ]))
            story.append(kt([author_table]))


# ============================================================
# 메인
# ============================================================

def make_daily_pdf(customer, date_obj=None, output_path=None, author_info=None):
    """
    일간 PDF 생성 (6페이지).
    
    Parameters
    ----------
    customer : dict
        {'name', 'mbti', 'birthdate', 'jisi'}
    date_obj : date | str | None
        기준 날짜 (None이면 오늘)
    output_path : str | Path | None
        출력 경로 (None이면 자동 생성)
    author_info : dict | None
        하단 작성자/사업자 정보. 모든 키 옵션:
          {
            'creator_name': '루밍 (looming)',
            'business_name': '이설빈 / 사업자등록번호 000-00-00000',
            'contact': '문의: example@email.com',
            'platform': '크몽 판매 상품',
          }
        None이면 기본 푸터만 표시.
    """
    if date_obj is None:
        date_obj = date.today()
    if isinstance(date_obj, str):
        date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
    
    profile = calc_profile_jisi(customer['birthdate'], customer.get('jisi'))
    profile['NAME'] = customer['name']
    
    card_id_base, direction = pick_card_for_date(date_obj)
    direction_kr = '정방향' if direction == 'upright' else '역방향'
    card_key = f"{card_id_base}_{direction}"
    
    with open(CARDS_DB_FILE, encoding='utf-8') as f:
        cards_db = json.load(f)
    
    mbti = customer['mbti']
    card_data = dict(cards_db[mbti][card_key])
    card_data['card_id_base'] = card_id_base
    
    lucky = get_daily_items(profile, card_key, date_obj)
    
    register_fonts()
    styles = make_styles()
    
    NumberedCanvas.customer_name = customer['name']
    registered = pdfmetrics.getRegisteredFontNames()
    NumberedCanvas.primary_font = 'NanumGothic' if 'NanumGothic' in registered else 'Helvetica'
    
    if output_path is None:
        date_str = date_obj.strftime('%Y%m%d')
        output_path = OUTPUT_DIR / f"{customer['name']}_일간운세_{date_str}.pdf"
    else:
        output_path = Path(output_path)
    
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm, bottomMargin=20*mm,
        title=f"{customer['name']}님 일간 운세",
        author='루밍 (looming)',
    )
    
    story = []
    build_page1(story, customer, profile, card_data, direction_kr, card_key, date_obj, styles)
    build_page2_mbti(story, customer, profile, card_data, direction, card_key, date_obj, styles)
    build_page3_monthly_flow(story, customer, profile, card_key, date_obj, styles)
    build_page4_astro(story, customer, profile, card_key, date_obj, styles)
    build_page5_lucky(story, customer, profile, lucky, card_key, styles)
    build_page6_integrated(story, customer, profile, card_data, direction, card_key, lucky, styles, author_info)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path


if __name__ == '__main__':
    sample_customer = {
        'name': '홍길동',
        'mbti': 'INTJ',
        'birthdate': '1990-05-15',
        'jisi': None,
    }
    
    # ===== 작성자 정보 — 루밍이 직접 수정해서 사용 =====
    # 사용 안 하려면 None으로 설정
    sample_author_info = {
        'creator_name':  '루밍 (looming)',
        'business_name': '이설빈 / 사업자등록번호: 000-00-00000',
        'contact':       '문의: looming@example.com',
        'platform':      '크몽 / 숨고 / 텀블벅 판매 상품',
    }
    
    print("=" * 60)
    print("make_daily.py 6페이지 재설계 버전")
    print("=" * 60)
    print(f"고객: {sample_customer['name']} ({sample_customer['mbti']})")
    print(f"생년월일: {sample_customer['birthdate']}")
    print(f"기준 날짜: {date.today()}")
    print()
    
    try:
        pdf_path = make_daily_pdf(sample_customer, author_info=sample_author_info)
        print(f"✅ PDF 생성 완료: {pdf_path}")
        print(f"   파일 크기: {pdf_path.stat().st_size:,} bytes")
    except FileNotFoundError as e:
        print(f"⚠️  필수 파일 없음: {e}")
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()

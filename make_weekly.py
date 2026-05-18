"""
make_weekly.py
==============
크몽 MBTI 타로 운세 — 주간 PDF 생성기 (6페이지 × 7일 = 42페이지)

[작성자] 루밍 (looming)
[프로젝트] 크몽 MBTI 타로 운세 PDF 서비스

[페이지 구조 — 1일당 6페이지, 일간 PDF와 동일]
  p1: 오늘의 카드 + 메인 톤 + 키워드
  p2: MBTI 심층 해석
  p3: 이달 흐름과의 연결
  p4: 별자리·띠·에너지 지도
  p5: 행운 아이템 + 확언
  p6: 종합 리딩 + ⭐ 꿈의 메시지 + ⭐ 내일과의 에너지 연결
      (마지막 날에는 'author_info 박스' + '한 주 마무리' 메시지)

  → 7일치 = 42페이지
  → 푸터: '루밍의 MBTI 타로 운세 | 주간 운세 | {NAME}님 전용 | n/42'

[입력]
  customer: dict — make_daily.py와 동일
  start_date: 주간 시작일 (datetime.date)
  output_path: 출력 경로 (기본: 자동)
  author_info: dict | None — 마지막 7일차 p6 하단에 표시
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
import reportlab.pdfgen.canvas as rl_canvas

from manse_calc import calc_profile_jisi
from lucky_items import get_weekly_items  # 주간 15개 (일간 10개 + 5개 추가, 숫자 4개)
from astro_items import get_energy_map, get_caution

from integration import (
    get_main_tone, get_element_support,
    get_star_support, get_zod_support,
    get_mbti_card_link, get_monthly_flow,
    get_integrated_message,
    _get_category,  # 카드 키 → 카테고리 추출 (꿈/내일 메시지에 필요)
    josa_i, josa_eun, josa_eul, josa_wa, josa_ira,
)

from intro_pages import build_cover_page, build_intro_page

# 배경지 페인터 (2026-05-17 추가)
from backgrounds import make_bg_painter

# make_daily.py의 공통 유틸 + 페이지 빌더 재활용
# (p1은 주간 전용 제목 필요해서 새로 작성, p5는 일간 10개 → 주간 15개라 새로 작성)
from make_daily import (
    C, register_fonts, make_styles, pick_card_for_date,
    get_card_image_path, fill, kt, sp, section_header,
    CARDS_DB_FILE, OUTPUT_DIR,
    build_page2_mbti, build_page3_monthly_flow,
    build_page4_astro,
)


# ============================================================
# 주간 푸터 — 1/42 ~ 42/42
# ============================================================

class WeeklyNumberedCanvas(rl_canvas.Canvas):
    # ⭐ 푸터 형식: {title}는 자유 입력 (예: "운세의 정원")
    footer_template = '{title}  |  주간 운세  |  {name}님 전용  |  {n}/{total}'
    customer_name = '고객'
    primary_font = 'NanumGothic'
    footer_title = '운세의 정원'   # ⭐ 자유 입력 제목 (기본값)
    author_suffix = ''             # ⭐ 푸터 뒤에 붙일 텍스트 (예: 판매처)

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
        text = self.footer_template.format(
            title=self.footer_title,
            name=self.customer_name, n=page_num, total=total
        )
        # ⭐ 자유 입력 정보가 있으면 푸터 뒤에 이어붙임
        if self.author_suffix:
            text = text + '  |  ' + self.author_suffix
        try:
            self.setFont(self.primary_font, 8)
        except Exception:
            self.setFont('Helvetica', 8)
        self.setFillColor(C['BROWN'])
        page_w, _ = A4
        self.drawCentredString(page_w / 2, 12 * mm, text)


# ============================================================
# 주간 전용 데이터 — 꿈의 메시지 (카드 카테고리별)
# ============================================================

DREAM_MESSAGES_BY_CATEGORY = {
    '시작/모험':   "오늘 밤 꿈속에서 처음 보는 길을 걷는다면, 그것은 내일의 새 출발을 알리는 신호예요.",
    '창조/실행':   "꿈에서 무언가를 만드는 손길이 보인다면, 마음속 창작 욕구가 형태를 갖추려는 거예요.",
    '직관/지혜':   "오늘 꿈은 평소보다 더 또렷할 수 있어요. 깨어나면 그 한 장면을 적어두세요.",
    '풍요/사랑':   "꿈속에서 따뜻한 음식이나 풍성한 자연이 보이면, 사랑과 풍요가 다가오는 흐름이에요.",
    '안정/권위':   "꿈에서 든든한 건물이나 단단한 사람을 보면, 본인의 기반이 더 단단해지고 있다는 신호예요.",
    '전통/교육':   "오래된 책이나 어른의 모습이 꿈에 나타나면, 배움이 깊어지는 시기가 다가오고 있어요.",
    '관계/조화':   "꿈에서 누군가와 마주 앉아 대화하고 있다면, 그 관계에 대한 마음이 정리되는 중이에요.",
    '추진/돌파':   "꿈에서 달리거나 무언가를 넘는 모습이 보인다면, 깨어 있을 때의 추진력이 더 강해질 거예요.",
    '용기/내면':   "꿈속에서 두려움 너머를 보는 자신을 만난다면, 깨어 있을 때도 한 걸음 더 내디딜 수 있어요.",
    '성찰/내면':   "조용한 공간이 꿈에 나타나면, 마음 깊은 곳이 회복되고 있다는 신호예요.",
    '변화/순환':   "꿈에서 계절이 바뀌거나 길이 갈라지는 풍경을 보면, 삶의 전환점이 다가오고 있어요.",
    '변화/돌파':   "꿈에서 무너지는 풍경 뒤에 새 길이 나타난다면, 변화 이후의 가능성을 미리 보여주는 거예요.",
    '균형/정의':   "꿈에서 무언가를 저울질하거나 판단하는 장면은, 본인의 가치 기준을 다듬는 시간이에요.",
    '인내/관점':   "꿈속에서 시간이 느리게 흐르는 느낌을 받는다면, 잠시 멈춰 보는 게 답이라는 메시지예요.",
    '균형/조화':   "꿈에서 부드러운 색감이나 음악을 만나면, 일상의 균형이 회복되고 있어요.",
    '욕망/속박':   "꿈에서 무언가 떨쳐내는 동작이 보인다면, 마음속 집착에서 자유로워지는 흐름이에요.",
    '희망/영감':   "별빛이나 새벽 하늘이 꿈에 나타나면, 깨어 있을 때 영감의 문이 열릴 거예요.",
    '결단/각성':   "꿈에서 또렷한 한 마디 말을 듣는다면, 그것이 오늘 본인이 가야 할 방향이에요.",
    '완성/성취':   "꿈속에서 무언가를 완성하는 장면은, 깨어 있을 때의 결실이 다가오고 있다는 신호예요.",
    '안정/풍요':   "풍요로운 풍경이나 가득 찬 그릇이 꿈에 보이면, 현실의 안정이 더 단단해지고 있어요.",
}


# ============================================================
# 주간 전용 데이터 — 내일과의 에너지 연결
# ============================================================

BRIDGE_BY_CATEGORY = {
    '시작/모험':   "내일은 새로운 시도가 어울리는 흐름이 와요. 오늘의 마무리를 가볍게 정리해두세요.",
    '창조/실행':   "내일은 본인의 창의력이 한층 더 발휘되는 날이에요. 오늘 떠오른 영감을 잊지 마세요.",
    '직관/지혜':   "내일은 깊은 통찰이 찾아오는 흐름입니다. 오늘 밤은 조용히 마음을 비워두세요.",
    '풍요/사랑':   "내일은 따뜻한 관계와 풍요가 다가오는 흐름이에요. 마음의 문을 열어두세요.",
    '안정/권위':   "내일은 단단한 기반이 빛나는 날입니다. 오늘 미뤄둔 정리 하나만 마무리하면 좋아요.",
    '전통/교육':   "내일은 배움과 가르침이 어우러지는 흐름이에요. 평소 관심 있던 주제를 떠올려보세요.",
    '관계/조화':   "내일은 사람과 사람을 잇는 흐름이 강해져요. 오늘 미뤄둔 연락 한 번이 가치 있어요.",
    '추진/돌파':   "내일은 추진력이 한층 더 강해지는 흐름이에요. 오늘의 휴식이 내일의 추진을 만들어요.",
    '용기/내면':   "내일은 작은 용기가 큰 변화를 부르는 흐름이에요. 오늘은 충분히 쉬어두세요.",
    '성찰/내면':   "내일은 깊은 성찰이 답을 주는 흐름이에요. 오늘부터 조용한 시간을 준비해두세요.",
    '변화/순환':   "내일은 흐름이 한 번 전환되는 날입니다. 오늘은 마음을 가볍게 비워두세요.",
    '변화/돌파':   "내일은 묵은 것을 털고 새 길로 진입하는 흐름이에요. 오늘 미련은 오늘 두고 가세요.",
    '균형/정의':   "내일은 공정한 판단이 길을 여는 흐름이에요. 오늘의 감정은 오늘 마무리하세요.",
    '인내/관점':   "내일은 한 박자 늦추는 게 답인 흐름이에요. 오늘부터 호흡을 깊게 가져가세요.",
    '균형/조화':   "내일은 부드러운 균형이 빛나는 날입니다. 오늘은 극단을 피해 가볍게.",
    '욕망/속박':   "내일은 진짜 원하는 것을 분별하는 흐름이에요. 오늘의 충동은 한 박자 미뤄두세요.",
    '희망/영감':   "내일은 영감이 풍부하게 흘러드는 흐름이에요. 오늘 밤은 마음을 열어두세요.",
    '결단/각성':   "내일은 명료한 결단이 길을 여는 날입니다. 오늘은 여러 가능성을 정리해두세요.",
    '완성/성취':   "내일은 결실이 다가오는 흐름이에요. 오늘 미뤄둔 마지막 한 걸음만 준비해두세요.",
    '안정/풍요':   "내일은 안정적인 풍요가 자리 잡는 흐름이에요. 오늘의 일과를 깔끔하게 마무리하세요.",
}


def _dream_text(card_key):
    """카드 키 → 꿈의 메시지 (카테고리 매핑)"""
    cat = _get_category(card_key)
    return DREAM_MESSAGES_BY_CATEGORY.get(cat, DREAM_MESSAGES_BY_CATEGORY['안정/풍요'])


def _bridge_text(today_key, tomorrow_key):
    """오늘→내일 카드 카테고리 기반 연결 문장"""
    if not tomorrow_key:
        return None
    tomorrow_cat = _get_category(tomorrow_key)
    return BRIDGE_BY_CATEGORY.get(
        tomorrow_cat,
        "내일도 본인만의 흐름으로 자연스럽게 흘러갈 수 있어요."
    )


# ============================================================
# 주간 p1 — 새 제목: "{NAME}님의 운세 리딩" + 부제 "주간 운세 (Day n/7)"
# ============================================================

def build_weekly_page1(story, customer, profile, card_data, direction_kr,
                       card_key, date_obj, styles, day_num, total_days):
    """
    주간 PDF의 1일자 첫 페이지.
    일간 build_page1과 동일한 카드 박스 + 핵심 키워드 구조이지만,
    제목과 부제만 주간용으로 새로 작성.
    """
    wd = ['월', '화', '수', '목', '금', '토', '일'][date_obj.weekday()]
    date_str = f"{date_obj.year}년 {date_obj.month}월 {date_obj.day}일 {wd}요일"
    # ⭐ MBTI '모름' 시 프로필 줄에서 MBTI 부분 생략
    if customer['mbti'] == '모름':
        profile_str = (
            f"{profile.get('STAR', '')} · "
            f"{profile.get('ZOD', '')} · {profile.get('BIRTH', '')}"
        )
    else:
        profile_str = (
            f"{customer['mbti']} · {profile.get('STAR', '')} · "
            f"{profile.get('ZOD', '')} · {profile.get('BIRTH', '')}"
        )

    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'

    # ─── 메인 제목 (이름 강조) ───
    story.append(Paragraph(
        f"{customer['name']}님의 운세 리딩",
        styles['title']
    ))

    # ─── 부제: 주간 운세 · 날짜 · Day n/7 ───
    subtitle_text = (
        f"주간 운세 · {date_str} · <b>Day {day_num} / {total_days}</b>"
    )
    story.append(Paragraph(subtitle_text, ParagraphStyle(
        'wk_sub1', fontName=main_font, fontSize=14, leading=18,
        alignment=TA_CENTER, textColor=C['PURPLE'], spaceAfter=4
    )))

    # ─── 셋째 줄: 프로필 정보 ───
    story.append(Paragraph(profile_str, ParagraphStyle(
        'wk_sub2', fontName=main_font, fontSize=13, leading=17,
        alignment=TA_CENTER, textColor=C['DG'], spaceAfter=12
    )))
    story.append(sp(4))

    main_tone = get_main_tone(card_key, length='weekly')

    # ─── 카드 박스 (일간 build_page1과 동일) ───
    card_img_path = get_card_image_path(card_data['card_id_base'])
    if card_img_path.exists():
        card_img = Image(str(card_img_path), width=55*mm, height=90*mm)
    else:
        card_img = Paragraph(
            f"<b>{card_data['name']}</b><br/>{card_data.get('kr', '')}<br/><br/>({direction_kr})",
            styles['quote']
        )

    info_label = ParagraphStyle('info_label', fontName=main_font, fontSize=13, leading=17, textColor=C['DG'])
    info_card_name = ParagraphStyle('info_card', fontName=bold_font, fontSize=22, leading=27, textColor=C['BROWN'])
    info_keyword = ParagraphStyle('info_kw', fontName=main_font, fontSize=13, leading=17, textColor=C['DG'], spaceAfter=8)
    info_body = ParagraphStyle('info_body', fontName=main_font, fontSize=14, leading=20, alignment=TA_JUSTIFY, textColor=C['NIGHT'])
    info_msg_label = ParagraphStyle('info_msg', fontName=bold_font, fontSize=14, leading=18, textColor=C['BROWN'], spaceBefore=6, spaceAfter=4)

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
        ParagraphStyle('dir', fontName=bold_font, fontSize=15, leading=19,
                       alignment=TA_CENTER, textColor=C['PURPLE'])
    ))
    story.append(sp(8))
    story.append(Paragraph(f'"{main_tone["core"]}"', styles['core']))

    story.append(PageBreak())


# ============================================================
# 주간 p5 — 행운 아이템 15개 (일간 10개 + 5개 추가) + 확언
# ============================================================

def build_weekly_page5(story, customer, profile, lucky, card_key, styles):
    """주간 행운 아이템 페이지 — 15개 + 확언 3문장."""
    main_tone = get_main_tone(card_key, length='weekly')

    story.append(section_header(
        f"이번 주의 행운 아이템 — '{main_tone['keyword']}'을 부르는 것들",
        styles, C['GOLD']
    ))
    story.append(sp(12))

    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'

    # 행운의 숫자: 주간은 4개로 확장
    nums_parts = [
        lucky.get('행운의 숫자1', ''),
        lucky.get('행운의 숫자2', ''),
        lucky.get('행운의 숫자3', ''),
        lucky.get('행운의 숫자4', ''),
    ]
    nums_str = ', '.join(str(n) for n in nums_parts if n)

    # 15개 — 7행 × 4열 (왼쪽 라벨/값, 오른쪽 라벨/값) + 마지막 한 줄 행운의 복권 단독
    # 좌: 색·음식·방향·숫자·귀인·원석·복권     (7개)
    # 우: 향기·소재·음악·황금시간대·차·꽃·피해야할것·행운물건  (8개)
    # → 좌7 + 우8 = 15개. 행 수: max(7,8)=7행이지만 7행으로는 14칸. 마지막 1개는 별행 처리.
    # 깔끔하게 8행 4열 (14칸+빈칸2)로 가는 게 더 안정적
    
    rows = [
        ['행운의 색',       lucky.get('행운의 색', ''),         '추천 향기',       lucky.get('추천 향기', '')],
        ['행운의 음식',     lucky.get('행운의 음식', ''),       '추천 소재',       lucky.get('추천 소재', '')],
        ['행운의 방향',     lucky.get('행운의 방향', ''),       '추천 음악',       lucky.get('추천 음악', '')],
        ['행운의 숫자',     nums_str,                            '황금 시간대',     lucky.get('황금 시간대', '')],
        ['귀인 조우',       lucky.get('귀인 조우', ''),         '추천 차',         lucky.get('추천 차', '')],
        ['행운의 원석',     lucky.get('행운의 원석', ''),       '행운의 꽃',       lucky.get('행운의 꽃', '')],
        ['오늘의 행운 물건', lucky.get('오늘의 행운 물건', ''), '피해야 할 것',    lucky.get('피해야 할 것', '')],
        ['행운의 복권',     lucky.get('행운의 복권', ''),       '',                ''],
    ]

    lucky_table = Table(rows, colWidths=[30*mm, 53*mm, 30*mm, 53*mm])
    lucky_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), main_font),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('FONTNAME', (0, 0), (0, -1), bold_font),
        ('FONTNAME', (2, 0), (2, -1), bold_font),
        ('BACKGROUND', (0, 0), (0, -1), C['LE']),
        ('BACKGROUND', (2, 0), (2, -2), C['LE']),  # 마지막 행 우측은 빈칸이라 배경색 X
        ('TEXTCOLOR', (0, 0), (0, -1), C['EARTH']),
        ('TEXTCOLOR', (2, 0), (2, -1), C['EARTH']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.3, C['GOLD']),
        # 마지막 행의 빈 칸 2개는 테두리/배경 정리
        ('BACKGROUND', (2, -1), (-1, -1), C['CREAM']),
        ('LINEAFTER', (1, -1), (1, -1), 0.3, C['GOLD']),
    ]))
    story.append(kt([lucky_table]))
    story.append(sp(14))

    # ─── 확언 3문장 ───
    story.append(Paragraph(
        "이번 주의 확언 3문장 - 아침에 소리내어 읽어보세요 (또는, 속으로 읽어보세요.)",
        ParagraphStyle('aff_title', fontName=bold_font, fontSize=18, leading=22,
                       alignment=TA_CENTER, textColor=C['INDIGO'],
                       spaceBefore=10, spaceAfter=8)
    ))
    story.append(sp(4))

    affirmations = [
        f"나는 이번 주 <b>'{main_tone['keyword']}'</b>의 흐름을 신뢰하며 한 걸음 내딛는다.",
        f"내 안의 {profile.get('ELEMENT', '')} 기운이 이번 주의 흐름을 든든히 받쳐준다.",
        f"오늘 {customer['name']}{josa_i(customer['name'])} 내리는 선택은 미래의 나에게 좋은 선물이 된다.",
    ]

    for aff in affirmations:
        story.append(Paragraph(f'"{aff}"', styles['quote']))
        story.append(sp(3))

    story.append(PageBreak())


# ============================================================
# 주간 p6 — 일간 p6 + 꿈 메시지 + 내일 카드 미리보기
# ============================================================

def build_weekly_page6(story, customer, profile, card_data, direction, card_key,
                      lucky, styles, day_num, total_days,
                      tomorrow_card_key=None, tomorrow_date=None,
                      tomorrow_card_data=None, tomorrow_direction_kr=None,
                      author_info=None, length='weekly'):
    """
    주간 종합 리딩 페이지 (p6).
    일간 p6 내용 그대로 + 꿈 메시지 + 내일 카드 미리보기.
    마지막 날(day_num == total_days)에는 author_info 박스 표시.
    length: 'weekly'(기본) 또는 'monthly' (make_monthly에서 재활용 시 전달)
    """
    mbti = customer['mbti']
    # ⭐ MBTI '모름' 시 통합 메시지 계산은 임의 MBTI로 (mbti 행은 표에서 제외됨)
    safe_mbti = 'INTJ' if mbti == '모름' else mbti
    intg = get_integrated_message(card_key, profile, safe_mbti, direction, length=length)
    main_tone = get_main_tone(card_key, length=length)

    story.append(section_header(
        f"Day {day_num} 종합 리딩 — 5가지 운세가 같이 말하는 것",
        styles, C['BROWN']
    ))
    story.append(sp(12))

    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'

    # ─── 핵심 키워드 ───
    story.append(Paragraph(
        f"<b>오늘의 핵심 키워드</b>",
        ParagraphStyle('kw_label', fontName=main_font, fontSize=14, leading=18,
                       alignment=TA_CENTER, textColor=C['DG'])
    ))
    story.append(Paragraph(
        f'<b>{intg["keyword"]}</b>',
        ParagraphStyle('kw_big', fontName=bold_font, fontSize=30, leading=38,
                       alignment=TA_CENTER, textColor=C['GOLD'],
                       spaceBefore=4, spaceAfter=14)
    ))

    # ─── 5가지 운세 통합 표 (셀을 Paragraph로 감싸 <b> 태그 렌더링) ───
    # 표 셀 전용 스타일 — 좌측 라벨용 / 우측 본문용
    cell_label_style = ParagraphStyle(
        'cell_label', fontName=bold_font, fontSize=14, leading=18,
        alignment=TA_CENTER, textColor=C['BROWN']
    )
    cell_body_style = ParagraphStyle(
        'cell_body', fontName=main_font, fontSize=14, leading=19,
        alignment=TA_LEFT, textColor=C['NIGHT']
    )
    cell_header_style = ParagraphStyle(
        'cell_header', fontName=bold_font, fontSize=14, leading=18,
        alignment=TA_CENTER, textColor=C['CREAM']
    )

    def P(txt, style):
        return Paragraph(txt, style)

    rows = [
        [P("운세", cell_header_style),                                                  P("오늘 이 운세가 말하는 것", cell_header_style)],
        [P(f"타로 · {card_data.get('kr', card_data['name'])}", cell_label_style),       P(intg['rows']['tarot'], cell_body_style)],
    ]
    # ⭐ MBTI '모름' 시 MBTI 행 제외
    if mbti != '모름':
        rows.append([P(f"MBTI · {mbti}", cell_label_style),                              P(intg['rows']['mbti'],  cell_body_style)])
    rows.extend([
        [P(f"사주 · {profile.get('ELEMENT', '')} 일간", cell_label_style),               P(intg['rows']['saju'],  cell_body_style)],
        [P(f"별자리 · {profile.get('STAR', '')}", cell_label_style),                     P(intg['rows']['star'],  cell_body_style)],
        [P(f"띠 · {profile.get('ZOD', '')}", cell_label_style),                          P(intg['rows']['zod'],   cell_body_style)],
    ])
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
    story.append(sp(12))

    # ─── 5가지가 가리키는 방향 ───
    story.append(kt([
        Paragraph("✦ 5가지가 동시에 가리키는 방향", styles['h3']),
        Paragraph(intg['integration'], styles['body_just']),
    ]))
    story.append(sp(10))

    # ─── 꿈의 메시지 (⭐ 주간 전용) ───
    story.append(kt([
        Paragraph("✦ 오늘 밤 꿈의 메시지", styles['h3']),
        Paragraph(_dream_text(card_key), styles['body_just']),
    ]))
    story.append(sp(10))

    # ─── 내일 카드 미리보기 / 한 주 마무리 (⭐ 주간 전용) ───
    if tomorrow_card_key and tomorrow_card_data:
        bridge = _bridge_text(card_key, tomorrow_card_key)
        tomorrow_name = tomorrow_card_data.get('name', '')
        tomorrow_kr   = tomorrow_card_data.get('kr', '')
        tomorrow_tone = get_main_tone(tomorrow_card_key)
        tomorrow_keyword = tomorrow_tone['keyword']

        preview_text = (
            f"내일({tomorrow_date.month}월 {tomorrow_date.day}일)의 카드는 "
            f"<b>{tomorrow_name}</b> · {tomorrow_kr} <b>({tomorrow_direction_kr})</b>이에요. "
            f"키워드는 <b>'{tomorrow_keyword}'</b>입니다. {bridge}"
        )
        story.append(kt([
            Paragraph("✦ 내일과의 에너지 연결", styles['h3']),
            Paragraph(preview_text, styles['body_just']),
        ]))
    else:
        # 마지막 날 — 한 주 마무리
        closing_text = (
            f"이번 주의 마지막 날이에요. 지난 7일 동안 흘러온 에너지를 잠시 되짚어보세요. "
            f"가장 마음에 남은 한 가지가 있다면, 그것이 다음 주로 가져갈 씨앗입니다. "
            f"{customer['name']}님의 한 주가 의미 있는 시간이었기를 바랍니다."
        )
        story.append(kt([
            Paragraph("✦ 한 주를 마무리하며", styles['h3']),
            Paragraph(closing_text, styles['body_just']),
        ]))

    # 작성자/판매처 정보는 모든 페이지 푸터에 표시됨 (WeeklyNumberedCanvas.author_suffix 사용)
    # 따라서 마지막 7일차 박스는 제거됨.

    story.append(PageBreak())


# ============================================================
# 메인 함수
# ============================================================

def make_weekly_pdf(customer, start_date=None, output_path=None, author_info=None,
                    store_link='', counsel_link='', shuffle_seed=None):
    """
    주간 PDF 생성 (6페이지 × 7일 = 42페이지).

    Parameters
    ----------
    customer : dict
        {'name', 'mbti', 'birthdate', 'jisi'}
    start_date : date | str | None
        주간 시작일 (None이면 오늘부터)
    output_path : str | Path | None
        저장 경로 (None이면 자동)
    author_info : dict | None
        하단 작성자/사업자 정보. 마지막 7일차 p6 하단에 표시.
        {
          'creator_name': '루밍 (looming)',
          'business_name': '이설빈 / 사업자등록번호 000-00-00000',
          'contact': '문의: example@email.com',
          'platform': '크몽 판매 상품',
        }
        None이면 표시 안 됨.
    """
    if start_date is None:
        start_date = date.today()
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()

    # 만세력 (한 번만)
    profile = calc_profile_jisi(customer['birthdate'], customer.get('jisi'))
    profile['NAME'] = customer['name']

    # 카드 DB 로드
    with open(CARDS_DB_FILE, encoding='utf-8') as f:
        cards_db = json.load(f)

    mbti = customer['mbti']
    # ⭐ "모름" 처리 — 카드 로딩에 사용할 안전 키
    cards_lookup_key = next(iter(cards_db.keys())) if mbti == '모름' else mbti

    # 폰트 + 스타일
    register_fonts()
    styles = make_styles()

    # 푸터 설정
    WeeklyNumberedCanvas.customer_name = customer['name']
    registered = pdfmetrics.getRegisteredFontNames()
    WeeklyNumberedCanvas.primary_font = 'NanumGothic' if 'NanumGothic' in registered else 'Helvetica'
    # ⭐ 푸터 제목과 작성자/판매처 정보 설정
    WeeklyNumberedCanvas.footer_title = (author_info or {}).get('footer_title', '운세의 정원') if author_info else '운세의 정원'
    WeeklyNumberedCanvas.author_suffix = (author_info or {}).get('author_suffix', '') if author_info else ''

    # 출력 경로
    if output_path is None:
        start_str = start_date.strftime('%Y%m%d')
        end_str = (start_date + timedelta(days=6)).strftime('%m%d')
        output_path = OUTPUT_DIR / f"{customer['name']}_주간운세_{start_str}_{end_str}.pdf"
    else:
        output_path = Path(output_path)

    # PDF 빌드
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm, bottomMargin=20*mm,
        title=f"{customer['name']}님 주간 운세",
        author='루밍 (looming)',
    )

    # ─── 7일치 카드 미리 계산 (내일 카드 연결용) ───
    daily_data = []
    for i in range(7):
        d = start_date + timedelta(days=i)
        card_id_base, direction = pick_card_for_date(d, shuffle_seed=shuffle_seed)
        direction_kr = '정방향' if direction == 'upright' else '역방향'
        card_key = f"{card_id_base}_{direction}"
        card_data = dict(cards_db[cards_lookup_key][card_key])
        card_data['card_id_base'] = card_id_base
        lucky = get_weekly_items(profile, card_key, d)
        daily_data.append({
            'date': d,
            'card_id_base': card_id_base,
            'direction': direction,
            'direction_kr': direction_kr,
            'card_key': card_key,
            'card_data': card_data,
            'lucky': lucky,
        })

    # ─── 7일 루프 — 각 일자에 6페이지씩 ───
    story = []
    
    # ⭐ 표지 페이지 (p1)
    wd = ['월', '화', '수', '목', '금', '토', '일'][start_date.weekday()]
    end_date = start_date + timedelta(days=6)
    date_str_kor = (
        f"{start_date.year}년 {start_date.month}월 {start_date.day}일 {wd}요일 ~ "
        f"{end_date.month}월 {end_date.day}일"
    )
    build_cover_page(
        story, customer,
        pdf_type='주간',
        date_str=date_str_kor,
        subtitle_extra='Day 1 → Day 7',
    )
    
    # ⭐ 도입 페이지 (p2)
    build_intro_page(
        story,
        pdf_type='주간',
        store_link=store_link,
        counsel_link=counsel_link,
        customer=customer,
        date_str=date_str_kor,
    )
    
    total_days = 7
    for day_idx, d in enumerate(daily_data):
        day_num = day_idx + 1

        # p1: 주간 전용 (제목 + 부제 + Day n/7 표기)
        build_weekly_page1(story, customer, profile,
                           d['card_data'], d['direction_kr'], d['card_key'],
                           d['date'], styles, day_num, total_days)
        # p2~p4: 일간과 동일 (재활용)
        build_page2_mbti(story, customer, profile,
                         d['card_data'], d['direction'], d['card_key'],
                         d['date'], styles)
        build_page3_monthly_flow(story, customer, profile,
                                 d['card_key'], d['date'], styles)
        build_page4_astro(story, customer, profile,
                          d['card_key'], d['date'], styles)
        build_weekly_page5(story, customer, profile, d['lucky'],
                          d['card_key'], styles)

        # p6: 주간 전용 (꿈 메시지 + 내일 카드 미리보기)
        if day_idx < 6:
            tomorrow = daily_data[day_idx + 1]
            tomorrow_card_key = tomorrow['card_key']
            tomorrow_date = tomorrow['date']
            tomorrow_card_data = tomorrow['card_data']
            tomorrow_direction_kr = tomorrow['direction_kr']
        else:
            tomorrow_card_key = None
            tomorrow_date = None
            tomorrow_card_data = None
            tomorrow_direction_kr = None

        build_weekly_page6(
            story, customer, profile,
            d['card_data'], d['direction'], d['card_key'],
            d['lucky'], styles, day_num, total_days,
            tomorrow_card_key=tomorrow_card_key,
            tomorrow_date=tomorrow_date,
            tomorrow_card_data=tomorrow_card_data,
            tomorrow_direction_kr=tomorrow_direction_kr,
            author_info=author_info,
        )

    # ⭐ 배경지 적용 (2026-05-17 추가)
    # cover_page=1: 표지 페이지
    # skip_pages=(2,): 도입 페이지(p2)는 배경 OFF — 가독성 우선
    bg = make_bg_painter(cover_page=1, skip_pages=(2,))

    doc.build(story, onFirstPage=bg, onLaterPages=bg, canvasmaker=WeeklyNumberedCanvas)
    return output_path


# ============================================================
# CLI / 단독 실행
# ============================================================

if __name__ == '__main__':
    sample_customer = {
        'name': '홍길동',
        'mbti': 'INTJ',
        'birthdate': '1990-05-15',
        'jisi': None,
    }

    # ===== 작성자 정보 — 루밍이 직접 수정해서 사용 =====
    sample_author_info = {
        'creator_name':  '루밍 (looming)',
        'business_name': '이설빈 / 사업자등록번호: 000-00-00000',
        'contact':       '문의: looming@example.com',
        'platform':      '크몽 / 숨고 / 텀블벅 판매 상품',
    }

    print("=" * 60)
    print("make_weekly.py — 주간 PDF 생성 (6페이지 × 7일 = 42페이지)")
    print("=" * 60)
    print(f"고객: {sample_customer['name']} ({sample_customer['mbti']})")
    print(f"생년월일: {sample_customer['birthdate']}")
    print(f"주간 시작일: {date.today()}")
    print(f"주간 종료일: {date.today() + timedelta(days=6)}")
    print()

    try:
        pdf_path = make_weekly_pdf(sample_customer, author_info=sample_author_info)
        print(f"✅ PDF 생성 완료: {pdf_path}")
        print(f"   파일 크기: {pdf_path.stat().st_size:,} bytes")
    except FileNotFoundError as e:
        print(f"⚠️  필수 파일 없음: {e}")
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()

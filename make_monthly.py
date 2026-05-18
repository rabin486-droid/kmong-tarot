"""
make_monthly.py
===============
크몽 MBTI 타로 운세 — 월간 PDF 생성기 (7페이지 × 30일 = 210페이지)

[작성자] 루밍 (looming)
[프로젝트] 크몽 MBTI 타로 운세 PDF 서비스

[페이지 구조 — 1일당 7페이지]
  p1: 메인 제목 + "월간 운세 · Day n/30" + 카드 박스
  p2: MBTI 심층 해석                     (일간 재활용)
  p3: 이달 흐름과의 연결                  (일간 재활용)
  p4: 별자리·띠·에너지 지도               (일간 재활용)
  p5: 행운 아이템 20개 + 확언 3문장        (월간 전용)
  p6: 종합 리딩 + 꿈 메시지 + 내일 카드   (주간 build_weekly_page6 재활용)
  p7: ⭐ 달의 위상 + 저널 Q&A 3개 + 이달 목표 (월간 전용)

  → 30일치 = 210페이지
  → 푸터: '루밍의 MBTI 타로 운세 | 월간 운세 | {NAME}님 전용 | n/210'

[입력]
  customer: dict (name, mbti, birthdate, jisi)
  start_date: 월 시작일 (None이면 이번 달 1일)
  days: 일수 (기본 30)
  output_path: 저장 경로
  author_info: dict | None — 마지막 30일차 p7 하단에 표시
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
from lucky_items import get_monthly_items

from integration import (
    get_main_tone, get_element_support,
    get_star_support, get_zod_support,
    get_mbti_card_link, get_monthly_flow,
    get_integrated_message,
    _get_category,
    josa_i, josa_eun, josa_eul, josa_wa, josa_ira,
)

from intro_pages import build_cover_page, build_intro_page

# make_daily.py의 공통 유틸 + p2~p4 재활용
from make_daily import (
    C, register_fonts, make_styles, pick_card_for_date,
    get_card_image_path, fill, kt, sp, section_header,
    CARDS_DB_FILE, OUTPUT_DIR,
    build_page2_mbti, build_page3_monthly_flow,
    build_page4_astro,
)

# make_weekly.py의 p6 (종합 리딩 + 꿈 메시지 + 내일 카드 미리보기)
from make_weekly import build_weekly_page6

# 배경지 페인터 (2026-05-17 추가)
from backgrounds import make_bg_painter


# ============================================================
# 월간 푸터 — 1/210 ~ 210/210
# ============================================================

class MonthlyNumberedCanvas(rl_canvas.Canvas):
    # ⭐ 푸터 형식: {title}는 자유 입력 (예: "운세의 정원")
    footer_template = '{title}  |  월간 운세  |  {name}님 전용  |  {n}/{total}'
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
# 달의 4단계 위상
# ============================================================
# 초승달(1~7일) → 상현달(8~15일) → 보름달(16~22일) → 그믐달(23~30일+)

LUNAR_PHASES = [
    {
        'text_name': '초승달',
        'phase_text': '새로운 시작과 씨앗을 심는 시기',
        'keywords': ['시작', '의도', '씨앗', '가능성'],
        'guide': (
            "초승달은 새 시작과 의도를 정하는 시기예요. "
            "마음에 품은 의도를 종이에 적어두면, 한 달의 흐름이 그 방향으로 흘러갑니다. "
            "거창한 목표보다 소박하고 구체적인 의도가 더 잘 자랍니다."
        ),
        'practice': '오늘 하나의 의도를 종이에 적고, 잘 보이는 곳에 붙여두세요.',
    },
    {
        'text_name': '상현달',
        'phase_text': '성장과 행동의 시기',
        'keywords': ['성장', '실행', '추진', '확장'],
        'guide': (
            "상현달은 초승달에 심은 의도가 자라나는 시기예요. "
            "이제 작게라도 행동으로 옮길 때입니다. "
            "장애물이 보여도 그것은 성장의 자극일 뿐이에요."
        ),
        'practice': '의도를 행동으로 옮기는 첫 단계 하나를 오늘 실행해보세요.',
    },
    {
        'text_name': '보름달',
        'phase_text': '결실과 명료함의 시기',
        'keywords': ['결실', '완성', '드러남', '명료함'],
        'guide': (
            "보름달은 그동안 자라난 것들이 가장 또렷하게 드러나는 시기예요. "
            "감사할 일과 정리할 일이 함께 보이는 때이기도 합니다. "
            "감정도 평소보다 더 크게 느껴질 수 있으니 깊은 호흡을 챙기세요."
        ),
        'practice': '오늘 감사한 일 3가지를 적고, 정리하고 싶은 것 하나도 함께 적어보세요.',
    },
    {
        'text_name': '그믐달',
        'phase_text': '내려놓기와 정리의 시기',
        'keywords': ['내려놓기', '회복', '정리', '준비'],
        'guide': (
            "그믐달은 이번 주기를 정리하고 다음 새 달을 준비하는 시기예요. "
            "더 이상 필요 없는 것을 부드럽게 내려놓는 시간입니다. "
            "쉬는 것도 적극적인 행동임을 기억하세요."
        ),
        'practice': '오늘은 한 가지를 정리하거나 내려놓아보세요. 물건이든 생각이든.',
    },
]


def get_lunar_phase(day_in_month):
    """월 안에서의 일자(1~31) → 달의 위상 단계 반환"""
    if day_in_month <= 7:
        return LUNAR_PHASES[0]  # 초승달
    elif day_in_month <= 15:
        return LUNAR_PHASES[1]  # 상현달
    elif day_in_month <= 22:
        return LUNAR_PHASES[2]  # 보름달
    else:
        return LUNAR_PHASES[3]  # 그믐달


# ============================================================
# 저널 Q&A — 카드 카테고리별 3개 질문 + 답안 가이드
# ============================================================

JOURNAL_QA_BY_CATEGORY = {
    '시작/모험': [
        ('오늘 새로 시작하고 싶은 것이 하나 있다면, 그건 무엇인가요?',
         '구체적으로 적을수록 시작이 가까워져요. 막연한 "건강하게 살기"보다 "주 3회 산책"처럼.'),
        ('내가 시작하지 못하는 진짜 이유는 무엇일까요?',
         '실패에 대한 두려움일까요, 완벽주의일까요? 그 이름을 알면 다루기 쉬워져요.'),
        ('오늘 단 하나만 시작한다면, 가장 작은 한 걸음은 무엇일까요?',
         '5분만 하면 되는 일로 정해보세요. 그 정도라면 오늘 안에 가능해요.'),
    ],
    '창조/실행': [
        ('머릿속에서 오래 굴려온 아이디어가 있다면, 그건 무엇인가요?',
         '꺼내놓는 것 자체가 창조의 시작이에요. 완성도는 신경 쓰지 말고 적어보세요.'),
        ('그 아이디어를 실현하는 데 가장 큰 장애물은 무엇인가요?',
         '시간 부족, 자원 부족? 아니면 평가에 대한 두려움? 진짜 이유를 들여다보세요.'),
        ('오늘 그 아이디어를 위해 할 수 있는 가장 작은 행동은?',
         '메모, 검색, 한 사람에게 말하기 — 무엇이든 좋아요. 작아도 시작이 되니까.'),
    ],
    '직관/지혜': [
        ('최근에 마음 깊은 곳에서 느낀 한 가지 신호는 무엇인가요?',
         '논리로는 설명 안 되지만 분명히 느껴진 그것. 직관은 종종 그렇게 다가와요.'),
        ('그 신호가 나에게 무엇을 말하고 있다고 생각하나요?',
         '서둘러 해석하지 말고 그저 곁에 두어보세요. 답은 시간이 알려줄 거예요.'),
        ('내가 가장 명료하게 생각할 수 있는 시간/장소는 어디인가요?',
         '그 시간/장소를 의도적으로 자주 만들어보세요. 직관은 거기서 자랍니다.'),
    ],
    '풍요/사랑': [
        ('내가 받은 것 중 가장 따뜻했던 것은 무엇이었나요?',
         '받은 만큼 누군가에게도 전할 수 있어요. 풍요는 흐를 때 더 커집니다.'),
        ('나는 충분히 받을 자격이 있다고 믿나요?',
         '받기를 어려워한다면, 받는 연습부터 해보세요. 작은 호의를 자연스럽게 받기.'),
        ('오늘 누군가에게 따뜻한 한마디를 건넨다면, 누구일까요?',
         '꼭 거창하지 않아도 돼요. 한 줄의 안부가 큰 의미가 될 수 있어요.'),
    ],
    '안정/권위': [
        ('내가 쌓아온 것 중 가장 자랑스러운 한 가지는?',
         '소소해 보여도 시간이 들어간 것이라면 충분히 자랑해도 돼요.'),
        ('지금 책임지고 있는 일 중 부담스러운 것은 무엇인가요?',
         '혼자 짊어진다고 다 책임지는 건 아니에요. 나눌 수 있는 부분도 보세요.'),
        ('나의 기반을 더 단단하게 만드는 한 가지 습관은?',
         '큰 변화가 아니어도 좋아요. 매일 5분의 같은 행동이 기반이 됩니다.'),
    ],
    '전통/교육': [
        ('최근에 깊이 배우고 싶었던 것은 무엇인가요?',
         '관심이 가는 분야는 곧 성장의 신호예요. 작은 단위로 시작해보세요.'),
        ('나에게 가르침을 준 사람 중 가장 기억에 남는 사람은?',
         '그 사람이 준 것을 떠올려보면, 내가 누군가에게 줄 수 있는 것도 보여요.'),
        ('오늘 새로 알게 된 한 가지는 무엇인가요?',
         '하루에 하나씩만 적어도, 한 달이면 30가지가 쌓여요.'),
    ],
    '관계/조화': [
        ('지금 내 곁에 있는 사람 중 가장 고마운 사람은 누구인가요?',
         '그 사람에게 오늘 안부 한 줄 보내보세요. 짧아도 진심은 전해져요.'),
        ('관계에서 가장 어려운 부분은 무엇인가요?',
         '솔직한 표현, 거리 두기, 갈등 해결... 무엇이든 그 자체로 답을 향한 첫 걸음이에요.'),
        ('내가 관계에서 가장 잘하는 한 가지는?',
         '그것을 자각하면 관계가 더 자연스러워져요. 본인의 강점을 신뢰하세요.'),
    ],
    '추진/돌파': [
        ('지금 미뤄두고 있는 결단이 있나요?',
         '미루는 것도 결정의 한 형태예요. 그러나 그 결정의 비용을 알고 있는 게 중요해요.'),
        ('그 결단을 미루는 진짜 이유는 무엇인가요?',
         '두려움인지, 시기인지, 정보 부족인지 분별해보세요. 각각 다른 처방이 필요해요.'),
        ('결단을 위해 오늘 할 수 있는 가장 작은 정보 수집은?',
         '한 명에게 묻기, 한 글 읽기 — 그 정도면 충분히 다음으로 갈 수 있어요.'),
    ],
    '용기/내면': [
        ('내가 가장 두려워하는 한 가지는 무엇인가요?',
         '두려움을 이름 부르면 그 크기가 줄어들어요. 적어보는 것 자체가 용기예요.'),
        ('그 두려움 너머에 진짜 원하는 것은 무엇일까요?',
         '두려움이 큰 만큼 그 너머에 있는 것도 소중한 거예요.'),
        ('오늘 가장 작은 용기 하나는 무엇이었나요?',
         '거창하지 않아도 좋아요. 망설이다가 한 행동, 그게 다 용기였어요.'),
    ],
    '성찰/내면': [
        ('지금 나에게 가장 필요한 것은 무엇인가요?',
         '쉼, 위로, 자극, 변화 — 본인에게 솔직해지면 답이 보여요.'),
        ('최근에 본인을 칭찬한 마지막 순간은 언제였나요?',
         '본인을 인정하는 것도 능력이에요. 오늘은 한 가지를 의식적으로 칭찬해보세요.'),
        ('내가 가장 본래의 나로 있을 수 있는 순간은 언제인가요?',
         '그 순간을 더 자주 만들수록 다른 시간도 균형이 잡혀요.'),
    ],
    '변화/순환': [
        ('지금 자연스럽게 끝나가는 것이 있다면 무엇인가요?',
         '억지로 붙잡지 않는 것도 지혜예요. 끝은 새 시작의 다른 이름이니까.'),
        ('변화 앞에서 내가 가장 자주 느끼는 감정은?',
         '두려움, 설렘, 슬픔... 그 감정에 이름을 붙이면 다루기 쉬워져요.'),
        ('이번 변화를 통해 무엇을 배우고 싶나요?',
         '단순한 통과가 아니라 의미 있는 시간이 되도록, 의도를 가져보세요.'),
    ],
    '변화/돌파': [
        ('지금 무너뜨려야 할 한 가지 패턴이 있다면 무엇인가요?',
         '오래된 습관이나 관계일 수 있어요. 그게 보인다는 것 자체가 변화의 시작이에요.'),
        ('변화 후의 나는 어떤 모습이었으면 좋겠나요?',
         '구체적으로 그려볼수록 그 방향으로 자연스럽게 흘러가요.'),
        ('오늘 할 수 있는 가장 작은 돌파는 무엇인가요?',
         '미뤄둔 한 통의 메시지, 한 번의 거절 — 무엇이든 좋아요.'),
    ],
    '균형/정의': [
        ('최근에 균형을 잃었다고 느낀 순간은 언제였나요?',
         '균형은 한 번 잡고 끝이 아니에요. 일상의 흐름 속에서 계속 조율하는 것이죠.'),
        ('일과 휴식의 비율이 지금 어떤가요?',
         '7:3, 5:5, 어떤 비율이든 본인에게 맞는 게 정답이에요.'),
        ('오늘 균형을 위해 의식적으로 한 가지 한다면 무엇일까요?',
         '거창하지 않아도 좋아요. 5분 산책, 한 컵의 차 — 그것도 균형이에요.'),
    ],
    '인내/관점': [
        ('지금 기다리고 있는 결과가 있나요?',
         '기다림도 적극적인 행동이에요. 그 사이의 시간을 어떻게 채울지가 중요해요.'),
        ('이 상황을 다른 사람의 눈으로 본다면 어떻게 보일까요?',
         '한 발 떨어져 보면 그동안 못 본 게 보여요. 새로운 길도 함께.'),
        ('오늘 한 박자 늦춰도 되는 일은 무엇인가요?',
         '서두름이 늘 답은 아니에요. 의식적으로 천천히 가는 연습도 해보세요.'),
    ],
    '균형/조화': [
        ('내 안에 서로 다른 두 가지가 있다면 무엇과 무엇인가요?',
         '예: 안정과 모험, 사색과 활동. 둘 다 본인의 일부임을 인정하세요.'),
        ('그 두 가지 사이에서 어떻게 균형을 잡고 있나요?',
         '어느 한쪽이 너무 강해지면 다른 쪽이 그리워져요. 그 신호를 잘 듣기.'),
        ('오늘 어느 쪽에 조금 더 시간을 주면 좋을까요?',
         '본인의 직감이 가리키는 쪽이 답이에요.'),
    ],
    '욕망/속박': [
        ('지금 내가 가장 강하게 원하는 것은 무엇인가요?',
         '솔직하게 적어보세요. 외면하던 욕구를 인정하는 것도 자유의 시작이에요.'),
        ('그것을 원하는 이유는 무엇인가요?',
         '진짜 욕구인지, 외부의 영향인지 분별해보면 다음 길이 보여요.'),
        ('내가 자유로워지고 싶은 한 가지가 있다면?',
         '집착, 관계, 습관 — 무엇이든 자각하는 것 자체가 첫 걸음이에요.'),
    ],
    '희망/영감': [
        ('최근에 마음을 두근거리게 한 무언가가 있었나요?',
         '아주 작은 것이라도 좋아요. 그것이 영감의 씨앗이 될 수 있어요.'),
        ('내가 가장 빛났던 순간은 언제였나요?',
         '그 순간의 기억을 자주 꺼내보세요. 어둠 속의 등불이 됩니다.'),
        ('오늘 누군가에게 영감을 줄 수 있다면, 어떤 메시지일까요?',
         '본인에게 가장 필요한 메시지가 동시에 다른 사람에게도 닿는 경우가 많아요.'),
    ],
    '결단/각성': [
        ('지금 가장 명료하게 결정할 수 있는 한 가지는 무엇인가요?',
         '큰 결정이 아니어도 돼요. 오늘 점심 메뉴부터 시작해도 좋아요.'),
        ('결정을 흐릿하게 만드는 외부의 영향이 있나요?',
         '주변의 기대, 사회의 시선... 한 발 떨어져 본인의 목소리에 집중해보세요.'),
        ('오늘 내린 가장 작은 결정 하나는 무엇이었나요?',
         '의식적으로 본인이 결정했다고 느낀 순간을 기록하면 결단력이 자라요.'),
    ],
    '완성/성취': [
        ('이번 달 마무리하고 싶은 한 가지가 있다면?',
         '큰 일이 아니어도 좋아요. 작은 마무리들이 모여 큰 성취가 됩니다.'),
        ('내가 이미 이뤄낸 것 중 잊고 있던 것은 무엇인가요?',
         '본인의 작은 성취들을 자주 떠올려보세요. 그게 다음 발걸음의 연료가 돼요.'),
        ('성취 후의 빈자리를 어떻게 채우고 싶나요?',
         '다음 목표를 서두르지 말고, 잠시 그 자리에 머무는 것도 좋아요.'),
    ],
    '안정/풍요': [
        ('내가 누리고 있는 안정 중 당연하지 않은 것은 무엇인가요?',
         '평범한 일상도 자주 들여다보면 풍요로움이 보여요.'),
        ('재정/관계/건강 중 지금 가장 안정적인 영역은?',
         '그 영역의 비결을 다른 영역에도 적용해볼 수 있어요.'),
        ('나의 풍요를 더 풍성하게 만드는 한 가지 습관은?',
         '저축, 감사 기록, 정기 점검 — 작은 습관이 큰 안정을 만들어요.'),
    ],
}


# ============================================================
# 월간 p1 — "{NAME}님의 운세 리딩" + "월간 운세 · Day n/30" + 카드 박스
# ============================================================

def build_monthly_page1(story, customer, profile, card_data, direction_kr,
                        card_key, date_obj, styles, day_num, total_days):
    """월간 PDF의 첫 페이지 — 일간 p1과 동일 구조이나 제목·부제만 다름."""
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

    # ─── 메인 제목 ───
    story.append(Paragraph(
        f"{customer['name']}님의 운세 리딩",
        styles['title']
    ))
    # ─── 부제 1: 월간 운세 · 날짜 · Day n/30 ───
    subtitle_text = (
        f"월간 운세 · {date_str} · <b>Day {day_num} / {total_days}</b>"
    )
    story.append(Paragraph(subtitle_text, ParagraphStyle(
        'mt_sub1', fontName=main_font, fontSize=14, leading=18,
        alignment=TA_CENTER, textColor=C['PURPLE'], spaceAfter=4
    )))
    # ─── 부제 2: 프로필 ───
    story.append(Paragraph(profile_str, ParagraphStyle(
        'mt_sub2', fontName=main_font, fontSize=13, leading=17,
        alignment=TA_CENTER, textColor=C['DG'], spaceAfter=12
    )))
    story.append(sp(4))

    main_tone = get_main_tone(card_key, length='monthly')

    # ─── 카드 박스 ───
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
# 월간 p5 — 행운 아이템 20개 + 확언 3문장
# ============================================================

def build_monthly_page5(story, customer, profile, lucky, card_key, styles):
    """월간 행운 아이템 페이지 — 20개 + 확언 3문장."""
    main_tone = get_main_tone(card_key, length='monthly')

    story.append(section_header(
        f"이번 달의 행운 아이템 — '{main_tone['keyword']}'을 부르는 것들",
        styles, C['GOLD']
    ))
    story.append(sp(10))

    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'

    # 행운의 숫자: 월간은 6개로 확장
    nums = ', '.join(
        str(lucky.get(f'행운의 숫자{i}', '')) for i in range(1, 7)
        if lucky.get(f'행운의 숫자{i}', '') != ''
    )

    # 20개 항목 — 10행 × 4열 (라벨/값/라벨/값) 완전히 채움
    # 좌 10개: 색·음식·방향·숫자·귀인·차·행운물건·피해야·액세서리·이달선물
    # 우 10개: 향기·소재·음악·황금시간대·원석·꽃·복권·영상장르·오늘의 키워드·이달 추천 공간
    rows = [
        ['행운의 색',       lucky.get('행운의 색', ''),         '추천 향기',       lucky.get('추천 향기', '')],
        ['행운의 음식',     lucky.get('행운의 음식', ''),       '추천 소재',       lucky.get('추천 소재', '')],
        ['행운의 방향',     lucky.get('행운의 방향', ''),       '추천 음악',       lucky.get('추천 음악', '')],
        ['행운의 숫자',     nums,                                '황금 시간대',     lucky.get('황금 시간대', '')],
        ['귀인 조우',       lucky.get('귀인 조우', ''),         '행운의 원석',     lucky.get('행운의 원석', '')],
        ['추천 차',         lucky.get('추천 차', ''),           '행운의 꽃',       lucky.get('행운의 꽃', '')],
        ['오늘의 행운 물건', lucky.get('오늘의 행운 물건', ''), '행운의 복권',     lucky.get('행운의 복권', '')],
        ['피해야 할 것',    lucky.get('피해야 할 것', ''),      '추천 영상 장르', lucky.get('추천 영상 장르', '')],
        ['행운의 액세서리', lucky.get('행운의 액세서리', ''),  '오늘의 키워드',  lucky.get('오늘의 키워드', '')],
        ['이달 선물',       lucky.get('이달 선물', ''),         '이달 추천 공간', lucky.get('이달 추천 공간', '')],
    ]

    lucky_table = Table(rows, colWidths=[28*mm, 55*mm, 28*mm, 55*mm])
    lucky_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), main_font),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), bold_font),
        ('FONTNAME', (2, 0), (2, -1), bold_font),
        ('BACKGROUND', (0, 0), (0, -1), C['LE']),
        ('BACKGROUND', (2, 0), (2, -1), C['LE']),
        ('TEXTCOLOR', (0, 0), (0, -1), C['EARTH']),
        ('TEXTCOLOR', (2, 0), (2, -1), C['EARTH']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.3, C['GOLD']),
    ]))
    story.append(kt([lucky_table]))
    story.append(sp(12))

    # ─── 확언 3문장 ───
    story.append(Paragraph(
        "이번 달의 확언 3문장 - 아침에 소리내어 읽어보세요 (또는, 속으로 읽어보세요.)",
        ParagraphStyle('aff_title', fontName=bold_font, fontSize=18, leading=22,
                       alignment=TA_CENTER, textColor=C['INDIGO'],
                       spaceBefore=8, spaceAfter=8)
    ))
    story.append(sp(4))

    affirmations = [
        f"나는 이번 달 <b>'{main_tone['keyword']}'</b>의 흐름을 신뢰하며 한 걸음 내딛는다.",
        f"내 안의 {profile.get('ELEMENT', '')} 기운이 이번 달의 흐름을 든든히 받쳐준다.",
        f"오늘 {customer['name']}{josa_i(customer['name'])} 내리는 선택은 미래의 나에게 좋은 선물이 된다.",
    ]

    for aff in affirmations:
        story.append(Paragraph(f'"{aff}"', styles['quote']))
        story.append(sp(3))

    story.append(PageBreak())


# ============================================================
# 월간 p7 — ⭐ 달의 위상 + 저널 Q&A 3개 + 이달 목표
# ============================================================

def build_monthly_page7(story, customer, profile, card_key, date_obj,
                        day_in_month, mbti, lucky, styles,
                        day_num=None, total_days=None, author_info=None):
    """
    월간 전용 마지막 페이지.
      1) 달의 위상 (4단계)
      2) 저널 Q&A 3개 (카드 카테고리별)
      3) 이달 목표 연결 (lucky_items의 '이달 목표 연결' 키)
      4) 마지막 30일차에는 author_info 박스
    """
    bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    main_font = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'

    phase = get_lunar_phase(day_in_month)

    # ─── 페이지 헤더 ───
    story.append(section_header(
        f"달의 에너지 · 저널 · 이달 목표",
        styles, C['INDIGO']
    ))
    story.append(sp(10))

    # ─── 1) 달의 위상 ───
    phase_title_style = ParagraphStyle(
        'phase_title', fontName=bold_font, fontSize=16, leading=20,
        alignment=TA_CENTER, textColor=C['CREAM']
    )
    phase_header = Table(
        [[Paragraph(f"<b>{phase['text_name']}</b> · {phase['phase_text']}", phase_title_style)]],
        colWidths=[166*mm]
    )
    phase_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C['PURPLE']),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(phase_header)
    story.append(sp(8))

    story.append(kt([
        Paragraph("✦ 달의 에너지 가이드", styles['h3']),
        Paragraph(phase['guide'], styles['body_just']),
    ]))
    story.append(sp(6))

    # 키워드 박스
    kw_text = ' · '.join(phase['keywords'])
    story.append(Paragraph(
        f"<b>이 시기의 키워드 — {kw_text}</b>",
        ParagraphStyle('phase_kw', fontName=bold_font, fontSize=15, leading=20,
                       alignment=TA_CENTER, textColor=C['GOLD'],
                       spaceBefore=4, spaceAfter=8)
    ))

    story.append(kt([
        Paragraph("✦ 오늘의 달 실천", styles['h3']),
        Paragraph(phase['practice'], styles['quote']),
    ]))
    story.append(sp(12))

    # ─── 2) 저널 Q&A 3개 ───
    today_cat = _get_category(card_key)
    qa_list = JOURNAL_QA_BY_CATEGORY.get(today_cat, JOURNAL_QA_BY_CATEGORY['안정/풍요'])

    story.append(Paragraph("✦ 오늘의 저널", styles['h2']))
    story.append(Paragraph(
        "<i>아래 세 가지 질문에 마음을 열고 답해보세요. 정답은 없습니다.</i>",
        ParagraphStyle('jr_intro', fontName=main_font, fontSize=13, leading=17,
                       alignment=TA_LEFT, textColor=C['DG'], spaceAfter=6)
    ))

    for idx, (question, hint) in enumerate(qa_list, 1):
        story.append(kt([
            Paragraph(f"<b>Q{idx}. {question}</b>",
                      ParagraphStyle('q', fontName=bold_font, fontSize=14, leading=19,
                                     textColor=C['BROWN'], spaceBefore=4, spaceAfter=2)),
            Paragraph(f"<i>→ {hint}</i>",
                      ParagraphStyle('hint', fontName=main_font, fontSize=13, leading=17,
                                     textColor=C['NIGHT'], leftIndent=10, spaceAfter=6)),
        ]))

    story.append(sp(10))

    # ─── 3) 이달 목표 연결 ───
    goal_text = lucky.get('이달 목표 연결', '')
    if goal_text:
        story.append(kt([
            Paragraph("✦ 이달 목표 연결", styles['h2']),
            Paragraph(goal_text, styles['quote']),
        ]))

    # 작성자/판매처 정보는 모든 페이지 푸터에 표시됨 (MonthlyNumberedCanvas.author_suffix 사용)
    # 따라서 마지막 30일차 박스는 제거됨.

    story.append(PageBreak())


# ============================================================
# 메인 함수
# ============================================================

def make_monthly_pdf(customer, start_date=None, days=30, output_path=None, author_info=None,
                     store_link='', counsel_link='', shuffle_seed=None):
    """
    월간 PDF 생성 (7페이지 × 일수 = 일수 × 7페이지).

    Parameters
    ----------
    customer : dict
        {'name', 'mbti', 'birthdate', 'jisi'}
    start_date : date | str | None
        월 시작일 (None이면 이번 달 1일)
    days : int
        일수 (기본 30, 최대 31)
    output_path : str | Path | None
        저장 경로
    author_info : dict | None
        하단 작성자/사업자 정보. 마지막 일자 p7 하단에 표시.
    """
    if start_date is None:
        today = date.today()
        start_date = today.replace(day=1)
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
    MonthlyNumberedCanvas.customer_name = customer['name']
    registered = pdfmetrics.getRegisteredFontNames()
    MonthlyNumberedCanvas.primary_font = 'NanumGothic' if 'NanumGothic' in registered else 'Helvetica'
    # ⭐ 푸터 제목과 작성자/판매처 정보 설정
    MonthlyNumberedCanvas.footer_title = (author_info or {}).get('footer_title', '운세의 정원') if author_info else '운세의 정원'
    MonthlyNumberedCanvas.author_suffix = (author_info or {}).get('author_suffix', '') if author_info else ''

    # 출력 경로
    if output_path is None:
        ym = start_date.strftime('%Y%m')
        output_path = OUTPUT_DIR / f"{customer['name']}_월간운세_{ym}.pdf"
    else:
        output_path = Path(output_path)

    # PDF 빌드
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm, bottomMargin=20*mm,
        title=f"{customer['name']}님 월간 운세",
        author='루밍 (looming)',
    )

    # ─── 일수만큼 미리 계산 ───
    daily_data = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        card_id_base, direction = pick_card_for_date(d, shuffle_seed=shuffle_seed)
        direction_kr = '정방향' if direction == 'upright' else '역방향'
        card_key = f"{card_id_base}_{direction}"
        card_data = dict(cards_db[cards_lookup_key][card_key])
        card_data['card_id_base'] = card_id_base
        lucky = get_monthly_items(profile, card_key, mbti, d)
        daily_data.append({
            'date': d,
            'card_id_base': card_id_base,
            'direction': direction,
            'direction_kr': direction_kr,
            'card_key': card_key,
            'card_data': card_data,
            'lucky': lucky,
            'day_in_month': i + 1,  # 달 위상 계산용
        })

    # ─── 30일 루프 — 각 일자에 7페이지씩 ───
    story = []
    
    # ⭐ 표지 페이지 (p1)
    wd = ['월', '화', '수', '목', '금', '토', '일'][start_date.weekday()]
    end_date = start_date + timedelta(days=days-1)
    date_str_kor = (
        f"{start_date.year}년 {start_date.month}월 {start_date.day}일 ~ "
        f"{end_date.month}월 {end_date.day}일"
    )
    build_cover_page(
        story, customer,
        pdf_type='월간',
        date_str=date_str_kor,
        subtitle_extra=f'Day 1 → Day {days}',
    )
    
    # ⭐ 도입 페이지 (p2)
    build_intro_page(
        story,
        pdf_type='월간',
        store_link=store_link,
        counsel_link=counsel_link,
        customer=customer,
        date_str=date_str_kor,
    )
    
    total_days = days
    for day_idx, d in enumerate(daily_data):
        day_num = day_idx + 1

        # p1: 월간 전용 (제목 + Day n/30 표기)
        build_monthly_page1(story, customer, profile,
                            d['card_data'], d['direction_kr'], d['card_key'],
                            d['date'], styles, day_num, total_days)
        # p2~p4: 일간과 동일
        build_page2_mbti(story, customer, profile,
                         d['card_data'], d['direction'], d['card_key'],
                         d['date'], styles)
        build_page3_monthly_flow(story, customer, profile,
                                 d['card_key'], d['date'], styles)
        build_page4_astro(story, customer, profile,
                          d['card_key'], d['date'], styles)
        # p5: 월간 전용 (행운 아이템 20개)
        build_monthly_page5(story, customer, profile, d['lucky'],
                            d['card_key'], styles)

        # p6: 주간 build_weekly_page6 재활용 (꿈 메시지 + 내일 카드 미리보기)
        # 단, 월간에서는 author_info를 p7에 표시하므로 p6에는 안 보냄
        if day_idx < days - 1:
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
            author_info=None,  # 월간은 p7에서 표시하므로 p6에선 None
            length='monthly',
        )

        # p7: 월간 전용 (달의 위상 + 저널 Q&A + 이달 목표)
        # author_info는 마지막 일자에만 표시되도록 day_num/total_days 전달
        build_monthly_page7(
            story, customer, profile,
            d['card_key'], d['date'], d['day_in_month'],
            mbti, d['lucky'], styles,
            day_num=day_num, total_days=total_days,
            author_info=author_info,
        )

    # ⭐ 배경지 적용 (2026-05-17 추가)
    # cover_page=1: 표지 페이지 (메인 제목/주문정보)
    # skip_pages=(2,): 도입 페이지(p2)는 배경 OFF — 가독성 우선
    bg = make_bg_painter(cover_page=1, skip_pages=(2,))

    doc.build(story, onFirstPage=bg, onLaterPages=bg, canvasmaker=MonthlyNumberedCanvas)
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

    # ===== 작성자 정보 =====
    sample_author_info = {
        'creator_name':  '루밍 (looming)',
        'business_name': '이설빈 / 사업자등록번호: 000-00-00000',
        'contact':       '문의: looming@example.com',
        'platform':      '크몽 / 숨고 / 텀블벅 판매 상품',
    }

    today = date.today()
    start = today.replace(day=1)

    print("=" * 60)
    print("make_monthly.py — 월간 PDF 생성 (7페이지 × 30일 = 210페이지)")
    print("=" * 60)
    print(f"고객: {sample_customer['name']} ({sample_customer['mbti']})")
    print(f"생년월일: {sample_customer['birthdate']}")
    print(f"시작일: {start}")
    print(f"일수: 30일")
    print()
    print("⏳ 210페이지 생성 — 1~2분 정도 소요됩니다...")
    print()

    try:
        pdf_path = make_monthly_pdf(sample_customer, start_date=start, days=30,
                                    author_info=sample_author_info)
        print(f"✅ PDF 생성 완료: {pdf_path}")
        print(f"   파일 크기: {pdf_path.stat().st_size:,} bytes")
    except FileNotFoundError as e:
        print(f"⚠️  필수 파일 없음: {e}")
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()

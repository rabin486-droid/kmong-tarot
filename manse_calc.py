"""
manse_calc.py
=============
생년월일(시) → 일간 → 오행/띠/별자리 통합 계산 모듈.

[작성자] 루밍 (looming)
[프로젝트] 크몽 MBTI 타로 운세 PDF 서비스

[핵심 함수]
  calc_profile(birth_date, birth_time=None)
    → {'ELEMENT': '토', 'ZOD': '쥐띠', 'STAR': '물병자리', 'BIRTH': '1984년생'}
  
  calc_profile_jisi(birth_date, jisi=None)  ★ Streamlit 드롭다운용
    → 12지시('자시'~'해시')로 입력 받는 래퍼

[입력]
  birth_date: 'YYYY-MM-DD' 또는 datetime.date  (필수)
  birth_time: 'HH:MM' 또는 None ('모름')        (선택, 분 단위 입력 시)
  jisi:       '자시'~'해시' 또는 None/'모름'    (선택, 드롭다운 입력 시)

[Streamlit 드롭다운 사용 예]
  from manse_calc import JISI_LABELS, calc_profile_jisi
  
  # 셀렉트박스 options
  options = JISI_LABELS  # [(label, value), ...]
  
  # 사용자 선택값으로 계산
  jisi = '자시'  # 사용자가 고른 값
  profile = calc_profile_jisi('1984-02-15', jisi)

[설계 — 옵션 C: 100% 정통 사주]
  ELEMENT는 항상 일간(日干) 기반으로 산출한다.
  띠 기준 오행은 라이브러리 비상 폴백용으로만 사용.

  - 시 있음 + 23:00 이후 → 다음 날 일간 사용 (자시 보정)
  - 시 있음 + 그 외     → 당일 일간 사용
  - 시 모름             → 당일 일간 사용 (자시 보정 생략, ~96% 정확)

[METHOD 값 의미]
  'ilgan_with_time'        : 시 있음, 자시 외
  'ilgan_jasi_corrected'   : 시 있음, 자시(23~)로 다음날 일간 사용
  'ilgan_no_time'          : 시 모름, 당일 일간 사용
  'zod_emergency_fallback' : 라이브러리 비상 시만 (정상 작동에선 발생 안 함)
"""

from korean_lunar_calendar import KoreanLunarCalendar
from datetime import date, datetime, timedelta


# ============================================================
# 매핑 테이블
# ============================================================

# 천간(天干) → 오행
# 갑·을 = 목, 병·정 = 화, 무·기 = 토, 경·신 = 금, 임·계 = 수
ILGAN_TO_ELEMENT = {
    '갑': '목', '을': '목',
    '병': '화', '정': '화',
    '무': '토', '기': '토',
    '경': '금', '신': '금',
    '임': '수', '계': '수',
}

# 지지(地支) → 띠
JIJI_TO_ZOD = {
    '자': '쥐띠', '축': '소띠', '인': '호랑이띠', '묘': '토끼띠',
    '진': '용띠', '사': '뱀띠', '오': '말띠', '미': '양띠',
    '신': '원숭이띠', '유': '닭띠', '술': '개띠', '해': '돼지띠',
}

# 띠 → 띠 기준 납음 오행 (시 모를 때 폴백용)
ZOD_TO_ELEMENT_FALLBACK = {
    '쥐띠': '수',
    '소띠': '토',
    '호랑이띠': '목',
    '토끼띠': '목',
    '용띠': '토',
    '뱀띠': '화',
    '말띠': '화',
    '양띠': '토',
    '원숭이띠': '금',
    '닭띠': '금',
    '개띠': '토',
    '돼지띠': '수',
}

# ============================================================
# 12지시(時辰) 매핑 — Streamlit 드롭다운 입력용
# ============================================================
# 12지시는 사주에서 시간을 다루는 기본 단위. 양력 24시를 2시간씩 12개로 나눔.
# 사용자가 분 단위(HH:MM)로 입력하기 어려울 때 12지시 드롭다운으로 받음.

# 12지시 → 대표 시각 (HH:MM) 매핑
# 각 지시의 중간 시각을 대표값으로 사용 → calc_profile에 그대로 전달 가능
# ★ 자시(子時)는 23:30으로 설정 → 한국 사주 정통: 자시 = 새 하루의 시작
#   → calc_profile의 자시 보정 로직(hour>=23) 발동 → 다음날 일간 사용
JISI_TO_HOUR = {
    '자시': '23:30',  # 23:00~01:00  ★ 자시 보정 발동 — 다음날 일간 사용
    '축시': '02:00',  # 01:00~03:00
    '인시': '04:00',  # 03:00~05:00
    '묘시': '06:00',  # 05:00~07:00
    '진시': '08:00',  # 07:00~09:00
    '사시': '10:00',  # 09:00~11:00
    '오시': '12:00',  # 11:00~13:00
    '미시': '14:00',  # 13:00~15:00
    '신시': '16:00',  # 15:00~17:00
    '유시': '18:00',  # 17:00~19:00
    '술시': '20:00',  # 19:00~21:00
    '해시': '22:00',  # 21:00~23:00
}

# 드롭다운 라벨 (사용자가 보는 텍스트)
# Streamlit selectbox의 options로 그대로 사용 가능
JISI_LABELS = [
    ('모름',  None),                          # 기본값 — 시 없이 계산
    ('자시 (밤 11시 ~ 새벽 1시)',  '자시'),
    ('축시 (새벽 1시 ~ 3시)',      '축시'),
    ('인시 (새벽 3시 ~ 5시)',      '인시'),
    ('묘시 (새벽 5시 ~ 7시)',      '묘시'),
    ('진시 (오전 7시 ~ 9시)',      '진시'),
    ('사시 (오전 9시 ~ 11시)',     '사시'),
    ('오시 (낮 11시 ~ 오후 1시)',  '오시'),
    ('미시 (오후 1시 ~ 3시)',      '미시'),
    ('신시 (오후 3시 ~ 5시)',      '신시'),
    ('유시 (오후 5시 ~ 7시)',      '유시'),
    ('술시 (저녁 7시 ~ 9시)',      '술시'),
    ('해시 (저녁 9시 ~ 11시)',     '해시'),
]


def jisi_to_hour(jisi):
    """12지시 → 대표 시각(HH:MM) 변환.
    
    [입력] '자시' / '축시' / ... / '해시' / None / '모름'
    [출력] 'HH:MM' 문자열 또는 None
    """
    if jisi is None or jisi == '모름':
        return None
    return JISI_TO_HOUR.get(jisi)


def calc_profile_jisi(birth_date, jisi=None):
    """12지시 입력 버전 — calc_profile의 래퍼.
    
    Streamlit 드롭다운에서 12지시 받아 calc_profile에 전달.
    
    [입력]
      birth_date: 'YYYY-MM-DD' 또는 datetime.date
      jisi:       '자시'~'해시' 또는 None/'모름'
    
    [출력]
      calc_profile()과 동일 (ELEMENT, ZOD, STAR, BIRTH, ILGAN, METHOD)
    """
    birth_time = jisi_to_hour(jisi)
    return calc_profile(birth_date, birth_time)

# 별자리 경계 (양력 월·일 기반)
# (month, day, name) — 시작일
ZODIAC_BOUNDARIES = [
    (1, 20, '물병자리'),   # 1/20 ~ 2/18
    (2, 19, '물고기자리'),  # 2/19 ~ 3/20
    (3, 21, '양자리'),      # 3/21 ~ 4/19
    (4, 20, '황소자리'),    # 4/20 ~ 5/20
    (5, 21, '쌍둥이자리'),  # 5/21 ~ 6/21
    (6, 22, '게자리'),      # 6/22 ~ 7/22
    (7, 23, '사자자리'),    # 7/23 ~ 8/22
    (8, 23, '처녀자리'),    # 8/23 ~ 9/22
    (9, 23, '천칭자리'),    # 9/23 ~ 10/22
    (10, 23, '전갈자리'),   # 10/23 ~ 11/21
    (11, 22, '사수자리'),   # 11/22 ~ 12/21
    (12, 22, '염소자리'),   # 12/22 ~ 1/19
]


# ============================================================
# 기본 계산
# ============================================================

def calc_zodiac(birth_date):
    """양력 생년월일 → 별자리"""
    m, d = birth_date.month, birth_date.day
    # 염소자리는 12/22 ~ 1/19로 연 경계를 넘으므로 별도 처리
    if (m == 12 and d >= 22) or (m == 1 and d <= 19):
        return '염소자리'
    for i in range(len(ZODIAC_BOUNDARIES) - 1, -1, -1):
        bm, bd, name = ZODIAC_BOUNDARIES[i]
        if name == '염소자리':
            continue
        if m > bm or (m == bm and d >= bd):
            return name
    # 폴백 (이론상 안 옴)
    return '염소자리'


def calc_zod_from_year(year):
    """출생연도 → 띠 (간이 계산, 양력 기준)
    
    주의: 정확히는 음력 새해 또는 입춘 기준이지만,
    일반 사용자가 '몇년생'을 양력으로 인식하므로 양력 연도 기준.
    더 정확한 띠 계산은 calc_profile_full에서 GapJa로 함.
    """
    # 1900년 = 경자년 (쥐띠)이므로 (year - 1900) % 12 인덱스로 매핑
    zod_list = ['쥐띠', '소띠', '호랑이띠', '토끼띠', '용띠', '뱀띠',
                '말띠', '양띠', '원숭이띠', '닭띠', '개띠', '돼지띠']
    # 1900년이 쥐띠인지 확인: 사실 1900년은 경자년이라 쥐띠 맞음
    # 하지만 KARI 기준 입춘으로 띠가 바뀌므로, 정확한 띠는 GapJa로 추출 권장
    return zod_list[(year - 1900) % 12]


def parse_gapja(gapja_str):
    """갑자 문자열 파싱.
    
    예: '갑자년 병인월 기묘일' →
        {'year': '갑자', 'month': '병인', 'day': '기묘',
         'day_chun': '기', 'day_ji': '묘'}
    """
    parts = gapja_str.replace('(윤월)', '').strip().split()
    # year, month, day, (optional)hour
    result = {}
    for p in parts:
        p = p.strip()
        if p.endswith('년'):
            result['year'] = p[:-1]
        elif p.endswith('월'):
            result['month'] = p[:-1]
        elif p.endswith('일'):
            result['day'] = p[:-1]
        elif p.endswith('시'):
            result['hour'] = p[:-1]
    
    # 일주 분해: 두 글자 한글 → 첫 글자 = 천간(일간), 둘째 글자 = 지지
    if 'day' in result and len(result['day']) == 2:
        result['day_chun'] = result['day'][0]
        result['day_ji'] = result['day'][1]
    if 'year' in result and len(result['year']) == 2:
        result['year_chun'] = result['year'][0]
        result['year_ji'] = result['year'][1]
    
    return result


# ============================================================
# 통합 계산 (메인 함수)
# ============================================================

def calc_profile(birth_date, birth_time=None):
    """
    생년월일(시) → 운세 변수 4개 반환.
    
    [입력]
      birth_date: 'YYYY-MM-DD' 문자열 또는 datetime.date 객체
      birth_time: 'HH:MM' 문자열 또는 None (모름)
    
    [출력]
      {
        'ELEMENT': '수',           # 오행 (목·화·토·금·수)
        'ZOD': '쥐띠',             # 띠 (12개)
        'STAR': '물병자리',        # 별자리 (12개)
        'BIRTH': '1984년생',       # 출생연도 + 년생
        'ILGAN': '임',             # 일간 (시 입력 시만, 디버그용)
        'METHOD': 'ilgan'          # 'ilgan' (정통 사주) or 'zod_fallback' (시 모름)
      }
    """
    # birth_date 파싱
    if isinstance(birth_date, str):
        birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
    
    profile = {}
    
    # 별자리
    profile['STAR'] = calc_zodiac(birth_date)
    
    # 갑자 추출 (KARI 만세력 기준)
    cal = KoreanLunarCalendar()
    cal.setSolarDate(birth_date.year, birth_date.month, birth_date.day)
    gapja = cal.getGapJaString()
    parsed = parse_gapja(gapja)
    
    # 띠 — GapJa 연주의 지지에서 추출 (입춘 보정 자동 적용됨)
    year_ji = parsed.get('year_ji')
    if year_ji and year_ji in JIJI_TO_ZOD:
        profile['ZOD'] = JIJI_TO_ZOD[year_ji]
    else:
        profile['ZOD'] = calc_zod_from_year(birth_date.year)
    
    # 출생연도 표기
    profile['BIRTH'] = f"{birth_date.year}년생"
    
    # 오행 계산 — 정통 사주 일간 기반
    # 시 입력 여부와 관계없이 일간 오행 사용 (시는 자시 보정에만 영향)
    if birth_time:
        # 시 있음: 23:00 이후면 자시 보정 (다음 날 일간 사용)
        hour, minute = map(int, birth_time.split(':'))
        if hour >= 23:
            next_date = birth_date + timedelta(days=1)
            cal.setSolarDate(next_date.year, next_date.month, next_date.day)
            gapja_next = cal.getGapJaString()
            parsed_next = parse_gapja(gapja_next)
            day_chun = parsed_next.get('day_chun')
            method = 'ilgan_jasi_corrected'  # 자시 보정 적용
        else:
            day_chun = parsed.get('day_chun')
            method = 'ilgan_with_time'  # 시 있음, 보정 불필요
    else:
        # 시 모름: 당일 일간 그대로 (자시 보정 생략, ~96% 정확)
        day_chun = parsed.get('day_chun')
        method = 'ilgan_no_time'
    
    if day_chun and day_chun in ILGAN_TO_ELEMENT:
        profile['ELEMENT'] = ILGAN_TO_ELEMENT[day_chun]
        profile['ILGAN'] = day_chun
        profile['METHOD'] = method
    else:
        # 라이브러리 비정상: 만의 하나 일간 추출 실패 → 띠 기준 비상 폴백
        profile['ELEMENT'] = ZOD_TO_ELEMENT_FALLBACK[profile['ZOD']]
        profile['ILGAN'] = ''
        profile['METHOD'] = 'zod_emergency_fallback'
    
    return profile


# ============================================================
# 검증 실행 (이 파일 직접 실행 시)
# ============================================================

def _print_profile(label, birth_date, birth_time=None):
    p = calc_profile(birth_date, birth_time)
    time_str = f" {birth_time}" if birth_time else " (시 모름)"
    print(f"\n[{label}] {birth_date}{time_str}")
    print(f"  ELEMENT = {p['ELEMENT']}  (방식: {p['METHOD']}{', 일간=' + p['ILGAN'] if p['ILGAN'] else ''})")
    print(f"  ZOD     = {p['ZOD']}")
    print(f"  STAR    = {p['STAR']}")
    print(f"  BIRTH   = {p['BIRTH']}")


if __name__ == '__main__':
    print("=" * 60)
    print("만세력 계산 검증")
    print("=" * 60)
    
    # 케이스 1: 시 모름 (당일 일간 사용)
    _print_profile('A. 시 모름', '1984-02-15')
    
    # 케이스 2: 시 있음 (정통 사주)
    _print_profile('B. 시 있음 — 정통 사주', '1984-02-15', '14:30')
    
    # 케이스 3: 자시(23:00 이후) 경계 처리
    _print_profile('C. 자시(23시) — 다음날 일간', '1984-02-15', '23:30')
    _print_profile('C-2. 자시(00시) — 같은 일간', '1984-02-15', '00:30')
    
    # 케이스 4: 1993년생 닭띠/쌍둥이자리 (시 모름 vs 시 입력 비교)
    _print_profile('D. 1993년생 (시 모름)', '1993-06-15')
    _print_profile('D-2. 1993년생 (오전 9시)', '1993-06-15', '09:00')
    
    # 케이스 5: 입춘 경계 (음력 새해 직전)
    _print_profile('E. 입춘 전 (2024-01-15)', '2024-01-15')
    _print_profile('E-2. 입춘 후 (2024-03-15)', '2024-03-15')
    
    # 케이스 6: 별자리 경계
    _print_profile('F. 별자리 경계 (1/19, 염소)', '1990-01-19')
    _print_profile('F-2. 별자리 경계 (1/20, 물병)', '1990-01-20')
    _print_profile('F-3. 별자리 경계 (12/22, 염소)', '1990-12-22')
    
    # 케이스 7: 12지시 드롭다운 입력 검증
    print("\n" + "=" * 60)
    print("12지시 드롭다운 검증 (calc_profile_jisi)")
    print("=" * 60)
    test_date = '1984-02-15'
    for jisi_value in ['모름', '자시', '묘시', '오시', '술시', '해시']:
        p = calc_profile_jisi(test_date, jisi_value)
        time_str = f"({jisi_to_hour(jisi_value)})" if jisi_to_hour(jisi_value) else "(시 모름)"
        method = p['METHOD']
        ilgan_str = f", 일간={p['ILGAN']}" if p['ILGAN'] else ""
        print(f"  {jisi_value:6s} {time_str:14s} → ELEMENT={p['ELEMENT']}  ({method}{ilgan_str})")
    
    # 케이스 8: 다양한 띠 확인
    print("\n" + "=" * 60)
    print("띠 12개 검증 (양력 1월 1일 기준 — 입춘 후 정확도)")
    print("=" * 60)
    for year in range(2000, 2012):
        cal = KoreanLunarCalendar()
        cal.setSolarDate(year, 6, 15)  # 6월이면 입춘 후 확실
        gapja = cal.getGapJaString()
        parsed = parse_gapja(gapja)
        zod = JIJI_TO_ZOD.get(parsed.get('year_ji', ''))
        print(f"  {year}년 (6/15 기준): {gapja.split()[0]:6s} → {zod}")
    
    print("\n검증 완료.")

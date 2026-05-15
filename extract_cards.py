"""
extract_cards.py
================
6개 차수별 docx 파일을 읽어 cards_db.json 1개로 통합 변환하는 스크립트.

[작성자] 루밍 (looming)
[프로젝트] 크몽 MBTI 타로 운세 PDF 서비스
[1회용] cards_db.json 생성 후에는 다시 실행할 필요 없음.
        카드 해설 수정 시에만 재실행.

[입력]
  ./docs/카드해설_1차_메이저정방향.docx        (메이저 22장 정방향 × 16 MBTI = 352)
  ./docs/카드해설_2차_메이저역방향.docx        (메이저 22장 역방향 × 16 MBTI = 352)
  ./docs/카드해설_3차_Wands.docx               (Wands 14장 정·역 × 16 MBTI = 448)
  ./docs/카드해설_4차_Cups.docx                (Cups 14장 정·역 × 16 MBTI = 448)
  ./docs/Swords_5차_본문_448개.docx            (Swords 14장 정·역 × 16 MBTI = 448)
  ./docs/카드해설_6차_Pentacles.docx           (Pentacles 14장 정·역 × 16 MBTI = 448)

[출력]
  ./cards_db.json (한 파일, 약 0.5~1MB)

  구조:
  {
    "INTJ": {
      "major_00_upright":   {"name": "The Fool", "kr": "광대", "keyword": "...", "body": "...", "core": "..."},
      "major_00_reversed":  {...},
      ...
      "wands_01_upright":   {...},
      "wands_01_reversed":  {...},
      ...
      "pentacles_14_reversed": {...}
    },
    "INTP": {...},
    ...
    "ESFP": {...}
  }

  카드 ID 규칙:
    메이저:    major_00 ~ major_21       (Fool=00, World=21)
    Wands:     wands_01 ~ wands_14       (Ace=01, Ten=10, Page=11, Knight=12, Queen=13, King=14)
    Cups:      cups_01 ~ cups_14
    Swords:    swords_01 ~ swords_14
    Pentacles: pentacles_01 ~ pentacles_14

  방향 접미사: _upright (정방향), _reversed (역방향)

[실행]
  pip install python-docx
  python extract_cards.py

[검증]
  - 변환 후 자동 카운트 (16 MBTI × 156 카드방향 = 2,496개 모두 들어있는지 확인)
  - 누락된 카드 발견 시 경고 출력
  - 본문에 잔존하는 샘플 이름 하드코딩 검사
"""

from docx import Document
from pathlib import Path
import json
import re
import sys
from collections import defaultdict


# ============================================================
# 설정
# ============================================================

INPUT_DIR = Path("./docs")
OUTPUT_FILE = Path("./cards_db.json")

# 샘플 이름 목록 (외부 파일에서 로드, 없으면 빈 리스트)
# sample_names.txt: 한 줄에 한 이름씩 (작성 중 본문에 들어간 샘플 이름)
SAMPLE_NAMES_FILE = Path("./sample_names.txt")
if SAMPLE_NAMES_FILE.exists():
    SAMPLE_NAMES = [
        line.strip() for line in SAMPLE_NAMES_FILE.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.strip().startswith('#')
    ]
else:
    SAMPLE_NAMES = []

# 16 MBTI 유효성 검증용
VALID_MBTI = {
    'INTJ', 'INTP', 'ENTJ', 'ENTP',
    'INFJ', 'INFP', 'ENFJ', 'ENFP',
    'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
    'ISTP', 'ISFP', 'ESTP', 'ESFP'
}

# 메이저 카드 영문명 → 카드 ID 매핑
MAJOR_NAME_TO_ID = {
    'The Fool':           ('major_00', '광대'),
    'The Magician':       ('major_01', '마법사'),
    'The High Priestess': ('major_02', '여사제'),
    'The Empress':        ('major_03', '여황제'),
    'The Emperor':        ('major_04', '황제'),
    'The Hierophant':     ('major_05', '교황'),
    'The Lovers':         ('major_06', '연인'),
    'The Chariot':        ('major_07', '전차'),
    'Strength':           ('major_08', '힘'),
    'The Hermit':         ('major_09', '은둔자'),
    'Wheel of Fortune':   ('major_10', '운명의 수레바퀴'),
    'Justice':            ('major_11', '정의'),
    'The Hanged Man':     ('major_12', '매달린 사람'),
    'Death':              ('major_13', '죽음'),
    'Temperance':         ('major_14', '절제'),
    'The Devil':          ('major_15', '악마'),
    'The Tower':          ('major_16', '탑'),
    'The Star':           ('major_17', '별'),
    'The Moon':           ('major_18', '달'),
    'The Sun':            ('major_19', '태양'),
    'Judgement':          ('major_20', '심판'),
    'The World':          ('major_21', '세계'),
}


# ============================================================
# docx 파싱 헬퍼
# ============================================================

def docx_to_text(path):
    """python-docx로 docx 읽어서 단락 단위 텍스트 리스트로 반환."""
    doc = Document(path)
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def normalize_text(text):
    """본문 텍스트 정리: 샘플 이름 → 변수, 공백 정리.
    
    원본 docx에 작업 중 들어간 샘플 이름들을 {NAME} 변수로 일괄 치환.
    PDF 생성 시 {NAME}이 실제 의뢰자 이름으로 자동 대체됨.
    """
    # 1) 샘플 이름 → {NAME} 변수 치환
    for sample in SAMPLE_NAMES:
        text = re.sub(re.escape(sample) + r'님', '{NAME}님', text)
        text = re.sub(re.escape(sample), '{NAME}', text)
    # 3) body 끝부분에 인라인으로 박힌 "오늘의 핵심: ..." 제거
    #    (일부 ESFP 본문에서 한 단락 안에 본문+오늘의 핵심이 함께 들어옴)
    text = re.sub(r'\s*오늘의\s*핵심\s*[:：][^.!?]*[\.\?\!]*[\"\u201d]*\s*', ' ', text)
    # 4) 구분자 --- 제거
    text = re.sub(r'\s*-{3,}\s*', ' ', text)
    # 5) 연속 공백 정리
    text = re.sub(r'[ \t\n]+', ' ', text)
    return text.strip()


# ============================================================
# 차수별 파서 (헤더 형식이 6가지로 다름)
# ============================================================

# 메이저 카드 헤더 (1·2차)
# 예: "01. The Fool (광대) — 정방향"
RE_MAJOR_CARD = re.compile(
    r'^(\d{1,2})\.\s+(.+?)\s*\([^)]*\)\s*[—\-]\s*(정방향|역방향)$'
)

# 슈트 카드 헤더 (3·4차)
# 예: "01. Ace of Wands (완드 에이스) — 정방향"
#     "01R. Ace of Wands (완드 에이스) — 역방향"
RE_SUIT_CARD_34 = re.compile(
    r'^(\d{1,2})(R?)\.\s+(.+?)\s*\([^)]*\)\s*[—\-]\s*(정방향|역방향)$'
)

# 5차 Swords 카드 헤더
# 예: "01. Ace of Swords (소드 에이스) — 정방향"
RE_SUIT_CARD_5 = re.compile(
    r'^(\d{1,2})\.\s+(.+?)\s*\([^)]*\)\s*[—\-]\s*(정방향|역방향)$'
)

# 6차 Pentacles 카드 헤더
# 예: "P01. Ace of Pentacles (펜타클 에이스) — 정방향"
RE_SUIT_CARD_6 = re.compile(
    r'^P(\d{1,2})\.\s+(.+?)\s*\([^)]*\)\s*[—\-]\s*(정방향|역방향)$'
)

# MBTI 헤더 — 차수마다 형식 다름:
#   1·2·3·4차: "▸ INTJ × The Fool 정방향"
#   5차:       "INTJ × Ace of Swords 정방향"
#   6차:       "INTJ × Ace of Pentacles 정방향"
RE_MBTI_HEADER = re.compile(
    r'^(?:▸\s*)?([A-Z]{4})\s*×\s*(.+?)\s*(정방향|역방향)$'
)

# 키워드 라인
# 예: "키워드: 새로운 시작, 무한한 가능성, 첫걸음"
RE_KEYWORD = re.compile(r'^키워드[:：]\s*(.+)$')

# "오늘의 핵심" 라인
# 예: "오늘의 핵심: \"전략은 충분하다. 이제 발을 떼는 순간이다.\""
RE_CORE = re.compile(r'^오늘의\s*핵심[:：]\s*[\"\u201c]?(.+?)[\"\u201d]?$')


def strip_markdown_bold(text):
    """python-docx는 굵은 글씨를 일반 텍스트로 가져옴.
       하지만 혹시 ** 마크다운 잔존 시 제거."""
    return re.sub(r'\*+', '', text).strip()


def parse_card_header(line, suit):
    """카드 헤더 한 줄 파싱.
    
    suit: 'major' / 'wands' / 'cups' / 'swords' / 'pentacles'
    반환: (card_id, direction) 또는 None
    """
    line = strip_markdown_bold(line)
    
    if suit == 'major':
        m = RE_MAJOR_CARD.match(line)
        if m:
            num, name_eng, direction = m.groups()
            name_eng = name_eng.strip()
            if name_eng in MAJOR_NAME_TO_ID:
                card_id, kr = MAJOR_NAME_TO_ID[name_eng]
                return card_id, name_eng, kr, direction
        return None
    
    elif suit in ('wands', 'cups'):
        m = RE_SUIT_CARD_34.match(line)
        if m:
            num, r_flag, name_eng, direction = m.groups()
            card_id = f"{suit}_{int(num):02d}"
            # 한글명은 () 안 표기 그대로 사용
            return card_id, name_eng.strip(), '', direction
        return None
    
    elif suit == 'swords':
        m = RE_SUIT_CARD_5.match(line)
        if m:
            num, name_eng, direction = m.groups()
            card_id = f"swords_{int(num):02d}"
            return card_id, name_eng.strip(), '', direction
        return None
    
    elif suit == 'pentacles':
        m = RE_SUIT_CARD_6.match(line)
        if m:
            num, name_eng, direction = m.groups()
            card_id = f"pentacles_{int(num):02d}"
            return card_id, name_eng.strip(), '', direction
        return None
    
    return None


def parse_mbti_header(line):
    """MBTI 헤더 한 줄 파싱.
    반환: (mbti, direction) 또는 None
    """
    line = strip_markdown_bold(line)
    m = RE_MBTI_HEADER.match(line)
    if m:
        mbti, _card_name, direction = m.groups()
        if mbti in VALID_MBTI:
            return mbti, direction
    return None


def parse_keyword(line):
    """키워드 라인 파싱."""
    line = strip_markdown_bold(line)
    m = RE_KEYWORD.match(line)
    if m:
        return m.group(1).strip()
    return None


def parse_core(line):
    """'오늘의 핵심' 라인 파싱."""
    line = strip_markdown_bold(line)
    m = RE_CORE.match(line)
    if m:
        return m.group(1).strip().strip('"\u201c\u201d')
    return None


# ============================================================
# docx → 카드 데이터 추출
# ============================================================

def extract_from_docx(path, suit):
    """
    docx 1개 파싱 → 카드 데이터 리스트 반환.
    
    반환 형식:
      [
        {
          "mbti": "INTJ",
          "card_id": "major_00",
          "name": "The Fool",
          "kr": "광대",
          "direction": "정방향",
          "keyword": "새로운 시작, ...",
          "body": "오늘 광대 카드가...",
          "core": "전략은 충분하다. ..."
        },
        ...
      ]
    """
    paragraphs = docx_to_text(path)
    
    results = []
    current_card = None        # (card_id, name_eng, kr_name)
    current_keyword = ''
    current_mbti = None
    current_direction = None
    current_body_lines = []
    current_core = ''
    
    def flush():
        """현재 누적된 MBTI 항목을 결과에 추가."""
        if current_mbti and current_card:
            body = ' '.join(current_body_lines).strip()
            body = normalize_text(body)
            results.append({
                'mbti': current_mbti,
                'card_id': current_card[0],
                'name': current_card[1],
                'kr': current_card[2],
                'direction': current_direction,
                'keyword': current_keyword,
                'body': body,
                'core': normalize_text(current_core) if current_core else '',
            })
    
    for line in paragraphs:
        if not line:
            continue
        
        # 1) 카드 헤더 체크
        card_match = parse_card_header(line, suit)
        if card_match:
            flush()  # 이전 항목 저장
            card_id, name_eng, kr_name, direction = card_match
            current_card = (card_id, name_eng, kr_name)
            current_mbti = None
            current_direction = direction
            current_body_lines = []
            current_core = ''
            current_keyword = ''
            continue
        
        # 2) 키워드 라인 체크
        kw = parse_keyword(line)
        if kw:
            current_keyword = kw
            continue
        
        # 3) MBTI 헤더 체크
        mbti_match = parse_mbti_header(line)
        if mbti_match:
            flush()  # 이전 MBTI 항목 저장
            mbti, direction = mbti_match
            current_mbti = mbti
            current_direction = direction
            current_body_lines = []
            current_core = ''
            continue
        
        # 4) 오늘의 핵심 라인 체크
        core = parse_core(line)
        if core:
            current_core = core
            continue
        
        # 5) 그 외 → 본문 누적 (MBTI 헤더 이후에만)
        if current_mbti:
            # "오늘의 핵심"이 본문 안에 인라인으로 박혀 있는 경우도 처리
            # 예: ESFP The Fool — 본문 ... **오늘의 핵심: "..."**
            cleaned = strip_markdown_bold(line)
            inline_core = parse_core(cleaned)
            if inline_core:
                current_core = inline_core
            else:
                current_body_lines.append(cleaned)
    
    flush()  # 마지막 항목 저장
    return results


# ============================================================
# 메인
# ============================================================

def main():
    # 파일 → 슈트 매핑
    files = [
        ('카드해설_1차_메이저정방향.docx',   'major'),
        ('카드해설_2차_메이저역방향.docx',   'major'),
        ('카드해설_3차_Wands.docx',          'wands'),
        ('카드해설_4차_Cups.docx',           'cups'),
        ('Swords_5차_본문_448개.docx',       'swords'),
        ('카드해설_6차_Pentacles.docx',      'pentacles'),
    ]
    
    all_entries = []
    
    for fname, suit in files:
        path = INPUT_DIR / fname
        if not path.exists():
            print(f"⚠️  파일 없음: {path}")
            continue
        
        entries = extract_from_docx(path, suit)
        print(f"✅ {fname:42s}  ({suit:10s}) → {len(entries):4d}개 항목 추출")
        all_entries.extend(entries)
    
    print(f"\n📊 전체 항목 수: {len(all_entries)}개 (목표: 2,496개)")
    
    # ============================================================
    # 검증
    # ============================================================
    
    # 1) MBTI별 항목 수
    mbti_count = defaultdict(int)
    for e in all_entries:
        mbti_count[e['mbti']] += 1
    
    print(f"\n📋 MBTI별 항목 수 (각 156개여야 함):")
    for mbti in sorted(VALID_MBTI):
        cnt = mbti_count.get(mbti, 0)
        flag = '✅' if cnt == 156 else '⚠️ '
        print(f"  {flag} {mbti}: {cnt}개")
    
    # 2) 카드별 항목 수 (각 카드는 16 MBTI × 정·역 = 32개)
    #    아니, 한 카드ID는 정방향 16개 OR 역방향 16개를 별도로 가짐
    card_dir_count = defaultdict(int)
    for e in all_entries:
        key = f"{e['card_id']}_{e['direction']}"
        card_dir_count[key] += 1
    
    print(f"\n📋 카드×방향별 항목 수 (각 16개여야 함):")
    issues = []
    for key, cnt in sorted(card_dir_count.items()):
        if cnt != 16:
            issues.append((key, cnt))
    
    if not issues:
        print(f"  ✅ 모든 카드×방향 항목이 정확히 16개씩 (총 {len(card_dir_count)}종)")
    else:
        print(f"  ⚠️  문제 있는 카드: {len(issues)}건")
        for key, cnt in issues:
            print(f"     {key}: {cnt}개")
    
    # 3) 본문 잔존 샘플 이름 검사
    bad_count = 0
    for e in all_entries:
        for w in SAMPLE_NAMES:
            if w in e.get('body', '') or w in e.get('core', ''):
                bad_count += 1
                print(f"  ⚠️  샘플 이름 잔존: {e['mbti']} {e['card_id']} {e['direction']}")
    if bad_count == 0:
        if SAMPLE_NAMES:
            print(f"\n✅ 샘플 이름 잔존 0건 (모두 {{NAME}}으로 치환됨)")
        else:
            print(f"\n✅ 샘플 이름 검사 스킵 (sample_names.txt 없음)")
    
    # 4) 변수 자리표시자 분포
    var_stats = {'{ELEMENT}': 0, '{ZOD}': 0, '{STAR}': 0, '{NAME}': 0}
    for e in all_entries:
        for v in var_stats:
            var_stats[v] += e.get('body', '').count(v) + e.get('core', '').count(v)
    
    print(f"\n📋 변수 자리표시자 분포:")
    for v, c in var_stats.items():
        print(f"  {v}: {c}회")
    
    # ============================================================
    # JSON 저장 (MBTI → card_key 구조)
    # ============================================================
    
    db = defaultdict(dict)
    for e in all_entries:
        direction_key = 'upright' if e['direction'] == '정방향' else 'reversed'
        card_key = f"{e['card_id']}_{direction_key}"
        db[e['mbti']][card_key] = {
            'name': e['name'],
            'kr': e['kr'],
            'keyword': e['keyword'],
            'body': e['body'],
            'core': e['core'],
        }
    
    # MBTI 정렬 보장
    sorted_db = {mbti: db[mbti] for mbti in sorted(VALID_MBTI) if mbti in db}
    
    OUTPUT_FILE.write_text(
        json.dumps(sorted_db, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    
    print(f"\n💾 저장 완료: {OUTPUT_FILE}")
    print(f"   파일 크기: {OUTPUT_FILE.stat().st_size:,} bytes")
    print(f"\n🎉 변환 완료. cards_db.json 사용 준비됨.")


if __name__ == '__main__':
    main()

# 🎴 크몽 MBTI 타로 운세 PDF 생성기

## 빠른 시작 (3단계)

### 1단계: 폰트와 이미지 채우기

- `fonts/` 폴더에 나눔폰트 4개 넣기
- `images/` 폴더에 카드 이미지 79장 넣기

(각 폴더의 안내 txt 파일 참고)

### 2단계: 파이썬 라이브러리 설치

명령프롬프트에서 이 폴더로 이동 후:

```cmd
pip install reportlab korean-lunar-calendar python-docx
```

### 3단계: 테스트 실행

```cmd
python make_daily.py
```

→ `output/홍길동_일간운세_YYYYMMDD.pdf` 생성되면 성공!

## 더 자세한 내용

`로컬테스트_가이드.md` 파일 참고.

## 파일 설명

| 파일 | 용도 |
|---|---|
| `make_daily.py` | 일간 PDF (4페이지) 생성 |
| `make_weekly.py` | 주간 PDF (35페이지) 생성 |
| `make_monthly.py` | 월간 PDF (180페이지) 생성 |
| `cards_db.json` | 카드 해설 2,496개 통합 데이터 |
| `manse_calc.py` | 만세력 계산 (오행/띠/별자리) |
| `lucky_items.py` | 행운 아이템 데이터 |
| `astro_items.py` | 별자리/띠/에너지 지도 데이터 |
| `extract_cards.py` | docx → JSON 변환 (수정 시만 사용) |
| `make_backup_docx.py` | docx 백업 생성 (수정 시만 사용) |

## 문제 발생 시

`로컬테스트_가이드.md`의 "자주 발생할 오류" 섹션 참고.

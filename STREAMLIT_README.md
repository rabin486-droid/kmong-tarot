# 🔮 streamlit_app.py 사용 안내

크몽 MBTI 타로 운세 PDF 자동 생성기 — 웹앱 버전.

---

## 1. 설치 (최초 1회만)

작업 폴더로 이동:
```cmd
cd /d F:\크몽_타로_프로젝트\kmong-tarot
```

Streamlit 설치:
```cmd
python -m pip install streamlit
```

(이미 설치돼 있으면 건너뛰어도 됨)

---

## 2. 파일 배치

`streamlit_app.py` 를 작업 폴더 루트에 둡니다:
```
F:\크몽_타로_프로젝트\kmong-tarot\
├── streamlit_app.py   ← 여기!
├── make_daily.py
├── make_weekly.py
├── make_monthly.py
├── integration.py
├── manse_calc.py
├── lucky_items.py
├── ... (나머지 파일들)
```

같은 폴더에 있어야 `make_daily` 등을 import 할 수 있어요.

---

## 3. 실행

```cmd
cd /d F:\크몽_타로_프로젝트\kmong-tarot
python -m streamlit run streamlit_app.py
```

브라우저가 자동으로 열리며 `http://localhost:8501` 주소로 접속됩니다.

---

## 4. 사용 흐름

### A. 사이드바 — 작성자 정보 (한 번만 입력)
- 작성자명 / 사업자 정보 / 문의처 / 판매처
- 한 번 입력하면 세션 동안 모든 PDF에 자동 적용
- 토글로 켜고 끄기 가능

### B. 메인 화면
1. **고객 정보 입력**: 이름 / MBTI / 생년월일 / 태어난 시(선택)
   - 이름 입력하는 순간 별자리·띠·오행이 자동 계산되어 미리보기 표시
2. **PDF 종류 선택**: 일간 / 주간 / 월간 (라디오 버튼)
3. **기준 날짜 선택**: 기본은 오늘
4. **생성 버튼 클릭**
   - 일간: 약 3~5초
   - 주간: 약 20~30초 (단계별 진행 표시)
   - 월간: 약 1~2분 (단계별 진행 표시)
5. **다운로드 버튼 클릭** → PDF 저장
   - 동시에 `output/` 폴더에도 자동 저장됨

---

## 5. 단계별 진행 표시 업그레이드 (선택)

현재 `streamlit_app.py` 는 `make_weekly.py` / `make_monthly.py` 가 
`progress_callback` 파라미터를 지원하는지 자동 감지합니다.

### 지원 안 함 (현재 상태):
- 일간: progress 30% → 100% 두 단계만 표시
- 주간/월간: "단계별 표시 미지원" 메시지 + 통째로 생성

### 진짜 단계별 표시를 원하면:
`make_weekly.py` 와 `make_monthly.py` 를 살짝 수정해서 
다음 형태로 만들면 됩니다:

```python
def make_weekly_pdf(customer, start_date=None, author_info=None, 
                    progress_callback=None):
    # ... 기존 코드 ...
    for day_idx in range(7):
        # 각 일차 PDF 부분 생성
        # ...
        
        # 콜백 호출 (한 줄만 추가!)
        if progress_callback:
            progress_callback(day_idx + 1, 7)
    
    # ... 나머지 ...
```

이렇게만 추가하면 자동으로 단계별 진행이 표시됩니다 
(streamlit_app.py 는 수정 불필요).

---

## 6. 문제 해결

### "make_daily.py 를 불러올 수 없습니다" 오류
- streamlit을 작업 폴더에서 실행하고 있는지 확인:
  ```cmd
  cd /d F:\크몽_타로_프로젝트\kmong-tarot
  ```

### 폰트 깨짐 (■ 표시)
- `fonts/` 폴더에 나눔 폰트 4개가 있는지 확인:
  - NanumGothic.ttf
  - NanumGothicBold.ttf
  - NanumMyeongjo.ttf
  - NanumMyeongjoBold.ttf

### 카드 이미지 안 나옴
- `images/` 폴더에 79장의 카드 이미지가 있는지 확인
- 파일명 규칙: `major_00.png.jpeg`, `wands_A.png.jpeg` 등

### 만세력 계산 오류
- `manse_calc.py` 가 작업 폴더에 있는지 확인
- 생년월일이 1900-01-01 ~ 오늘 범위 안인지 확인

---

## 7. 배포 옵션 (나중에)

### A. 로컬에서만 사용 (현재)
- 본인 PC에서만 실행
- 가장 안전 · 가장 빠름

### B. 같은 와이파이 다른 기기에서 접속
```cmd
python -m streamlit run streamlit_app.py --server.address 0.0.0.0
```
- 같은 와이파이의 폰/태블릿에서 `http://본인PC_IP:8501` 접속

### C. Streamlit Cloud (무료 호스팅)
- GitHub repo 연결 → 자동 배포
- ⚠️ 무료 플랜은 1GB 메모리 제한 (월간 210p는 부하 큼)
- ⚠️ Public 접근 시 보안 고려 필요

### D. 크몽 판매용 자동화
- 본인 PC에서 streamlit 켜두고
- 고객 정보 받으면 → 폼에 입력 → PDF 즉시 생성 → 메일 첨부

---

## 8. 다음 작업 추천

- [ ] `make_weekly.py` / `make_monthly.py` 에 `progress_callback` 추가
- [ ] 작성자 정보 프리셋 저장 (json 파일로 영구 보관)
- [ ] 일괄 생성 모드 (CSV 업로드 → 여러 명 PDF 한 번에)
- [ ] 로그 기록 (누구 PDF 언제 만들었는지)

---

제작: 루밍 (looming) / 이설빈  
GitHub: rabin486-droid/kmong-tarot

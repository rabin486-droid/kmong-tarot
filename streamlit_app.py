"""
streamlit_app.py
================
운세의 정원 — MBTI 타로 PDF 자동 생성기 (웹앱)

실행:
    cd /d F:\\크몽_타로_프로젝트\\kmong-tarot
    python -m streamlit run streamlit_app.py

기능:
- 고객 정보 폼 (이름 / MBTI / 생년월일 한글 드롭다운 / 태어난 시)
- 일간 / 주간 / 월간 PDF 종류 선택
- 사이드바 푸터 설정:
  - 푸터 제목 (드롭다운 + 추가 버튼, 기본: "운세의 정원")
  - 판매처(루밍스튜디오) (드롭다운 + 추가 버튼, 기본: "루밍스튜디오")
  - 추가한 항목은 footer_presets.json 에 영구 저장
- 생성 중 단계별 진행 표시
- 완료 후 다운로드 버튼

제작자: 루밍 (looming) / 이설빈
"""

import sys
import time
import json
import traceback
import calendar
from datetime import date
from pathlib import Path

import streamlit as st

# --- 작업 폴더를 import 경로에 추가 ---
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# --- 프리셋 저장 파일 ---
PRESETS_FILE = BASE_DIR / 'footer_presets.json'


def _safe_import():
    """make_*.py 를 import 시도. 실패 시 None 반환."""
    mods = {}
    errors = []
    for name in ['make_daily', 'make_weekly', 'make_monthly']:
        try:
            mods[name] = __import__(name)
        except Exception as e:
            errors.append(f"{name}: {e}")
            mods[name] = None
    return mods, errors


# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(
    page_title="운세의 정원 — PDF 생성기",
    page_icon="🌿",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ============================================================
# 상수
# ============================================================
MBTI_LIST = [
    '모름',
    'INTJ', 'INTP', 'ENTJ', 'ENTP',
    'INFJ', 'INFP', 'ENFJ', 'ENFP',
    'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
    'ISTP', 'ISFP', 'ESTP', 'ESFP',
]

JISI_OPTIONS = {
    '모름 (선택 안 함)': None,
    '자시 (23:00~01:00)': '자',
    '축시 (01:00~03:00)': '축',
    '인시 (03:00~05:00)': '인',
    '묘시 (05:00~07:00)': '묘',
    '진시 (07:00~09:00)': '진',
    '사시 (09:00~11:00)': '사',
    '오시 (11:00~13:00)': '오',
    '미시 (13:00~15:00)': '미',
    '신시 (15:00~17:00)': '신',
    '유시 (17:00~19:00)': '유',
    '술시 (19:00~21:00)': '술',
    '해시 (21:00~23:00)': '해',
}

PDF_TYPE_INFO = {
    '일간': {'pages': 6,   'desc': '6페이지 · 1일 운세 · 약 3초',     'est_seconds': 5},
    '주간': {'pages': 42,  'desc': '42페이지 · 7일 운세 · 약 20~30초', 'est_seconds': 30},
    '월간': {'pages': 210, 'desc': '210페이지 · 30일 운세 · 약 1~2분', 'est_seconds': 90},
}

DEFAULT_PRESETS = {
    'titles':        ['운세의 정원'],
    'suffixes':      ['루밍스튜디오'],
    'store_links':   [''],      # 운세의 정원 스토어 URL 목록
    'counsel_links': [''],      # 타로 상담 안내 URL 목록
}


# ============================================================
# 프리셋 영구 저장 (json)
# ============================================================
def load_presets():
    if PRESETS_FILE.exists():
        try:
            with open(PRESETS_FILE, encoding='utf-8') as f:
                data = json.load(f)
            for k, v in DEFAULT_PRESETS.items():
                if k not in data or not isinstance(data[k], list) or not data[k]:
                    data[k] = v[:]
            return data
        except Exception:
            pass
    save_presets(DEFAULT_PRESETS)
    return {k: v[:] for k, v in DEFAULT_PRESETS.items()}


def save_presets(presets):
    try:
        with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"프리셋 저장 실패: {e}")


# ============================================================
# 세션 상태 초기화
# ============================================================
def _init_session_state():
    presets = load_presets()
    defaults = {
        'presets':              presets,
        'selected_title':       presets['titles'][0],
        'selected_suffix':      presets['suffixes'][0],
        'selected_store_link':   presets['store_links'][0]   if presets['store_links']   else '',
        'selected_counsel_link': presets['counsel_links'][0] if presets['counsel_links'] else '',
        'footer_enabled':       True,
        'shuffle_seed':         '',   # ⭐ 카드 셔플 시드 (빈 문자열이면 날짜로만 결정)
        'last_pdf_path':        None,
        'last_pdf_bytes':       None,
        'last_pdf_filename':    None,
        'last_customer_name':   None,
        'last_pdf_type':        None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_session_state()


# ============================================================
# 사이드바 — 푸터 설정
# ============================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("### 🌿 푸터 설정")
        st.caption("PDF 모든 페이지 맨 아래에 표시되는 한 줄입니다.")

        st.session_state.footer_enabled = st.toggle(
            "푸터 정보 표시",
            value=st.session_state.footer_enabled,
        )

        presets = st.session_state.presets

        # ===== 푸터 제목 =====
        st.markdown("#### 푸터 제목")
        st.caption("예: 운세의 정원, 오라클 카드 리딩 등")

        if st.session_state.selected_title not in presets['titles']:
            st.session_state.selected_title = presets['titles'][0]

        title_choice = st.selectbox(
            "선택",
            options=presets['titles'],
            index=presets['titles'].index(st.session_state.selected_title),
            key='title_select',
            disabled=not st.session_state.footer_enabled,
            label_visibility='collapsed',
        )
        st.session_state.selected_title = title_choice

        with st.expander("➕ 새 제목 추가", expanded=False):
            new_title = st.text_input(
                "새 제목",
                key='new_title_input',
                placeholder="예: 오라클 카드 리딩",
                disabled=not st.session_state.footer_enabled,
                label_visibility='collapsed',
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("추가", key='add_title_btn',
                             disabled=not st.session_state.footer_enabled,
                             use_container_width=True):
                    nt = new_title.strip()
                    if nt and nt not in presets['titles']:
                        presets['titles'].append(nt)
                        save_presets(presets)
                        st.session_state.selected_title = nt
                        st.success(f"'{nt}' 추가됨!")
                        st.rerun()
                    elif not nt:
                        st.warning("제목을 입력하세요.")
                    else:
                        st.info("이미 있는 제목이에요.")
            with c2:
                if st.button("🗑️ 선택 삭제", key='del_title_btn',
                             disabled=not st.session_state.footer_enabled or len(presets['titles']) <= 1,
                             use_container_width=True,
                             help="현재 선택된 제목 삭제 (최소 1개는 남김)"):
                    if title_choice in presets['titles'] and len(presets['titles']) > 1:
                        presets['titles'].remove(title_choice)
                        save_presets(presets)
                        st.session_state.selected_title = presets['titles'][0]
                        st.rerun()

        st.divider()

        # ===== 판매처 =====
        st.markdown("#### 판매처 (루밍스튜디오)")
        st.caption("푸터 맨 끝에 들어가는 정보예요.")

        if st.session_state.selected_suffix not in presets['suffixes']:
            st.session_state.selected_suffix = presets['suffixes'][0]

        suffix_choice = st.selectbox(
            "선택",
            options=presets['suffixes'],
            index=presets['suffixes'].index(st.session_state.selected_suffix),
            key='suffix_select',
            disabled=not st.session_state.footer_enabled,
            label_visibility='collapsed',
        )
        st.session_state.selected_suffix = suffix_choice

        with st.expander("➕ 새 판매처 추가", expanded=False):
            new_suffix = st.text_input(
                "새 판매처",
                key='new_suffix_input',
                placeholder="예: 크몽, 텀블벅 등",
                disabled=not st.session_state.footer_enabled,
                label_visibility='collapsed',
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("추가", key='add_suffix_btn',
                             disabled=not st.session_state.footer_enabled,
                             use_container_width=True):
                    ns = new_suffix.strip()
                    if ns and ns not in presets['suffixes']:
                        presets['suffixes'].append(ns)
                        save_presets(presets)
                        st.session_state.selected_suffix = ns
                        st.success(f"'{ns}' 추가됨!")
                        st.rerun()
                    elif not ns:
                        st.warning("판매처를 입력하세요.")
                    else:
                        st.info("이미 있는 판매처예요.")
            with c2:
                if st.button("🗑️ 선택 삭제", key='del_suffix_btn',
                             disabled=not st.session_state.footer_enabled or len(presets['suffixes']) <= 1,
                             use_container_width=True,
                             help="현재 선택된 판매처 삭제 (최소 1개는 남김)"):
                    if suffix_choice in presets['suffixes'] and len(presets['suffixes']) > 1:
                        presets['suffixes'].remove(suffix_choice)
                        save_presets(presets)
                        st.session_state.selected_suffix = presets['suffixes'][0]
                        st.rerun()

        st.divider()

        # ===== PDF 안 링크 (구매처 + 상담) =====
        st.markdown("### 🔗 PDF 안 링크")
        st.caption("도입 페이지(p2)에 표시되는 링크입니다.")

        # ── 구매처 (운세의 정원 스토어) ──
        st.markdown("#### 🛍️ 운세의 정원 스토어")
        st.caption("카드 · 풍수용품 등 판매 페이지 URL")

        store_links = presets['store_links']
        if not store_links:
            store_links = ['']
            presets['store_links'] = store_links

        if st.session_state.selected_store_link not in store_links:
            st.session_state.selected_store_link = store_links[0]

        # 빈 문자열도 선택 가능하도록 표시 라벨 변환
        def _link_label(url):
            return url if url else '(링크 없음)'

        store_choice = st.selectbox(
            "선택",
            options=store_links,
            index=store_links.index(st.session_state.selected_store_link),
            key='store_link_select',
            format_func=_link_label,
            label_visibility='collapsed',
        )
        st.session_state.selected_store_link = store_choice

        with st.expander("➕ 새 스토어 링크 추가/관리", expanded=False):
            new_store = st.text_input(
                "새 스토어 URL",
                key='new_store_input',
                placeholder="예: https://smartstore.naver.com/...",
                label_visibility='collapsed',
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("추가", key='add_store_btn', use_container_width=True):
                    ns = new_store.strip()
                    if ns and ns not in store_links:
                        store_links.append(ns)
                        save_presets(presets)
                        st.session_state.selected_store_link = ns
                        st.success(f"추가됨!")
                        st.rerun()
                    elif not ns:
                        st.warning("URL을 입력하세요.")
                    else:
                        st.info("이미 있는 URL이에요.")
            with c2:
                if st.button("🗑️ 선택 삭제", key='del_store_btn',
                             disabled=len(store_links) <= 1,
                             use_container_width=True):
                    if store_choice in store_links and len(store_links) > 1:
                        store_links.remove(store_choice)
                        save_presets(presets)
                        st.session_state.selected_store_link = store_links[0]
                        st.rerun()

        st.markdown("")  # 간격

        # ── 상담 (타로 상담 안내) ──
        st.markdown("#### 🌙 타로 상담 안내")
        st.caption("잠못드는밤 타로상담소 등 1:1 상담 페이지 URL")

        counsel_links = presets['counsel_links']
        if not counsel_links:
            counsel_links = ['']
            presets['counsel_links'] = counsel_links

        if st.session_state.selected_counsel_link not in counsel_links:
            st.session_state.selected_counsel_link = counsel_links[0]

        counsel_choice = st.selectbox(
            "선택",
            options=counsel_links,
            index=counsel_links.index(st.session_state.selected_counsel_link),
            key='counsel_link_select',
            format_func=_link_label,
            label_visibility='collapsed',
        )
        st.session_state.selected_counsel_link = counsel_choice

        with st.expander("➕ 새 상담 링크 추가/관리", expanded=False):
            new_counsel = st.text_input(
                "새 상담 URL",
                key='new_counsel_input',
                placeholder="예: https://open.kakao.com/...",
                label_visibility='collapsed',
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("추가", key='add_counsel_btn', use_container_width=True):
                    nc = new_counsel.strip()
                    if nc and nc not in counsel_links:
                        counsel_links.append(nc)
                        save_presets(presets)
                        st.session_state.selected_counsel_link = nc
                        st.success(f"추가됨!")
                        st.rerun()
                    elif not nc:
                        st.warning("URL을 입력하세요.")
                    else:
                        st.info("이미 있는 URL이에요.")
            with c2:
                if st.button("🗑️ 선택 삭제", key='del_counsel_btn',
                             disabled=len(counsel_links) <= 1,
                             use_container_width=True):
                    if counsel_choice in counsel_links and len(counsel_links) > 1:
                        counsel_links.remove(counsel_choice)
                        save_presets(presets)
                        st.session_state.selected_counsel_link = counsel_links[0]
                        st.rerun()

        st.divider()

        # ===== 푸터 미리보기 =====
        st.markdown("#### ✦ 푸터 미리보기")
        if st.session_state.footer_enabled:
            preview = f"**{st.session_state.selected_title}** | 일간 운세 | OOO님 전용 | 6/6 | **{st.session_state.selected_suffix}**"
        else:
            preview = "*(푸터 OFF)* — 푸터에 작성자/판매처 정보가 안 나옵니다."
        st.caption(preview)

        st.divider()
        st.caption("💡 추가한 항목은 `footer_presets.json` 에 저장되어 다음에도 그대로 있어요.")
        st.caption("🌿 운세의 정원 — PDF 생성기")


def _build_author_info():
    if not st.session_state.footer_enabled:
        return {
            'footer_title':   '운세의 정원',
            'author_suffix':  '',
        }
    return {
        'footer_title':   st.session_state.selected_title.strip() or '운세의 정원',
        'author_suffix':  st.session_state.selected_suffix.strip(),
    }


# ============================================================
# 한글 년/월/일 드롭다운
# ============================================================
def korean_date_picker(label, default_year=1990, default_month=5, default_day=15, key_prefix='dob'):
    current_year = date.today().year
    years = list(range(1900, current_year + 1))
    months = list(range(1, 13))

    st.markdown(f"**{label}**")
    c1, c2, c3 = st.columns(3)
    with c1:
        year = st.selectbox(
            "년",
            options=years,
            index=years.index(default_year) if default_year in years else len(years) - 30,
            format_func=lambda y: f"{y}년",
            key=f'{key_prefix}_year',
        )
    with c2:
        month = st.selectbox(
            "월",
            options=months,
            index=default_month - 1,
            format_func=lambda m: f"{m}월",
            key=f'{key_prefix}_month',
        )
    with c3:
        max_day = calendar.monthrange(year, month)[1]
        days = list(range(1, max_day + 1))
        default_d = default_day if default_day <= max_day else max_day
        day = st.selectbox(
            "일",
            options=days,
            index=default_d - 1,
            format_func=lambda d: f"{d}일",
            key=f'{key_prefix}_day',
        )

    return date(year, month, day)


# ============================================================
# 메인 — 고객 정보 입력
# ============================================================
def render_customer_form():
    st.markdown("### 1️⃣ 고객 정보")

    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input(
            "이름 *",
            value="",
            placeholder="예: 홍길동",
        )
    with col2:
        mbti = st.selectbox(
            "MBTI *",
            options=MBTI_LIST,
            index=0,
            format_func=lambda m: '모름 (보편 해석)' if m == '모름' else m,
            help="MBTI를 모르시면 '모름'을 선택하세요. 카드 자체의 일반 해석으로 운세를 받으실 수 있어요.",
        )

    birthdate = korean_date_picker(
        "생년월일 *",
        default_year=1990, default_month=5, default_day=15,
        key_prefix='birth',
    )

    jisi_label = st.selectbox(
        "태어난 시 (선택)",
        options=list(JISI_OPTIONS.keys()),
        index=0,
        help="모르면 '모름' 그대로 두세요. 일간 사주는 그래도 계산돼요.",
    )

    return {
        'name': name.strip(),
        'mbti': mbti,
        'birthdate': birthdate.strftime('%Y-%m-%d'),
        'jisi': JISI_OPTIONS[jisi_label],
    }


def render_profile_preview(customer):
    if not customer['name']:
        return
    try:
        from manse_calc import calc_profile_jisi
        profile = calc_profile_jisi(customer['birthdate'], customer.get('jisi'))
        st.markdown("#### ✦ 자동 계산 결과")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("별자리", profile.get('STAR', '-'))
        c2.metric("띠", profile.get('ZOD', '-'))
        c3.metric("일간 오행", profile.get('ELEMENT', '-'))
        c4.metric("출생연도", profile.get('BIRTH', '-'))
    except Exception as e:
        st.warning(f"프로필 자동 계산 실패: {e}")
        with st.expander("상세 오류"):
            st.code(traceback.format_exc())


# ============================================================
# PDF 종류 선택
# ============================================================
def render_pdf_type():
    st.markdown("### 2️⃣ PDF 종류")
    pdf_type = st.radio(
        "어떤 PDF를 만들까요?",
        options=list(PDF_TYPE_INFO.keys()),
        format_func=lambda k: f"{k}  ·  {PDF_TYPE_INFO[k]['desc']}",
        horizontal=True,
    )
    today = date.today()
    base_date = korean_date_picker(
        "기준 날짜",
        default_year=today.year, default_month=today.month, default_day=today.day,
        key_prefix='base',
    )
    return pdf_type, base_date


# ============================================================
# 🎴 카드 셔플 (카드 다시 섞기)
# ============================================================
def render_shuffle():
    """카드 셔플 시드 관리 — 마음에 안 들면 다시 섞기."""
    st.markdown("### 🎴 카드 셔플")
    
    # 현재 시드 표시
    current = st.session_state.shuffle_seed
    if current:
        st.caption(f"🔮 현재 셔플: `{current}` — 같은 셔플로 PDF 생성됨")
    else:
        st.caption("🔮 현재: 기본 카드 (날짜 기반)")
    
    col1, col2 = st.columns([3, 2])
    with col1:
        if st.button(
            "🔀 카드 다시 섞기",
            use_container_width=True,
            help="새로운 카드 조합으로 PDF 생성됩니다 (날짜 같아도 다른 카드)",
        ):
            # 랜덤 시드 생성 (현재 시각 기반 — 고유함)
            import random, string
            new_seed = ''.join(random.choices(
                string.ascii_lowercase + string.digits, k=8
            ))
            st.session_state.shuffle_seed = new_seed
            st.rerun()
    with col2:
        if st.button(
            "↩️ 기본으로 복귀",
            use_container_width=True,
            disabled=(not current),
            help="날짜 기반 기본 카드로 돌아갑니다",
        ):
            st.session_state.shuffle_seed = ''
            st.rerun()
    
    # 고급: 직접 입력
    with st.expander("⚙️ 직접 셔플 값 입력 (고급)", expanded=False):
        st.caption("같은 값을 입력하면 같은 카드가 나옵니다. 재현용.")
        manual_seed = st.text_input(
            "셔플 값",
            value=current,
            placeholder="예: abc123, 고객이름, 아무 텍스트",
            key='manual_shuffle_input',
            label_visibility='collapsed',
        )
        if st.button("적용", key='apply_manual_seed'):
            st.session_state.shuffle_seed = manual_seed.strip()
            st.rerun()


# ============================================================
# PDF 생성
# ============================================================
def generate_pdf(customer, pdf_type, base_date, author_info, mods,
                 store_link='', counsel_link='', shuffle_seed=None):
    type_info = PDF_TYPE_INFO[pdf_type]
    total_days = {'일간': 1, '주간': 7, '월간': 30}[pdf_type]

    with st.status(f"🌿 {pdf_type} 운세 PDF 생성 중...", expanded=True) as status:
        st.write(f"📋 고객: **{customer['name']}** ({customer['mbti']})")
        st.write(f"📅 기준 날짜: {base_date.year}년 {base_date.month}월 {base_date.day}일")
        if shuffle_seed:
            st.write(f"🔮 카드 셔플: `{shuffle_seed}`")
        st.write(f"📄 총 {type_info['pages']}페이지 · 예상 {type_info['est_seconds']}초")
        st.write("---")

        progress_bar = st.progress(0.0, text="시작 중...")
        progress_text = st.empty()
        start_time = time.time()

        def on_progress(current_day, total, message=None):
            ratio = current_day / total if total > 0 else 0
            elapsed = time.time() - start_time
            eta = (elapsed / current_day * (total - current_day)) if current_day > 0 else 0
            msg = message or f"Day {current_day}/{total} 생성 중..."
            progress_bar.progress(min(ratio, 1.0), text=msg)
            progress_text.caption(f"⏱ 경과 {elapsed:.1f}초 · 남은 시간 약 {eta:.0f}초")

        try:
            if pdf_type == '일간':
                if mods['make_daily'] is None:
                    raise ImportError("make_daily.py 를 불러올 수 없습니다.")
                progress_bar.progress(0.3, text="카드 뽑는 중...")
                pdf_path = mods['make_daily'].make_daily_pdf(
                    customer, date_obj=base_date, author_info=author_info,
                    store_link=store_link, counsel_link=counsel_link,
                    shuffle_seed=shuffle_seed,
                )
                progress_bar.progress(1.0, text="✅ 완성!")

            elif pdf_type == '주간':
                if mods['make_weekly'] is None:
                    raise ImportError("make_weekly.py 를 불러올 수 없습니다.")
                pdf_path = _call_with_optional_callback(
                    mods['make_weekly'].make_weekly_pdf,
                    customer, base_date, author_info, on_progress,
                    total_days=7, progress_bar=progress_bar,
                    store_link=store_link, counsel_link=counsel_link,
                    shuffle_seed=shuffle_seed,
                )
                progress_bar.progress(1.0, text="✅ 완성!")

            elif pdf_type == '월간':
                if mods['make_monthly'] is None:
                    raise ImportError("make_monthly.py 를 불러올 수 없습니다.")
                pdf_path = _call_with_optional_callback(
                    mods['make_monthly'].make_monthly_pdf,
                    customer, base_date, author_info, on_progress,
                    total_days=30, progress_bar=progress_bar,
                    store_link=store_link, counsel_link=counsel_link,
                    shuffle_seed=shuffle_seed,
                )
                progress_bar.progress(1.0, text="✅ 완성!")

            else:
                raise ValueError(f"알 수 없는 PDF 종류: {pdf_type}")

            elapsed = time.time() - start_time
            status.update(
                label=f"✅ {pdf_type} PDF 생성 완료! ({elapsed:.1f}초)",
                state="complete", expanded=False,
            )

            pdf_path = Path(pdf_path)
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            return pdf_path, pdf_bytes

        except Exception as e:
            status.update(label=f"❌ PDF 생성 실패: {e}", state="error")
            st.error(f"오류: {e}")
            with st.expander("상세 오류 (개발자용)"):
                st.code(traceback.format_exc())
            return None, None


def _call_with_optional_callback(fn, customer, base_date, author_info,
                                  callback, total_days, progress_bar,
                                  store_link='', counsel_link='',
                                  shuffle_seed=None):
    import inspect
    try:
        sig = inspect.signature(fn)
        supports_callback = 'progress_callback' in sig.parameters
    except (ValueError, TypeError):
        supports_callback = False

    extra_kwargs = {
        'store_link':   store_link,
        'counsel_link': counsel_link,
        'shuffle_seed': shuffle_seed,
    }

    if supports_callback:
        return fn(customer, start_date=base_date, author_info=author_info,
                  progress_callback=callback, **extra_kwargs)
    else:
        progress_bar.progress(0.1, text=f"📝 총 {total_days}일치 운세 생성 시작...")
        try:
            return fn(customer, start_date=base_date, author_info=author_info, **extra_kwargs)
        except TypeError:
            try:
                return fn(customer, date_obj=base_date, author_info=author_info, **extra_kwargs)
            except TypeError:
                return fn(customer, base_date, author_info=author_info, **extra_kwargs)


# ============================================================
# 다운로드
# ============================================================
def render_download_section():
    if not st.session_state.last_pdf_bytes:
        return

    st.markdown("### 📥 다운로드")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success(
            f"✅ **{st.session_state.last_customer_name}**님의 "
            f"**{st.session_state.last_pdf_type}** PDF 준비 완료!"
        )
        st.caption(f"📄 파일명: `{st.session_state.last_pdf_filename}`")
        st.caption(f"💾 크기: {len(st.session_state.last_pdf_bytes) / 1024:.1f} KB")
    with col2:
        st.download_button(
            label="📥 PDF 다운로드",
            data=st.session_state.last_pdf_bytes,
            file_name=st.session_state.last_pdf_filename,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )

    if st.session_state.last_pdf_path:
        st.caption(f"📁 로컬 저장: `{st.session_state.last_pdf_path}`")


# ============================================================
# 메인
# ============================================================
def main():
    st.title("🌿 운세의 정원")
    st.caption("MBTI 타로 PDF 자동 생성기 · 폼 입력 → PDF 생성 → 다운로드")
    st.divider()

    mods, errors = _safe_import()
    if errors:
        with st.expander("⚠️ 일부 모듈을 불러올 수 없습니다", expanded=False):
            for err in errors:
                st.code(err)

    render_sidebar()
    customer = render_customer_form()

    if customer['name']:
        render_profile_preview(customer)

    st.divider()
    pdf_type, base_date = render_pdf_type()

    st.divider()
    render_shuffle()

    st.divider()
    st.markdown("### 3️⃣ 생성")

    type_key_map = {'일간': 'make_daily', '주간': 'make_weekly', '월간': 'make_monthly'}
    can_generate = bool(customer['name']) and mods.get(type_key_map[pdf_type]) is not None

    if not customer['name']:
        st.info("👆 위에서 고객 이름을 입력해주세요.")

    if st.button(
        f"🌿 {pdf_type} 운세 PDF 생성",
        type="primary",
        use_container_width=True,
        disabled=not can_generate,
    ):
        author_info = _build_author_info()
        # shuffle_seed: 빈 문자열이면 None으로 변환 (날짜 기본 동작)
        seed = st.session_state.shuffle_seed.strip() if st.session_state.shuffle_seed else None
        pdf_path, pdf_bytes = generate_pdf(
            customer, pdf_type, base_date, author_info, mods,
            store_link=st.session_state.selected_store_link,
            counsel_link=st.session_state.selected_counsel_link,
            shuffle_seed=seed,
        )
        if pdf_bytes:
            st.session_state.last_pdf_path = pdf_path
            st.session_state.last_pdf_bytes = pdf_bytes
            st.session_state.last_pdf_filename = pdf_path.name
            st.session_state.last_customer_name = customer['name']
            st.session_state.last_pdf_type = pdf_type

    if st.session_state.last_pdf_bytes:
        st.divider()
        render_download_section()


if __name__ == '__main__':
    main()

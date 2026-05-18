"""
backgrounds.py — 운세의 정원 PDF 배경지 모듈 (v3.1)
2026-05-17 v3.1 (알PDF 호환성 + JPEG 임베드)

v3 → v3.1 변경:
    - PNG → JPG 사용 (알PDF 호환성 + 파일 크기 1/2)
    - PDF 1.4로 명시 (호환성)
    - 디버그 출력 추가
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader


BASE_DIR = Path(__file__).parent.resolve()
BG_DIR = BASE_DIR / 'backgrounds'

# JPG 우선, 없으면 PNG fallback
COVER_IMG = BG_DIR / 'cover.jpg'
BODY_IMG = BG_DIR / 'body.jpg'

# fallback
if not COVER_IMG.exists():
    COVER_IMG = BG_DIR / 'cover.png'
if not BODY_IMG.exists():
    BODY_IMG = BG_DIR / 'body.png'


_IMG_CACHE = {}


def _get_image(path):
    key = str(path)
    if key not in _IMG_CACHE:
        if path.exists():
            _IMG_CACHE[key] = ImageReader(str(path))
        else:
            print(f'[backgrounds] ⚠ 이미지 없음: {path}')
            _IMG_CACHE[key] = None
    return _IMG_CACHE[key]


def draw_cover(canvas):
    img = _get_image(COVER_IMG)
    if img is None:
        return
    w, h = A4
    canvas.drawImage(img, 0, 0, width=w, height=h,
                     preserveAspectRatio=False, mask='auto')


def draw_body(canvas):
    img = _get_image(BODY_IMG)
    if img is None:
        return
    w, h = A4
    canvas.drawImage(img, 0, 0, width=w, height=h,
                     preserveAspectRatio=False, mask='auto')


def make_bg_painter(skip_pages=(2,), cover_page=1, verbose=False):
    """
    ReportLab onFirstPage/onLaterPages 콜백 반환.

    Args:
        skip_pages (tuple): 배경 OFF 페이지 (기본 (2,) = 목차)
        cover_page (int): 표지 페이지 번호 (기본 1)
        verbose (bool): True면 각 페이지마다 디버그 출력

    Returns:
        function(canvas, doc) — ReportLab 콜백
    """
    skip_set = set(skip_pages)

    if verbose:
        print(f'[backgrounds] painter 생성 — skip_pages={skip_pages}, cover_page={cover_page}')
        print(f'[backgrounds] COVER: {COVER_IMG} (존재: {COVER_IMG.exists()})')
        print(f'[backgrounds] BODY:  {BODY_IMG} (존재: {BODY_IMG.exists()})')

    def painter(canvas, doc):
        page_num = doc.page
        if verbose:
            print(f'[backgrounds] p{page_num}', end=' ')
        if page_num in skip_set:
            if verbose:
                print('→ skip (배경 없음)')
            return
        canvas.saveState()
        if page_num == cover_page:
            if verbose:
                print('→ 표지 그리기')
            draw_cover(canvas)
        else:
            if verbose:
                print('→ 본문 그리기')
            draw_body(canvas)
        canvas.restoreState()

    return painter


if __name__ == '__main__':
    from reportlab.pdfgen.canvas import Canvas

    out_dir = BASE_DIR / 'output'
    out_dir.mkdir(exist_ok=True)

    print('=== 이미지 파일 확인 ===')
    print(f'표지: {COVER_IMG} → {"OK" if COVER_IMG.exists() else "없음"}')
    print(f'본문: {BODY_IMG} → {"OK" if BODY_IMG.exists() else "없음"}')

    print('\n=== 단독 표지 PDF ===')
    c = Canvas(str(out_dir / 'bg_test_cover.pdf'), pagesize=A4, pdfVersion=(1, 4))
    draw_cover(c)
    c.showPage()
    c.save()
    print('✓ bg_test_cover.pdf')

    print('\n=== 단독 본문 PDF ===')
    c = Canvas(str(out_dir / 'bg_test_body.pdf'), pagesize=A4, pdfVersion=(1, 4))
    draw_body(c)
    c.showPage()
    c.save()
    print('✓ bg_test_body.pdf')

    print('\n=== 합본 PDF (6페이지 시뮬레이션) ===')
    c = Canvas(str(out_dir / 'bg_test_combined.pdf'), pagesize=A4, pdfVersion=(1, 4))

    # p1 표지
    draw_cover(c)
    c.setFont('Helvetica', 24)
    c.drawString(100, 700, '[ p1 - COVER ]')
    c.showPage()

    # p2 목차 (배경 없음)
    c.setFont('Helvetica', 24)
    c.drawString(100, 700, '[ p2 - TOC (no background) ]')
    c.showPage()

    # p3~p6 본문
    for i in range(3, 7):
        draw_body(c)
        c.setFont('Helvetica', 24)
        c.drawString(100, 700, f'[ p{i} - BODY ]')
        c.showPage()

    c.save()
    print('✓ bg_test_combined.pdf (6페이지)')

    print('\n→ output 폴더 확인')

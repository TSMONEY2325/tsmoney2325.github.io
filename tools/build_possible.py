#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
/possible/ 업체별 개별 페이지 생성기  (태성투자대부 tsmoney.kr)

기준 데이터(companies.json) -> 업체별 페이지(possible/<기업명>/index.html)
                              -> page-index.json
                              -> 목록 페이지(possible/index.html)의 가나다순 목록·기업 수
                              -> sitemap.xml (possible 항목)
                              -> 신규 업체의 thumbnail.png (없을 때만 생성)

사용법
  python tools/build_possible.py check                  # 데이터 점검만
  python tools/build_possible.py add new_companies.csv  # 신규 업체 추가 (권장 흐름)
  python tools/build_possible.py rebuild                # 전체 페이지 재생성 (템플릿 수정 후)

자세한 절차는 tools/README.md 참고.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import sys
from html import escape
from pathlib import Path
from urllib.parse import quote

SITE = "https://tsmoney.kr"
PHONE = "02-999-2325"
FIELDS = ["기업명", "대표자", "기업구분", "업종", "설립일", "주소", "사업자번호"]
EMPTY = "-"  # 값이 비어 있을 때 페이지에 표시할 문자

HERE = Path(__file__).resolve().parent
ROOT_DEFAULT = HERE.parent

# ---------------------------------------------------------------- 지역 표기
# 주소 맨 앞 지역명은 아래 '전체 표기'로 통일한다. (왼쪽: 전체 표기, 오른쪽: 줄임말)
REGION_ALIASES = {
    "서울특별시": ["서울", "서울시"],
    "전남광주통합특별시": ["광주", "광주광역시", "전남", "전라남도"],
    "부산광역시": ["부산", "부산시"],
    "대구광역시": ["대구", "대구시"],
    "인천광역시": ["인천", "인천시"],
    "대전광역시": ["대전", "대전시"],
    "울산광역시": ["울산", "울산시"],
    "세종특별자치시": ["세종", "세종시"],
    "경기도": ["경기"],
    "강원특별자치도": ["강원", "강원도"],
    "충청북도": ["충북"],
    "충청남도": ["충남"],
    "전북특별자치도": ["전북", "전라북도"],
    "경상북도": ["경북"],
    "경상남도": ["경남"],
    "제주특별자치도": ["제주", "제주도"],
}
REGION_MAP = {}
for _full, _aliases in REGION_ALIASES.items():
    REGION_MAP[_full] = _full
    for _a in _aliases:
        REGION_MAP[_a] = _full


# ---------------------------------------------------------------- 정규화/검증
def clean(v) -> str:
    v = "" if v is None else str(v).strip()
    return "" if v == EMPTY else v


def norm_region(addr: str) -> str:
    addr = clean(addr)
    if not addr:
        return ""
    first, _, rest = addr.partition(" ")
    full = REGION_MAP.get(first)
    if full is None:
        return addr  # 모르는 지역명은 그대로 두고 check에서 경고
    return f"{full} {rest}".strip()


def norm_biznum(v: str) -> str:
    """사업자번호 -> 'XXX-XX-X****' (뒤 4자리 가림).
    형식이 이상한 값은 숫자를 추측해 고치지 않고 그대로 두며, check/add 에서 경고한다."""
    v = re.sub(r"-{2,}", "-", clean(v))
    if not v:
        return ""
    m = re.fullmatch(r"(\d{3})-?(\d{2})-?(\d{5})", v)          # 전체 번호
    if m:
        return f"{m[1]}-{m[2]}-{m[3][0]}****"
    m = re.fullmatch(r"(\d{3})-(\d{2})-(\d?)\*{4,5}", v)        # 이미 가려진 번호
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}****"
    m = re.fullmatch(r"(\d{3})-(\d{2})-(\d?)", v)               # 뒷부분이 잘린 번호
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}****"
    return v


def biz_issue(rec: dict) -> str:
    v = rec["사업자번호"]
    if v and not re.fullmatch(r"\d{3}-\d{2}-\d?\*{4}", v):
        return f"{rec['기업명']}: 사업자번호 형식 이상 -> '{v}' (직접 확인 필요)"
    return ""


def url_for(name: str) -> str:
    # 사이트맵·canonical과 같은 형태: 괄호는 그대로, 한글만 인코딩
    return f"{SITE}/possible/{quote(name, safe='()')}/"


def norm_record(r: dict) -> dict:
    out = {k: clean(r.get(k)) for k in FIELDS}
    out["주소"] = norm_region(out["주소"])
    out["사업자번호"] = norm_biznum(out["사업자번호"])
    out["url"] = url_for(out["기업명"])
    return out


def validate(rec: dict) -> list[str]:
    errs = []
    name = rec["기업명"]
    if not name:
        return ["기업명이 비어 있음"]
    if re.search(r'[\\/:*?"<>|]', name) or name != name.strip() or name.endswith(".") or name.startswith("."):
        errs.append(f"{name}: 폴더 이름으로 쓸 수 없는 문자가 있음")
    est = rec["설립일"]
    if est:
        m = re.match(r"^(\d{4})년 (\d{1,2})월 (\d{1,2})일$", est)
        if not m or not (1900 <= int(m.group(1)) <= dt.date.today().year):
            errs.append(f"{name}: 설립일 형식/연도 이상 -> '{est}' (예: 1986년 3월 25일)")
    addr = rec["주소"]
    if addr and addr.split(" ", 1)[0] not in REGION_ALIASES:
        errs.append(f"{name}: 주소 앞 지역명을 인식하지 못함 -> '{addr}'")
    return errs


# ---------------------------------------------------------------- 파일 입출력
def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_text_auto(path: Path) -> str:
    """UTF-8(BOM 포함) 또는 엑셀 'CSV (쉼표로 분리)' 의 옛 한글 방식(CP949)을 자동 판별해 읽는다."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{path.name}: 글자 인코딩을 읽지 못했습니다. 엑셀에서 CSV로 다시 저장해 보세요.")


def read_new(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        data = json.loads(read_text_auto(path))
        return data if isinstance(data, list) else [data]
    reader = csv.DictReader(io.StringIO(read_text_auto(path), newline=""))
    header = [(h or "").strip() for h in (reader.fieldnames or [])]
    missing = [k for k in FIELDS if k not in header]
    if missing:
        raise ValueError(
            f"{path.name}: 첫 줄(제목 줄)에 열 이름이 없습니다 -> {', '.join(missing)} "
            "(제목 줄을 지우지 말고 new_companies_template.csv 의 첫 줄과 같게 두세요)"
        )
    reader.fieldnames = header
    rows = []
    for r in reader:
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items() if k is not None}
        if any(r.values()):  # 엑셀이 남기는 빈 줄(,,,,,,)은 건너뜀
            rows.append(r)
    return rows


# ---------------------------------------------------------------- 페이지 템플릿
TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__URL__">
<meta property="og:type" content="article">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__URL__">
<meta property="og:image" content="__URL__thumbnail.png">
<style>
:root{font-family:Pretendard,Apple SD Gothic Neo,Malgun Gothic,sans-serif;color:#16202e;background:#f5f7fa}
*{box-sizing:border-box}body{margin:0}
.wrap{max-width:1080px;margin:0 auto;padding:30px 18px 60px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:28px;box-shadow:0 8px 30px rgba(16,24,40,.05)}
h1{margin:0 0 12px;font-size:31px;letter-spacing:-.02em}
.muted{color:#64748b;line-height:1.78}
.hero{display:block;width:100%;max-width:960px;margin:0 auto 22px;border-radius:16px;border:1px solid #e2e8f0}
.table{width:100%;border-collapse:collapse;margin-top:22px}
.table th,.table td{border-bottom:1px solid #e8edf3;padding:13px;text-align:left;vertical-align:top}
.table th{width:140px;background:#fafbfd;color:#516173}
.links{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:24px}
.btn{display:inline-block;padding:13px 20px;border-radius:10px;border:1px solid #16202e;background:#fff;color:#16202e;text-decoration:none;font-weight:700}
.btn.primary{background:#16202e;color:#fff}
.back{display:inline-block;margin-bottom:18px;color:#53677e;text-decoration:none}
@media (max-width:640px){h1{font-size:25px}.card{padding:20px}.table th{width:105px}}
</style>
</head>
<body>
<main class="wrap">
<a class="back" href="../index.html">← 전자어음할인 기업 목록</a>
<section class="card">
<img class="hero" src="thumbnail.png" alt="__NAME__ 전자어음할인 안내 대표 이미지">
<h1>__NAME__ 전자어음할인 안내</h1>
<p class="muted">__INTRO__</p>
<table class="table">__ROWS__</table>
<nav class="links" aria-label="바로가기">
<a class="btn" href="/bill-discount/">어음할인 총정리</a>
<a class="btn" href="/calculator/">할인 수수료 계산기</a>
<a class="btn primary" href="tel:__PHONE__">상담하기</a>
</nav>
</section>
</main>
</body>
</html>
"""


def render_page(c: dict) -> str:
    name = c["기업명"]
    addr = c["주소"]
    sido = addr.split(" ", 1)[0] if addr else ""
    upjong = c["업종"]

    detail = ""
    if sido and upjong:
        detail = f" {sido}에 소재하며, 업종은 {upjong}입니다."
    elif sido:
        detail = f" {sido}에 소재합니다."
    elif upjong:
        detail = f" 업종은 {upjong}입니다."
    intro = (
        f"전자어음을 발행하는 {name}의 간략한 기업정보를 제공하는 페이지입니다.{detail} "
        "전자어음의 할인 가능 여부와 할인율 등의 조건은 발행사 및 금융시장의 현황에 따라 변동이 있습니다. "
        "어음할인 관련 자세한 상담이 필요하신 경우 전화 문의바랍니다."
    )
    title = f"{name} 전자어음할인 안내 | 태성투자대부"
    rows = "".join(
        f"<tr><th>{label}</th><td>{escape(c[key] or EMPTY)}</td></tr>"
        for label, key in [("기업명", "기업명"), ("대표자", "대표자"), ("기업구분", "기업구분"),
                           ("업종", "업종"), ("설립일", "설립일"), ("주소", "주소"), ("사업자번호", "사업자번호")]
    )
    html = TEMPLATE
    for token, value in {
        "__TITLE__": escape(title, quote=True),
        "__DESC__": escape(intro, quote=True),
        "__URL__": escape(c["url"], quote=True),
        "__NAME__": escape(name),
        "__INTRO__": escape(intro),
        "__ROWS__": rows,
        "__PHONE__": PHONE,
    }.items():
        html = html.replace(token, value)
    return html


# ---------------------------------------------------------------- 썸네일(신규 업체용)
# 기존 썸네일(1200x675, 흰 카드 + 남색 머리띠 + 큰 상호)에 맞춰 만든 디자인.
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/Library/Fonts/AppleGothic.ttf",
]


def find_font(explicit: str | None):
    for p in ([explicit] if explicit else []) + FONT_CANDIDATES:
        if p and Path(p).exists():
            return p
    return None


def make_thumbnail(path: Path, name: str, font_path: str):
    from PIL import Image, ImageDraw, ImageFont

    W, H, SS = 1200, 675, 2  # SS: 선명하게 그리기 위한 2배 확대 후 축소

    def font(size):
        idx = 1 if "NotoSansCJK" in font_path else 0  # Noto .ttc 에서 1번이 한국어
        try:
            return ImageFont.truetype(font_path, int(size * SS), index=idx)
        except Exception:
            return ImageFont.truetype(font_path, int(size * SS))

    def wrap(text, f, max_w):
        lines, cur = [], ""
        for ch in text:
            if f.getlength(cur + ch) > max_w * SS and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
        return lines

    img = Image.new("RGB", (W * SS, H * SS), "#f5f7fa")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([28 * SS, 28 * SS, 1172 * SS, 647 * SS], radius=24 * SS,
                        fill="#ffffff", outline="#e2e8f0", width=2 * SS)
    d.rounded_rectangle([28 * SS, 28 * SS, 1172 * SS, 155 * SS], radius=24 * SS,
                        fill="#16202e", corners=(True, True, False, False))
    d.text((600 * SS, 93 * SS), "전자어음할인 안내", font=font(48), fill="#ffffff", anchor="mm")

    # 상호: 기본 150px 한 줄, 길면 줄이고, 그래도 넘치면 두 줄
    max_w = 1020
    lines, size = None, None
    for sz in range(150, 71, -6):
        f = font(sz)
        if f.getlength(name) <= max_w * SS:
            lines, size = [name], sz
            break
    if lines is None:
        for sz in range(110, 55, -6):
            f = font(sz)
            cand = wrap(name, f, max_w)
            if len(cand) <= 2:
                lines, size = cand, sz
                break
    if lines is None:
        size = 56
        lines = wrap(name, font(size), max_w)[:2]
    f = font(size)
    line_h = size * 1.22
    top = 426 - (line_h * (len(lines) - 1)) / 2
    for i, ln in enumerate(lines):
        d.text((600 * SS, (top + i * line_h) * SS), ln, font=f, fill="#16202e", anchor="mm")

    img = img.resize((W, H), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)


# ---------------------------------------------------------------- 사이트맵
def update_sitemap(sitemap: Path, companies: list[dict], today: str, touch: set[str], touch_all: bool,
                   touch_list: bool = False):
    if not sitemap.exists():
        print(f"  ! 사이트맵을 찾지 못해 건너뜀: {sitemap}")
        return
    text = sitemap.read_text(encoding="utf-8")
    blocks = re.findall(r"<url>.*?</url>", text, re.S)
    head = text[: text.index("<url>")]
    tail = text[text.rindex("</url>") + len("</url>"):]
    prefix = f"{SITE}/possible/"

    def loc(b):
        return re.search(r"<loc>(.*?)</loc>", b, re.S).group(1).strip()

    def lastmod(b):
        m = re.search(r"<lastmod>(.*?)</lastmod>", b, re.S)
        return m.group(1).strip() if m else today

    is_indiv = lambda b: loc(b).startswith(prefix) and loc(b) != prefix
    first = next((i for i, b in enumerate(blocks) if is_indiv(b)), len(blocks))
    before = [b for b in blocks[:first] if not is_indiv(b)]
    after = [b for b in blocks[first:] if not is_indiv(b)]
    old = {loc(b): lastmod(b) for b in blocks if is_indiv(b)}

    items = []
    for c in companies:
        u = c["url"]
        lm = today if (touch_all or u in touch or u not in old) else old[u]
        items.append(
            f"<url>\n<loc>{u}</loc>\n<lastmod>{lm}</lastmod>\n"
            "<changefreq>monthly</changefreq>\n<priority>0.6</priority>\n</url>"
        )
    if touch_list:
        def bump(b):
            if loc(b) == prefix:
                return re.sub(r"<lastmod>.*?</lastmod>", f"<lastmod>{today}</lastmod>", b, flags=re.S)
            return b
        before = [bump(b) for b in before]
        after = [bump(b) for b in after]
    body = "\n".join(before + items + after)
    sitemap.write_text(f"{head}{body}{tail}", encoding="utf-8")


# ---------------------------------------------------------------- 목록 페이지 (possible/index.html)
# 목록 페이지의 가나다순 목록(<div id="cho-groups"> ... </div>)과 기업 수 문구만 다시 쓴다.
# 나머지(디자인, 검색 스크립트, 문구)는 건드리지 않는다.
LIST_BAR = ["ㄱ", "ㄴ", "ㄷ", "ㄹ", "ㅁ", "ㅂ", "ㅅ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ", "기타"]
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_CHO_BASE = {"ㄲ": "ㄱ", "ㄸ": "ㄷ", "ㅃ": "ㅂ", "ㅆ": "ㅅ", "ㅉ": "ㅈ"}
# True: 목록 링크를 %28 %29 로 인코딩(기존 방식) / False: 사이트맵·canonical 과 같이 괄호 그대로
LIST_LINK_ENCODE_PARENS = False
_LIST_END = "\n        </div>\n      </div>\n      <div id=\"no-res\">"


def cho_group(name: str) -> str:
    """(주)·(유) 등 괄호 표기를 뺀 뒤 첫 글자의 초성. 한글이 아니면 '기타'."""
    core = re.sub(r"\([^)]*\)", "", name).strip()
    ch = core[:1]
    if ch and "가" <= ch <= "힣":
        c = _CHO[(ord(ch) - 0xAC00) // 588]
        return _CHO_BASE.get(c, c)
    return "기타"


def list_href(name: str) -> str:
    safe = "" if LIST_LINK_ENCODE_PARENS else "()"
    return f"./{quote(name, safe=safe)}/"


def render_list_groups(companies: list[dict]) -> str:
    buckets = {g: [] for g in LIST_BAR}
    for c in sorted(companies, key=lambda c: c["기업명"]):
        buckets[cho_group(c["기업명"])].append(c["기업명"])
    parts = []
    for i, g in enumerate(LIST_BAR):
        items = "\n".join(
            f'<a class="etc-item" href="{list_href(n)}" data-n="{escape(n, quote=True)}">'
            f'<span class="etc-dot"></span><span class="etc-name">{escape(n)}</span></a>'
            for n in buckets[g]
        )
        show = " show" if i == 0 else ""
        parts.append(
            f'<div class="cho-group{show}" id="cho-{g}"><div class="cho-label">{g} ({len(buckets[g]):,}개)</div>'
            f'<div class="etc-grid" id="eg-{g}">{items}</div></div>'
        )
    return '<div id="cho-groups">' + "".join(parts) + "</div>"


def render_list_page(text: str, companies: list[dict]) -> str:
    start = text.find('<div id="cho-groups">')
    end = text.find(_LIST_END, start) if start >= 0 else -1
    if start < 0 or end < 0:
        raise ValueError("목록 페이지에서 가나다순 목록 위치(cho-groups)를 찾지 못했습니다. 페이지 구조가 바뀌었는지 확인하세요.")
    new = text[:start] + render_list_groups(companies) + text[end:]
    total = f"{len(companies):,}"
    new = re.sub(r"(전체 )[\d,]+(개 기업)", rf"\g<1>{total}\g<2>", new)
    new = re.sub(r"(총 )[\d,]+(개 기업)", rf"\g<1>{total}\g<2>", new)
    return new


def update_list_page(path: Path, companies: list[dict]) -> bool:
    """목록 페이지를 갱신한다. 파일이 없거나 구조가 달라 못 하면 False (다른 작업은 계속 진행)."""
    if not path.exists():
        print(f"  ! 목록 페이지를 찾지 못해 건너뜀: {path}  (--list-page 로 위치 지정)")
        return False
    old = path.read_text(encoding="utf-8")
    try:
        new = render_list_page(old, companies)
    except ValueError as e:
        print(f"  ! {e}")
        return False
    if new != old:
        path.write_text(new, encoding="utf-8")
    return True


def list_page_status(path: Path, companies: list[dict]) -> str:
    if not path.exists():
        return f"목록 페이지 없음({path})"
    t = path.read_text(encoding="utf-8")
    names = set(re.findall(r'<a class="etc-item" href="[^"]*" data-n="([^"]*)"', t))
    from html import unescape
    names = {unescape(n) for n in names}
    want = {c["기업명"] for c in companies}
    if names == want:
        return f"목록 페이지: 업체 {len(want)}개 일치"
    return f"목록 페이지 불일치: 목록에만 {len(names - want)}개, 데이터에만 {len(want - names)}개 (rebuild 로 맞춤)"


# ---------------------------------------------------------------- 공통 빌드
def write_pages(root: Path, targets: list[dict], font_path, make_thumbs: bool):
    made_thumbs, skipped = 0, 0
    for c in targets:
        folder = root / "possible" / c["기업명"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(render_page(c), encoding="utf-8")
        thumb = folder / "thumbnail.png"
        if make_thumbs and not thumb.exists():
            if font_path is None:
                skipped += 1
                continue
            try:
                make_thumbnail(thumb, c["기업명"], font_path)
                made_thumbs += 1
            except ModuleNotFoundError:
                print("  ! Pillow가 없어 썸네일을 만들지 못했습니다: pip install pillow")
                make_thumbs = False
    if skipped:
        print(f"  ! 한글 폰트를 찾지 못해 썸네일 {skipped}개를 만들지 못했습니다 (--font 로 폰트 경로 지정)")
    return made_thumbs


def write_indexes(args, companies):
    save_json(args.page_index, [
        {"order": i, "기업명": c["기업명"], "url": c["url"]} for i, c in enumerate(companies, 1)
    ])


# ---------------------------------------------------------------- 명령
def cmd_check(args):
    data = [norm_record(r) for r in load_json(args.companies)]
    errs, names = [], {}
    for r in data:
        errs += validate(r)
        names[r["기업명"]] = names.get(r["기업명"], 0) + 1
    errs += [f"{n}: 중복 {k}건" for n, k in names.items() if k > 1]
    empty = {k: sum(1 for r in data if not r[k]) for k in FIELDS[1:]}
    print(f"업체 {len(data)}개 / 빈 값: " + ", ".join(f"{k} {v}" for k, v in empty.items() if v))
    for r in data:
        if biz_issue(r):
            print("  ⚠", biz_issue(r))
    for e in errs:
        print("  ✗", e)
    print(list_page_status(args.list_page, data))
    print("문제 없음" if not errs else f"문제 {len(errs)}건")
    return 1 if errs else 0


def cmd_add(args):
    existing = [norm_record(r) for r in load_json(args.companies)]
    have = {c["기업명"] for c in existing}
    new, errs, seen = [], [], set()
    try:
        raw_rows = read_new(Path(args.file))
    except (ValueError, OSError, csv.Error) as e:
        print(f"추가를 중단했습니다. {e}")
        return 1
    if not raw_rows:
        print("추가를 중단했습니다. 파일에 업체 행이 없습니다. (제목 줄 아래에 업체를 적어 주세요)")
        return 1
    for raw in raw_rows:
        rec = norm_record(raw)
        e = validate(rec)
        if biz_issue(rec):
            e.append(biz_issue(rec))
        if rec["기업명"] in have or rec["기업명"] in seen:
            e.append(f"{rec['기업명']}: 이미 등록된 업체(중복)")
        errs += e
        seen.add(rec["기업명"])
        new.append(rec)
    if errs:
        print("추가를 중단했습니다. 아래를 고친 뒤 다시 실행하세요. (아무 파일도 바뀌지 않았습니다)")
        for e in errs:
            print("  ✗", e)
        return 1

    merged = sorted(existing + new, key=lambda c: c["기업명"])
    save_json(args.companies, merged)
    font_path = find_font(args.font)
    n_thumb = write_pages(args.root, new, font_path, not args.skip_thumbnails)
    write_indexes(args, merged)
    today = dt.date.today().isoformat()
    listed = update_list_page(args.list_page, merged)
    update_sitemap(args.sitemap, merged, today, {c["url"] for c in new}, False, touch_list=listed)

    out = args.companies.parent / f"new_urls_{today.replace('-', '')}.txt"
    out.write_text("\n".join(c["url"] for c in new) + "\n", encoding="utf-8")
    print(f"신규 {len(new)}개 추가 완료 (전체 {len(merged)}개), 썸네일 {n_thumb}개 생성")
    print(f"서치어드바이저 수집요청용 주소 목록: {out}")
    print("목록 페이지:", "자동 갱신 완료" if listed else "갱신하지 못함(위 안내 확인)")
    print("남은 작업: GitHub Desktop 에서 Commit -> Push -> 서치어드바이저 수집 요청")
    return 0


def cmd_rebuild(args):
    data = [norm_record(r) for r in load_json(args.companies)]
    errs = [e for r in data for e in validate(r)]
    if errs:
        print("데이터 문제로 중단합니다. 먼저 `check` 로 확인하세요.")
        for e in errs[:20]:
            print("  ✗", e)
        return 1
    data.sort(key=lambda c: c["기업명"])
    for r in data:
        if biz_issue(r):
            print("  ⚠", biz_issue(r))
    save_json(args.companies, data)
    font_path = find_font(args.font)
    n_thumb = write_pages(args.root, data, font_path, not args.skip_thumbnails)
    write_indexes(args, data)
    listed = update_list_page(args.list_page, data)
    update_sitemap(args.sitemap, data, dt.date.today().isoformat(), set(), True, touch_list=listed)
    print(f"전체 {len(data)}개 페이지 재생성 완료 (새 썸네일 {n_thumb}개, 기존 썸네일은 유지)")
    return 0


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=ROOT_DEFAULT, help="사이트 루트(기본: tools 폴더의 상위)")
    common.add_argument("--companies", type=Path, default=HERE / "companies.json", help="기준 데이터")
    common.add_argument("--page-index", dest="page_index", type=Path, default=None, help="page-index.json 위치")
    common.add_argument("--sitemap", type=Path, default=None, help="sitemap.xml 위치(기본: 루트)")
    common.add_argument("--list-page", dest="list_page", type=Path, default=None,
                        help="목록 페이지 위치(기본: 루트/possible/index.html)")
    common.add_argument("--font", default=None, help="썸네일용 한글 폰트 파일 경로")
    common.add_argument("--skip-thumbnails", action="store_true", help="썸네일 생성 건너뛰기")

    ap = argparse.ArgumentParser(description="/possible/ 업체 페이지 생성기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", parents=[common], help="데이터 점검")
    p_add = sub.add_parser("add", parents=[common], help="신규 업체 추가 (CSV 또는 JSON)")
    p_add.add_argument("file")
    sub.add_parser("rebuild", parents=[common], help="전체 페이지 재생성")
    args = ap.parse_args()

    args.root = args.root.resolve()
    args.companies = args.companies.resolve()
    args.page_index = (args.page_index or args.companies.parent / "page-index.json").resolve()
    args.sitemap = (args.sitemap or args.root / "sitemap.xml").resolve()
    args.list_page = (args.list_page or args.root / "possible" / "index.html").resolve()
    sys.exit({"check": cmd_check, "add": cmd_add, "rebuild": cmd_rebuild}[args.cmd](args))


if __name__ == "__main__":
    main()

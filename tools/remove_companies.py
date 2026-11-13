#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
/possible/ 업체 삭제 도구 (부도·폐업·합병 업체 정리용)

사용법 (저장소 맨 위에서)
  1) 삭제할 업체 이름을 한 줄에 하나씩 적은 텍스트 파일을 만든다 (예: 삭제업체.txt)
  2) python tools/remove_companies.py 삭제업체.txt

한 번에 처리하는 것
  - tools/companies.json 에서 업체 삭제
  - possible/<업체명>/ 폴더 삭제
  - sitemap.xml 에서 해당 항목만 삭제 (다른 항목의 lastmod 는 그대로)
  - tools/page-index.json 갱신
  - 목록 페이지(possible/index.html)의 가나다순 목록과 기업 수 갱신

이름이 하나라도 데이터에 없으면 아무것도 바꾸지 않고 멈춘다.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import xml.dom.minidom
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_DEFAULT = HERE.parent


def read_names(args) -> list[str]:
    names = []
    for item in args.names:
        p = Path(item)
        if p.suffix.lower() == ".txt" and p.exists():
            raw = p.read_bytes()
            for enc in ("utf-8-sig", "cp949"):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                sys.exit(f"{p.name}: 글자 인코딩을 읽지 못했습니다. 메모장에서 UTF-8로 다시 저장하세요.")
            names += [ln.strip() for ln in text.splitlines()]
        else:
            names.append(item.strip())
    out, seen = [], set()
    for n in names:
        if n and n not in seen:
            out.append(n)
            seen.add(n)
    return out


def squash(s: str) -> str:
    return re.sub(r"\s", "", s)


def remove_from_sitemap(text: str, urls: list[str]) -> tuple[str, int]:
    removed = 0
    for u in urls:
        pat = re.compile(r"<url>\s*<loc>" + re.escape(u) + r"</loc>.*?</url>[ \t]*\r?\n?", re.S)
        text, n = pat.subn("", text)
        removed += n
    return text, removed


def main():
    ap = argparse.ArgumentParser(description="/possible/ 업체 삭제 도구")
    ap.add_argument("names", nargs="+", help="삭제할 업체 이름 또는 이름이 적힌 .txt 파일 (한 줄에 하나)")
    ap.add_argument("--root", type=Path, default=ROOT_DEFAULT, help="사이트 루트(기본: tools 폴더의 상위)")
    ap.add_argument("--companies", type=Path, default=HERE / "companies.json")
    ap.add_argument("--page-index", dest="page_index", type=Path, default=None)
    ap.add_argument("--sitemap", type=Path, default=None)
    ap.add_argument("--list-page", dest="list_page", type=Path, default=None)
    ap.add_argument("--yes", action="store_true", help="확인 질문 없이 진행")
    args = ap.parse_args()

    root = args.root.resolve()
    companies_path = args.companies.resolve()
    page_index = (args.page_index or companies_path.parent / "page-index.json").resolve()
    sitemap = (args.sitemap or root / "sitemap.xml").resolve()
    list_page = (args.list_page or root / "possible" / "index.html").resolve()

    names = read_names(args)
    if not names:
        sys.exit("삭제할 업체 이름이 없습니다.")

    data = json.loads(companies_path.read_text(encoding="utf-8"))
    by_name = {c["기업명"]: c for c in data}

    missing = [n for n in names if n not in by_name]
    if missing:
        print("삭제를 중단했습니다. 아래 이름이 companies.json 에 없습니다. (아무 파일도 바뀌지 않았습니다)")
        pool = {squash(k): k for k in by_name}
        for n in missing:
            hint = pool.get(squash(n))
            print(f"  ✗ {n!r}" + (f"  -> 띄어쓰기만 다른 업체: {hint!r}" if hint else ""))
        sys.exit(1)

    targets = [by_name[n] for n in names]
    print(f"삭제 대상 {len(targets)}개:")
    for c in targets:
        folder = root / "possible" / c["기업명"]
        print(f"  - {c['기업명']}  (폴더 {'있음' if folder.is_dir() else '없음'})")
    if not args.yes:
        if input("정말 삭제할까요? (y/n): ").strip().lower() != "y":
            print("취소했습니다. 아무 파일도 바뀌지 않았습니다.")
            return

    remaining = [c for c in data if c["기업명"] not in set(names)]
    urls = [c["url"] for c in targets]

    # --- 모든 새 내용을 메모리에서 먼저 만들고 검증한 뒤에 쓴다 ---
    new_sitemap = None
    n_sm = 0
    if sitemap.exists():
        new_sitemap, n_sm = remove_from_sitemap(sitemap.read_text(encoding="utf-8"), urls)
        try:
            xml.dom.minidom.parseString(new_sitemap.encode("utf-8"))
        except Exception as e:  # 구조가 깨지면 쓰지 않는다
            sys.exit(f"사이트맵 구조 검사에 실패해서 중단했습니다 (아무 파일도 바뀌지 않았습니다): {e}")

    new_list = None
    if list_page.exists():
        sys.path.insert(0, str(HERE))
        try:
            import build_possible as bp  # 같은 폴더의 생성기 함수를 재사용

            new_list = bp.render_list_page(list_page.read_text(encoding="utf-8"), remaining)
        except Exception as e:
            print(f"  ! 목록 페이지는 자동 갱신하지 못했습니다({e}). 끝난 뒤 `python tools/build_possible.py rebuild` 로 맞추세요.")

    # --- 쓰기 ---
    companies_path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    page_index.write_text(
        json.dumps([{"order": i, "기업명": c["기업명"], "url": c["url"]} for i, c in enumerate(remaining, 1)],
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if new_sitemap is not None:
        sitemap.write_text(new_sitemap, encoding="utf-8")
    if new_list is not None:
        list_page.write_text(new_list, encoding="utf-8")
    n_dir = 0
    for c in targets:
        folder = root / "possible" / c["기업명"]
        if folder.is_dir():
            shutil.rmtree(folder)
            n_dir += 1

    print(f"완료: 업체 {len(targets)}개 삭제 (남은 업체 {len(remaining)}개)")
    print(f"  폴더 {n_dir}개 삭제, 사이트맵 항목 {n_sm}개 삭제, 목록 페이지 {'갱신' if new_list is not None else '갱신 못함'}")
    print("남은 작업: GitHub Desktop 에서 Commit -> Push")


if __name__ == "__main__":
    main()

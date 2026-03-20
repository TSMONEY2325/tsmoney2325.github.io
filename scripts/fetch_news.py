#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
전자어음 뉴스 자동 수집 및 요약 스크립트
- 네이버 검색 API에서 '전자어음' 키워드 뉴스 수집
- Claude AI로 요약
- news/index.html 자동 생성
"""

import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
import anthropic
import re

# ── 설정 ──
KEYWORD = "전자어음"
MAX_ITEMS = 50
DATA_FILE = "news/news_data.json"
NEWS_HTML = "news/index.html"
KST = timezone(timedelta(hours=9))

def fetch_naver_news(client_id, client_secret):
    """네이버 검색 API로 전자어음 뉴스 수집"""
    # 큰따옴표로 감싸서 정확한 키워드만 검색
    encoded = urllib.parse.quote(f'"{KEYWORD}"')
    url = f"https://openapi.naver.com/v1/search/news.json?query={encoded}&display=50&sort=date"

    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", client_id)
    req.add_header("X-Naver-Client-Secret", client_secret)

    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            result = json.loads(res.read().decode('utf-8'))
    except Exception as e:
        print(f"네이버 뉴스 수집 실패: {e}")
        return []

    items = []
    for item in result.get('items', [])[:MAX_ITEMS]:
        title = re.sub(r'<[^>]+>', '', item.get('title', '')).strip()
        desc = re.sub(r'<[^>]+>', '', item.get('description', '')).strip()
        link = item.get('originallink') or item.get('link', '')
        pubdate = item.get('pubDate', '')
        
        # 출처 추출 (링크에서 도메인 추출)
        try:
            source = urllib.parse.urlparse(link).netloc.replace('www.', '')
        except:
            source = '뉴스'

        if title and link:
            items.append({
                'title': title,
                'link': link,
                'desc': desc[:300],
                'pubdate': pubdate,
                'source': source,
            })

    print(f"수집된 뉴스: {len(items)}개")
    return items

def load_existing():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(data):
    os.makedirs('news', exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def summarize(client, title, desc):
    if not desc or len(desc) < 30:
        return desc or title
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"다음 뉴스를 2~3문장으로 간결하게 요약해주세요. 핵심 내용만 담고 출처나 기자명은 제외해주세요.\n\n제목: {title}\n내용: {desc}"
            }]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"요약 실패: {e}")
        return desc[:150] + '...'

def parse_date(article):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(article.get('pubdate', ''))
    except:
        return datetime.min.replace(tzinfo=timezone.utc)

def generate_html(articles):
    now = datetime.now(KST).strftime('%Y년 %m월 %d일 %H:%M')

    cards = ''
    for a in articles:
        date_str = a.get('pubdate', '')
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            date_str = dt.astimezone(KST).strftime('%Y.%m.%d')
        except:
            date_str = date_str[:16] if date_str else ''

        source = a.get('source', '뉴스')
        summary = a.get('summary', a.get('desc', ''))[:200]

        cards += f'''
        <article class="news-card rv">
          <div class="news-meta">
            <span class="news-source">{source}</span>
            <span class="news-date">{date_str}</span>
          </div>
          <h3 class="news-title">
            <a href="{a['link']}" target="_blank" rel="noopener">{a['title']}</a>
          </h3>
          <p class="news-summary">{summary}</p>
          <a href="{a['link']}" target="_blank" rel="noopener" class="news-link">원문 보기 →</a>
        </article>'''

    if not cards:
        cards = '<div class="no-news">현재 수집된 뉴스가 없습니다.</div>'

    html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>전자어음 뉴스 — 최신 전자어음 소식 | 태성투자대부</title>
<meta name="description" content="전자어음 관련 최신 뉴스와 소식을 확인하세요. 전자어음할인 시장 동향, 제도 변화, 금융 정책 등 업계 최신 정보 제공. ☎ 02-999-2325">
<meta name="keywords" content="전자어음뉴스,전자어음최신뉴스,전자어음할인뉴스,전자어음시장동향,어음할인뉴스,전자어음제도,전자어음금융">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://tsmoney.kr/news/">
<meta property="og:title" content="전자어음 뉴스 — 최신 전자어음 소식">
<meta property="og:description" content="전자어음 관련 최신 뉴스와 시장 동향을 확인하세요.">
<meta property="og:url" content="https://tsmoney.kr/news/">
<meta property="og:image" content="https://tsmoney.kr/assets/main.png">
<meta property="og:locale" content="ko_KR">
<meta name="naver-site-verification" content="81a30ebd7364cc8429a3dd44d5da267a">
<meta name="google-site-verification" content="5f8ceb170073c3be">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&family=Pretendard:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--g:#1B3A6B;--gm:#16336B;--gl:#1A56C4;--gp:#E8F0FB;--a:#E8B800;--al:#FEE500;--w:#fff;--off:#F6F3EE;--st:#EAE5DC;--g2:#DDD8CF;--g4:#A5A09A;--g6:#6A6560;--text:#1A1714;--serif:'Nanum Myeongjo',Georgia,serif;--sans:'Pretendard','Apple SD Gothic Neo',sans-serif}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:var(--sans);background:var(--off);color:var(--text);overflow-x:hidden;-webkit-font-smoothing:antialiased}}
::-webkit-scrollbar{{width:5px}}::-webkit-scrollbar-track{{background:var(--off)}}::-webkit-scrollbar-thumb{{background:var(--gm);border-radius:3px}}
nav{{position:fixed;top:0;left:0;right:0;z-index:500;height:72px;display:flex;align-items:center;justify-content:space-between;padding:0 5vw;background:var(--g);border-bottom:2px solid rgba(232,184,0,.3);transition:box-shadow .3s}}
nav.scrolled{{box-shadow:0 4px 24px rgba(0,0,0,.25)}}
.logo{{display:flex;align-items:center;gap:9px;text-decoration:none}}
.logo-mark{{width:44px;height:44px;border-radius:9px;overflow:hidden;background:var(--w);display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.logo-text{{display:flex;flex-direction:column;gap:1px}}
.logo-name{{font-family:var(--sans);font-size:17px;font-weight:600;color:var(--w);letter-spacing:.01em;line-height:1.2}}
.logo-reg{{font-size:12px;font-weight:500;color:rgba(255,255,255,.72);letter-spacing:.01em;line-height:1}}
.nav-links{{display:flex;gap:2px;list-style:none}}
.nav-links a{{font-size:14px;font-weight:500;color:rgba(255,255,255,.82);text-decoration:none;padding:7px 13px;border-radius:8px;transition:color .18s,background .18s;white-space:nowrap}}
.nav-links a:hover,.nav-links a.on{{color:var(--al);background:rgba(255,255,255,.08)}}
.nav-links a.on{{font-weight:700;color:var(--al)}}
.nav-r{{display:flex;align-items:center;gap:9px}}
.nav-tel{{font-size:15px;font-weight:700;color:var(--al);text-decoration:none;letter-spacing:.02em;white-space:nowrap}}
.btn-kko{{background:#FEE500;color:#3C1E1E;font-size:12px;font-weight:700;padding:7px 13px;border-radius:8px;text-decoration:none;display:flex;align-items:center;gap:5px;white-space:nowrap}}
.hbg{{display:none;flex-direction:column;gap:5px;cursor:pointer;padding:6px;border:none;background:none}}
.hbg span{{display:block;width:22px;height:2px;background:var(--w);border-radius:2px}}
.mob{{display:none;position:fixed;top:72px;left:0;right:0;z-index:499;background:rgba(255,255,255,.97);backdrop-filter:blur(16px);border-bottom:1px solid var(--g2);padding:14px 5vw 18px;flex-direction:column;gap:4px}}
.mob.open{{display:flex}}
.mob a{{font-size:15px;font-weight:500;color:var(--text);text-decoration:none;padding:11px 14px;border-radius:10px}}
.mob a:hover{{background:var(--gp);color:var(--g)}}
.mob .m-tel{{margin-top:10px;padding:13px;background:var(--g);border-radius:12px;color:var(--al);font-family:var(--serif);font-size:18px;font-weight:800;text-align:center}}
.mob .m-kko{{background:#FEE500;color:#3C1E1E;font-weight:700;font-size:13px;padding:12px;border-radius:12px;text-align:center}}
.pw{{padding-top:72px}}
.ph{{background:var(--g);padding:52px 5vw 0;text-align:center}}
.phi{{max-width:640px;margin:0 auto}}
.pey{{font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--a);margin-bottom:13px;display:flex;align-items:center;justify-content:center;gap:10px}}
.pey::before,.pey::after{{content:'';width:14px;height:1px;background:var(--a)}}
.ph h1{{font-family:var(--serif);font-size:clamp(26px,4vw,40px);font-weight:800;color:var(--w);line-height:1.2;letter-spacing:-.025em;margin-bottom:12px}}
.ph h1 em{{font-style:normal;color:var(--al)}}
.ph p{{font-size:14px;color:rgba(255,255,255,.52);line-height:1.85;padding-bottom:36px}}
.updated{{font-size:11px;color:rgba(255,255,255,.35);padding-bottom:20px}}
.nsec{{padding:0 5vw 72px}}
.nw{{max-width:860px;margin:-20px auto 0}}
.news-grid{{display:flex;flex-direction:column;gap:16px;margin-top:8px}}
.news-card{{background:var(--w);border-radius:16px;border:1px solid var(--st);padding:24px 28px;transition:transform .2s,box-shadow .2s}}
.news-card:hover{{transform:translateY(-3px);box-shadow:0 10px 28px rgba(27,58,107,.1)}}
.news-meta{{display:flex;align-items:center;gap:10px;margin-bottom:10px}}
.news-source{{font-size:11px;font-weight:700;padding:3px 9px;border-radius:20px;background:var(--gp);color:var(--g)}}
.news-date{{font-size:11px;color:var(--g4)}}
.news-title{{font-size:17px;font-weight:700;color:var(--text);margin-bottom:10px;line-height:1.4}}
.news-title a{{color:inherit;text-decoration:none}}
.news-title a:hover{{color:var(--g)}}
.news-summary{{font-size:13px;color:var(--g6);line-height:1.85;margin-bottom:14px}}
.news-link{{font-size:12px;font-weight:600;color:var(--gl);text-decoration:none}}
.news-link:hover{{color:var(--g)}}
.no-news{{text-align:center;padding:60px;color:var(--g4);font-size:15px;background:var(--w);border-radius:16px;border:1px solid var(--st)}}
.rv{{opacity:0;transform:translateY(22px);transition:opacity .6s ease,transform .6s ease}}
.rv.vis{{opacity:1;transform:none}}
footer{{background:#06100E;padding:36px 5vw 28px}}
.ft-wrap{{max-width:1060px;margin:0 auto;display:grid;grid-template-columns:1fr auto;gap:40px;align-items:start}}
.ft-legal{{font-size:11px;color:rgba(255,255,255,.55);line-height:2.1}}
.ft-nav{{display:flex;flex-direction:column;gap:8px;align-items:flex-end;flex-shrink:0}}
.ft-nav a{{font-size:13px;color:rgba(255,255,255,.65);text-decoration:none;transition:color .2s;white-space:nowrap}}
.ft-nav a:hover{{color:var(--al)}}
@media(max-width:860px){{.nav-links{{display:none}}.hbg{{display:flex}}.nav-tel{{display:none}}}}
@media(max-width:600px){{.news-card{{padding:18px}}.ft-wrap{{grid-template-columns:1fr}}.ft-nav{{align-items:flex-start}}}}
</style>
</head>
<body>
<nav id="nav">
  <a class="logo" href="/"><div class="logo-mark"><img src="/assets/logo.jpg" alt="태성투자대부 로고" style="width:42px;height:42px;object-fit:contain;display:block;"></div><span class="logo-text"><span class="logo-name">태성투자대부</span><span class="logo-reg">대부업 2019-서울중구-0048</span></span></a>
  <ul class="nav-links">
    <li><a href="/">📑 전자어음할인</a></li>
    <li><a href="/calculator/">📉 수수료 계산기</a></li>
    <li><a href="/possible/">📋 할인 가능 목록</a></li>
    <li><a href="/corporate/">🏢 기업금융</a></li>
    <li><a href="/news/" class="on">📰 전자어음 뉴스</a></li>
  </ul>
  <div class="nav-r">
    <a class="nav-tel" href="tel:02-999-2325">02-999-2325</a>
    <a class="btn-kko" href="https://open.kakao.com/o/s8YmMcOc" target="_blank" rel="noopener">💬 카카오 상담</a>
    <button class="hbg" id="hbg"><span></span><span></span><span></span></button>
  </div>
</nav>
<div class="mob" id="mob">
  <a href="/">📑 전자어음할인</a>
  <a href="/calculator/">📉 수수료 계산기</a>
  <a href="/possible/">📋 할인 가능 목록</a>
  <a href="/corporate/">🏢 기업금융</a>
  <a href="/news/">📰 전자어음 뉴스</a>
  <a class="m-tel" href="tel:02-999-2325">📞 02-999-2325</a>
  <a class="m-kko" href="https://open.kakao.com/o/s8YmMcOc" target="_blank">💬 카카오톡 상담하기</a>
</div>

<div class="pw">
  <div class="ph">
    <div class="phi">
      <div class="pey">News</div>
      <h1>전자어음 <em>최신 뉴스</em></h1>
      <p>전자어음 관련 최신 뉴스와 시장 동향을 확인하세요.</p>
      <div class="updated">최종 업데이트: {now}</div>
    </div>
  </div>
  <div class="nsec">
    <div class="nw">
      <div class="news-grid">
        {cards}
      </div>
    </div>
  </div>
</div>

<footer>
  <div class="ft-wrap">
    <div class="ft-legal">
      상호 : 태성투자대부 | 대표자명 : 신현수 | 주소 : 서울 중구 명동2길 57 태평양빌딩 506-1호<br>
      대부업등록번호 : 2019-서울중구-0048 | 등록지자체 : 서울시 중구청(02-3396-5697)<br>
      연이자율 최대 20% / 연체이자율 최대 20% / 이자 외 추가비용 X / 조기상환수수료 X / 중개수수료 요구 및 수취는 불법입니다.<br>
      "과도한 빚, 고통의 시작입니다." &nbsp; "대출 시 귀하의 신용등급이 하락할 수 있습니다."
    </div>
    <div class="ft-nav">
      <a href="/">전자어음할인</a>
      <a href="/calculator/">수수료 계산기</a>
      <a href="/possible/">할인 가능 목록</a>
      <a href="/corporate/">기업금융</a>
      <a href="/news/">전자어음 뉴스</a>
    </div>
  </div>
</footer>

<script>
window.addEventListener('scroll',()=>document.getElementById('nav').classList.toggle('scrolled',scrollY>10));
document.getElementById('hbg').addEventListener('click',()=>document.getElementById('mob').classList.toggle('open'));
const obs=new IntersectionObserver(e=>e.forEach(x=>{{if(x.isIntersecting)x.target.classList.add('vis')}}),{{threshold:.1}});
document.querySelectorAll('.rv').forEach(el=>obs.observe(el));
</script>
</body>
</html>'''

    os.makedirs('news', exist_ok=True)
    with open(NEWS_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"뉴스 페이지 생성 완료: {len(articles)}개 기사")

def main():
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    naver_id = os.environ.get('NAVER_CLIENT_ID')
    naver_secret = os.environ.get('NAVER_CLIENT_SECRET')

    if not api_key:
        print("ANTHROPIC_API_KEY 없음")
        return
    if not naver_id or not naver_secret:
        print("NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET 없음")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # 기존 데이터 로드
    existing = load_existing()
    existing_links = {a['link'] for a in existing}

    # 네이버 뉴스 수집
    fetched = fetch_naver_news(naver_id, naver_secret)

    # 새 뉴스만 필터링
    new_items = [item for item in fetched if item['link'] not in existing_links]
    print(f"새 뉴스: {len(new_items)}개")

    # 새 뉴스 요약
    for item in new_items:
        print(f"요약 중: {item['title'][:40]}...")
        item['summary'] = summarize(client, item['title'], item['desc'])

    # 합치기 + 날짜순 정렬
    all_articles = new_items + existing
    all_articles.sort(key=parse_date, reverse=True)
    all_articles = all_articles[:100]

    save_data(all_articles)
    generate_html(all_articles)
    print("완료!")

if __name__ == '__main__':
    main()

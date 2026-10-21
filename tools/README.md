# /possible/ 업체 페이지 관리 (tsmoney.kr)

업체 데이터 한 곳(`companies.json`)을 기준으로 개별 페이지, 썸네일, 목록 페이지, `page-index.json`, 사이트맵을 만드는 도구입니다.
**업체를 추가할 때는 항상 이 문서의 절차를 따릅니다.** (손으로 폴더나 HTML을 만들거나 목록을 고치지 않습니다)

## 파일 구성

| 파일 | 역할 |
|---|---|
| `tools/build_possible.py` | 생성기 본체 (`check` / `add` / `rebuild`) |
| `tools/companies.json` | **기준 데이터** (업체 정보의 유일한 원본) |
| `tools/page-index.json` | 순서·기업명·주소 목록 (생성기가 매번 새로 씀) |
| `tools/new_companies_template.csv` | 신규 업체 입력 양식 |
| `possible/<기업명>/index.html` | 업체 페이지 (생성기가 만듦) |
| `possible/<기업명>/thumbnail.png` | 대표 이미지 (없을 때만 생성, 기존 것은 건드리지 않음) |
| `possible/index.html` | 목록 페이지 (가나다순 목록과 기업 수만 생성기가 갱신) |
| `sitemap.xml` | possible 항목은 생성기가 갱신, 나머지 항목은 그대로 유지 |

준비물: Python 3, 썸네일용 `pip install pillow`, 한글 폰트(없으면 `--font 폰트경로`).

## 작업 전에

1. GitHub Desktop을 열고 위쪽 `Fetch origin`을 누릅니다. `Pull origin`이 보이면 눌러서 최신 상태로 맞춥니다.
2. 명령 창을 엽니다. GitHub Desktop 메뉴 `Repository` → `Show in Explorer`로 저장소 폴더를 열고,
   위쪽 주소창을 클릭해 `cmd`를 입력한 뒤 Enter를 누릅니다. 아래 명령은 모두 이 창에서 입력합니다.

## 새 업체 추가 절차

1. `tools/new_companies_template.csv`를 복사해 저장소 맨 위(`tools` 폴더와 같은 자리)에 `신규업체.csv`로 저장하고 업체 행을 채웁니다.
   (엑셀에서는 `CSV (쉼표로 분리)`든 `CSV UTF-8`이든 상관없이 저장하면 됩니다. 한글 인코딩은 자동으로 판별합니다. 예시 행은 지우세요)
   - 열: `기업명, 대표자, 기업구분, 업종, 설립일, 주소, 사업자번호`
   - 설립일은 `1986년 3월 25일` 형식, 모르는 값은 비워 둡니다. (페이지에는 `-`로 표시)
   - 주소 앞 지역명은 줄임말(서울, 경기, 경남 등)이어도 됩니다. 자동으로 전체 표기로 바뀝니다.
   - 사업자번호는 전체 번호를 넣어도 됩니다. 뒤 4자리가 자동으로 `****`로 바뀝니다.
2. 실행합니다.
   ```
   python build_possible.py add 신규업체.csv
   ```
   - 문제가 있으면 **아무 파일도 바꾸지 않고** 이유를 알려줍니다. (중복 업체, 설립일 형식, 알 수 없는 지역명, 사업자번호 형식)
   - 문제가 없으면 아래가 한 번에 처리됩니다.
     `companies.json` 갱신 → 업체 페이지·썸네일 생성 → **목록 페이지(가나다순 목록, 기업 수) 갱신** →
     `page-index.json`·`sitemap.xml` 갱신 → 수집요청용 주소 목록 `tools/new_urls_날짜.txt` 생성
3. GitHub Desktop을 열면 왼쪽 `Changes`에 바뀐 파일이 나옵니다. `new_urls_날짜.txt`와 `신규업체.csv`는 체크를 풀고,
   왼쪽 아래 칸에 "업체 추가"라고 적어 `Commit to main`을 누른 뒤 위쪽 `Push origin`을 누릅니다. (몇 분 뒤 사이트에 반영됩니다)
4. 서치어드바이저 '웹페이지 수집' 요청에 `tools/new_urls_날짜.txt`의 주소를 넣습니다.
   요청 한도는 공개되지 않았으니 하루 30~50개부터 시작해 늘려 가며, 1~2일 뒤 노출을 확인합니다.
5. 필요하면 `rss.xml`에 신규 업체 항목을 추가해 RSS를 다시 제출합니다. (`pubDate`는 실제 추가한 날짜)

## 자동으로 적용되는 규칙

- 지역: 주소 맨 앞을 아래 16개 전체 표기로 통일
  서울특별시, 전남광주통합특별시, 부산광역시, 대구광역시, 인천광역시, 대전광역시, 울산광역시, 세종특별자치시,
  경기도, 강원특별자치도, 충청북도, 충청남도, 전북특별자치도, 경상북도, 경상남도, 제주특별자치도
  (광주광역시·광주·전라남도·전남은 전남광주통합특별시로 바뀝니다)
- 사업자번호: `XXX-XX-X****` 형태로 뒤 4자리를 가림
- 빈 값: 페이지 표에 `-` 표시
- 주소 규칙: 사이트맵·canonical·`url` 필드·목록 링크 모두 괄호를 그대로 쓰고 한글만 인코딩 (`/possible/(%EC%A3%BC)…/`)
  (목록 링크를 예전처럼 `%28 %29`로 쓰려면 `build_possible.py`의 `LIST_LINK_ENCODE_PARENS = True`)
- 정렬: `companies.json`과 `page-index.json`은 기업명 가나다(유니코드) 순서
- 목록 분류: `(주)`·`(유)` 같은 괄호 표기를 뺀 뒤 첫 글자의 초성(ㄲ→ㄱ 등)으로 분류, 한글이 아니면 '기타'. 그룹 안은 기업명 순서
- 업체 페이지: 제목 `{기업명} 전자어음할인 안내 | 태성투자대부`,
  본문 소개 + 기업정보 표 + 하단 링크 3개(어음할인 총정리 `/bill-discount/`, 할인 수수료 계산기 `/calculator/`, 상담하기 `tel:02-999-2325`)
- 썸네일: 1200x675, 흰 카드와 남색 머리띠, 큰 상호. 상호가 길면 글자를 줄이고 두 줄로 나눔

## 다른 명령

- 데이터 점검만: `python tools/build_possible.py check`  (목록 페이지가 데이터와 일치하는지도 알려줌)
- 템플릿(문구·디자인)이나 `companies.json`을 고쳤을 때 전체 재생성: `python tools/build_possible.py rebuild`
  - 모든 `index.html`과 목록 페이지를 다시 만들고 사이트맵의 possible 항목 `lastmod`를 오늘로 바꿉니다. 썸네일은 건드리지 않습니다.
  - 업체 페이지 템플릿은 `build_possible.py` 안의 `TEMPLATE`과 `render_page()`입니다.
- 썸네일 생성을 건너뛰려면 명령 뒤에 `--skip-thumbnails`
- 파일 위치가 다르면 `--root`, `--companies`, `--page-index`, `--sitemap`, `--list-page` 옵션으로 지정

## 주의

- `companies.json`은 직접 고쳐도 되지만, 고친 뒤에는 `rebuild`를 실행해야 페이지와 목록에 반영됩니다.
- 목록 페이지는 가나다순 목록(`<div id="cho-groups">`)과 "전체/총 N개 기업" 문구만 바꿉니다.
  페이지 구조를 크게 바꿔서 이 위치를 찾지 못하면, 목록은 건드리지 않고 이유를 알려준 뒤 나머지 작업만 진행합니다.
- `tools/` 폴더도 GitHub Pages로 공개되므로, 검색에 잡히지 않게 `robots.txt`에 `Disallow: /tools/`를 넣는 것을 권합니다.
- 사업자번호 형식이 이상한 업체는 `check`에서 ⚠로 표시됩니다. 자동으로 고치지 않으니 직접 확인해서 `companies.json`을 수정한 뒤 `rebuild`하세요.

# webinar-auto-registration

국내 IT 웨비나를 **매일 자동으로 수집·등록**하고, **구글 캘린더에 추가**하며,
**월별 일정 + 경품 정보 홈페이지**(GitHub Pages)로 공개하는 프로젝트입니다.

## 대상 사이트

| 키 | 이름 | 주소 | 스크래퍼 상태 |
|---|---|---|---|
| `allshowtv` | 올쇼TV | https://www.allshowtv.com | ✅ 실서비스 검증됨 |
| `ddtube` | DD튜브 | https://www.ddtube.co.kr | ✅ 실서비스 검증됨(상세페이지 보강) |
| `talkit` | 토크아이티 | https://talkit.tv | ✅ 실서비스 검증됨 |
| `sharedit` | 쉐어드IT | https://www.sharedit.co.kr | ✅ 실서비스 검증됨(제목 [MMDD] 코드 활용) |
| `dubiz` | 두비즈 | https://dubiz.co.kr | 🟡 코드 작성 완료, 라이브 미검증(사내 프록시 차단) |
| `e4ds` | e4ds | https://www.e4ds.com/webinar.asp | ⚙️ 로그인 필요 |
| `cloit` | CLOIT:ON | https://webinar.cloit.com | ⚙️ SPA, 현재 세션 없음 |

> ✅ 4개 사이트는 실제 사이트에서 정상 수집을 확인했습니다.
> 🟡 두비즈는 관찰된 구조(`/onoffmix/` → `/Event/NNN`)로 스크래퍼를 작성했으나
> **사내 보안 프록시가 dubiz.co.kr을 차단**해 개발 환경에서 라이브 검증은 못 했습니다
> — GitHub Actions(사외망)에서는 접근 가능하므로 첫 실행 후 확인하세요.
> ⚙️ e4ds는 로그인, CLOIT:ON은 현재 대기 세션이 없어 셀렉터 검증이 보류 상태입니다.
> 셀렉터가 안 맞으면 해당 사이트는 **빈 결과**를 내도록 설계돼 있어(날짜 파싱 실패 시 스킵)
> 잘못된 데이터가 올라가지 않습니다.

## 동작 방식

```
매일 08:00 KST (GitHub Actions cron)
  1. pipeline.py     → 7개 사이트 스크래핑 → 경품 추출 → data/webinars.json 생성
  2. registrar.py    → (활성화된 사이트) 로그인 후 사전등록
  3. calendar_sync.py→ 등록한 웨비나를 구글 캘린더에 추가(멱등)
  4. docs/ 갱신       → webinars.json + webinars.ics 재생성 후 커밋
```

홈페이지(`docs/`)는 `webinars.json`을 읽어 **월별 달력 / 목록** 뷰, **출처·경품 필터**,
**경품 상세**, **구글 캘린더 추가 링크**를 제공합니다.

## 요구사항

- **Python 3.11+** (CI는 3.11 사용, 로컬 3.12 검증)
- **Playwright Chromium** — `python -m playwright install chromium`
  (리눅스에서 시스템 라이브러리가 없으면 `--with-deps` 필요, sudo 요구)
- 의존성은 [requirements.txt](requirements.txt)에 **버전 고정**되어 재현 가능

## 로컬 실행 (재현 절차)

```bash
# 1) 클론
git clone https://github.com/leemgs/webinar-auto-registration.git
cd webinar-auto-registration

# 2) 가상환경 + 의존성 (버전 고정)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium      # 필요시: --with-deps

# 3) 소스 경로 (pytest.ini에도 pythonpath=src 설정됨)
export PYTHONPATH=src

# 4) 테스트 (오프라인, 브라우저 불필요)
pytest                                      # 14 tests

# 5) 공개 일정 스크래핑 + data/·docs/ 생성
python -m webinar.pipeline -v
python -m webinar.pipeline --site ddtube --site talkit -v   # 특정 사이트만

# 6) 등록 플로우 시뮬레이션 (실제 제출 안 함)
python -m webinar.registrar --dry-run --site ddtube -v

# 7) 홈페이지 미리보기 → http://localhost:8000
python -m http.server -d docs 8000
```

> `data/webinars.json`은 **커밋되는 결과물**(진실의 원천)입니다. `pipeline`은 기존
> 데이터와 **병합**하고(등록 상태·수동 경품 보존), 60일 지난 과거 웨비나는 정리합니다.

## 구글 캘린더 설정 (OAuth 리프레시 토큰)

1. Google Cloud Console에서 **Google Calendar API** 활성화.
2. **OAuth 2.0 클라이언트 ID**(유형: 데스크톱 앱) 생성.
3. 토큰 발급:
   ```bash
   export GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=...
   python scripts/get_google_token.py
   ```
4. 출력된 `GOOGLE_REFRESH_TOKEN` 을 `.env` 또는 GitHub Secret 에 저장.

> 인증 없이 쓰려면 `docs/webinars.ics` 를 구글 캘린더 **"URL로 추가"** 로 구독해도 됩니다.

## GitHub 설정

### Secrets (Settings → Secrets and variables → Actions)

| 이름 | 용도 |
|---|---|
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` | 구글 캘린더 |
| `GOOGLE_CALENDAR_ID` | 대상 캘린더(기본 `primary`) |
| `SITE_<KEY>_USER`, `SITE_<KEY>_PASS` | 사이트별 로그인 (예: `SITE_DDTUBE_USER`) |

> 사이트 계정 Secret 이 없으면 해당 사이트의 **등록만** 건너뜁니다(수집은 계속).

### GitHub Pages

Settings → Pages → Source: **Deploy from a branch**, Branch: `main` / `/docs`.
게시 후 `https://<user>.github.io/webinar-auto-registration/` 에서 홈페이지 확인.

## 자동 등록(register) 활성화

기본적으로 모든 사이트의 등록은 **비활성**(`config/sites.yaml` 의 `register.enabled: false`)입니다.
실제 계정으로 로그인 폼 셀렉터를 검증한 뒤 사이트별로 `true` 로 바꾸세요.

```yaml
# config/sites.yaml
ddtube:
  login:
    url: "https://www.ddtube.co.kr/login"
    user_selector: "input[name='email']"
    pass_selector: "input[type='password']"
    submit_selector: "button[type='submit']"
  register:
    enabled: true          # ← 검증 후 활성화
    button_selector: "a:has-text('사전등록')"
    confirm_selector: "button:has-text('확인')"
```

셀렉터 확인 팁: 실제 로그인 페이지에서 개발자도구로 입력창/버튼의 selector 를 확인해
`config/sites.yaml` 에 반영한 뒤 `--dry-run` 으로 점검하세요.

## 경품 정보

- 자동: `webinar/prizes.py` 가 텍스트에서 경품 키워드(설문/질문/상담/시청)를 best-effort 추출.
- 수동: `config/prizes_override.yaml` 에 웨비나 id 기준으로 정확한 경품을 입력하면 우선 적용됩니다.

경품 종류: `survey`(설문) · `question`(질문) · `consult`(상담) · `attendance`(참석/시청)

## 구조

```
config/            사이트 설정(sites.yaml), 경품 오버라이드(prizes_override.yaml)
src/webinar/
  models.py        Webinar / Prize 데이터 모델
  config.py        설정·시크릿 로드
  storage.py       data/webinars.json 읽기/쓰기/병합
  browser.py       Playwright 브라우저 헬퍼
  scrapers/        사이트별 스크래퍼(base + 7개)
  prizes.py        경품 추출/병합
  registrar.py     로그인 + 사전등록
  calendar_sync.py 구글 캘린더 동기화
  ics_export.py    ICS 피드 생성
  pipeline.py      전체 파이프라인(entry point)
scripts/           get_google_token.py
data/webinars.json 수집 결과(진실의 원천)
docs/              GitHub Pages 홈페이지
tests/             오프라인 파서 테스트
```

## 새 사이트 추가 / 스크래퍼 관리

1. `config/sites.yaml` 에 사이트 항목 추가 (`base_url`, `listing_url`, `wait_selector`, `login`, `register`).
2. `src/webinar/scrapers/<key>.py` 에 `Scraper(BaseScraper)` 작성 — `parse(html) -> list[Webinar]` 만 구현하면 됩니다. 공통 헬퍼 활용:
   - `self.select_cards(soup, [selectors])` / `self.cards_to_webinars(cards, ...)`
   - 날짜/시간 파서 `parse_date`, `parse_time` (한글 "7월 8일", `D-2`, "오후 2:00" 등 지원)
   - `require_date=True`(기본): 날짜 파싱 실패 시 항목을 버려 **오탐 방지**
3. `src/webinar/scrapers/__init__.py` 의 `SCRAPER_MODULES` 에 키 등록.
4. `tests/test_parsers.py` 에 저장한 HTML 스니펫으로 **오프라인 테스트** 추가(브라우저 불필요).

> 스크래퍼 설계 원칙: **fetch(브라우저)와 parse(HTML)를 분리** → parse는 픽스처로
> 결정적 테스트 가능. 봇 차단/JS 렌더링은 실제 브라우저(Playwright)로 처리.
> 사이트 개편 시 대부분 `config/sites.yaml` 의 셀렉터만 손보면 됩니다.

## 문제 해결

- **git push 실패 `Empty reply from server`**: 일부 사내 프록시가 HTTP/2 push(POST)를
  끊습니다. HTTP/1.1 강제로 해결 — `git -c http.version=HTTP/1.1 push`.
  (읽기 전용 fetch/ls-remote는 HTTP/2로도 동작)
- **특정 사이트 수집 결과가 계속 0건**: 셀렉터 문제이기 전에 **네트워크 차단**을
  먼저 확인하세요. 사내 보안 프록시가 외부 사이트(예: dubiz.co.kr)를 막으면 응답이
  차단 안내 페이지로 옵니다. GitHub Actions(사외망)에서는 접근됩니다.
- **`playwright` 브라우저 오류**: `python -m playwright install chromium` (리눅스 CI는
  `--with-deps`). 워크플로우는 `--with-deps chromium` 를 사용합니다.
- **개별 사이트 실패가 전체를 막지 않음**: 각 스크래퍼/단계는 예외를 흡수하고 로그만
  남기도록 설계돼, 하루치 작업이 한 사이트 때문에 중단되지 않습니다.

## 주의

- 각 사이트의 이용약관을 준수하세요. 자동 등록은 **본인 계정**으로만 사용하세요.
- 스크래퍼 셀렉터는 사이트 개편 시 `config/sites.yaml` / `scrapers/*.py` 에서 조정이 필요할 수 있습니다.

# webinar

국내 IT 웨비나를 **매일 자동으로 수집·등록**하고, **사용자가 지정한 구글 계정
(여러 개 가능)의 캘린더에 자동 sync**하며, **월별 일정 + 경품 정보 홈페이지**
(GitHub Pages)로 공개하는 프로젝트입니다.

---

## 🧩 한눈에 보기

8개 웨비나 사이트에서 일정을 **수집**하고, 하나의 데이터(`data/webinars.json`)로 **정리**한 뒤,
**등록·캘린더·홈페이지** 세 갈래로 **활용**하는 단일 파이프라인입니다. 매일 GitHub Actions가 돌립니다.

```mermaid
flowchart LR
    subgraph SRC["🌐 웨비나 사이트 (8)"]
        S1["올쇼TV · DD튜브<br/>토크아이티 · 쉐어드IT"]
        S2["두비즈 · e4ds<br/>CLOIT:ON · 채널온TV"]
    end

    subgraph PIPE["🐍 pipeline.py · Playwright"]
        direction LR
        SC["📡 scrapers<br/><b>수집</b><br/>파싱·정규화"]
        PR["🎁 prizes<br/><b>경품 추출</b>"]
        MG["🗃️ storage<br/><b>병합·정리</b>"]
        SC --> PR --> MG
    end

    DB[("📄 data/webinars.json<br/><b>진실의 원천</b>")]

    subgraph OUT["🎯 활용"]
        RG["📝 registrar<br/>사전등록"]
        CAL["📅 calendar_sync<br/>구글 캘린더<br/>(지정 계정 · 다중)"]
        WEB["🌐 docs/ 홈페이지<br/>+ webinars.ics"]
    end

    S1 --> SC
    S2 --> SC
    MG --> DB
    DB --> RG
    DB --> CAL
    DB --> WEB
    RG -. "등록 상태 기록" .-> DB
    CRON["⏰ GitHub Actions<br/>매일 08:00 KST"] -. "트리거" .-> PIPE

    style SC fill:#dbeafe,stroke:#3b82f6,color:#1e3a8a
    style PR fill:#fef3c7,stroke:#f59e0b,color:#78350f
    style MG fill:#e9d5ff,stroke:#a855f7,color:#581c87
    style DB fill:#dcfce7,stroke:#22c55e,color:#14532d
    style WEB fill:#dcfce7,stroke:#22c55e,color:#14532d
    style RG fill:#fee2e2,stroke:#ef4444,color:#7f1d1d
    style CAL fill:#fef3c7,stroke:#f59e0b,color:#78350f
```

| 단계 | 모듈 | 한 줄 설명 |
|---|---|---|
| 📡 **수집** | [`scrapers/`](src/webinar/scrapers) | 8개 사이트에서 제목·일시·링크·썸네일 파싱 (봇 차단/JS는 Playwright로) |
| 🎁 **경품 추출** | [`prizes.py`](src/webinar/prizes.py) | 설문/질문/상담/참석 경품 키워드 추출 + 수동 오버라이드 병합 |
| 🗃️ **정리** | [`storage.py`](src/webinar/storage.py) | 기존 데이터와 병합(등록 상태·경품 보존), 60일 지난 항목 정리 |
| 📝 **등록** | [`registrar.py`](src/webinar/registrar.py) | (활성 사이트) 로그인 후 사전등록, 멱등 |
| 📅 **캘린더** | [`calendar_sync.py`](src/webinar/calendar_sync.py) | 지정한 구글 계정(들)의 캘린더에 upsert(중복 없음, [계정 설정](#원하는-구글-계정-지정--여러-계정에-동시-sync--configgoogleyaml)) + [`ics_export.py`](src/webinar/ics_export.py) 백업 |
| 🌐 **공개** | [`docs/`](docs) | 월별 달력/목록·필터·경품·구글캘린더 링크 홈페이지 (GitHub Pages) |
| ⏰ **자동화** | [`daily.yml`](.github/workflows/daily.yml) | 매일 08:00 KST cron으로 위 전 과정 실행·커밋 |

---

## 대상 사이트

| 키 | 이름 | 주소 | 스크래퍼 상태 |
|---|---|---|---|
| `allshowtv` | 올쇼TV | https://www.allshowtv.com | ✅ 실서비스 검증됨 |
| `ddtube` | DD튜브 | https://www.ddtube.co.kr | ✅ 홈 슬라이더 + `/webinar/`·`/conference/` 목록, 최신 24개 상세페이지(종료시각 포함) |
| `talkit` | 토크아이티 | https://talkit.tv | ✅ 실서비스 검증됨 |
| `sharedit` | 쉐어드IT | https://www.sharedit.co.kr | ⚠️ GitHub 호스팅 러너는 Cloudflare 챌린지로 차단 → self-hosted 러너로 수집, 필요 시 [수동 등록](#수집이-막힌-웨비나-등록-sharedit-등) |
| `dubiz` | 두비즈 | https://dubiz.co.kr | 🟡 코드 작성 완료, 라이브 미검증(사내 프록시 차단) |
| `e4ds` | e4ds | https://www.e4ds.com/webinar.asp | ⚙️ 로그인 필요 |
| `cloit` | CLOIT:ON | https://webinar.cloit.com | ⚙️ SPA, 현재 세션 없음 |
| `chontv` | 채널온TV | https://chontv.com | 🟡 코드 작성 완료, 라이브 미검증(개발망 프록시 차단) |

> ✅ 4개 사이트는 실제 사이트에서 정상 수집을 확인했습니다.
> 🟡 두비즈(`/onoffmix/` → `/Event/NNN`)와 채널온TV(`/{채널}/{id}`)는 관찰된 구조로
> 스크래퍼를 작성했으나 **개발망 프록시가 두 도메인을 차단**해 개발 환경에서 라이브
> 검증은 못 했습니다 — GitHub Actions(사외망)에서는 접근 가능하므로 첫 실행 후 확인하세요.
> ⚙️ e4ds는 로그인, CLOIT:ON은 현재 대기 세션이 없어 셀렉터 검증이 보류 상태입니다.
> 셀렉터가 안 맞으면 해당 사이트는 **빈 결과**를 내도록 설계돼 있어(날짜 파싱 실패 시 스킵)
> 잘못된 데이터가 올라가지 않습니다.

## 동작 흐름 (Operation Flow)

매일 1회, GitHub Actions가 아래 순서로 실행합니다. 각 단계는 독립적으로 실패를 흡수하므로
한 사이트/한 단계가 실패해도 나머지는 계속 진행됩니다.

```mermaid
sequenceDiagram
    autonumber
    participant CR as ⏰ Actions cron
    participant PP as 🐍 pipeline.py
    participant ST as 🌐 웨비나 사이트
    participant DB as 📄 webinars.json
    participant RG as 📝 registrar
    participant GC as 📅 Google Calendar
    participant PG as 🌐 docs/ (Pages)

    CR->>PP: 매일 08:00 KST 실행
    PP->>ST: 8개 사이트 스크래핑
    ST-->>PP: 웨비나 목록(제목·일시·링크)
    PP->>PP: 경품 추출 + 기존 데이터 병합·정리
    PP->>DB: webinars.json 저장
    PP->>RG: (enabled·계정 있는 사이트) 등록 요청
    RG->>ST: 로그인 → 사전등록 제출
    RG->>DB: registered=true 기록
    PP->>GC: 수집한 전체 웨비나를 지정 계정별 캘린더에 upsert(멱등)
    PP->>PG: webinars.json / webinars.ics 갱신 후 커밋
    Note over PG: GitHub Pages가 홈페이지 자동 갱신
```

1. **수집** — `pipeline.py`가 8개 사이트를 스크래핑하고 경품을 추출합니다.
2. **정리** — 기존 `data/webinars.json`과 병합(등록 상태·수동 경품 보존), 60일 지난 항목 정리.
3. **등록** — 계정이 있고 `register.enabled: true`인 사이트에 로그인 후 사전등록(멱등).
4. **캘린더** — GitHub Actions는 수집한 전체 웨비나를 지정한 구글 계정(들)의 캘린더에 upsert하고 `webinars.ics` 백업 피드를 생성합니다. 로컬 명령은 기본적으로 등록 완료 일정만 대상으로 하며 `--all`로 전체 일정을 동기화합니다.
5. **공개** — `docs/`의 데이터를 갱신·커밋 → GitHub Pages 홈페이지 자동 반영.

> 홈페이지(`docs/`)는 `webinars.json`을 읽어 **월별 달력 / 목록** 뷰, **출처·경품 필터**,
> **경품 상세**, **구글 캘린더 추가 링크**를 제공합니다.

## 요구사항

- **Python 3.11+** (CI는 3.11 사용, 로컬 3.12 검증)
- **Playwright Chromium** — `python -m playwright install chromium`
  (리눅스에서 시스템 라이브러리가 없으면 `--with-deps` 필요, sudo 요구)
- 의존성은 [requirements.txt](requirements.txt)에 **버전 고정**되어 재현 가능

## 로컬 실행 (재현 절차)

```bash
# 1) 클론
git clone https://github.com/leemgs/webinar.git
cd webinar

# 2) 가상환경 + 의존성 (버전 고정)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium      # 필요시: --with-deps

# 3) 소스 경로 (pytest.ini에도 pythonpath=src 설정됨)
export PYTHONPATH=src

# 4) 테스트 (오프라인, 브라우저 불필요)
pytest                                      # 오프라인 테스트 전체

# 5) 공개 일정 스크래핑 + data/·docs/ 생성
python -m webinar.pipeline -v
python -m webinar.pipeline --site ddtube --site talkit -v   # 특정 사이트만

# 6) 등록 플로우 시뮬레이션 (실제 제출 안 함)
python -m webinar.registrar --dry-run --site ddtube -v

# 6.5) 구글 캘린더 sync (config/google.yaml 또는 GOOGLE_* 환경변수 설정 후)
python -m webinar.calendar_sync -v                  # 설정된 모든 계정에 sync
python -m webinar.calendar_sync --account work -v   # 지정한 계정만
python -m webinar.calendar_sync --all -v            # 등록 여부 무관 전체 일정
python -m webinar.calendar_sync --all --strict -v   # CI용: 인증/쓰기 실패 시 오류 종료

# 7) 홈페이지 미리보기 → http://localhost:8000
python -m http.server -d docs 8000
```

> `data/webinars.json`은 **커밋되는 결과물**(진실의 원천)입니다. `pipeline`은 기존
> 데이터와 **병합**하고(등록 상태·수동 경품 보존), 60일 지난 과거 웨비나는 정리합니다.
> 일부 사이트가 일시적인 봇 차단이나 네트워크 오류로 `0건`을 반환하면 해당 사이트의
> 기존 일정은 보존하고 나머지 사이트 수집은 계속합니다. 모든 사이트가 동시에 `0건`일
> 때만 전체 장애로 판단해 저장하지 않고 실패합니다. 사이트별 응답 건수는 Actions 요약에 표시됩니다.
> Calendar API의 일시적인 `rateLimitExceeded`/HTTP 429 응답은 지수 백오프로 자동
> 재시도하며, CI에서는 일정별 쓰기 간격을 1초로 제한합니다.

## 구글 캘린더 설정 (OAuth 리프레시 토큰) — 따라하기

> 링크를 클릭해 순서대로 진행하면 됩니다. 소요 5~10분. **한 번만** 하면 됩니다.

### 1단계 — Google Cloud 프로젝트 만들기
- 👉 <https://console.cloud.google.com/projectcreate> 접속 → 이름 예: `webinar-calendar` → **만들기**.
- 만든 프로젝트가 상단에 선택돼 있는지 확인.

### 2단계 — Google Calendar API 활성화
- 👉 <https://console.cloud.google.com/apis/library/calendar-json.googleapis.com> 접속 → **사용(Enable)** 클릭.

### 3단계 — OAuth 동의 화면 구성
- 👉 <https://console.cloud.google.com/apis/credentials/consent> 접속.
- User Type: **External(외부)** 선택 → 만들기.
- 앱 이름/사용자 지원 이메일/개발자 연락처만 채우고 저장하며 진행.
- **Test users(테스트 사용자)** 에 **본인 Gmail 주소 추가**.
- ⚠️ **중요**: 게시 상태가 **Testing** 이면 리프레시 토큰이 **7일 후 만료**됩니다.
  계속 쓰려면 동의 화면에서 **"앱 게시(Publish app / 프로덕션으로 전환)"** 를 눌러
  `In production` 상태로 두세요(개인 사용은 미인증 경고만 뜨고 그대로 사용 가능).

### 4단계 — OAuth 클라이언트 ID 발급 (데스크톱 앱)
- 👉 <https://console.cloud.google.com/apis/credentials> 접속.
- **+ 사용자 인증 정보 만들기 → OAuth 클라이언트 ID** → 애플리케이션 유형 **데스크톱 앱** → 만들기.
- 표시되는 **클라이언트 ID** 와 **클라이언트 보안 비밀번호** 를 복사 → 각각
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.

### 5단계 — 리프레시 토큰 발급 (로컬에서 1회)
```bash
export PYTHONPATH=src
export GOOGLE_CLIENT_ID="<4단계 클라이언트 ID>"
export GOOGLE_CLIENT_SECRET="<4단계 보안 비밀번호>"
python scripts/get_google_token.py     # 브라우저가 열리며 동의 → 토큰 출력
```
출력된 `GOOGLE_REFRESH_TOKEN=...` 값을 복사합니다.

### 6단계 — 대상 캘린더 ID 확인 (`GOOGLE_CALENDAR_ID`)
- 기본 개인 캘린더면 그냥 `primary` 를 쓰면 됩니다.
- 특정 캘린더에 넣으려면 👉 <https://calendar.google.com/calendar/u/0/r/settings> →
  왼쪽에서 캘린더 선택 → **"캘린더 통합"** 섹션의 **캘린더 ID**(예: `abcd...@group.calendar.google.com`) 복사.

> 인증 설정이 번거로우면 캘린더 동기화를 건너뛰고, 게시된 `webinars.ics` 를
> 구글 캘린더 **"기타 캘린더 → URL로 추가"** 에 붙여 구독해도 됩니다:
> `https://leemgs.github.io/webinar/webinars.ics`

### 원하는 구글 계정 지정 / 여러 계정에 동시 sync — `config/google.yaml`

일정을 넣을 구글 계정을 **이름 붙여 직접 지정**할 수 있고, 여러 계정을 등록하면
`calendar_sync` 가 **각 계정의 캘린더에 모두 자동 upsert** 합니다(멱등, 중복 없음).

```bash
cp config/google.example.yaml config/google.yaml   # 복사 후 채우기 (.gitignore 제외됨)
```

```yaml
# config/google.yaml  (⚠️ 커밋되지 않음)
personal:
  client_id: "xxxxx.apps.googleusercontent.com"
  client_secret: "GOCSPX-..."
  refresh_token: "1//0g..."          # scripts/get_google_token.py 로 계정별 발급
  calendar_id: "primary"             # 생략 시 primary
work:
  client_id: "..."
  client_secret: "..."
  refresh_token: "..."
  calendar_id: "abcd@group.calendar.google.com"
  only_registered: false             # 이 계정엔 등록 여부와 무관하게 전체 일정 sync
```

- **계정별 토큰 발급**: `scripts/get_google_token.py` 를 계정마다 한 번씩 실행하고,
  브라우저에서 **해당 구글 계정으로 로그인**해 동의하면 됩니다. 스크립트가
  `google.yaml` 에 붙여넣을 스니펫도 출력해 줍니다.
- **실행**: `python -m webinar.calendar_sync -v` (모든 계정),
  `--account work` 로 특정 계정만, `--all` 로 등록 여부 무관 전체 sync.
- **CI(GitHub Actions)**: 같은 YAML 내용을 통째로 `GOOGLE_ACCOUNTS_YAML` 시크릿
  하나에 넣으면 됩니다(아래 Secrets 표 참고).
- **우선순위**: `GOOGLE_ACCOUNTS_YAML` 환경변수 → `config/google.yaml` →
  단일 계정 환경변수(`GOOGLE_CLIENT_ID` 등, `default` 계정으로 취급).
  같은 이름은 먼저 정의된 쪽이 우선합니다. 기존 단일 계정 설정은 그대로 동작합니다.

## GitHub Secrets 등록 — 따라하기

리포지토리 시크릿 페이지에서 등록합니다:
👉 <https://github.com/leemgs/webinar/settings/secrets/actions>
(또는 저장소 → **Settings → Secrets and variables → Actions → New repository secret**)

**New repository secret** 버튼을 눌러 아래 이름/값을 **하나씩** 추가하세요.

### 값은 어디서 가져오나 — 발급처 한눈에

| Secret 이름 | 접속할 사이트 | 가져오는 방법 |
|---|---|---|
| `GOOGLE_CLIENT_ID`<br/>`GOOGLE_CLIENT_SECRET` | 👉 [Google Cloud Console — 사용자 인증 정보](https://console.cloud.google.com/apis/credentials) | **+ 사용자 인증 정보 만들기 → OAuth 클라이언트 ID → 데스크톱 앱**으로 생성하면 두 값이 함께 표시됩니다. 처음이라면 먼저 [프로젝트 생성](https://console.cloud.google.com/projectcreate) → [Calendar API 활성화](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com) → [OAuth 동의 화면 구성](https://console.cloud.google.com/apis/credentials/consent) 순서로 진행하세요([1~4단계 상세](#1단계--google-cloud-프로젝트-만들기)). |
| `GOOGLE_REFRESH_TOKEN` | (사이트 아님) 로컬 터미널 + 구글 로그인 창 | 위 두 값을 환경변수로 넣고 `python scripts/get_google_token.py` 실행 → 브라우저에 <https://accounts.google.com> 로그인/동의 창이 뜨고, 동의하면 터미널에 토큰이 출력됩니다([5단계 상세](#5단계--리프레시-토큰-발급-로컬에서-1회)). |
| `GOOGLE_CALENDAR_ID` | 👉 [Google Calendar 설정](https://calendar.google.com/calendar/u/0/r/settings) | 기본 개인 캘린더면 그냥 `primary` 입력(사이트 접속 불필요). 특정 캘린더면 왼쪽에서 캘린더 선택 → **"캘린더 통합"** 섹션의 **캘린더 ID** 복사([6단계 상세](#6단계--대상-캘린더-id-확인-google_calendar_id)). |
| `GOOGLE_ACCOUNTS_YAML` | 위 발급처들을 **계정마다 반복** | 새 사이트는 없습니다. sync 할 구글 계정마다 위 절차(클라이언트 ID·시크릿은 공용 가능, 리프레시 토큰은 **해당 계정으로 로그인**해 발급)를 반복한 뒤, [`config/google.example.yaml`](config/google.example.yaml) 형식의 YAML로 묶어 통째로 넣습니다. |

### 필수 — 구글 캘린더 (안 넣으면 캘린더 동기화만 스킵)

| Secret 이름 | 용도 (출처) | 설명 |
|---|---|---|
| `GOOGLE_CLIENT_ID` | OAuth 클라이언트 ID (4단계) | 이 앱을 구글에 식별시키는 **공개 식별자**. OAuth 클라이언트를 만들 때 발급되는 `xxxxx.apps.googleusercontent.com` 형식의 값. |
| `GOOGLE_CLIENT_SECRET` | OAuth 보안 비밀번호 (4단계) | 위 클라이언트 ID와 **짝을 이루는 비밀 키**. 토큰 교환 시 앱의 신원을 증명합니다. 외부에 노출 금지. |
| `GOOGLE_REFRESH_TOKEN` | 리프레시 토큰 (5단계) | 사용자 동의를 **1회** 받은 뒤 발급되는 장기 자격증명. 매 실행마다 이 토큰으로 단기 액세스 토큰을 자동 재발급받아 **캘린더에 일정을 쓸 권한**을 얻습니다. (동의 화면이 Testing 상태면 7일 후 만료 — 3단계 주의 참고) |
| `GOOGLE_CALENDAR_ID` | 대상 캘린더 (6단계) | 일정을 **넣을 캘린더의 식별자**. 본인 기본 캘린더는 `primary`, 별도 캘린더는 `xxxx@group.calendar.google.com` 형식. 기본값 `primary`. |
| `GOOGLE_ACCOUNTS_YAML` | (선택) 여러 계정 지정 | `config/google.yaml` 과 **같은 YAML 내용을 통째로** 넣는 시크릿. 여러 구글 계정의 캘린더에 동시에 sync 할 때 사용. 이 시크릿이 있으면 계정 이름이 겹치는 항목에 한해 위 단일 계정 값보다 우선. |

### 선택 — 사이트별 로그인 (넣은 사이트만 자동 등록)

계정이 있는 사이트만 아래처럼 **`SITE_<대문자키>_USER` / `SITE_<대문자키>_PASS`** 쌍으로 추가.
키는 [대상 사이트](#대상-사이트) 표의 소문자 키를 대문자로.

| 사이트 | USER Secret | PASS Secret |
|---|---|---|
| 올쇼TV | `SITE_ALLSHOWTV_USER` | `SITE_ALLSHOWTV_PASS` |
| 쉐어드IT | `SITE_SHAREDIT_USER` | `SITE_SHAREDIT_PASS` |
| DD튜브 | `SITE_DDTUBE_USER` | `SITE_DDTUBE_PASS` |
| e4ds | `SITE_E4DS_USER` | `SITE_E4DS_PASS` |
| 토크아이티 | `SITE_TALKIT_USER` | `SITE_TALKIT_PASS` |
| 두비즈 | `SITE_DUBIZ_USER` | `SITE_DUBIZ_PASS` |
| CLOIT:ON | `SITE_CLOIT_USER` | `SITE_CLOIT_PASS` |

> 사이트 계정 Secret 이 없으면 해당 사이트의 **등록만** 건너뜁니다(일정 수집은 계속).
> 실제 등록은 `config/sites.yaml` 의 `register.enabled: true` 까지 켜야 동작합니다([아래](#자동-등록register-활성화)).

### 로컬에서 계정 편하게 관리 — `config/accounts.yaml`

여러 사이트의 아이디/암호를 `SITE_*_USER/PASS` 로 하나씩 넣기 번거롭다면, **사이트별로
묶인 한 파일**로 관리할 수 있습니다. (로컬 실행 전용 — CI는 위 Secrets 사용)

```bash
cp config/accounts.example.yaml config/accounts.yaml   # 복사 후 채우기
```

```yaml
# config/accounts.yaml  (⚠️ .gitignore 로 제외되어 커밋되지 않음)
allshowtv:
  user: "your-id@example.com"
  pass: "your-password"
ddtube:
  user: "..."
  pass: "..."
# 계정 없는 사이트는 비워두면 됨
```

- **자격증명 우선순위**: 환경변수(`.env`·GitHub Secrets) → `config/accounts.yaml`.
  즉 CI에서는 Secrets가, 로컬에서는 이 파일이 쓰입니다.
- **역할 분리**: 사이트 **URL·셀렉터는 공개 설정** [`config/sites.yaml`](config/sites.yaml),
  **아이디·암호는 비공개** `config/accounts.yaml`. (URL은 이미 sites.yaml에서 한곳 관리)
- ⚠️ 이 저장소는 **공개**입니다. 비밀번호를 `data/` 나 커밋되는 파일에 넣지 마세요.
  `config/accounts.yaml` 과 `.env` 는 `.gitignore` 로 제외됩니다.

### (대안) gh CLI 로 한 번에 등록
```bash
# 브라우저 UI 대신 터미널에서. 값은 프롬프트로 입력됨.
gh secret set GOOGLE_CLIENT_ID     --repo leemgs/webinar
gh secret set GOOGLE_CLIENT_SECRET --repo leemgs/webinar
gh secret set GOOGLE_REFRESH_TOKEN --repo leemgs/webinar
gh secret set GOOGLE_CALENDAR_ID   --repo leemgs/webinar   # 예: primary
# 여러 구글 계정에 sync 하려면 google.yaml 내용을 통째로 하나의 시크릿에:
gh secret set GOOGLE_ACCOUNTS_YAML --repo leemgs/webinar < config/google.yaml
gh secret set SITE_DDTUBE_USER     --repo leemgs/webinar
gh secret set SITE_DDTUBE_PASS     --repo leemgs/webinar
```

### 등록 확인 & 첫 실행
- 등록된 시크릿 목록: 👉 <https://github.com/leemgs/webinar/settings/secrets/actions>
- 수동 실행(사전등록은 dry-run): 👉 <https://github.com/leemgs/webinar/actions/workflows/daily.yml>
  → **Run workflow**, 또는 CLI: `gh workflow run daily.yml`

## 수집이 막힌 웨비나 등록 (sharedit 등)

쉐어드IT(`www.sharedit.co.kr`, `webinar.sharedit.co.kr`)는 **GitHub Actions 러너(데이터센터 IP)에
Cloudflare 관리형 챌린지**(`cf-mitigated: challenge`, "Just a moment...")를 띄웁니다. 그래서 일일 동기화는
쉐어드IT의 **새 웨비나를 수집할 수 없고**, 이전에 저장된 일정만 남아 "가끔 누락"처럼 보입니다.
(CI 로그 기준 최소 8/27 이후 매 실행 0건) 다음 두 방법으로 보완합니다.

### 방법 1 — 수동 등록 (즉시, 권장)
Actions → **웨비나 수동 등록 (Add webinar)** → *Run workflow* (GitHub 모바일 앱에서도 가능)

| 입력 | 예 |
| --- | --- |
| 사이트 | `sharedit` |
| URL (선택) | `https://webinar.sharedit.co.kr/posts/36031` — 모르면 비워 두기 → 쉐어드IT 웨비나 목록으로 연결 |
| 제목 / 날짜 | `…` / `2026-10-27` |
| 시작·종료 (선택) | `14:00` / `15:00` — 비우면 **종일 일정** |

`config/manual_webinars.yaml`에 기록되고 데이터·ICS·구글 캘린더까지 약 1분 내 반영됩니다.
같은 사이트+URL(URL이 없으면 같은 날짜+제목)로 다시 실행하면 해당 항목이 **수정**됩니다(예: 나중에 시간 추가).
같은 웨비나가 실제로 수집되면(같은 URL, 또는 같은 날짜+비슷한 제목) 항상 수집 데이터가 우선하고,
YAML에서 지운 수동 항목은 다음 반영 때 데이터·캘린더에서도 빠집니다.
로컬에서는: `python -m webinar.manual add --source sharedit --url … --title … --date 2026-10-27 --time 14:00`
→ `python -m webinar.manual apply`.

### 방법 2 — self-hosted 러너 (모든 워크플로 기본값)
모든 워크플로(`daily.yml`, `add-webinar.yml`)는 **`runs-on: self-hosted`** 로 실행됩니다.
집/사무실 PC는 일반 방문자처럼 접속되므로 일일 동기화가 쉐어드IT까지 직접 수집합니다.
**러너가 등록되어 온라인 상태가 아니면 워크플로는 대기(Queued) 상태로 멈춥니다.**

러너 PC 준비 (Linux 권장, macOS 가능):
1. Settings → Actions → Runners → **New self-hosted runner** 안내대로 설치·등록 (기본 라벨 `self-hosted` 그대로)
   후 `./svc.sh install && ./svc.sh start` 로 서비스 등록 (PC가 켜져 있어야 cron이 돕니다)
2. **Python 3.10+** 와 `git` 설치. Linux는 최초 1회 root로 Chromium 의존 라이브러리와 Xvfb 설치:
   `sudo apt-get install -y xvfb && sudo python3 -m pip install playwright==1.48.0 && sudo python3 -m playwright install-deps chromium`
3. 나머지는 자동입니다 — [`setup-runner`](.github/actions/setup-runner/action.yml) 액션이
   `~/.cache/webinar-venv` 가상환경·패키지·Playwright Chromium을 만들고 이후 실행에서 재사용합니다.
   화면이 없는 Linux에서는 [`scripts/with_display.sh`](scripts/with_display.sh)가 Xvfb로 실행합니다
   (Xvfb가 없으면 headless로 대체).
4. **글꼴**: Chromium이 글꼴을 하나도 찾지 못하면 웹폰트를 쓰는 모든 페이지에서
   `FATAL ... remote_font_face_source.cc` 로 죽어(`Page crashed`) 거의 모든 사이트가 0건이 됩니다.
   Chromium은 자체 내장 fontconfig를 쓰므로 `fc-list`에 글꼴이 보여도 시스템 설정(`/etc/fonts`)을 못 읽으면
   이렇게 됩니다. `setup-runner`가 글꼴 폴더를 직접 지정한 독립 `fonts.conf`를 만들어 `FONTCONFIG_FILE`로
   지정하고, 글꼴이 없으면 sudo 없이 `fonts-nanum`·`fonts-dejavu-core`를 `~/.cache/webinar-fonts`에 풉니다
   (직접 설치: `sudo apt-get install -y fonts-nanum fonts-dejavu-core`).
   일일 동기화의 **Runner diagnostics** 단계가 메모리·글꼴·디스플레이와 Chromium 시험 접속 결과를 출력합니다.
   페이지가 죽으면 쿠키를 유지한 채 Chromium을 다시 띄워 재시도하고, 계속 죽으면 남은 페이지를 건너뜁니다
   (이전 데이터 유지, 수집 단계는 최대 45분).

#### (대안) systemd 서비스로 직접 등록 — 재부팅 후 자동 시작

러너 PC가 Linux라면 `./svc.sh install` 대신 systemd 유닛을 직접 작성해도 됩니다.
`run.sh`를 포그라운드로 돌리고 systemd가 프로세스 관리·자동 재시작·부팅 시 시작을 맡습니다.
`User`/`Group`/`WorkingDirectory`/`ExecStart` 경로를 **러너가 설치된 사용자·경로에 맞게 수정**하세요.

```ini
# /etc/systemd/system/github-actions-runner-webinar.service
[Unit]
Description=GitHub Actions Self-hosted Runner (webinar)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple

# ✅ runner가 설치된 사용자/경로에 맞게 수정
User=invain
Group=invain
WorkingDirectory=/var/www/invain/github-actions/webinar

# run.sh는 포그라운드로 실행되며 systemd가 프로세스를 관리합니다
ExecStart=/var/www/invain/github-actions/webinar/run.sh

# 비정상 종료 시 자동 재시작
Restart=always
RestartSec=10

# 로그는 journald로 쌓임 (journalctl로 확인)
KillSignal=SIGINT
TimeoutStopSec=30

# (옵션) 파일 디스크립터/프로세스 제한 완화
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now github-actions-runner-webinar.service   # 부팅 시 자동 시작 + 지금 시작
sudo systemctl status github-actions-runner-webinar.service         # 상태 확인
journalctl -u github-actions-runner-webinar.service -f              # 실시간 로그
```

> 러너가 온라인이어야 워크플로가 실행됩니다. 위 서비스가 `active (running)`이면
> GitHub의 **Settings → Actions → Runners** 목록에서도 러너가 **Idle/Active** 로 보입니다.
> `./svc.sh install` 방식과 systemd 유닛 방식 중 **하나만** 쓰세요(중복 실행 금지).

> ⚠️ 공개 저장소에서 self-hosted 러너를 쓸 때는 Settings → Actions → General 에서
> **외부 기여자의 fork PR 워크플로 실행에 승인 필요**를 켜 두세요(러너 PC 보호). 이 워크플로는 PR에서 실행되지 않습니다.
> 차단 우회 도구(캡차 풀이·프록시 회전 등)는 사용하지 않습니다 — 일반 방문자와 같은 브라우저 접속만 합니다.

## GitHub Pages

Settings → Pages → Source: **Deploy from a branch**, Branch: `main` / `/docs`.
게시 후 👉 <https://leemgs.github.io/webinar/> 에서 홈페이지 확인.

메뉴마다 고유 주소가 있어 바로 접속할 수 있습니다(루트 주소는 달력으로 이동):

| 메뉴 | 주소 |
|------|------|
| 대시보드 | <https://leemgs.github.io/webinar/dashboard/> |
| 달력 | <https://leemgs.github.io/webinar/calendar/> |
| 목록 | <https://leemgs.github.io/webinar/list/> |

페이지 HTML은 `scripts/build_pages.py`가 생성합니다. 머리글·메뉴·바닥글을 고치려면 이 스크립트를 수정한 뒤
`python scripts/build_pages.py`를 실행하세요(`tests/test_pages.py`가 생성 결과와 커밋된 파일을 비교합니다).

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
config/            사이트 설정(sites.yaml), 경품 오버라이드(prizes_override.yaml),
                   구글 계정 예시(google.example.yaml → 로컬 google.yaml)
src/webinar/
  models.py        Webinar / Prize 데이터 모델
  config.py        설정·시크릿 로드
  storage.py       data/webinars.json 읽기/쓰기/병합
  browser.py       Playwright 브라우저 헬퍼
  scrapers/        사이트별 스크래퍼(base + 8개)
  prizes.py        경품 추출/병합
  registrar.py     로그인 + 사전등록
  calendar_sync.py 구글 캘린더 동기화
  ics_export.py    ICS 피드 생성
  pipeline.py      전체 파이프라인(entry point)
scripts/           get_google_token.py
data/webinars.json 수집 결과(진실의 원천)
docs/              GitHub Pages 홈페이지
tests/             오프라인 테스트 (파서 + 캘린더 sync, 브라우저·네트워크 불필요)
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

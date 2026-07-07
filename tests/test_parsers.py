"""Offline parser tests — no browser required."""
from __future__ import annotations

from datetime import date

from webinar.scrapers.base import parse_date, parse_time
from webinar.scrapers import get_scraper
from webinar import prizes, config


REF = date(2026, 7, 6)


# --- date parsing ----------------------------------------------------------
def test_parse_date_iso():
    assert parse_date("2026-07-08") == date(2026, 7, 8)
    assert parse_date("2026.07.08") == date(2026, 7, 8)
    assert parse_date("2026년 7월 8일") == date(2026, 7, 8)


def test_parse_date_month_day():
    assert parse_date("7월 8일", ref=REF) == date(2026, 7, 8)
    assert parse_date("7/8", ref=REF) == date(2026, 7, 8)


def test_parse_date_dday():
    assert parse_date("D-2", ref=REF) == date(2026, 7, 8)


def test_parse_date_rollover():
    # a January date viewed in December should roll to next year
    assert parse_date("1월 5일", ref=date(2026, 12, 20)) == date(2027, 1, 5)


def test_parse_date_none():
    assert parse_date("no date here") is None


# --- time parsing ----------------------------------------------------------
def test_parse_time_variants():
    assert parse_time("14:00").hour == 14
    assert parse_time("오후 2시").hour == 14
    assert parse_time("오후 2시 30분").minute == 30
    assert parse_time("3:00 PM").hour == 15
    assert parse_time("오전 9시").hour == 9
    # Korean AM/PM with a colon (talkit's <time> format)
    t = parse_time("7월 9일(목) 오후 2:00~3:00")
    assert (t.hour, t.minute) == (14, 0)


# --- ddtube detail-link scraper -------------------------------------------
# The homepage links to /dNNNN/ detail pages (possibly multiple links per page,
# with/without trailing slash). parse() collects unique detail URLs; titles and
# dates are filled in later by _enrich() from each detail page.
DDTUBE_HTML = """
<html><body>
  <a href="/d2107" data-type="button">사전등록 바로가기 &gt;</a>
  <a href="/d2107/">[Synology] NVMe 스토리지 혁신</a>
  <a href="https://www.ddtube.co.kr/d2108">사전 등록</a>
  <a href="/mypage">마이페이지</a>
</body></html>
"""


def test_ddtube_collects_unique_detail_urls():
    scraper = get_scraper("ddtube", {"base_url": "https://www.ddtube.co.kr"})
    items = scraper.parse(DDTUBE_HTML)
    urls = {w.register_url for w in items}
    # d2107 appears twice (with/without slash) -> deduped to one canonical url
    assert urls == {
        "https://www.ddtube.co.kr/d2107/",
        "https://www.ddtube.co.kr/d2108/",
    }


# --- generic card scraper --------------------------------------------------
CARD_HTML = """
<html><body>
  <ul class="seminar_list">
    <li>
      <a href="/seminar/1"><strong class="tit">Enterprise AI Platform 전략</strong></a>
      <img src="/t.png"><span>2026.07.08 오후 3시</span>
      <span class="host">M Cloud Bridge</span>
    </li>
  </ul>
</body></html>
"""


def test_generic_card_scraper():
    scraper = get_scraper("allshowtv", {"base_url": "https://www.allshowtv.com"})
    items = scraper.parse(CARD_HTML)
    assert len(items) == 1
    w = items[0]
    assert w.title == "Enterprise AI Platform 전략"
    assert w.host == "M Cloud Bridge"
    assert w.start_kst.startswith("2026-07-08T15:00")
    assert w.url == "https://www.allshowtv.com/seminar/1"


# --- talkit anchor-card scraper -------------------------------------------
TALKIT_HTML = """
<html><body>
  <a href="/main/events/3697">
    <div><h3>미토스가 촉발한 AI 기반 Identity 공격 위험 [네오아이앤이]</h3>
    <time>7월 9일(목) 오후 2:00~3:00</time></div>
  </a>
  <a href="/main/webinars">웨비나</a>
</body></html>
"""


def test_talkit_scraper():
    scraper = get_scraper("talkit", {"base_url": "https://talkit.tv"})
    items = scraper.parse(TALKIT_HTML)
    assert len(items) == 1  # nav "웨비나" link filtered out
    w = items[0]
    assert w.url == "https://talkit.tv/main/events/3697"
    assert "미토스" in w.title
    assert w.start_kst.endswith("T14:00:00+09:00")


# --- allshowtv title tidying ----------------------------------------------
ALLSHOW_HTML = """
<html><body>
  <ul class="seminar_list">
    <li>
      <a href="/detail.html?idx=1735"><img src="/t.jpg">
      [엠클라우드브리지] Copilot 이후 기업은 왜 AI Platform 체계로 가는가?
      2026년 07월 08일(수) 15:00 ~ 16:00 D-2</a>
    </li>
  </ul>
</body></html>
"""


def test_allshowtv_title_and_host():
    scraper = get_scraper("allshowtv", {"base_url": "https://www.allshowtv.com"})
    items = scraper.parse(ALLSHOW_HTML)
    assert len(items) == 1
    w = items[0]
    assert w.host == "엠클라우드브리지"
    assert w.title == "Copilot 이후 기업은 왜 AI Platform 체계로 가는가?"
    assert w.start_kst.startswith("2026-07-08T15:00")


# --- sharedit listing scraper ---------------------------------------------
SHAREDIT_HTML = """
<html><body>
  <nav class="tab"><a href="/seminars?category_code=webinars">웨비나</a></nav>
  <ul class="list">
    <li>
      <figure style="background-image: url('https://cdn.example/2312.png');"></figure>
      <header><span class="sponsor">Databricks</span><span class="category">웨비나</span>
        <strong><a title="Databricks Data + AI 러닝 페스티벌 2026" href="/seminars/2312">Databricks Data + AI 러닝 페스티벌 2026</a></strong>
      </header>
      <dl class="info"><dt>일시</dt><dd>2026-07-22(수) 09:00 ~ 17:00</dd><dt>댓글</dt><dd>1개</dd></dl>
    </li>
    <li>
      <header><span class="sponsor">Okta</span><span class="category">웨비나</span>
        <strong><a title="[0715] Okta for AI Agent 론칭 웨비나" href="/seminars/2315">[0715] Okta for AI Agent 론칭 웨비나</a></strong>
      </header>
      <dl class="info"><dt>일시</dt><dd>2026-07-15(수) 14:00 ~ 15:00</dd></dl>
    </li>
    <div class="tag"><a title="추천 세미나 - 날짜없음" href="/seminars/9999">10일 (금) (세미나)</a></div>
  </ul>
</body></html>
"""


def test_sharedit_scraper():
    scraper = get_scraper("sharedit", {"base_url": "https://www.sharedit.co.kr"})
    items = scraper.parse(SHAREDIT_HTML)
    # 2 real <li> webinars captured (recommendation tag w/o 일시 dropped)
    assert len(items) == 2
    by_url = {w.url: w for w in items}
    # date comes from <dl class="info"> 일시 (no [MMDD] in this title)
    db = by_url["https://www.sharedit.co.kr/seminars/2312"]
    assert db.start_kst.startswith("2026-07-22T09:00")
    assert db.host == "Databricks"
    assert db.thumbnail == "https://cdn.example/2312.png"
    # [MMDD] title is cleaned and still dated from 일시
    okta = by_url["https://www.sharedit.co.kr/seminars/2315"]
    assert okta.title == "Okta for AI Agent 론칭 웨비나"
    assert okta.start_kst.startswith("2026-07-15T14:00")


# --- dubiz anchor-card scraper --------------------------------------------
DUBIZ_HTML = """
<html><body>
  <a href="/Event/503">
    <h3>생명 과학 산업의 미래: 자동화에서 자율 운영으로</h3>
    <span>7월 16일(목) 10:30</span> <span>D-10</span>
  </a>
  <a href="/Event/502"><h3>제조 디지털 트랜스포메이션 웨비나</h3><span>7월 21일(화) 10:00</span></a>
  <a href="/Replay/">리플레이</a>
</body></html>
"""


def test_dubiz_scraper():
    scraper = get_scraper("dubiz", {"base_url": "https://dubiz.co.kr"})
    items = scraper.parse(DUBIZ_HTML)
    assert len(items) == 2  # /Replay/ nav link excluded (no /Event/, no date)
    w = next(x for x in items if x.url.endswith("/Event/503"))
    assert "생명 과학" in w.title
    assert w.start_kst.startswith("2026-07-16T10:30")


# --- prize extraction ------------------------------------------------------
def test_extract_prizes():
    text = "생방송 시청 후 설문 참여자 추첨하여 스타벅스 기프티콘을 드립니다."
    found = prizes.extract_prizes(text)
    types = {p.type for p in found}
    assert "survey" in types


def test_extract_prizes_empty():
    assert prizes.extract_prizes("그냥 일반 웨비나 소개 문구") == []


# --- eventus (event-us.kr) scraper -----------------------------------------
def test_eventus_resolve_date():
    from webinar.scrapers.eventus import Scraper as Eventus

    ref = date(2026, 7, 7)
    assert Eventus._resolve_date("07월09일(목) 오후 2시", ref) == date(2026, 7, 9)
    assert Eventus._resolve_date("03월23일", ref) is None  # far past -> dropped
    # year-end wrap (Dec viewing Jan) within 120 days -> next year
    assert Eventus._resolve_date("01월05일", date(2026, 12, 20)) == date(2027, 1, 5)
    assert Eventus._resolve_date("날짜 없음", ref) is None


def test_eventus_title_prefers_alt():
    from bs4 import BeautifulSoup
    from webinar.scrapers.eventus import Scraper as Eventus

    node = BeautifulSoup(
        '<div><img alt="기본" src="x/event-default-img.jpg">'
        '<img alt="Finance AX Roadmap" src="https://cdn/a.png"></div>',
        "html.parser",
    ).div
    assert Eventus._title(node) == "Finance AX Roadmap"  # skips default-img alt


def test_select_prize_images_by_selector():
    # allshowtv: 경품 안내 section is <div class="gift"><img ...></div>
    sc = get_scraper("allshowtv", {"base_url": "https://www.allshowtv.com"})
    soup = sc.soup(
        '<div class="gift"><h4>경품 안내</h4>'
        '<img src="/img/prize.jpg"></div><img src="/img/other.png">'
    )
    assert sc.select_prize_images(soup, ".gift img") == [
        "https://www.allshowtv.com/img/prize.jpg"
    ]


def test_select_prize_images_by_filename():
    sc = get_scraper("ddtube", {"base_url": "https://www.ddtube.co.kr"})
    soup = sc.soup(
        '<img src="http://www.ddtube.co.kr/a/event.jpg">'  # http -> https upgraded
        '<img src="/logo.png">'
    )
    assert sc.select_prize_images(soup) == ["https://www.ddtube.co.kr/a/event.jpg"]


def test_unwrap_next_image():
    from webinar.scrapers.base import BaseScraper

    src = "/main/_next/image?url=https%3A%2F%2Ftalkit.tv%2Fuserfiles%2Fimages%2Ffile1.jpg&w=1920&q=75"
    assert BaseScraper._unwrap_next_image(src) == "https://talkit.tv/userfiles/images/file1.jpg"
    assert BaseScraper._unwrap_next_image("https://x/a.jpg") == "https://x/a.jpg"


def test_talkit_giveaway_prize_selector():
    # the giveaway tab panel's image, with a Next.js proxy URL, is unwrapped
    sc = get_scraper("talkit", {"base_url": "https://talkit.tv"})
    soup = sc.soup(
        '<div id="radix-x-content-giveaway">'
        '<img src="/main/_next/image?url=https%3A%2F%2Ftalkit.tv%2Fuserfiles%2Fimages%2Fgift.jpg&w=1920"></div>'
    )
    assert sc.select_prize_images(soup, "[id$='-content-giveaway'] img") == [
        "https://talkit.tv/userfiles/images/gift.jpg"
    ]


def test_is_prize_image():
    assert prizes.is_prize_image("https://x/2026/06/event.jpg")
    assert prizes.is_prize_image("https://x/synology_participate.jpg")
    assert prizes.is_prize_image("https://x/uploads/참여방법_Orange5.jpg")
    assert not prizes.is_prize_image("https://x/2026/06/logo.jpg")
    assert not prizes.is_prize_image("https://x/2560-1440-1024x576.jpg")
    assert not prizes.is_prize_image("")


# --- credentials precedence -----------------------------------------------
def test_site_credentials_from_env(monkeypatch):
    monkeypatch.setenv("SITE_FOO_USER", "u1")
    monkeypatch.setenv("SITE_FOO_PASS", "p1")
    assert config.site_credentials("foo") == ("u1", "p1")


def test_site_credentials_absent(monkeypatch):
    monkeypatch.delenv("SITE_BAR_USER", raising=False)
    monkeypatch.delenv("SITE_BAR_PASS", raising=False)
    # no config/accounts.yaml in the test env -> both None
    assert config.site_credentials("bar") == (None, None)

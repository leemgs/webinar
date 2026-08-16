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


def test_allshowtv_collects_mixed_card_layouts_and_lazy_thumbnail():
    """A featured-card match must not hide webinars in another card layout."""
    html = """
    <ul class="seminar_list"><li>
      <a href="/detail.html?idx=1"><strong>첫 번째 웨비나</strong></a>
      <span>2026.08.10 14:00</span>
    </li></ul>
    <article class="seminar">
      <a href="/detail.html?idx=2"><h3>두 번째 웨비나</h3></a>
      <img data-original="/lazy.jpg"><time>2026.08.11 15:00</time>
    </article>
    """
    scraper = get_scraper("allshowtv", {"base_url": "https://www.allshowtv.com"})
    items = scraper.parse(html)
    assert {w.title for w in items} == {"첫 번째 웨비나", "두 번째 웨비나"}
    second = next(w for w in items if w.title == "두 번째 웨비나")
    assert second.thumbnail == "https://www.allshowtv.com/lazy.jpg"


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
    # explicit "15:00 ~ 16:00" range -> honour the published end time
    assert w.end_kst.startswith("2026-07-08T16:00")


def test_allshowtv_multi_hour_range_end_time():
    """The published end time wins over the default 1h span (e.g. 14:00~16:30)."""
    html = """
    <ul class="newlist"><li>
      <a href="/detail.html?idx=1748"><img src="/t.jpg">
      [센드버드] 끝까지 책임지는 AI 에이전트: 도입을 넘어 운영으로
      2026년 08월 27일(목) 14:00 ~ 16:30 D-13</a>
    </li></ul>
    """
    scraper = get_scraper("allshowtv", {"base_url": "https://www.allshowtv.com"})
    items = scraper.parse(html)
    assert len(items) == 1
    w = items[0]
    assert w.host == "센드버드"
    assert w.start_kst.startswith("2026-08-27T14:00")
    assert w.end_kst.startswith("2026-08-27T16:30")


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


def test_sharedit_external_campaign_card():
    """Campaigns hosted on the webinar subdomain must not be omitted."""
    html = """
    <section class="webinar-card">
      <img src="/uploads/ai365.jpg"
           alt="OpenAI 기반 Microsoft Enterprise AI Platform Ai 365 에이전트 소개">
      <h3>OpenAI 기반 Microsoft Enterprise AI Platform Ai 365 에이전트 소개</h3>
      <p>2026.08.26(수) 14:00 - 15:00</p>
      <a href="https://webinar.sharedit.co.kr/ai365-agent/">자세히 보기</a>
    </section>
    """
    scraper = get_scraper("sharedit", {"base_url": "https://www.sharedit.co.kr"})
    items = scraper.parse(html)
    assert len(items) == 1
    webinar = items[0]
    assert webinar.title.startswith("OpenAI 기반 Microsoft")
    assert webinar.start_kst == "2026-08-26T14:00:00+09:00"
    assert webinar.url == "https://webinar.sharedit.co.kr/ai365-agent"
    assert webinar.thumbnail == "https://www.sharedit.co.kr/uploads/ai365.jpg"


def test_sharedit_rejects_unrelated_external_link():
    scraper = get_scraper("sharedit", {"base_url": "https://www.sharedit.co.kr"})
    html = '<section><p>2026.08.26 14:00</p><a href="https://example.com">광고</a></section>'
    assert scraper.parse(html) == []


def test_sharedit_posts_board_captures_august_26_webinar():
    """The current post_type_id=4 board uses /posts/ links, not /seminars/."""
    html = """
    <div class="post-card">
      <a href="/posts/2401">
        <img data-src="https://cdn.example/ai365.jpg"
             alt="[0826] OpenAI 기반 Microsoft Enterprise AI Platform Ai 365 에이전트 소개와 기업 교육·지식관리 Agent 활용 전략">
        <strong>[0826] OpenAI 기반 Microsoft Enterprise AI Platform Ai 365 에이전트 소개와 기업 교육·지식관리 Agent 활용 전략</strong>
      </a>
      <span>2026.08.26</span><span>14:00 - 15:00</span>
    </div>
    """
    scraper = get_scraper("sharedit", {"base_url": "https://www.sharedit.co.kr"})
    items = scraper.parse(html)
    assert len(items) == 1
    webinar = items[0]
    assert webinar.url == "https://www.sharedit.co.kr/posts/2401"
    assert webinar.title.startswith("OpenAI 기반 Microsoft")
    assert webinar.start_kst == "2026-08-26T14:00:00+09:00"
    assert webinar.thumbnail == "https://cdn.example/ai365.jpg"


SHAREDIT_35963_DETAIL = """
<html><head>
  <meta property="og:title" content="[0826] OpenAI 기반 Microsoft Enterprise AI Platform Ai 365 에이전트 소개와 기업 교육·지식관리 Agent 활용 전략">
  <meta property="og:image" content="https://cdn.example/35963.jpg">
</head><body><article class="post-content">
  <h1>OpenAI 기반 Microsoft Enterprise AI Platform Ai 365</h1>
  <p>2026.08.26(수) 14:00 - 15:00</p>
</article></body></html>
"""


def test_sharedit_parses_supplied_35963_detail_page():
    scraper = get_scraper("sharedit", {"base_url": "https://www.sharedit.co.kr"})
    webinar = scraper.parse_detail(
        SHAREDIT_35963_DETAIL, "https://www.sharedit.co.kr/posts/35963"
    )
    assert webinar.url == "https://www.sharedit.co.kr/posts/35963"
    assert webinar.start_kst == "2026-08-26T14:00:00+09:00"
    assert webinar.title.startswith("OpenAI 기반 Microsoft")
    assert webinar.thumbnail == "https://cdn.example/35963.jpg"


def test_sharedit_retries_challenged_listing_and_enriches_known_detail():
    listing = """
    <div><a href="/posts/35963"><strong>[0826] Ai 365 웨비나</strong></a>
    <span>2026.08.26</span></div>
    """

    class FakeBrowser:
        listing_calls = 0

        def get_html(self, url, **kwargs):
            if "post_type_id=4" in url:
                self.listing_calls += 1
                if self.listing_calls == 1:
                    return "<html><title>Just a moment...</title></html>"
                return listing
            return SHAREDIT_35963_DETAIL

    scraper = get_scraper("sharedit", {
        "base_url": "https://www.sharedit.co.kr",
        "listing_url": "https://www.sharedit.co.kr/posts?post_type_id=4",
        "wait_selector": "a[href^='/posts/']",
        "detail_urls": ["https://www.sharedit.co.kr/posts/35963"],
    })
    browser = FakeBrowser()
    items = scraper.fetch(browser)
    assert browser.listing_calls == 2
    assert len(items) == 1
    assert items[0].start_kst == "2026-08-26T14:00:00+09:00"


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


# --- chontv detail-link scraper -------------------------------------------
# Detail links are /{channel-slug}/{id} (e.g. /paloaltonetworks/548). Nav links
# without a numeric id (/about, /channels, /login) are excluded; require_date
# drops any matched link that has no parseable date.
CHONTV_HTML = """
<html><body>
  <nav><a href="/about">웨비나 허브</a><a href="/channels">채널</a></nav>
  <ul class="webinar-list">
    <li><a href="/paloaltonetworks/548">
      <h3>글로벌 사례로 보는 유통 기업 보안 혁신 웨비나</h3>
      <span>2026년 07월 22일(수) 14:00~15:00</span>
    </a></li>
    <li><a href="https://chontv.com/event/858">
      <h3>슈퍼컴퓨터가 클라우드를 만나면 벌어지는 일들</h3>
      <time>2026년 08월 05일(수) 10:00~11:00</time>
    </a></li>
  </ul>
  <a href="/login">로그인</a>
</body></html>
"""


def test_chontv_scraper():
    scraper = get_scraper("chontv", {"base_url": "https://chontv.com"})
    items = scraper.parse(CHONTV_HTML)
    assert len(items) == 2  # nav links (/about, /channels, /login) excluded
    by_url = {w.url: w for w in items}
    w = by_url["https://chontv.com/paloaltonetworks/548"]
    assert "유통 기업 보안" in w.title
    assert w.start_kst.startswith("2026-07-22T14:00")
    assert "https://chontv.com/event/858" in by_url


# The live site renders JS cards keyed by data-event-no (no href); the title is
# in .event-list-title and the schedule in .event-day. "수요레터" newsletters
# are skipped and the same event repeated across sections is de-duplicated.
CHONTV_EVENT_CARDS_HTML = """
<html><body>
  <div class="wait-events"><div class="row">
    <div class="event-row-col">
      <div class="thumbnail event-list-thumbnail">
        <a class="go-event-btn" data-event-no="1266">
          <div class="event-list-thumb-image" style="background:linear-gradient(rgba(0,0,0,.1),rgba(0,0,0,.1)),url(https://chontv.com/assets/data/event/thumb__x.jpg?u=1);"></div>
        </a>
        <div class="caption"><div class="caption-info">
          <div class="event-list-title"><a class="go-event-btn" data-event-no="1266">탈(脫) 오라클, 맞춤형 마이그레이션 전략</a></div>
          <div class="event-day"><i class="fa fa-clock"></i> 2026년 08월 25일(화) 14:00~15:00</div>
        </div></div>
      </div>
    </div>
    <div class="event-row-col">
      <div class="thumbnail">
        <a class="go-event-btn" data-event-no="1243"><div class="event-list-thumb-image"></div></a>
        <div class="caption"><div class="caption-info">
          <div class="event-list-title"><a class="go-event-btn" data-event-no="1243">Cyber Resilience Insight 2026</a></div>
          <div class="event-day display-none">2026년 06월 23일(화) 14:00~16:30</div>
        </div></div>
      </div>
    </div>
  </div></div>
  <div class="sector-events-18"><div class="row">
    <div class="event-row-col">
      <div class="thumbnail">
        <a class="go-event-btn" data-event-no="1272"><div class="event-list-thumb-image"></div></a>
        <div class="caption"><div class="caption-info">
          <div class="event-list-title"><a class="go-event-btn" data-event-no="1272">행복은 강도가 아니라 빈도입니다 [수요레터 241회]</a></div>
          <div class="event-day display-none">2026년 08월 12일(수)</div>
        </div></div>
      </div>
    </div>
  </div></div>
  <div class="done-events"><div class="row">
    <div class="event-row-col">
      <div class="thumbnail">
        <a class="go-event-btn" data-event-no="1266"><div class="event-list-thumb-image"></div></a>
        <div class="caption"><div class="caption-info">
          <div class="event-list-title"><a class="go-event-btn" data-event-no="1266">탈(脫) 오라클, 맞춤형 마이그레이션 전략</a></div>
          <div class="event-day display-none">2026년 08월 25일(화) 14:00~15:00</div>
        </div></div>
      </div>
    </div>
  </div></div>
</body></html>
"""


def test_chontv_event_no_cards():
    scraper = get_scraper("chontv", {"base_url": "https://chontv.com"})
    items = scraper.parse(CHONTV_EVENT_CARDS_HTML)
    by_url = {w.url: w for w in items}
    # newsletter (1272) skipped; duplicate 1266 collapsed -> 2 unique webinars
    assert set(by_url) == {
        "https://chontv.com/event/1266",
        "https://chontv.com/event/1243",
    }
    w = by_url["https://chontv.com/event/1266"]
    assert "오라클" in w.title
    assert w.start_kst.startswith("2026-08-25T14:00")
    assert w.thumbnail == "https://chontv.com/assets/data/event/thumb__x.jpg?u=1"
    # explicit 14:00~16:30 range honoured over the default 1h span
    assert by_url["https://chontv.com/event/1243"].end_kst.startswith("2026-06-23T16:30")


# --- prize extraction ------------------------------------------------------
def test_extract_prizes():
    text = "생방송 시청 후 설문 참여자 추첨하여 스타벅스 기프티콘을 드립니다."
    found = prizes.extract_prizes(text)
    types = {p.type for p in found}
    assert "survey" in types


def test_extract_prizes_empty():
    assert prizes.extract_prizes("그냥 일반 웨비나 소개 문구") == []


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


def test_sharedit_slice_selector_excludes_footer():
    # sharedit embeds the webinar (경품 포함) as CDN slices; footer is excluded
    sc = get_scraper("sharedit", {"base_url": "https://www.sharedit.co.kr"})
    soup = sc.soup(
        '<img src="https://sharedit.speedgabia.com/Webinar/2026/okta/1.png">'
        '<img src="https://sharedit.speedgabia.com/Webinar/2026/okta/2.png">'
        '<img src="https://sharedit.speedgabia.com/Webinar/2026/sharedit_footer.png">'
        '<img src="https://other/logo.png">'
    )
    got = sc.select_prize_images(
        soup, "img[src*='speedgabia.com/Webinar']:not([src*='footer'])"
    )
    assert got == [
        "https://sharedit.speedgabia.com/Webinar/2026/okta/1.png",
        "https://sharedit.speedgabia.com/Webinar/2026/okta/2.png",
    ]


def test_prize_images_near_heading():
    # dubiz: <h2>경품 안내</h2><img ...> then a later section stops collection
    sc = get_scraper("dubiz", {"base_url": "https://dubiz.co.kr"})
    soup = sc.soup(
        "<h1>발표자</h1><img src='https://x/speaker.png'>"
        "<h2>경품 안내</h2>"
        "<img src='https://files.dubiz.co.kr/userfiles/images/file1.png'>"
        "<h2>문의하기</h2><img src='https://x/after.png'>"
    )
    assert sc.prize_images_near_heading(soup, "경품") == [
        "https://files.dubiz.co.kr/userfiles/images/file1.png"
    ]


def test_unwrap_next_image():
    from webinar.scrapers.base import BaseScraper

    src = "/main/_next/image?url=https%3A%2F%2Ftalkit.tv%2Fuserfiles%2Fimages%2Ffile1.jpg&w=1920&q=75"
    assert BaseScraper._unwrap_next_image(src) == "https://talkit.tv/userfiles/images/file1.jpg"
    assert BaseScraper._unwrap_next_image("https://x/a.jpg") == "https://x/a.jpg"


def test_talkit_giveaway_prize_selector_new_layout():
    # new /main/events/NNN: Radix giveaway panel; Next.js proxy URL is unwrapped
    sc = get_scraper("talkit", {"base_url": "https://talkit.tv"})
    soup = sc.soup(
        '<div id="radix-x-content-giveaway">'
        '<img src="/main/_next/image?url=https%3A%2F%2Ftalkit.tv%2Fuserfiles%2Fimages%2Fgift.jpg&w=1920"></div>'
    )
    assert sc.select_prize_images(soup, sc.PRIZE_SELECTOR) == [
        "https://talkit.tv/userfiles/images/gift.jpg"
    ]


def test_talkit_giveaway_prize_selector_legacy_layout():
    # legacy /Event/NNN: Bootstrap #goodsTab pane (dedupes responsive duplicate)
    sc = get_scraper("talkit", {"base_url": "https://talkit.tv"})
    soup = sc.soup(
        '<div id="goodsTab"><img src="/userfiles/images/file1.jpg">'
        '<img src="/userfiles/images/file1.jpg"></div>'
        '<div id="joinTab"><img src="/userfiles/images/steps.jpg"></div>'
    )
    assert sc.select_prize_images(soup, sc.PRIZE_SELECTOR) == [
        "https://talkit.tv/userfiles/images/file1.jpg"
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

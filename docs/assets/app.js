"use strict";

// --- metadata ---------------------------------------------------------------
const SOURCES = {
  allshowtv: { name: "올쇼TV", color: "var(--c-allshowtv)", url: "https://www.allshowtv.com" },
  sharedit: { name: "쉐어드IT", color: "var(--c-sharedit)", url: "https://www.sharedit.co.kr/posts?post_type_id=4" },
  ddtube: { name: "DD튜브", color: "var(--c-ddtube)", url: "https://www.ddtube.co.kr" },
  e4ds: { name: "e4ds", color: "var(--c-e4ds)", url: "https://www.e4ds.com/webinar.asp" },
  talkit: { name: "토크아이티", color: "var(--c-talkit)", url: "https://talkit.tv/main/webinars/upcoming" },
  dubiz: { name: "두비즈", color: "var(--c-dubiz)", url: "https://dubiz.co.kr/onoffmix/" },
  cloit: { name: "CLOIT:ON", color: "var(--c-cloit)", url: "https://webinar.cloit.com" },
  chontv: { name: "채널온TV", color: "var(--c-chontv)", url: "https://chontv.com" },
};
const SRC_HEX = {
  allshowtv: "#e8590c", sharedit: "#2f9e44", ddtube: "#1971c2", e4ds: "#9c36b5",
  talkit: "#e8478b", dubiz: "#0c8599", cloit: "#f08c00", chontv: "#6741d9",
};
const PRIZES = {
  survey: { name: "설문", color: "var(--p-survey)", hex: "#1971c2" },
  question: { name: "질문", color: "var(--p-question)", hex: "#2f9e44" },
  consult: { name: "상담", color: "var(--p-consult)", hex: "#9c36b5" },
  attendance: { name: "참석/시청", color: "var(--p-attendance)", hex: "#e8590c" },
};

// 기술 종목(카테고리): 태그가 비어 있어 제목·주최 텍스트를 키워드로 분류한다.
// 순서 = 우선순위(먼저 매칭되는 종목으로 1건 배정 → 합계 = 전체 건수).
const CATEGORIES = [
  { key: "security", name: "보안", color: "var(--cat-2)",
    re: /보안|security|제로\s?트러스트|zero\s?trust|아이덴티티|identity|인증|방화벽|침해|위협|threat|취약점|vulnerab|랜섬|ransom|\bSOC\b|crowdstrike|크라우드스트라이크|배드\s?봇|bad\s?bot|OT\s?보안|사이버|cyber|복원력|resilience|디도스|ddos|악성|malware|해킹|미토스|beyondtrust|cyberark|약관|금소법/i },
  { key: "hardware", name: "반도체·하드웨어", color: "var(--cat-6)",
    re: /반도체|semicon|회로|circuit|전력|power|컨버터|converter|\bFPGA\b|임베디드|embedded|\bPCB\b|\bMCU\b|센서|sensor|\bLED\b|DC-?DC|LTspice|저잡음|신호|boot\s?sequence|인클로저|enclosure|스토리지|storage|\bHBM\b|드라이브|하드\s?드라이브|웨이퍼|\bSiC\b|MOSFET|커패시터|capacitor|계측|측정|아두이노|arduino|라즈베리|보드/i },
  { key: "factory", name: "제조·자동화·로봇", color: "var(--cat-5)",
    re: /제조|manufactur|자동화|automat|로봇|robot|팩토리|factory|\bAMR\b|모션|motion|머신비전|machine\s?vision|품질검사|산업|industr|자율제조|스마트\s?팩토리|physical\s?ai|\bMiR\b|서보|servo|공장|물류|dematic|autostore/i },
  { key: "cloud", name: "클라우드·인프라", color: "var(--cat-4)",
    re: /클라우드|cloud|\bSaaS\b|쿠버네티스|kubernetes|데이터\s?센터|datacenter|인프라|infra|마이그레이션|migrat|devops|gitlab|컨테이너|container|가상화|virtual|온프레|oracle|오라클|주권/i },
  { key: "data", name: "데이터·분석", color: "var(--cat-3)",
    re: /데이터|\bdata\b|데이터베이스|database|\bDB\b|postgres|\bSQL\b|분석|analytic|옵저버|observ|최적화|optimiz|마이닝|파이프라인|pipeline|거버넌스|governance|\bDLP\b|토큰|의사결정/i },
  { key: "network", name: "네트워크·통신", color: "var(--cat-7)",
    re: /\b5G\b|네트워크|network|통신|특화망|\bAPI\b|트래픽|traffic|\bCPO\b|광학|optic|인터커넥트|interconnect|이더넷|ethernet|무선|wireless|기지국|대역폭|번역|deepl/i },
  { key: "ai", name: "AI·에이전트", color: "var(--cat-1)",
    re: /\bAI\b|인공지능|\bLLM\b|에이전트|agent|머신러닝|machine\s?learning|딥러닝|deep\s?learning|\bGPT\b|파운데이션|foundation|온디바이스|on-?device|gemini|copilot|생성형|generative|추론|inference|엣지|edge/i },
  { key: "etc", name: "기타", color: "var(--cat-8)", re: null },
];

function classify(w) {
  const text = `${w.title || ""} ${w.host || ""} ${(w.tags || []).join(" ")}`;
  for (const c of CATEGORIES) {
    if (c.re && c.re.test(text)) return c;
  }
  return CATEGORIES[CATEGORIES.length - 1]; // 기타
}

// --- state ------------------------------------------------------------------
const state = {
  webinars: [],
  view: "calendar",
  cursor: new Date(),
  activeSources: new Set(Object.keys(SOURCES)),
  activePrizes: new Set(), // empty = no prize filter
};

// --- helpers ----------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const pad = (n) => String(n).padStart(2, "0");
const dayKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

function parseDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return isNaN(d) ? null : d;
}

function fmtTime(iso) {
  const d = parseDate(iso);
  if (!d) return "시간 미정";
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fmtDateTime(iso) {
  const d = parseDate(iso);
  if (!d) return "일정 미정";
  const wd = ["일", "월", "화", "수", "목", "금", "토"][d.getDay()];
  return `${d.getMonth() + 1}월 ${d.getDate()}일 (${wd}) ${fmtTime(iso)}`;
}

function passesFilter(w) {
  if (!state.activeSources.has(w.source)) return false;
  if (state.activePrizes.size > 0) {
    const types = new Set((w.prizes || []).map((p) => p.type));
    let hit = false;
    for (const t of state.activePrizes) if (types.has(t)) hit = true;
    if (!hit) return false;
  }
  return true;
}

function visibleWebinars() {
  return state.webinars.filter(passesFilter);
}

// --- filters UI -------------------------------------------------------------
function renderFilters() {
  const srcBox = $("#source-filters");
  srcBox.innerHTML = "";
  for (const [key, meta] of Object.entries(SOURCES)) {
    const chip = document.createElement("button");
    const on = state.activeSources.has(key);
    chip.className = "chip" + (on ? " active" : " off");
    chip.style.background = on ? SRC_HEX[key] : "";
    chip.innerHTML = `<span class="dot"></span>${meta.name}`;
    chip.onclick = () => {
      if (state.activeSources.has(key)) state.activeSources.delete(key);
      else state.activeSources.add(key);
      render();
    };
    srcBox.appendChild(chip);
  }

  const prizeBox = $("#prize-filters");
  prizeBox.innerHTML = "";
  const label = document.createElement("span");
  label.className = "chip";
  label.style.cursor = "default";
  label.style.borderStyle = "dashed";
  label.textContent = "🎁 경품";
  prizeBox.appendChild(label);
  for (const [key, meta] of Object.entries(PRIZES)) {
    const chip = document.createElement("button");
    const on = state.activePrizes.has(key);
    chip.className = "chip" + (on ? " active" : "");
    chip.style.background = on ? meta.hex : "";
    chip.textContent = meta.name;
    chip.onclick = () => {
      if (state.activePrizes.has(key)) state.activePrizes.delete(key);
      else state.activePrizes.add(key);
      render();
    };
    prizeBox.appendChild(chip);
  }
}

// --- calendar ---------------------------------------------------------------
function renderCalendar() {
  const grid = $("#calendar-grid");
  grid.innerHTML = "";
  const y = state.cursor.getFullYear();
  const m = state.cursor.getMonth();
  $("#cal-title").textContent = `${y}년 ${m + 1}월`;

  const byDay = {};
  for (const w of visibleWebinars()) {
    const d = parseDate(w.start_kst);
    if (!d) continue;
    (byDay[dayKey(d)] = byDay[dayKey(d)] || []).push(w);
  }

  const first = new Date(y, m, 1);
  const startPad = first.getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const todayKey = dayKey(new Date());

  for (let i = 0; i < startPad; i++) {
    const cell = document.createElement("div");
    cell.className = "cal-cell empty";
    grid.appendChild(cell);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const date = new Date(y, m, day);
    const k = dayKey(date);
    const cell = document.createElement("div");
    cell.className = "cal-cell";
    if (date.getDay() === 0) cell.classList.add("sun");
    if (date.getDay() === 6) cell.classList.add("sat");
    if (k === todayKey) cell.classList.add("today");

    const num = document.createElement("div");
    num.className = "daynum";
    num.textContent = day;
    cell.appendChild(num);

    const events = (byDay[k] || []).sort((a, b) =>
      (a.start_kst || "").localeCompare(b.start_kst || "")
    );
    for (const w of events) {
      const ev = document.createElement("div");
      ev.className = "ev";
      ev.style.background = SRC_HEX[w.source] || "#666";
      const gift = (w.prizes && w.prizes.length) ? '<span class="gift">🎁</span>' : "";
      ev.innerHTML = `${gift}<span class="ev-title">${fmtTime(w.start_kst)} ${escapeHtml(w.title)}</span>`;
      ev.title = w.title;
      ev.onclick = () => openModal(w);
      cell.appendChild(ev);
    }
    grid.appendChild(cell);
  }
}

// --- list -------------------------------------------------------------------
function renderList() {
  const box = $("#list-view");
  box.innerHTML = "";
  const items = visibleWebinars()
    .filter((w) => w.start_kst)
    .sort((a, b) => a.start_kst.localeCompare(b.start_kst));

  const groups = {};
  for (const w of items) {
    const d = parseDate(w.start_kst);
    const k = dayKey(d);
    (groups[k] = groups[k] || []).push(w);
  }

  const todayKey = dayKey(new Date());
  let anchored = false;
  for (const k of Object.keys(groups).sort()) {
    const wrap = document.createElement("div");
    wrap.className = "list-day";
    // mark the first group on/after today so we can auto-scroll there
    const isAnchor = !anchored && k >= todayKey;
    if (isAnchor) {
      wrap.id = "list-today-anchor";
      wrap.classList.add("is-today");
      anchored = true;
    }
    const isToday = k === todayKey;
    if (isToday) wrap.classList.add("today-group");  // highlight today's webinars
    const d = parseDate(groups[k][0].start_kst);
    const wd = ["일", "월", "화", "수", "목", "금", "토"][d.getDay()];
    const h = document.createElement("h3");
    h.textContent = `${d.getFullYear()}. ${d.getMonth() + 1}. ${d.getDate()} (${wd})`;
    if (isToday) h.innerHTML = escapeHtml(h.textContent) + ' <span class="today-badge">오늘</span>';
    wrap.appendChild(h);

    for (const w of groups[k]) {
      const card = document.createElement("div");
      card.className = "list-card";
      card.onclick = () => openModal(w);
      const prizeBadges = (w.prizes || [])
        .map((p) => `<span class="badge" style="background:${PRIZES[p.type]?.hex || '#888'}">🎁 ${PRIZES[p.type]?.name || p.type}</span>`)
        .join("");
      card.innerHTML = `
        <div class="src-bar" style="background:${SRC_HEX[w.source] || '#666'}"></div>
        <div class="lc-body">
          <p class="lc-title">${escapeHtml(w.title)}</p>
          <div class="lc-meta">
            <span>🕒 ${fmtTime(w.start_kst)}</span>
            <span class="src-tag" style="background:${SRC_HEX[w.source] || '#666'}">${SOURCES[w.source]?.name || w.source}</span>
            ${w.host ? `<span>${escapeHtml(w.host)}</span>` : ""}
          </div>
          ${prizeBadges ? `<div class="lc-prizes">${prizeBadges}</div>` : ""}
        </div>`;
      wrap.appendChild(card);
    }
    box.appendChild(wrap);
  }
  if (!items.length) box.innerHTML = '<p class="empty">표시할 웨비나가 없습니다.</p>';
}

// --- dashboard --------------------------------------------------------------
function monthKey(iso) { const d = parseDate(iso); return d ? `${d.getFullYear()}-${pad(d.getMonth() + 1)}` : null; }

// horizontal bar chart: rows = [{name, value, color}] (label carries identity,
// value is direct-labeled — satisfies the light-mode contrast relief rule)
function hbars(rows) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return `<div class="hbars">${rows.map((r) => `
    <div class="hbar-row" title="${escapeHtml(r.name)}: ${r.value}건">
      <span class="hbar-name"><span class="hbar-dot" style="background:${r.color}"></span>${escapeHtml(r.name)}</span>
      <span class="hbar-track"><span class="hbar-fill" style="width:${(r.value / max) * 100}%;background:${r.color}"></span></span>
      <span class="hbar-val" style="color:${r.color}">${r.value}</span>
    </div>`).join("")}</div>`;
}

// vertical column chart: cols = [{label, value, current}]
function vbars(cols) {
  const max = Math.max(1, ...cols.map((c) => c.value));
  return `<div class="vbars">${cols.map((c) => `
    <div class="vbar-col${c.current ? " is-current" : ""}" title="${escapeHtml(c.label)}: ${c.value}건">
      <span class="vbar-track"><span class="vbar-fill" style="height:${(c.value / max) * 100}%;background:${c.color || "var(--accent)"}">
        <span class="vbar-val" style="color:${c.color || "var(--accent)"}">${c.value}</span></span></span>
      <span class="vbar-label">${escapeHtml(c.label)}</span>
    </div>`).join("")}</div>`;
}

function renderDashboard() {
  const box = $("#dashboard-view");
  const all = state.webinars;
  if (!all.length) { box.innerHTML = '<p class="empty">표시할 데이터가 없습니다.</p>'; return; }

  const now = new Date();
  const todayKey = dayKey(now);
  const thisMonth = `${now.getFullYear()}-${pad(now.getMonth() + 1)}`;
  const upcoming = all.filter((w) => (w.start_kst || "") && dayKey(parseDate(w.start_kst) || new Date(0)) >= todayKey);
  const activeSites = new Set(all.map((w) => w.source));
  const thisMonthCount = all.filter((w) => monthKey(w.start_kst) === thisMonth).length;

  // per-source counts (identity color = each site's brand color)
  const bySite = {};
  for (const w of all) bySite[w.source] = (bySite[w.source] || 0) + 1;
  const siteRows = Object.keys(SOURCES)
    .map((k) => ({ name: SOURCES[k].name, value: bySite[k] || 0, color: SRC_HEX[k] }))
    .sort((a, b) => b.value - a.value);

  // per-category counts (기술 종목)
  const byCat = new Map(CATEGORIES.map((c) => [c.key, 0]));
  for (const w of all) { const c = classify(w); byCat.set(c.key, byCat.get(c.key) + 1); }
  const catRows = CATEGORIES
    .map((c) => ({ name: c.name, value: byCat.get(c.key), color: c.color }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value);

  // monthly trend: fill every month between the first and last dated webinar
  const months = all.map((w) => monthKey(w.start_kst)).filter(Boolean).sort();
  let monthCols = [];
  if (months.length) {
    const [ys, ms] = months[0].split("-").map(Number);
    const [ye, me] = months[months.length - 1].split("-").map(Number);
    const counts = {};
    for (const m of months) counts[m] = (counts[m] || 0) + 1;
    for (let y = ys, m = ms; y < ye || (y === ye && m <= me); m === 12 ? (y++, m = 1) : m++) {
      const key = `${y}-${pad(m)}`;
      monthCols.push({ label: `${String(y).slice(2)}.${pad(m)}`, value: counts[key] || 0, current: key === thisMonth });
    }
  }

  // yearly totals
  const byYear = {};
  for (const w of all) { const y = (w.start_kst || "").slice(0, 4); if (y) byYear[y] = (byYear[y] || 0) + 1; }
  const yearCols = Object.keys(byYear).sort()
    .map((y) => ({ label: `${y}년`, value: byYear[y], current: y === String(now.getFullYear()) }));

  box.innerHTML = `
    <div class="dash-kpis">
      <div class="kpi"><span class="kpi-val">${all.length}</span><span class="kpi-label">전체 웨비나</span><span class="kpi-sub">수집 누적</span></div>
      <div class="kpi"><span class="kpi-val">${upcoming.length}</span><span class="kpi-label">예정 웨비나</span><span class="kpi-sub">오늘 이후</span></div>
      <div class="kpi"><span class="kpi-val">${activeSites.size}<span style="font-size:1rem;color:var(--text-muted)"> / ${Object.keys(SOURCES).length}</span></span><span class="kpi-label">수집 사이트</span><span class="kpi-sub">일정 등록됨</span></div>
      <div class="kpi"><span class="kpi-val">${thisMonthCount}</span><span class="kpi-label">이번 달 웨비나</span><span class="kpi-sub">${thisMonth}</span></div>
    </div>

    <div class="dash-grid">
      <div class="card">
        <h3>사이트별 웨비나 수</h3>
        <p class="card-sub">출처별 수집 건수 (전체 기간)</p>
        ${hbars(siteRows)}
      </div>
      <div class="card">
        <h3>기술 종목 분포</h3>
        <p class="card-sub">제목 키워드 기반 자동 분류 · 기술 트렌드</p>
        ${hbars(catRows)}
      </div>
      <div class="card span-2">
        <h3>월별 웨비나 추이</h3>
        <p class="card-sub">개최월 기준 건수 (강조 = 이번 달)</p>
        ${vbars(monthCols)}
      </div>
      <div class="card span-2">
        <h3>연도별 웨비나 수</h3>
        <p class="card-sub">개최연도 기준 건수 (강조 = 올해)</p>
        ${vbars(yearCols)}
      </div>
    </div>
    <p class="dash-note">※ 기술 종목은 웨비나 제목·주최명 키워드로 자동 분류한 추정치이며, 실제 주제와 다를 수 있습니다.</p>`;
}

// --- modal ------------------------------------------------------------------
function gcalLink(w) {
  const s = parseDate(w.start_kst);
  if (!s) return null;
  const e = parseDate(w.end_kst) || new Date(s.getTime() + 3600000);
  const fmt = (d) =>
    d.getUTCFullYear() + pad(d.getUTCMonth() + 1) + pad(d.getUTCDate()) + "T" +
    pad(d.getUTCHours()) + pad(d.getUTCMinutes()) + "00Z";
  const details = [
    w.host ? `주최: ${w.host}` : "",
    `신청: ${w.register_url || w.url}`,
  ].filter(Boolean).join("\n");
  const p = new URLSearchParams({
    action: "TEMPLATE",
    text: `[웨비나] ${w.title}`,
    dates: `${fmt(s)}/${fmt(e)}`,
    details,
    ctz: "Asia/Seoul",
  });
  return `https://calendar.google.com/calendar/render?${p.toString()}`;
}

function openModal(w) {
  const body = $("#modal-body");
  // 경품 섹션: 텍스트 경품(배지) + 경품 안내 이미지(배너)를 함께 표시, 없으면 안내.
  const prizeItems = (w.prizes || []).map((p) => `
        <div class="prize-item">
          <div class="p-head"><span class="badge" style="background:${PRIZES[p.type]?.hex || '#888'}">${PRIZES[p.type]?.name || p.type}</span>${p.item ? `<strong>${escapeHtml(p.item)}</strong>` : ""}</div>
          ${p.condition ? `<div class="p-cond">${escapeHtml(p.condition)}</div>` : ""}
        </div>`).join("");
  const prizeImgs = (w.prize_images || [])
    .map((src) => `<img class="prize-img" src="${encodeURI(src)}" alt="${escapeHtml(w.title)} 경품 안내" loading="lazy">`)
    .join("");
  const prizeInner = prizeItems || prizeImgs
    ? prizeItems + prizeImgs
    : `<div class="prize-empty">경품 안내는 주최 측이 <b>홍보 이미지</b>로만 제공하는 경우가 많습니다. ${w.thumbnail ? "위 <b>홍보 배너</b> 또는 " : ""}아래 <b>사이트에서 신청</b>에서 설문·시청·상담 경품(예: 스타벅스 쿠폰·태블릿 등)을 확인하세요.</div>`;
  const prizeHtml = `<div class="modal-prizes"><h4>🎁 경품 정보</h4>${prizeInner}</div>`;

  const gcal = gcalLink(w);
  body.innerHTML = `
    <div class="modal-body">
      <h3>${escapeHtml(w.title)}</h3>
      ${w.thumbnail ? `<img class="modal-thumb" src="${encodeURI(w.thumbnail)}" alt="${escapeHtml(w.title)} 홍보 이미지" loading="lazy">` : ""}
      <div class="modal-row"><span class="k">출처</span><span><span class="src-tag" style="background:${SRC_HEX[w.source] || '#666'}">${SOURCES[w.source]?.name || w.source}</span></span></div>
      <div class="modal-row"><span class="k">일시</span><span>${fmtDateTime(w.start_kst)}</span></div>
      ${w.host ? `<div class="modal-row"><span class="k">주최</span><span>${escapeHtml(w.host)}</span></div>` : ""}
      ${w.registered ? `<div class="modal-row"><span class="k">상태</span><span>✅ 자동 등록됨</span></div>` : ""}
      ${prizeHtml}
      <div class="modal-actions">
        <a class="btn primary" href="${w.register_url || w.url}" target="_blank" rel="noopener">사이트에서 신청 ↗</a>
        ${gcal ? `<a class="btn" href="${gcal}" target="_blank" rel="noopener">📅 구글 캘린더 추가</a>` : ""}
      </div>
    </div>`;
  $("#modal").classList.remove("hidden");
}

function closeModal() { $("#modal").classList.add("hidden"); }

// --- ICS subscription help --------------------------------------------------
function openIcsHelp() {
  const icsUrl = new URL("webinars.ics", location.href).href;
  const body = $("#modal-body");
  body.innerHTML = `
    <div class="modal-body ics-help">
      <h3>📅 구글 캘린더에 웨비나 일정 구독하기</h3>
      <p class="ics-help-intro">아래 ICS 주소를 구글 캘린더에 <b>URL로 추가</b>하면, 이 사이트의 웨비나 일정이 <b>자동으로 구독</b>되어 매일 갱신됩니다. 로그인·설치 없이 무료로 이용할 수 있어요.</p>
      <div class="ics-url-box">
        <code id="ics-url">${escapeHtml(icsUrl)}</code>
        <button class="btn" id="ics-copy" type="button">복사</button>
      </div>
      <ol class="ics-steps">
        <li>웹브라우저(PC 권장)에서 <a href="https://calendar.google.com/" target="_blank" rel="noopener">구글 캘린더</a>를 엽니다.</li>
        <li>왼쪽 <b>"다른 캘린더"</b> 옆의 <b>+</b> 버튼을 클릭한 뒤 <b>"URL로 추가"</b>를 선택합니다.</li>
        <li>위 ICS 주소를 붙여넣고 <b>"캘린더 추가"</b>를 클릭합니다.</li>
        <li>완료! "다른 캘린더" 목록에 <b>웨비나 일정</b>이 추가되며, 이후 자동으로 갱신됩니다.</li>
      </ol>
      <p class="ics-help-note">⏱️ 구글의 외부 URL 캘린더 새로고침은 다소 느릴 수 있습니다(보통 몇 시간~하루). 스마트폰 앱에서는 PC/웹에서 구독한 캘린더가 <b>설정 → 캘린더 표시</b>에 켜져 있어야 보입니다.</p>
    </div>`;
  $("#modal").classList.remove("hidden");
  const copyBtn = $("#ics-copy");
  if (copyBtn) {
    copyBtn.onclick = () => {
      const done = () => {
        copyBtn.textContent = "복사됨 ✓";
        setTimeout(() => (copyBtn.textContent = "복사"), 1500);
      };
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(icsUrl).then(done).catch(() => {});
      }
    };
  }
}

// --- render orchestration ---------------------------------------------------
function render() {
  renderFilters();
  const dashView = $("#dashboard-view");
  const calView = $("#calendar-view");
  const listView = $("#list-view");
  const filters = document.querySelector(".filters");
  // source/prize chips only apply to calendar & list; the dashboard is a
  // whole-dataset overview, so hide the filters there.
  filters.classList.toggle("hidden", state.view === "dashboard");
  dashView.classList.toggle("hidden", state.view !== "dashboard");
  calView.classList.toggle("hidden", state.view !== "calendar");
  listView.classList.toggle("hidden", state.view !== "list");
  if (state.view === "dashboard") renderDashboard();
  else if (state.view === "calendar") renderCalendar();
  else renderList();
}

// scroll the list so today's (or the nearest upcoming) group is at the top
function scrollListToToday() {
  requestAnimationFrame(() => {
    const el = document.getElementById("list-today-anchor");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// --- init -------------------------------------------------------------------
function bindEvents() {
  document.querySelectorAll(".view-toggle button").forEach((btn) => {
    btn.onclick = () => {
      state.view = btn.dataset.view;
      document.querySelectorAll(".view-toggle button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      render();
      if (state.view === "list") scrollListToToday();
    };
  });
  $("#prev-month").onclick = () => { state.cursor.setMonth(state.cursor.getMonth() - 1); render(); };
  $("#next-month").onclick = () => { state.cursor.setMonth(state.cursor.getMonth() + 1); render(); };
  $("#today-btn").onclick = () => { state.cursor = new Date(); render(); };
  document.querySelectorAll("[data-close]").forEach((el) => (el.onclick = closeModal));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  const icsHelp = $("#ics-help");
  if (icsHelp) icsHelp.onclick = (e) => { e.preventDefault(); openIcsHelp(); };
}

async function load() {
  try {
    const res = await fetch("webinars.json", { cache: "no-store" });
    const data = await res.json();
    state.webinars = data.webinars || data || [];
    if (data.generated_at) {
      const d = new Date(data.generated_at);
      $("#updated").textContent = `업데이트: ${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
    // jump cursor to the earliest upcoming webinar's month, if any
    const upcoming = state.webinars
      .map((w) => parseDate(w.start_kst))
      .filter((d) => d && d >= new Date(new Date().toDateString()))
      .sort((a, b) => a - b);
    if (upcoming.length) state.cursor = new Date(upcoming[0].getFullYear(), upcoming[0].getMonth(), 1);
  } catch (e) {
    console.error("failed to load webinars.json", e);
    $("#updated").textContent = "데이터를 불러오지 못했습니다.";
  }
  render();
}

bindEvents();
load();

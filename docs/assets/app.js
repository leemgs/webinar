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
// each menu is its own page (dashboard/, calendar/, list/); the page says which
// view it shows and where the site root is (for webinars.json / webinars.ics)
const PAGE = document.body.dataset;
const ROOT = PAGE.root || "./";

const state = {
  webinars: [],
  view: PAGE.view || "calendar",
  cursor: new Date(),
  activeSources: new Set(Object.keys(SOURCES)),
  activePrizes: new Set(), // empty = no prize filter
  // dashboard: month picked per card ("" = all months), kept in the URL
  periodMonth: Object.fromEntries(
    [["site", "month"], ["tech", "tech-month"]].map(([card, param]) => [card, new URLSearchParams(location.search).get(param) || ""])),
  // dashboard: sites picked per chart (empty = all), kept in the URL as
  // ?trend-sites=a,b (monthly), ?year-sites= (yearly), ?tech-sites= (기술 종목)
  siteFilter: Object.fromEntries([["month", "trend-sites"], ["year", "year-sites"], ["tech", "tech-sites"]].map(([chart, param]) =>
    [chart, new Set((new URLSearchParams(location.search).get(param) || "").split(",").filter((k) => k in SOURCES))])),
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

// a start stored at exactly 00:00 KST means "day known, time unknown"
const isDateOnly = (iso) => typeof iso === "string" && iso.slice(11, 19) === "00:00:00";

function fmtTime(iso) {
  const d = parseDate(iso);
  if (!d || isDateOnly(iso)) return "시간 미정";
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
      ev.innerHTML = `${gift}<span class="ev-title">${isDateOnly(w.start_kst) ? "" : fmtTime(w.start_kst) + " "}${escapeHtml(w.title)}</span>`;
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
      const cat = classify(w);
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
            <span class="cat-tag" style="background:${cat.color}">${escapeHtml(cat.name)}</span>
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
      <span class="hbar-track"><span class="hbar-fill" style="width:${(r.value / max) * 100}%;background:${r.color}${r.value ? "" : ";min-width:0"}"></span></span>
      <span class="hbar-val" style="color:${r.color}">${r.value}</span>
    </div>`).join("")}</div>`;
}

// stacking order of the per-site monthly columns (bottom → top): the order whose
// neighbouring site colors stay most distinct under color-vision deficiency
const STACK_ORDER = ["ddtube", "allshowtv", "e4ds", "sharedit", "chontv", "talkit", "cloit", "dubiz"];

// dark or white ink, whichever reads better on a segment's fill color
function inkOn(hex) {
  const lin = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const lum = (h) => {
    const [r, g, b] = [1, 3, 5].map((i) => lin(parseInt(h.slice(i, i + 2), 16) / 255));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const L = lum(hex), dark = "#1a2233";
  return (L + 0.05) / (lum(dark) + 0.05) > 1.05 / (L + 0.05) ? dark : "#ffffff";
}

// stacked column chart: cols = [{label, value, current, parts: [{key, value}]}]
// one segment per site (site color), total on top, per-site counts inside
// segments tall enough to hold them, and the full breakdown in each tooltip
function stackedVbars(cols, trackPx) {
  const max = Math.max(1, ...cols.map((c) => c.value));
  const shown = STACK_ORDER.filter((k) => cols.some((c) => c.parts.some((p) => p.key === k && p.value)));
  const legend = `<div class="chart-legend">${shown.map((k) => `
    <span class="legend-item"><span class="hbar-dot" style="background:${SRC_HEX[k]}"></span>${escapeHtml(SOURCES[k]?.name || k)}</span>`).join("")}</div>`;
  const bars = cols.map((c, i) => {
    const parts = STACK_ORDER.map((k) => c.parts.find((p) => p.key === k)).filter((p) => p && p.value);
    const segs = parts.map((p) => {
      const name = SOURCES[p.key]?.name || p.key;
      // a lone segment's count is already the total above the bar
      const label = parts.length > 1 && (p.value / max) * trackPx >= 14 ? p.value : "";
      return `<span class="vseg" style="flex-grow:${p.value};background:${SRC_HEX[p.key]};color:${inkOn(SRC_HEX[p.key])}" aria-label="${escapeHtml(name)} ${p.value}건">${label}</span>`;
    }).join("");
    const tip = parts.length ? `
        <span class="vbar-tip" role="tooltip"><b>${escapeHtml(c.label)} · ${c.value}건</b>${parts.slice().reverse().map((p) => `
          <span class="tip-row"><span class="hbar-dot" style="background:${SRC_HEX[p.key]}"></span>${escapeHtml(SOURCES[p.key]?.name || p.key)}<b>${p.value}</b></span>`).join("")}</span>` : "";
    return `
    <div class="vbar-col${c.current ? " is-current" : ""}${i >= cols.length / 2 ? " tip-left" : ""}" tabindex="0" aria-label="${escapeHtml(c.label)}: ${c.value}건${parts.map((p) => `, ${escapeHtml(SOURCES[p.key]?.name || p.key)} ${p.value}건`).join("")}">
      <span class="vbar-track"><span class="vbar-fill vbar-stack" style="height:${(c.value / max) * 100}%">
        <span class="vbar-val">${c.value}</span>${segs}</span></span>
      <span class="vbar-label">${escapeHtml(c.label)}</span>${tip}
    </div>`;
  }).join("");
  // table view: the same numbers for readers who can't hover or tell colors apart
  const table = `
    <details class="chart-table"><summary>표로 보기</summary>
      <div class="table-scroll"><table>
        <thead><tr><th>사이트</th>${cols.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("")}</tr></thead>
        <tbody>${shown.slice().reverse().map((k) => `<tr><th><span class="hbar-dot" style="background:${SRC_HEX[k]}"></span>${escapeHtml(SOURCES[k]?.name || k)}</th>${cols.map((c) => {
          const v = c.parts.find((p) => p.key === k)?.value || 0;
          return `<td>${v || "·"}</td>`;
        }).join("")}</tr>`).join("")}
          <tr class="total"><th>합계</th>${cols.map((c) => `<td>${c.value}</td>`).join("")}</tr></tbody>
      </table></div>
    </details>`;
  return `${legend}<div class="vbars vbars-stacked" style="height:${trackPx + 40}px">${bars}</div>${table}`;
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

  // the period cards count webinars of the whole period or of one month
  const inMonth = (month) => (month ? all.filter((w) => monthKey(w.start_kst) === month) : all);

  // per-source counts (identity color = each site's brand color)
  const siteRowsFor = (month) => {
    const bySite = {};
    for (const w of inMonth(month)) bySite[w.source] = (bySite[w.source] || 0) + 1;
    return Object.keys(SOURCES)
      .map((k) => ({ name: SOURCES[k].name, value: bySite[k] || 0, color: SRC_HEX[k] }))
      .sort((a, b) => b.value - a.value);
  };

  // per-category counts (기술 종목), optionally only for some sites
  const catRowsFor = (month, sites) => {
    const byCat = new Map(CATEGORIES.map((c) => [c.key, 0]));
    for (const w of inMonth(month)) {
      if (sites?.size && !sites.has(w.source)) continue;
      const c = classify(w);
      byCat.set(c.key, byCat.get(c.key) + 1);
    }
    return CATEGORIES
      .map((c) => ({ name: c.name, value: byCat.get(c.key), color: c.color }))
      .filter((r) => r.value > 0)
      .sort((a, b) => b.value - a.value);
  };

  const PERIOD_CARDS = {
    site: { param: "month", rowsFor: siteRowsFor, allSub: "출처별 수집 건수 (전체 기간)" },
    tech: { param: "tech-month", sites: true, rowsFor: catRowsFor, allSub: "제목 키워드 기반 자동 분류 · 기술 트렌드 (전체 기간)" },
  };
  const periodSub = (card, month, sites) => {
    if (!month && !sites?.size) return PERIOD_CARDS[card].allSub;
    const n = inMonth(month).filter((w) => !sites?.size || sites.has(w.source)).length;
    return [
      month ? `${month.replace("-", "년 ")}월 개최 기준` : "전체 기간",
      sites?.size ? [...sites].map((k) => SOURCES[k].name).join(", ") : "",
      `${n}건`,
    ].filter(Boolean).join(" · ");
  };
  // a card whose bars can be shown for 전체 or one month (chips above the bars),
  // and — for 기술 종목 — for some sites only (a second chip row)
  const periodCard = (card, title) => `
      <div class="card" data-period="${card}">
        <h3>${title}</h3>
        <p class="card-sub period-sub"></p>
        <div class="month-chips period-chips" role="group" aria-label="${title} 기간 선택">
          <button type="button" data-month="">전체</button>${monthCols.map((c) => `
          <button type="button" data-month="${c.key}"${c.current ? ' class="is-current" title="이번 달"' : ""}>${escapeHtml(c.label)}</button>`).join("")}
        </div>${PERIOD_CARDS[card].sites ? siteChipsHtml(title) : ""}
        <div class="period-bars"></div>
      </div>`;

  // monthly trend: fill every month between the first and last dated webinar
  const months = all.map((w) => monthKey(w.start_kst)).filter(Boolean).sort();
  let monthCols = [];
  if (months.length) {
    const [ys, ms] = months[0].split("-").map(Number);
    const [ye, me] = months[months.length - 1].split("-").map(Number);
    const counts = {};
    const bySiteMonth = {};
    for (const w of all) {
      const m = monthKey(w.start_kst);
      if (!m) continue;
      counts[m] = (counts[m] || 0) + 1;
      bySiteMonth[m] = bySiteMonth[m] || {};
      bySiteMonth[m][w.source] = (bySiteMonth[m][w.source] || 0) + 1;
    }
    for (let y = ys, m = ms; y < ye || (y === ye && m <= me); m === 12 ? (y++, m = 1) : m++) {
      const key = `${y}-${pad(m)}`;
      const parts = Object.entries(bySiteMonth[key] || {}).map(([k, v]) => ({ key: k, value: v }));
      monthCols.push({ key, label: `${String(y).slice(2)}.${pad(m)}`, value: counts[key] || 0, current: key === thisMonth, parts });
    }
  }

  // yearly totals, by site
  const byYear = {};
  for (const w of all) {
    const y = (w.start_kst || "").slice(0, 4);
    if (!y) continue;
    byYear[y] = byYear[y] || {};
    byYear[y][w.source] = (byYear[y][w.source] || 0) + 1;
  }
  const yearCols = Object.keys(byYear).sort().map((y) => {
    const parts = Object.entries(byYear[y]).map(([k, v]) => ({ key: k, value: v }));
    return { label: `${y}년`, value: parts.reduce((n, p) => n + p.value, 0), current: y === String(now.getFullYear()), parts };
  });

  const STACK_CARDS = {
    month: { param: "trend-sites", cols: monthCols, basis: "개최월 기준 건수", hint: "강조 = 이번 달" },
    year: { param: "year-sites", cols: yearCols, basis: "개최연도 기준 건수", hint: "강조 = 올해" },
  };
  // a stacked-by-site column chart with site chips to filter it
  const stackCard = (chart, title) => `
      <div class="card span-2" data-stack="${chart}">
        <h3>${title}</h3>
        <p class="card-sub stack-sub"></p>${siteChipsHtml(title)}
        <div class="stack-body"></div>
      </div>`;

  box.innerHTML = `
    <div class="dash-kpis">
      <div class="kpi"><span class="kpi-val">${all.length}</span><span class="kpi-label">전체 웨비나</span><span class="kpi-sub">수집 누적</span></div>
      <div class="kpi"><span class="kpi-val">${upcoming.length}</span><span class="kpi-label">예정 웨비나</span><span class="kpi-sub">오늘 이후</span></div>
      <div class="kpi"><span class="kpi-val">${activeSites.size}<span style="font-size:1rem;color:var(--text-muted)"> / ${Object.keys(SOURCES).length}</span></span><span class="kpi-label">수집 사이트</span><span class="kpi-sub">일정 등록됨</span></div>
      <div class="kpi"><span class="kpi-val">${thisMonthCount}</span><span class="kpi-label">이번 달 웨비나</span><span class="kpi-sub">${thisMonth}</span></div>
    </div>

    <div class="dash-grid">
${periodCard("site", "사이트별 웨비나 수")}${periodCard("tech", "기술 종목 분포")}
${stackCard("month", "월별 웨비나 추이")}${stackCard("year", "연도별 웨비나 수")}
    </div>
    <p class="dash-note">※ 기술 종목은 웨비나 제목·주최명 키워드로 자동 분류한 추정치이며, 실제 주제와 다를 수 있습니다.</p>`;

  // month chips: redraw only that card's bars, and keep the choice in the URL
  box.querySelectorAll("[data-period]").forEach((el) => {
    const card = el.dataset.period;
    const { param, rowsFor } = PERIOD_CARDS[card];
    const siteRow = el.querySelector(".site-chips");
    const sites = siteRow ? state.siteFilter[card] : null;
    const chips = el.querySelectorAll(".period-chips button");
    const draw = () => {
      const month = state.periodMonth[card];
      chips.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.month === month)));
      el.querySelector(".period-sub").textContent = periodSub(card, month, sites);
      const rows = rowsFor(month, sites);
      el.querySelector(".period-bars").innerHTML = rows.length ? hbars(rows) : '<p class="empty">해당 웨비나가 없습니다.</p>';
      setParam(param, month);
      if (sites) setParam(PERIOD_SITE_PARAM[card], [...sites].join(","));
    };
    chips.forEach((b) => (b.onclick = () => { state.periodMonth[card] = b.dataset.month; draw(); }));
    if (siteRow) bindSiteChips(siteRow, sites, draw);
    if (!monthCols.some((c) => c.key === state.periodMonth[card])) state.periodMonth[card] = "";
    draw();
    revealPressed(el.querySelector(".period-chips"));
    revealPressed(siteRow);
  });

  // monthly / yearly charts: site chips pick which sites are stacked; the scale
  // follows the selection so a small site stays readable, colors stay per site
  box.querySelectorAll("[data-stack]").forEach((el) => {
    const chart = el.dataset.stack;
    const { param, cols: allCols, basis, hint } = STACK_CARDS[chart];
    const on = state.siteFilter[chart]; // empty = all sites
    const draw = () => {
      const cols = allCols.map((c) => {
        const parts = c.parts.filter((p) => !on.size || on.has(p.key));
        return { ...c, parts, value: parts.reduce((n, p) => n + p.value, 0) };
      });
      const total = cols.reduce((n, c) => n + c.value, 0);
      el.querySelector(".stack-sub").textContent = on.size
        ? `${basis} · ${[...on].map((k) => SOURCES[k].name).join(", ")} · ${total}건 (${hint})`
        : `${basis} · 색 = 사이트, 막대 위 숫자 = 합계 (${hint})`;
      el.querySelector(".stack-body").innerHTML = stackedVbars(cols, 220);
      setParam(param, [...on].join(","));
    };
    bindSiteChips(el.querySelector(".site-chips"), on, draw);
    draw();
    revealPressed(el.querySelector(".site-chips"));
  });
}

const PERIOD_SITE_PARAM = { tech: "tech-sites" };

// update one dashboard query parameter in place ("" removes it; commas stay readable)
function setParam(name, value) {
  const url = new URL(location.href);
  if (value) url.searchParams.set(name, value); else url.searchParams.delete(name);
  history.replaceState(null, "", url.href.replace(/%2C/gi, ","));
}

// site chips: 전체 + one per site (site color dot)
function siteChipsHtml(title) {
  return `
        <div class="month-chips site-chips" role="group" aria-label="${title} 사이트 선택">
          <button type="button" data-site="">전체</button>${Object.keys(SOURCES).map((k) => `
          <button type="button" data-site="${k}"><span class="hbar-dot" style="background:${SRC_HEX[k]}"></span>${escapeHtml(SOURCES[k].name)}</button>`).join("")}
        </div>`;
}

// picking a site toggles it in `sites` (a Set, empty = all); 전체 — or every
// site picked — clears it. Calls onChange after each click.
function bindSiteChips(row, sites, onChange) {
  const chips = row.querySelectorAll("button");
  const sync = () => {
    row.toggleAttribute("data-filtered", sites.size > 0);
    chips.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.site ? sites.has(b.dataset.site) : !sites.size)));
  };
  chips.forEach((b) => (b.onclick = () => {
    const k = b.dataset.site;
    if (!k) sites.clear();
    else if (sites.has(k)) sites.delete(k);
    else sites.add(k);
    if (sites.size === Object.keys(SOURCES).length) sites.clear();
    sync();
    onChange();
  }));
  sync();
}

// a chip row scrolls sideways on phones: on load, bring the first picked chip
// (from the URL) into view instead of leaving it off-screen
function revealPressed(row) {
  const chip = row && [...row.querySelectorAll('[aria-pressed="true"]')].find((b) => b !== row.firstElementChild);
  if (chip && row.scrollWidth > row.clientWidth) row.scrollLeft = chip.offsetLeft - row.offsetLeft - 8;
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
  // date-only (unknown time) -> all-day: YYYYMMDD/YYYYMMDD(next day), taken
  // from the KST date string so the viewer's own timezone can't shift the day
  let dates = `${fmt(s)}/${fmt(e)}`;
  if (isDateOnly(w.start_kst)) {
    const day = w.start_kst.slice(0, 10);
    const next = new Date(`${day}T12:00:00Z`);
    next.setUTCDate(next.getUTCDate() + 1);
    dates = `${day.replace(/-/g, "")}/${next.toISOString().slice(0, 10).replace(/-/g, "")}`;
  }
  const p = new URLSearchParams({
    action: "TEMPLATE",
    text: `[웨비나] ${w.title}`,
    dates,
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
  const icsUrl = new URL(`${ROOT}webinars.ics`, location.href).href;
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
  // the dashboard is a whole-dataset overview: its page has no source/prize filters
  if (state.view === "dashboard") return renderDashboard();
  renderFilters();
  if (state.view === "calendar") renderCalendar();
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
  if (state.view === "calendar") {
    $("#prev-month").onclick = () => { state.cursor.setMonth(state.cursor.getMonth() - 1); render(); };
    $("#next-month").onclick = () => { state.cursor.setMonth(state.cursor.getMonth() + 1); render(); };
    $("#today-btn").onclick = () => { state.cursor = new Date(); render(); };
  }
  document.querySelectorAll("[data-close]").forEach((el) => (el.onclick = closeModal));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });
  const icsHelp = $("#ics-help");
  if (icsHelp) icsHelp.onclick = (e) => { e.preventDefault(); openIcsHelp(); };
}

async function load() {
  try {
    const res = await fetch(`${ROOT}webinars.json`, { cache: "no-store" });
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
  if (state.view === "list") scrollListToToday();
}

bindEvents();
load();

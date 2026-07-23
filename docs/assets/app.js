"use strict";

// --- metadata ---------------------------------------------------------------
const SOURCES = {
  allshowtv: { name: "올쇼TV", color: "var(--c-allshowtv)" },
  sharedit: { name: "쉐어드IT", color: "var(--c-sharedit)" },
  ddtube: { name: "DD튜브", color: "var(--c-ddtube)" },
  e4ds: { name: "e4ds", color: "var(--c-e4ds)" },
  talkit: { name: "토크아이티", color: "var(--c-talkit)" },
  dubiz: { name: "두비즈", color: "var(--c-dubiz)" },
  cloit: { name: "CLOIT:ON", color: "var(--c-cloit)" },
};
const SRC_HEX = {
  allshowtv: "#e8590c", sharedit: "#2f9e44", ddtube: "#1971c2", e4ds: "#9c36b5",
  talkit: "#e8478b", dubiz: "#0c8599", cloit: "#f08c00",
};
const PRIZES = {
  survey: { name: "설문", color: "var(--p-survey)", hex: "#1971c2" },
  question: { name: "질문", color: "var(--p-question)", hex: "#2f9e44" },
  consult: { name: "상담", color: "var(--p-consult)", hex: "#9c36b5" },
  attendance: { name: "참석/시청", color: "var(--p-attendance)", hex: "#e8590c" },
};

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
  const calView = $("#calendar-view");
  const listView = $("#list-view");
  if (state.view === "calendar") {
    calView.classList.remove("hidden");
    listView.classList.add("hidden");
    renderCalendar();
  } else {
    calView.classList.add("hidden");
    listView.classList.remove("hidden");
    renderList();
  }
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

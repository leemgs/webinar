// Access-code gate for the site (invited users only).
//
// initAuth() shows a code prompt until the visitor unlocks the site; unlock()
// hashes the typed code with SHA-256 in the browser and compares it with the
// digest(s) in config/access.json — `digest` is one hash or a list of them,
// one per valid code. A match is remembered in sessionStorage (this tab only)
// with the config version and the matched digest, so bumping `version` asks
// everyone for the code again, and removing a digest revokes that code.
//
// ⚠️ This is a light access restriction for a static site, NOT a security
// boundary: the digest, the data (webinars.json) and every page are public
// files, and the check runs in the visitor's browser. Never protect sensitive
// information with it.

const ACCESS_KEY = "webinar-hub-access";
// config/access.json sits next to assets/, whichever page loaded this script
const ACCESS_URL = new URL("../config/access.json", document.currentScript.src).href;

// hide the page until initAuth() decides (no flash of the content)
document.documentElement.classList.add("auth-locked");

let accessConfig = null;

async function loadAccessConfig() {
  if (!accessConfig) {
    const res = await fetch(ACCESS_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`access config: HTTP ${res.status}`);
    accessConfig = await res.json();
  }
  return accessConfig;
}

async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function readGrant() {
  try { return JSON.parse(sessionStorage.getItem(ACCESS_KEY) || "null"); } catch { return null; }
}

function writeGrant(cfg, digest) {
  try {
    sessionStorage.setItem(ACCESS_KEY, JSON.stringify({ version: cfg.version, digest }));
  } catch { /* storage blocked (e.g. private mode): unlocked for this page view only */ }
}

// the valid code hashes: `digest` may be a single hex string or a list
const digestsOf = (cfg) => [].concat(cfg.digest || []).map((d) => String(d).toLowerCase());

const isGranted = (grant, cfg) =>
  !!grant && grant.version === cfg.version && digestsOf(cfg).includes(grant.digest);

let resolveUnlocked;
// app.js waits on this before loading data and rendering
window.siteUnlocked = new Promise((resolve) => (resolveUnlocked = resolve));

function openSite() {
  document.getElementById("auth-gate")?.remove();
  document.documentElement.classList.remove("auth-locked");
  resolveUnlocked();
}

// Check `code` against config/access.json; on a match, remember the grant and
// open the site. Returns true when unlocked.
async function unlock(code) {
  const cfg = await loadAccessConfig();
  const typed = await sha256Hex(String(code || "").trim());
  if (!digestsOf(cfg).includes(typed)) return false;
  writeGrant(cfg, typed);
  openSite();
  return true;
}

function renderGate(message, { disabled = false } = {}) {
  const gate = document.createElement("div");
  gate.id = "auth-gate";
  gate.innerHTML = `
    <form class="auth-card" novalidate>
      <h1>📡 웨비나 허브</h1>
      <p class="auth-intro">초대받은 사용자를 위한 정보 공간입니다.<br>접속 코드를 입력하세요.</p>
      <label class="auth-label" for="auth-code">접속 코드</label>
      <input id="auth-code" name="code" type="password" autocomplete="current-password" required autofocus${disabled ? " disabled" : ""}>
      <button type="submit" class="auth-submit"${disabled ? " disabled" : ""}>입장</button>
      <p class="auth-error" role="alert" aria-live="assertive">${message || ""}</p>
    </form>`;
  document.body.prepend(gate);
  const form = gate.querySelector("form");
  const input = gate.querySelector("#auth-code");
  const error = gate.querySelector(".auth-error");
  const button = gate.querySelector(".auth-submit");
  form.onsubmit = async (e) => {
    e.preventDefault();
    if (!input.value.trim()) { error.textContent = "접속 코드를 입력하세요."; input.focus(); return; }
    button.disabled = true;
    error.textContent = "";
    try {
      if (!(await unlock(input.value))) {
        error.textContent = "접속 코드가 올바르지 않습니다.";
        input.select();
      }
    } catch (err) {
      console.error(err);
      error.textContent = "접속 설정을 불러오지 못했습니다. 잠시 후 다시 시도하세요.";
    } finally {
      button.disabled = false;
    }
  };
  input.focus();
}

// Open the site when this tab already holds a grant for the current config;
// otherwise show the code prompt.
async function initAuth() {
  if (!window.crypto?.subtle) {
    // SubtleCrypto exists only on https:// (and localhost)
    renderGate("이 브라우저에서는 접속 코드를 확인할 수 없습니다(https 주소로 접속하세요).", { disabled: true });
    return;
  }
  try {
    const cfg = await loadAccessConfig();
    if (isGranted(readGrant(), cfg)) return openSite();
    renderGate();
  } catch (err) {
    console.error(err);
    renderGate("접속 설정을 불러오지 못했습니다. 잠시 후 다시 시도하세요.");
  }
}

document.addEventListener("DOMContentLoaded", initAuth);

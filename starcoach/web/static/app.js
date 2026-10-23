"use strict";
// StarCoach web app: hash routes, plain DOM, no library.
// Every value from the API is escaped with esc() before it goes into HTML.

const $view = document.getElementById("view");
const $q = document.getElementById("q");
const $foot = document.getElementById("foot");

const EXAMPLES = [
  "گوشی سامسونگ زیر ۲۰۰ میلیون قسطی تو علاءالدین",
  "شارژر اپل ۲۰ وات اصل که الان باز باشه",
  "هندزفری بلوتوث ارزون نزدیک جمهوری",
  "دزدگیر اماکن بین ۱۰ تا ۱۵ میلیون",
  "محافظ برق کولر لاله زار فردا عصر",
  "نمیدونم چه مدلی هندزفری بخرم",
];

// ---------- formatting ----------
const nf = new Intl.NumberFormat("fa-IR");
const rtf = new Intl.RelativeTimeFormat("fa", { numeric: "auto" });
const dateFmt = new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" });

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function num(n) { return nf.format(n); }
function faDigits(t) { return String(t ?? "").replace(/[0-9]/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]); }
function toman(n) { return n == null ? null : `${num(n)} تومان`; }
function tomanShort(n) {
  if (n == null) return null;
  if (n >= 1e9) return `${new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 }).format(n / 1e9)} میلیارد تومان`;
  if (n >= 1e6) return `${new Intl.NumberFormat("fa-IR", { maximumFractionDigits: n < 1e7 ? 2 : 1 }).format(n / 1e6)} میلیون تومان`;
  if (n >= 1e3) return `${new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 0 }).format(n / 1e3)} هزار تومان`;
  return toman(n);
}
function ago(iso) {
  if (!iso) return null;
  const days = Math.round((new Date(iso) - Date.now()) / 86400000);
  if (Math.abs(days) < 1) return "امروز";
  if (Math.abs(days) < 60) return rtf.format(days, "day");
  const months = Math.round(days / 30);
  if (Math.abs(months) < 12) return rtf.format(months, "month");
  return rtf.format(Math.round(days / 365), "year");
}
function ageDays(iso) { return iso ? (Date.now() - new Date(iso)) / 86400000 : null; }
function unknown(text = "نامشخص") { return `<span class="muted">${esc(text)}</span>`; }

function openPill(open, text) {
  const cls = open === true ? "pill-open" : open === false ? "pill-closed" : "pill-unknown";
  return `<span class="chip ${cls}">${esc(text)}</span>`;
}
function nameBadge(shop) {
  if (!shop.name_is_real) return `<span class="chip pill-unknown" title="در داده‌ی مسابقه، نام بیشتر فروشگاه‌ها ساختگی است">نام نمایشی</span>`;
  const links = [
    shop.instagram ? `<a class="chip" target="_blank" rel="noopener" href="${esc(shop.instagram)}">📷 اینستاگرام</a>` : "",
    shop.website ? `<a class="chip" target="_blank" rel="noopener" href="${esc(shop.website)}">🌐 سایت</a>` : "",
  ].join("");
  return `<span class="chip pill-open" title="نام واقعی؛ صفحه‌ی آنلاین فروشگاه برای دیدن عکس و نمونه‌کار">فروشگاه با صفحه‌ی آنلاین</span>${links}`;
}
function neshan(lat, lon) { return `https://nshn.ir/?lat=${lat}&lng=${lon}`; }
function gmaps(lat, lon) { return `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`; }
function thumb(src, alt) {
  return src
    ? `<img class="thumb" loading="lazy" src="${esc(src)}" alt="${esc(alt)}">`
    : `<div class="thumb empty">بدون تصویر</div>`;
}

// ---------- user context: area, budget, visit time, purchase conditions ----------
const DAYS_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];
const CONDITIONS = [
  ["open", "فقط باز در زمان بازدید"],
  ["installments", "فقط خرید اقساطی"],
  ["torobpay", "ترب‌پی"],
  ["in_person_pay", "پرداخت حضوری اعلام‌شده"],
  ["fast", "ارسال فوری"],
  ["warranty", "گارانتی‌دار"],
];
const BUDGETS = [2e6, 5e6, 20e6, 50e6, 100e6, 200e6];
const RADII = [[300, "۳۰۰ متر"], [1000, "۱ کیلومتر"], [3000, "۳ کیلومتر"]];
const DEFAULT_CTX = {
  place: null, // {kind: "area" | "passage" | "me", name, lat, lon}
  radius_m: null, max_price: null, min_price: null, day: null, hour: null, sort: "price",
  open: false, installments: false, torobpay: false, in_person_pay: false, fast: false, warranty: false,
};
let ctx = loadCtx();
let AREAS = null;

function loadCtx() {
  try { return { ...DEFAULT_CTX, ...JSON.parse(localStorage.getItem("sc_ctx") || "{}") }; } catch { return { ...DEFAULT_CTX }; }
}
function saveCtx() { try { localStorage.setItem("sc_ctx", JSON.stringify(ctx)); } catch { /* private mode */ } }

function tehranNow() { return new Date(Date.now() + 3.5 * 3600e3); } // read with getUTC* (UTC+03:30, F17)
function visitISO() {
  if (ctx.day == null) return null;
  const now = tehranNow();
  const today = (now.getUTCDay() + 1) % 7; // JS Sun=0 → Iranian Sat=0
  const hour = ctx.hour ?? 11;
  let ahead = (ctx.day - today + 7) % 7;
  if (ahead === 0 && hour < now.getUTCHours()) ahead = 7;
  const d = new Date(now.getTime() + ahead * 86400e3);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(hour)}:00`;
}
function filterParams() {
  const p = new URLSearchParams();
  const pl = ctx.place;
  if (pl?.kind === "area") p.set("area", pl.name);
  if (pl?.kind === "passage") p.set("passage", pl.name);
  if (pl?.lat != null) { p.set("lat", pl.lat); p.set("lon", pl.lon); }
  if (ctx.radius_m && pl?.lat != null) p.set("radius_m", ctx.radius_m);
  if (ctx.max_price) p.set("max_price", ctx.max_price);
  if (ctx.min_price) p.set("min_price", ctx.min_price);
  const at = visitISO();
  if (at) p.set("at", at);
  for (const [k] of CONDITIONS) if (ctx[k]) p.set(k, "1");
  if (ctx.sort === "distance" && pl?.lat != null) p.set("sort", "distance");
  return p.toString();
}
function filtersActive() {
  return Boolean(ctx.place || ctx.max_price || ctx.min_price || CONDITIONS.some(([k]) => ctx[k]));
}
// API filter name → how to switch it off in ctx (for "relax" suggestions)
const RELAX_CTX = {
  max_price: { max_price: null }, min_price: { min_price: null }, area: { place: null }, passage: { place: null },
  radius_m: { radius_m: null }, open_only: { open: false }, installments: { installments: false },
  torobpay: { torobpay: false }, in_person_pay: { in_person_pay: false }, fast_delivery: { fast: false },
  warranty: { warranty: false },
};

const CLEAR_CTX = {
  place: { place: null, radius_m: null, sort: "price" },
  budget: { max_price: null, min_price: null },
  when: { day: null, hour: null },
  conds: Object.fromEntries(CONDITIONS.map(([k]) => [k, false])),
};
const CLEAR_UNDO_KEYS = {
  place: ["passage", "area"],
  budget: ["budget"],
  when: ["at"],
  conds: CONDITIONS.map(([k]) => k),
};

function ctxBarVisible() {
  // Filters only matter once the shopper is looking at results (or a page that uses them).
  const hash = location.hash || "#/";
  const [path, query] = hash.slice(1).split("?");
  if (!path || path === "/") return false;
  if (path.startsWith("/search")) return Boolean(new URLSearchParams(query || "").get("q")?.trim());
  return /\/(p|guide|compare|plan|passage|s|seller)\b/.test(path);
}

function renderCtxBar() {
  const bar = document.getElementById("ctxbar");
  if (!ctxBarVisible()) {
    bar.hidden = true;
    bar.innerHTML = "";
    return;
  }
  bar.hidden = false;
  const pl = ctx.place;
  const place = pl ? (pl.kind === "me" ? "نزدیک من" : pl.name) + (ctx.radius_m ? ` · ${RADII.find((r) => r[0] === ctx.radius_m)?.[1] || ""}` : "") : "همه‌ی محله‌ها";
  const budget = ctx.min_price && ctx.max_price ? `${tomanShort(ctx.min_price)} تا ${tomanShort(ctx.max_price)}`
    : ctx.max_price ? `تا ${tomanShort(ctx.max_price)}` : ctx.min_price ? `از ${tomanShort(ctx.min_price)} به بالا` : "هر بودجه";
  const when = ctx.day == null ? "الان" : `${DAYS_FA[ctx.day]} ساعت ${num(ctx.hour ?? 11)}`;
  const conds = CONDITIONS.filter(([k]) => ctx[k]).map(([, l]) => l);
  const chip = (on, text, clearKey) => on
    ? `<span class="ctxchip on"><button type="button" class="ctxchip-main" data-open-sheet>${esc(text)}</button><button type="button" class="ctxclear" data-clear-ctx="${clearKey}" aria-label="پاک کردن" title="پاک کردن">✕</button></span>`
    : `<button type="button" class="ctxchip" data-open-sheet>${esc(text)}</button>`;
  const anyOn = Boolean(pl || ctx.max_price || ctx.min_price || ctx.day != null || conds.length);
  const clearAll = anyOn
    ? `<button type="button" class="ctxchip ctxclear-all" data-clear-ctx="all" title="پاک کردن همه‌ی شرایط">پاک کردن ✕</button>`
    : "";
  const nOn = [pl, ctx.max_price || ctx.min_price, ctx.day != null].filter(Boolean).length + conds.length;
  const all = `<button type="button" class="ctxchip ctxall" data-open-sheet>⚙️ فیلترها${nOn ? ` (${num(nOn)})` : ""}</button>`;
  const locate = pl ? "" : `<button type="button" class="ctxchip ctxlocate" data-use-location>📍 نزدیک من</button>`;
  const active = [
    locate,
    pl && chip(true, "📍 " + place, "place"),
    (ctx.max_price || ctx.min_price) && chip(true, "💰 " + budget, "budget"),
    ctx.day != null && chip(true, "🕒 " + when, "when"),
    conds.length > 0 && chip(true, "💳 " + conds.join("، "), "conds"),
  ].filter(Boolean).join("");
  bar.innerHTML = all + active + clearAll;
}

async function openSheet() {
  if (!AREAS) { try { AREAS = await getJSON("/api/areas"); } catch { AREAS = { areas: [], passages: [] }; } }
  const sheet = document.getElementById("sheet");
  const pl = ctx.place;
  const radio = (name, value, label, checked) =>
    `<label class="opt"><input type="radio" name="${name}" value="${esc(value)}" ${checked ? "checked" : ""}><span>${esc(label)}</span></label>`;
  const check = (name, label) =>
    `<label class="opt"><input type="checkbox" name="${name}" ${ctx[name] ? "checked" : ""}><span>${esc(label)}</span></label>`;
  sheet.innerHTML = `
    <div class="sheet-head"><strong>فیلترها و شرایط خرید</strong><button type="button" class="ctxclear" id="sheetX" aria-label="بستن">✕</button></div>
    <form method="dialog" id="sheetForm">
      <h3>کجا؟</h3>
      <div class="opts">
        ${radio("placeKind", "", "همه‌ی محله‌ها", !pl)}
        ${radio("placeKind", "me", "نزدیک من", pl?.kind === "me")}
      </div>
      <p class="muted small" style="margin:6px 0">یا یک محله یا پاساژ:</p>
      <select name="place" style="width:100%">
        <option value="">—</option>
        <optgroup label="محله">${AREAS.areas.map((a) => `<option value="area|${esc(a.name)}" ${pl?.kind === "area" && pl.name === a.name ? "selected" : ""}>${esc(a.name)} (${num(a.shops)} فروشگاه)</option>`).join("")}</optgroup>
        <optgroup label="پاساژ">${AREAS.passages.map((a) => `<option value="passage|${esc(a.name)}" ${pl?.kind === "passage" && pl.name === a.name ? "selected" : ""}>${esc(a.name)} (${num(a.shops)} فروشگاه)</option>`).join("")}</optgroup>
      </select>
      <h3>فاصله (برای «نزدیک من»)</h3>
      <div class="opts">${radio("radius", "", "مهم نیست", !ctx.radius_m)}${RADII.map(([v, l]) => radio("radius", v, l, ctx.radius_m === v)).join("")}</div>
      <h3>بودجه (سقف قیمت)</h3>
      <div class="opts">${radio("budget", "", "مهم نیست", !ctx.max_price)}${BUDGETS.map((b) => radio("budget", b, tomanShort(b), ctx.max_price === b)).join("")}</div>
      <h3>زمان بازدید</h3>
      <div class="opts">
        <select name="day"><option value="">الان</option>${DAYS_FA.map((d, i) => `<option value="${i}" ${ctx.day === i ? "selected" : ""}>${d}</option>`).join("")}</select>
        <select name="hour">${[9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21].map((h) => `<option value="${h}" ${(ctx.hour ?? 11) === h ? "selected" : ""}>ساعت ${num(h)}</option>`).join("")}</select>
      </div>
      <h3>شرایط خرید</h3>
      <div class="opts">${CONDITIONS.map(([k, l]) => check(k, l)).join("")}</div>
      <h3>ترتیب فروشنده‌ها</h3>
      <div class="opts">${radio("sort", "price", "ارزان‌ترین", ctx.sort !== "distance")}${radio("sort", "distance", "نزدیک‌ترین", ctx.sort === "distance")}</div>
      <p class="muted small">قیمت‌ها ثبت‌شده‌ی فروشنده‌اند؛ بودجه فقط روی قیمت‌های عادی اعمال می‌شود. «باز» یعنی ساعت کاری اعلام‌شده؛ فروشگاه‌های بدون ساعت ثبت‌شده حذف می‌شوند.</p>
    </form>
    <div class="sheet-actions">
      <button type="button" class="btn" id="sheetReset">پاک کردن</button>
      <button type="button" class="btn primary" id="sheetApply">نمایش نتایج</button>
    </div>`;
  sheet.showModal();
  document.getElementById("sheetX").onclick = () => sheet.close();
  document.getElementById("sheetReset").onclick = () => { ctx = { ...DEFAULT_CTX }; applyCtx(); };
  document.getElementById("sheetApply").onclick = async () => {
    const fd = new FormData(document.getElementById("sheetForm"));
    const next = { ...DEFAULT_CTX };
    const placeSel = fd.get("place");
    if (placeSel) {
      const [kind, name] = placeSel.split("|");
      const src = kind === "area" ? AREAS.areas : AREAS.passages;
      const a = src.find((x) => x.name === name);
      next.place = { kind, name, lat: a?.lat, lon: a?.lon };
    } else if (fd.get("placeKind") === "me") {
      next.place = await myLocation();
    }
    next.radius_m = Number(fd.get("radius")) || null;
    next.max_price = Number(fd.get("budget")) || null;
    next.min_price = null;
    next.day = fd.get("day") === "" ? null : Number(fd.get("day"));
    next.hour = Number(fd.get("hour")) || 11;
    next.sort = fd.get("sort") || "price";
    for (const [k] of CONDITIONS) next[k] = fd.get(k) === "on";
    ctx = next;
    applyCtx();
  };
}

function myLocation() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) { alert("مرورگر شما موقعیت‌یابی را پشتیبانی نمی‌کند؛ یک محله یا پاساژ انتخاب کنید."); return resolve(null); }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ kind: "me", name: "نزدیک من", lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => { alert("دسترسی به موقعیت داده نشد؛ یک محله یا پاساژ انتخاب کنید."); resolve(null); },
      { timeout: 8000, maximumAge: 60000 },
    );
  });
}

// One-tap "use my location": nearest sellers first, no extra filter needed.
async function useMyLocation() {
  const me = await myLocation();
  if (!me) return false;
  ctx = { ...ctx, place: me, sort: "distance" };
  saveCtx();
  renderCtxBar();
  route();
  return true;
}

function applyCtx() {
  saveCtx();
  document.getElementById("sheet").close();
  renderCtxBar();
  route();
}

document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-ask]");
  if (a) { $q.value = a.dataset.ask; ask(a.dataset.ask); }
  const clear = e.target.closest("[data-clear-ctx]");
  if (clear) {
    e.preventDefault();
    e.stopPropagation();
    const key = clear.dataset.clearCtx;
    if (key === "all") ctx = { ...DEFAULT_CTX };
    else ctx = { ...ctx, ...(CLEAR_CTX[key] || {}) };
    if (lastAsk) {
      const drop = key === "all" ? null : new Set(CLEAR_UNDO_KEYS[key] || []);
      lastAsk.understood = drop ? lastAsk.understood.filter((x) => !drop.has(x.key)) : [];
    }
    applyCtx();
    return;
  }
  if (e.target.closest("[data-open-sheet]")) openSheet();
  if (e.target.closest("[data-use-location]")) useMyLocation();
  const area = e.target.closest("[data-pick-area]");
  if (area) {
    const [kind, name, lat, lon] = area.dataset.pickArea.split("|");
    ctx = { ...ctx, place: { kind, name, lat: Number(lat), lon: Number(lon) }, sort: "distance" };
    applyCtx();
  }
  const relax = e.target.closest("[data-relax]");
  if (relax) { ctx = { ...ctx, ...(RELAX_CTX[relax.dataset.relax] || {}) }; applyCtx(); }
});

// ---------- compare list (max 3 products) ----------
const COMPARE_MAX = 3;
let compareList = (() => { try { return JSON.parse(localStorage.getItem("sc_compare") || "[]"); } catch { return []; } })();
function saveCompare() { try { localStorage.setItem("sc_compare", JSON.stringify(compareList)); } catch { /* private mode */ } renderTray(); }
function inCompare(id) { return compareList.some((x) => x.id === id); }
function toggleCompare(id, title) {
  if (inCompare(id)) compareList = compareList.filter((x) => x.id !== id);
  else if (compareList.length >= COMPARE_MAX) { alert("حداکثر ۳ کالا را می‌توانید مقایسه کنید."); return; }
  else compareList.push({ id, title });
  saveCompare();
  document.querySelectorAll(`[data-compare="${CSS.escape(id)}"].cmp`).forEach((b) => {
    b.classList.toggle("on", inCompare(id));
    b.textContent = inCompare(id) ? "✓ در مقایسه" : "+ مقایسه";
  });
}
function compareBtn(id, title) {
  return `<button type="button" class="chip cmp ${inCompare(id) ? "on" : ""}" data-compare="${esc(id)}" data-title="${esc(title)}">${inCompare(id) ? "✓ در مقایسه" : "+ مقایسه"}</button>`;
}
function renderTray() {
  let tray = document.getElementById("tray");
  if (!tray) { tray = document.createElement("div"); tray.id = "tray"; tray.className = "tray"; document.body.appendChild(tray); }
  tray.hidden = compareList.length === 0 || location.hash.startsWith("#/compare");
  tray.innerHTML = `<span>${num(compareList.length)} کالا برای مقایسه</span>
    <span><button type="button" class="btn" data-compare-clear>پاک کردن</button>
    <a class="btn primary" href="#/compare">مقایسه</a></span>`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-compare]");
  if (b) {
    e.preventDefault(); e.stopPropagation();
    toggleCompare(b.dataset.compare, b.dataset.title);
    if (location.hash.startsWith("#/compare")) route();
  }
  if (e.target.closest("[data-compare-clear]")) { compareList = []; saveCompare(); if (location.hash.startsWith("#/compare")) route(); }
}, true);

function fmtDistance(m) {
  if (m < 50) return "کمتر از ۵۰ متر";
  if (m < 1000) return `${num(Math.round(m / 10) * 10)} متر`;
  return `${new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(m / 1000)} کیلومتر`;
}

async function viewCompare() {
  if (compareList.length < 2) {
    $view.innerHTML = `${backLink()}<div class="card empty-state">برای مقایسه حداقل ۲ کالا انتخاب کنید (دکمه‌ی «+ مقایسه» روی هر کالا).</div>`;
    return;
  }
  loading();
  let c;
  try { c = await getJSON(`/api/compare?ids=${compareList.map((x) => encodeURIComponent(x.id)).join(",")}&${filterParams()}`); } catch (e) { return failed(e); }
  const P = c.products;
  const best = (vals, fn) => { const ok = vals.filter((v) => v != null); return ok.length ? fn(...ok) : null; };
  const minPrice = best(P.map((p) => p.min_price), Math.min);
  const maxSellers = best(P.map((p) => p.sellers_match), Math.max);
  const nearest = best(P.map((p) => p.nearest_m), Math.min);
  const cell = (v, isBest) => `<td class="${isBest ? "best" : ""}">${v}</td>`;
  const row = (label, cells) => `<tr><th>${esc(label)}</th>${cells.join("")}</tr>`;
  const scope = c.filters_active ? " (با شرایط شما)" : "";
  const rows = [
    row(`کمترین قیمت ثبت‌شده${scope}`, P.map((p) => cell(p.min_price != null ? esc(tomanShort(p.min_price)) : unknown("ثبت نشده"), p.min_price === minPrice))),
    row("میانه‌ی قیمت همه‌ی فروشنده‌ها", P.map((p) => cell(p.median_price != null ? esc(tomanShort(p.median_price)) : unknown(), false))),
    row(`فروشنده${scope}`, P.map((p) => cell(`${num(p.sellers_match)} از ${num(p.sellers_total)}`, p.sellers_match === maxSellers))),
    row("باز در زمان بازدید", P.map((p) => cell(num(p.open_match), false))),
    ...(nearest != null ? [row("نزدیک‌ترین فروشنده", P.map((p) => cell(p.nearest_m != null ? esc(fmtDistance(p.nearest_m)) : unknown(), p.nearest_m === nearest)))] : []),
    row("فروشنده‌ی اقساطی", P.map((p) => cell(num(p.installment_sellers), false))),
    row("فروشنده با گارانتی", P.map((p) => cell(num(p.warranty_sellers), false))),
    row("تازه‌ترین تغییر قیمت", P.map((p) => cell(p.last_change ? esc(ago(p.last_change)) : unknown(), false))),
  ];
  const specRows = c.spec_rows.map((r) =>
    `<tr class="${r.same ? "same" : ""}"><th>${esc(r.key)}</th>${r.values.map((v) => `<td>${v == null ? unknown() : esc(v)}</td>`).join("")}</tr>`).join("");
  const n = P.length + 1;
  $view.innerHTML = `
    ${backLink()}
    <h1>مقایسه</h1>
    <p class="muted small">قیمت‌ها ثبت‌شده‌ی فروشنده‌اند؛ موجودی تأیید نشده. بهترین مقدار هر ردیف سبز است.</p>
    <div class="cmp-wrap"><table class="cmp-table">
      <thead><tr><th></th>${P.map((p) => `<th><a href="#/p/${esc(p.product_id)}">${thumb(p.image, p.title)}<div class="title-2 small">${esc(p.title)}</div></a>
        <button type="button" class="chip" data-compare="${esc(p.product_id)}" data-title="${esc(p.title)}">حذف</button></th>`).join("")}</tr></thead>
      <tbody>${rows.join("")}</tbody>
      <tbody><tr><th colspan="${n}" class="group">مشخصات فنی
        <label class="small" style="font-weight:400;margin-inline-start:8px"><input type="checkbox" id="diffOnly"> فقط تفاوت‌ها</label></th></tr>
        ${specRows || `<tr><td colspan="${n}">${unknown("مشخصات مشترکی ثبت نشده")}</td></tr>`}</tbody>
    </table></div>`;
  document.getElementById("diffOnly").onchange = (e) => document.querySelector(".cmp-table").classList.toggle("diff-only", e.target.checked);
}

// ---------- assistant: a sentence becomes filters (rules; /api/ask) ----------
let lastAsk = null; // {text, query, understood, ambiguous, patch, intent}
const UNDO = { // understood item -> how to take it back in ctx
  budget: { max_price: null, min_price: null }, installments: { installments: false }, torobpay: { torobpay: false },
  in_person_pay: { in_person_pay: false }, fast: { fast: false }, warranty: { warranty: false }, open: { open: false },
  passage: { place: null }, area: { place: null }, at: { day: null }, cheap: {},
};

async function ask(text) {
  let r;
  try { r = await getJSON(`/api/ask?text=${encodeURIComponent(text)}`); } catch { location.hash = `#/search?q=${encodeURIComponent(text)}`; return; }
  const patch = r.ctx_patch || {};
  if ("max_price" in patch || "min_price" in patch) { ctx.max_price = null; ctx.min_price = null; }
  ctx = { ...ctx, ...patch };
  saveCtx();
  renderCtxBar();
  lastAsk = { text, query: r.query || text, understood: r.understood, ambiguous: r.ambiguous, patch, intent: r.intent,
    category: r.category, source: r.source, thinking: Boolean(r.rules_struggled && r.llm_available) };
  if (!r.query && patch.place?.kind === "passage") { location.hash = `#/passage/${encodeURIComponent(patch.place.name)}`; return; }
  const target = `#/search?q=${encodeURIComponent(lastAsk.query)}`;
  if (location.hash === target) route(); else location.hash = target;
  if (lastAsk.thinking) smartAsk(text, patch);
}

// The rules answered at once; for a free description, ask the LLM in the background and update.
async function smartAsk(text, rulesPatch) {
  let r;
  try { r = await getJSON(`/api/ask?llm=1&text=${encodeURIComponent(text)}`); } catch { r = null; }
  if (!lastAsk || lastAsk.text !== text) return; // the user moved on
  if (!r || r.source !== "rules+llm" || r.llm_error) { lastAsk.thinking = false; lastAsk.llmFailed = true; route(); return; }
  for (const k of Object.keys(rulesPatch)) if (!(k in r.ctx_patch)) ctx[k] = DEFAULT_CTX[k];
  ctx = { ...ctx, ...r.ctx_patch };
  saveCtx();
  renderCtxBar();
  lastAsk = { ...lastAsk, query: r.query || lastAsk.query, understood: r.understood, intent: r.intent,
    category: r.category, source: r.source, thinking: false, smart: true, llmAdded: r.llm_added || [] };
  const target = `#/search?q=${encodeURIComponent(lastAsk.query)}`;
  if (location.hash === target) route(); else location.hash = target;
}

function understoodBanner(q) {
  if (!lastAsk || lastAsk.query !== q || (!lastAsk.understood.length && lastAsk.intent === "search" && !lastAsk.thinking && !lastAsk.smart)) return "";
  const items = lastAsk.understood.map((u) =>
    `<button type="button" class="chip reason-good" data-undo="${esc(u.key)}" title="برداشتن">${esc(u.label === "بودجه" ? "بودجه: " + u.text : u.label)} ✕</button>`).join("");
  let amb = "";
  if (lastAsk.ambiguous?.budget_unit && (ctx.max_price || ctx.min_price)) {
    const v = ctx.max_price || ctx.min_price;
    const other = v >= 1e6 ? v / 1000 : v * 1000;
    amb = `<div class="small" style="margin-top:6px">«تومن» را ${esc(tomanShort(v))} در نظر گرفتیم.
      <button type="button" class="chip cmp" data-budget-alt="${other}">منظورم ${esc(tomanShort(other))} بود</button></div>`;
  }
  const guide = lastAsk.intent === "choose"
    ? `<div class="actions"><a class="btn primary" href="#/guide?q=${encodeURIComponent(q)}">کمکم کن مدل مناسب را انتخاب کنم</a></div>` : "";
  const status = lastAsk.thinking ? `<div class="small" style="color:var(--primary)">⏳ دستیار هوشمند دارد جمله‌تان را دقیق‌تر می‌خواند…</div>`
    : lastAsk.smart ? `<div class="small" style="color:var(--primary)">✨ با کمک دستیار هوشمند خوانده شد${(lastAsk.llmAdded || []).includes("query") ? " (نام کالا از توضیح شما)" : ""}</div>`
    : lastAsk.llmFailed ? `<div class="small muted">دستیار هوشمند در دسترس نبود؛ خواندنِ قاعده‌مند نشان داده شده.</div>` : "";
  return `<div class="card small">${status}<div class="muted">از جمله‌ی شما فهمیدم${lastAsk.query ? ` — کالا: «${esc(lastAsk.query)}»` : ""}:</div>
    <div class="reasons">${items || '<span class="muted">شرط خاصی نبود</span>'}</div>${amb}${guide}</div>`;
}

document.addEventListener("click", (e) => {
  const u = e.target.closest("[data-undo]");
  if (u) {
    ctx = { ...ctx, ...(UNDO[u.dataset.undo] || {}) };
    if (lastAsk) lastAsk.understood = lastAsk.understood.filter((x) => x.key !== u.dataset.undo);
    applyCtx();
  }
  const alt = e.target.closest("[data-budget-alt]");
  if (alt) {
    const v = Number(alt.dataset.budgetAlt);
    if (ctx.max_price) ctx.max_price = v; else ctx.min_price = v;
    if (lastAsk) lastAsk.ambiguous = {};
    applyCtx();
  }
});

// ---------- guided model choice (R1) ----------
async function viewGuide(params) {
  const q = params.get("q") || "";
  const answers = {};
  for (const [k, v] of params) if (k.startsWith("a.")) answers[k.slice(2)] = v;
  loading();
  let g;
  const qs = new URLSearchParams({ q });
  for (const [k, v] of Object.entries(answers)) qs.set(`a.${k}`, v);
  try { g = await getJSON(`/api/guide?${qs}&${filterParams()}`); } catch (e) { return failed(e); }
  if (!g.category) {
    $view.innerHTML = `${backLink()}<div class="card empty-state">برای «${esc(q)}» دسته‌ای پیدا نشد. نام کالا را ساده‌تر بنویسید (مثلاً «هندزفری»).</div>`;
    return;
  }
  const said = params.get("t") || "";
  const link = (qid, value) => {
    const next = new URLSearchParams({ q });
    if (said) next.set("t", said);
    for (const [k, v] of Object.entries(answers)) if (k !== qid) next.set(`a.${k}`, v);
    if (value != null && answers[qid] !== value) next.set(`a.${qid}`, value);
    return `#/guide?${next}`;
  };
  const questions = g.questions.map((qq, i) => `
    <section class="card">
      <div class="muted small">سؤال ${num(i + 1)} از ${num(g.questions.length)}</div>
      <strong>${esc(qq.text)}</strong>
      <div class="chips" style="margin-top:8px">
        ${qq.options.map((o) => `<a class="chip ${answers[qq.id] === o.value ? "pill-open" : ""}" href="${link(qq.id, o.value)}">${esc(o.label)} <span class="muted">(${num(o.count)})</span></a>`).join("")}
        <a class="chip ${answers[qq.id] ? "" : "pill-open"}" href="${link(qq.id, null)}">مهم نیست</a>
      </div>
    </section>`).join("");
  const sugg = g.suggestions.map((p) => `
    <article class="card">
      <a class="product-card" href="#/p/${esc(p.product_id)}">
        ${thumb(p.image, p.title)}
        <div class="grow">
          <div class="title-2">${esc(p.title)}</div>
          <div class="between"><span class="price">میانه ${esc(tomanShort(p.median_price))}</span>
            <span class="chip">${num(p.sellers_match)} فروشنده${filtersActive() ? " با شرایط شما" : ""}</span></div>
        </div>
      </a>
      <div class="reasons"><span class="chip reason-good">${esc(p.why)}</span></div>
      <div class="ai-why" data-ai-why="${esc(p.product_id)}"></div>
      <div class="actions">${compareBtn(p.product_id, p.title)}<a class="btn" href="#/p/${esc(p.product_id)}">فروشنده‌ها</a></div>
    </article>`).join("");
  const compareAll = g.suggestions.length >= 2
    ? `<button type="button" class="btn primary" data-compare-set='${esc(JSON.stringify(g.suggestions.map((p) => ({ id: p.product_id, title: p.title }))))}'>مقایسه‌ی این ${num(g.suggestions.length)} مدل</button>` : "";
  $view.innerHTML = `
    ${backLink()}
    <section class="card">
      <h1 style="margin-top:0">راهنمای انتخاب: ${esc(g.category)}</h1>
      <p class="muted small" style="margin:0">سؤال‌ها از روی همین ${num(g.products)} مدلِ موجود در فروشگاه‌ها ساخته شده؛ عدد کنار هر گزینه یعنی چند مدل با آن جور است.</p>
    </section>
    ${aiGuideBox(q, g.category, said)}
    ${questions}
    <h2>${num(g.matching)} مدل با جواب‌های شما · ۳ پیشنهاد</h2>
    ${sugg || `<div class="card muted">مدلی با این جواب‌ها نماند؛ یکی از جواب‌ها را «مهم نیست» کنید.</div>`}
    <div class="actions">${compareAll}<a class="btn" href="#/search?q=${encodeURIComponent(q)}">همه‌ی نتایج «${esc(q)}»</a></div>`;
  aiGuide(q, g.category, answers, said);
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-compare-set]");
  if (b) { compareList = JSON.parse(b.dataset.compareSet).slice(0, COMPARE_MAX); saveCompare(); location.hash = "#/compare"; }
});

// ---------- seller contact (R5, R6) and alternatives (R7) ----------
const QUESTIONS_FA = {
  in_stock: "موجود دارید؟", price_now: "قیمت هنوز همین است؟", hours_today: "امروز تا کی باز هستید؟",
  warranty: "گارانتی؟", installments: "اقساط / ترب‌پی؟", hold: "تا رسیدنم نگه می‌دارید؟",
};
let contacts = (() => { try { return JSON.parse(localStorage.getItem("sc_contacts") || "{}"); } catch { return {}; } })();
function saveContacts() { try { localStorage.setItem("sc_contacts", JSON.stringify(contacts)); } catch { /* private mode */ } }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function contactChip(offerId) {
  const c = contacts[offerId];
  if (!c) return "";
  const t = new Date(c.at).toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" });
  if (c.status === "no_answer") return `<span class="chip pill-warn">پاسخی نداد (${t})</span>`;
  if (!c.facts.in_stock) return `<span class="chip pill-closed">ناموجود — پاسخ فروشنده (${t})</span>`;
  const price = c.facts.price_now ? ` · قیمت امروز ${tomanShort(c.facts.price_now)}${c.facts.price_changed ? " (تغییر کرده)" : ""}` : "";
  const hold = c.facts.hold_until ? ` · نگه می‌دارد تا ${c.facts.hold_until}` : "";
  return `<span class="chip pill-open">موجودی تأیید شد (${t})${esc(price)}${esc(hold)}</span>`;
}

async function sendContact(offerId, questions, onStep) {
  const body = { offer_id: offerId, questions, visit_at: visitISO(), request_id: `${offerId}-${Date.now()}` };
  const r = await fetch("/api/contact", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status}`);
  const res = await r.json();
  if (onStep) onStep("sent", res);
  await sleep(res.reply.delay_s * 400); // a short, honest "waiting" — the reply is simulated
  contacts[offerId] = { status: res.reply.status, facts: res.reply.facts, at: Date.now(), shop: res.shop_name };
  saveContacts();
  if (onStep) onStep("reply", res);
  return res;
}

function bubble(text, mine, note) {
  return `<div class="bubble ${mine ? "mine" : ""}">${esc(text).replace(/\n/g, "<br>")}${note ? `<div class="bubble-note">${esc(note)}</div>` : ""}</div>`;
}

function openContactSheet(offerId, shopName, productId, shopId) {
  const sheet = document.getElementById("sheet");
  const defaults = ["in_stock", "price_now", "hours_today"];
  sheet.innerHTML = `
    <form method="dialog" id="contactForm">
      <h3 style="margin-top:0">پرسیدن از «${esc(shopName || "فروشنده")}»</h3>
      <p class="muted small">دستیار این سؤال‌ها را از طرف شما می‌پرسد و جواب را این‌جا می‌آورد.</p>
      <div class="opts">${Object.entries(QUESTIONS_FA).map(([k, l]) =>
        `<label class="opt"><input type="checkbox" name="q" value="${k}" ${defaults.includes(k) ? "checked" : ""}><span>${esc(l)}</span></label>`).join("")}</div>
      <div id="chat" class="chat"></div>
      <div id="contactAfter"></div>
    </form>
    <div class="sheet-actions">
      <button type="button" class="btn" id="contactClose">بستن</button>
      <button type="button" class="btn primary" id="contactSend">بپرس</button>
    </div>`;
  sheet.showModal();
  document.getElementById("contactClose").onclick = () => { sheet.close(); route(); };
  document.getElementById("contactSend").onclick = async (ev) => {
    ev.target.disabled = true;
    const qs = [...sheet.querySelectorAll("input[name=q]:checked")].map((i) => i.value);
    const chat = document.getElementById("chat");
    try {
      await askSeller(offerId, qs.length ? qs : defaults, chat);
      const c = contacts[offerId];
      const after = document.getElementById("contactAfter");
      after.innerHTML = `<div style="margin:8px 0">${contactChip(offerId)}</div>`;
      if (c.status === "no_answer" || !c.facts.in_stock) after.innerHTML += await alternativesHTML(productId, shopId, c.status === "no_answer" ? "no_answer" : "out_of_stock");
    } catch (e) {
      chat.innerHTML = `<div class="notice">ارسال نشد (${esc(e.message)}). دوباره امتحان کنید.</div>`;
      ev.target.disabled = false;
    }
  };
}

async function alternativesHTML(productId, shopId, reason) {
  let a;
  try {
    const at = visitISO();
    a = await getJSON(`/api/alternatives?product_id=${encodeURIComponent(productId)}&shop_id=${encodeURIComponent(shopId || "")}&reason=${reason}${at ? "&at=" + at : ""}`);
  } catch { return ""; }
  const title = reason === "no_answer" ? "فروشنده جواب نداد؛ این‌ها همین کالا را دارند:" : reason === "closed" ? "این فروشگاه بسته است؛ جایگزین‌ها:" : "این فروشنده ندارد؛ این‌ها همین کالا را دارند:";
  const sellers = a.sellers.map((s) => `
    <div class="alt">
      <div class="between"><a href="#/s/${esc(s.shop_id)}"><strong>${esc(s.name)}</strong></a>${openPill(s.open_now, s.hours_status)}</div>
      <div class="muted small">${esc(s.where || s.area || "")} · ${esc(s.why)}</div>
      <div class="between"><span>${s.price ? esc(toman(s.price)) : unknown("قیمت ثبت نشده")}</span>
        ${contacts[s.offer_id] ? "" : ""}</div>
    </div>`).join("");
  const subs = (a.substitutes || []).map((p) => `
    <div class="alt" data-pid="${esc(p.product_id)}"><a href="#/p/${esc(p.product_id)}"><strong>${esc(p.title)}</strong></a>
      <div class="ai-why"></div>
      <div class="reasons">${p.why.map((w) => `<span class="chip reason-info">${esc(w)}</span>`).join("")}</div></div>`).join("");
  return `<div class="card small" style="margin-top:8px">
      <strong>${esc(title)}</strong> <span class="muted">(${num(a.sellers_total)} فروشنده‌ی باز)</span>
      ${sellers || `<p class="muted">فروشنده‌ی باز دیگری برای همین کالا نیست.</p>`}
      ${subs ? `<p style="margin:8px 0 4px"><strong>کالاهای مشابه:</strong></p><div class="ai-subs" data-ai="alt" data-product="${esc(productId)}" data-shop="${esc(shopId || "")}" data-reason="${esc(reason)}">${subs}<div class="ai-advice"></div></div>` : ""}
      ${(a.category_shops || []).length ? `<p style="margin:8px 0 4px"><strong>فروشگاه‌هایی که در همین دسته کار می‌کنند:</strong></p>
        <p class="muted small" style="margin:0">این کالا را ثبت نکرده‌اند؛ موجودی نامعلوم است — بپرسید.</p>
        ${a.category_shops.map((s) => `<div class="alt"><div class="between"><a href="#/s/${esc(s.shop_id)}"><strong>${esc(s.name)}</strong></a>${openPill(s.open_now, s.hours_status)}</div>
          <div class="muted small">${esc(s.where || s.area || "")}${s.distance_m != null ? " · " + esc(faDigits(fmtDistance(s.distance_m))) : ""}</div></div>`).join("")}` : ""}
    </div>`;
}

// The agent asks the first N matching sellers and reports which confirmed (R6).
async function askTopSellers(p, n = 3) {
  const box = document.getElementById("agentBox");
  const targets = p.sellers.slice(0, n);
  box.innerHTML = `<div class="card small"><strong>دستیار دارد از ${num(targets.length)} فروشنده می‌پرسد…</strong><div id="agentLog"></div></div>`;
  const log = document.getElementById("agentLog");
  const results = [];
  for (const e of targets) {
    const line = document.createElement("div");
    line.className = "muted";
    line.textContent = `… ${e.shop.name}`;
    log.appendChild(line);
    try {
      const res = await sendContact(e.offers[0].offer_id, ["in_stock", "price_now", "hours_today", "hold"]);
      results.push({ e, res });
      line.innerHTML = `${esc(e.shop.name)}: ${contactChip(e.offers[0].offer_id)}`;
    } catch { line.textContent = `${e.shop.name}: ارسال نشد`; }
  }
  const ok = results.filter((r) => r.res.reply.status === "answered" && r.res.reply.facts.in_stock);
  const best = ok.sort((a, b) => (a.res.reply.facts.price_now || 1e18) - (b.res.reply.facts.price_now || 1e18))[0];
  const summary = best
    ? `${num(ok.length)} از ${num(results.length)} فروشنده موجودی را تأیید کردند. ارزان‌ترینِ تأییدشده: «${esc(best.e.shop.name)}»${best.res.reply.facts.price_now ? " با " + esc(toman(best.res.reply.facts.price_now)) : ""}${best.e.shop.location_short ? " — " + esc(best.e.shop.location_short) : ""}.`
    : "هیچ‌کدام موجودی را تأیید نکردند.";
  box.querySelector(".card").insertAdjacentHTML("beforeend", `<p style="margin:8px 0 0"><strong>${summary}</strong></p>
    <p class="muted small" style="margin:4px 0 0">پاسخ‌ها نمایشی‌اند (شماره‌ها در داده ساختگی است).</p>
    ${best ? `<div class="actions">${planBtn(best.e.shop.shop_id, best.e.shop.name, p.title, p.product_id, best.e.offers[0].offer_id)}<a class="btn" href="#/plan">دیدن برنامه</a></div>` : ""}`);
  if (!best) box.querySelector(".card").insertAdjacentHTML("beforeend", await alternativesHTML(p.product_id, targets[0]?.shop.shop_id, "out_of_stock"));
}

document.addEventListener("click", (e) => {
  const c = e.target.closest("[data-contact]");
  if (c) openContactSheet(c.dataset.contact, c.dataset.shopName, c.dataset.productId, c.dataset.shopId);
  const alt = e.target.closest("[data-alts]");
  if (alt) {
    const box = document.getElementById(`alts-${alt.dataset.shopId}`);
    if (box) alternativesHTML(alt.dataset.alts, alt.dataset.shopId, alt.dataset.reason || "closed").then((h) => { box.innerHTML = h; });
  }
});

// ---------- visit plan (R4) and where-in-passage (R8) ----------
let planList = (() => { try { return JSON.parse(localStorage.getItem("sc_plan") || "[]"); } catch { return []; } })();
function savePlan() { try { localStorage.setItem("sc_plan", JSON.stringify(planList)); } catch { /* private mode */ } renderPlanLink(); }
function inPlan(shopId) { return planList.some((x) => x.shop_id === shopId); }
function renderPlanLink() {
  const a = document.getElementById("planLink");
  if (a) a.textContent = planList.length ? `🗺 برنامه‌ی بازدید (${num(planList.length)})` : "🗺 برنامه‌ی بازدید";
}
function planBtn(shopId, name, item, productId, offerId) {
  return `<button type="button" class="btn ${inPlan(shopId) ? "on" : ""}" data-plan-add="${esc(shopId)}" data-plan-name="${esc(name || "")}"
    data-plan-item="${esc(item || "")}" data-plan-product="${esc(productId || "")}" data-plan-offer="${esc(offerId || "")}">${inPlan(shopId) ? "✓ در برنامه" : "+ برنامه‌ی بازدید"}</button>`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-plan-add]");
  if (b) {
    const id = b.dataset.planAdd;
    if (inPlan(id)) planList = planList.filter((x) => x.shop_id !== id);
    else planList.push({ shop_id: id, name: b.dataset.planName, item: b.dataset.planItem, product_id: b.dataset.planProduct, offer_id: b.dataset.planOffer });
    savePlan();
    document.querySelectorAll(`[data-plan-add="${CSS.escape(id)}"]`).forEach((x) => {
      x.classList.toggle("on", inPlan(id));
      x.textContent = inPlan(id) ? "✓ در برنامه" : "+ برنامه‌ی بازدید";
    });
  }
  const rm = e.target.closest("[data-plan-remove]");
  if (rm) { planList = planList.filter((x) => x.shop_id !== rm.dataset.planRemove); savePlan(); route(); }
  const w = e.target.closest("[data-where]");
  if (w) {
    const box = document.getElementById(`where-${w.dataset.where}`);
    if (box) getJSON(`/api/shops/${encodeURIComponent(w.dataset.where)}/where`).then((d) => { box.innerHTML = whereHTML(d); }).catch(() => {});
  }
});

function whereHTML(w) {
  if (!w.passage) return `<p class="small muted">این فروشگاه در پاساژ ثبت نشده؛ آدرس: ${esc(w.address || "نامشخص")}</p>`;
  const unit = w.unit ? `واحد ${w.unit}` : w.plaque && !w.plaque_is_building ? `پلاک ${w.plaque}` : "واحد نامشخص";
  const where = [`${w.passage_kind || "پاساژ"} ${w.passage}`, w.floor_label || "طبقه نامشخص", unit].join("، ");
  const bnote = w.plaque_is_building && !w.unit ? `<div class="muted">«پلاک ${esc(w.plaque)}» پلاک ساختمان است و چند فروشگاه دیگر هم همین را دارند؛ شماره‌ی واحد را از فروشنده بپرسید.</div>` : "";
  const count = w.floor_shops ? `${num(w.floor_shops)} فروشگاه در این طبقه، ` : "";
  const nb = w.neighbours.filter((n) => n.unit).slice(0, 5).map((n) =>
    `<li>${esc(n.unit)} — ${esc(n.name || "")}${n.category ? ` <span class="muted">(${esc(n.category)})</span>` : ""}</li>`).join("");
  return `<div class="small" style="margin-top:6px"><strong>${esc(where)}</strong>${bnote}
    <div class="muted">${count}${num(w.passage_shops)} فروشگاه در این پاساژ (در داده‌ی ترب).</div>
    ${nb ? `<div style="margin-top:4px">واحدهای نزدیک${w.floor_shops ? " در همین طبقه" : ""} برای پیدا کردن راه:</div><ul style="margin:2px 0;padding-inline-start:18px">${nb}</ul>` : ""}
    <div class="muted">آدرس ثبت‌شده: ${esc(w.address || "نامشخص")}</div>
    <div class="ai-dir" data-ai="dir" data-shop="${esc(w.shop_id)}"></div></div>`;
}

async function viewPlan() {
  if (!planList.length) {
    $view.innerHTML = `${backLink()}<div class="card empty-state">برنامه‌ی بازدید خالی است. روی کارت هر فروشنده «+ برنامه‌ی بازدید» را بزنید.</div>`;
    return;
  }
  loading();
  const qs = new URLSearchParams({ shops: planList.map((x) => x.shop_id).join(",") });
  const at = visitISO();
  if (at) qs.set("at", at);
  if (ctx.place?.lat != null) { qs.set("lat", ctx.place.lat); qs.set("lon", ctx.place.lon); }
  let pl;
  try { pl = await getJSON(`/api/plan?${qs}`); } catch (e) { return failed(e); }
  const byShop = Object.fromEntries(planList.map((x) => [x.shop_id, x]));
  const start = ctx.place ? `از ${ctx.place.kind === "me" ? "موقعیت شما" : ctx.place.name}` : "از اولین فروشگاه";
  const warn = pl.warnings.map((w) => {
    const item = byShop[w.shop_id];
    const alt = w.kind === "closed" && item?.product_id
      ? `<button type="button" class="btn" data-alts="${esc(item.product_id)}" data-shop-id="${esc(w.shop_id)}" data-reason="closed">جایگزین</button>` : "";
    return `<div class="notice">${esc(w.text)} ${alt}<div id="alts-${esc(w.shop_id)}"></div></div>`;
  }).join("");
  let prev = ctx.place?.lat != null ? [ctx.place.lat, ctx.place.lon] : null;
  const stops = pl.stops.map((st, i) => {
    const item = byShop[st.shop_id] || {};
    const route = st.lat && prev ? `https://nshn.ir?origin=${prev[0]},${prev[1]}&destination=${st.lat},${st.lon}&vehicle=d` : (st.lat ? neshan(st.lat, st.lon) : null);
    if (st.lat) prev = [st.lat, st.lon];
    return `
      <article class="card stop">
        <div class="between"><span class="chip pill-open">${num(i + 1)} · ساعت ${esc(st.arrive)}</span>${openPill(st.open_on_arrival, st.hours_status)}</div>
        <div style="margin-top:6px"><a href="#/s/${esc(st.shop_id)}"><strong>${esc(st.name || "فروشگاه")}</strong></a>
          ${item.item ? `<div class="small muted">برای: ${esc(item.item)}</div>` : ""}</div>
        <div class="small">${esc(st.where || "محل دقیق در آدرس نیست")}${st.walk_m ? ` · ${num(st.walk_m)} متر پیاده از قبلی` : ""}</div>
        ${item.offer_id && contacts[item.offer_id] ? `<div style="margin-top:6px">${contactChip(item.offer_id)}</div>` : ""}
        <div class="actions">
          ${item.offer_id ? `<button type="button" class="btn primary" data-contact="${esc(item.offer_id)}" data-shop-name="${esc(st.name)}" data-product-id="${esc(item.product_id)}" data-shop-id="${esc(st.shop_id)}">از فروشنده بپرس</button>` : ""}
          <button type="button" class="btn" data-where="${esc(st.shop_id)}">کجای پاساژ؟</button>
          ${route ? `<a class="btn" target="_blank" rel="noopener" href="${route}">مسیر</a>` : ""}
          <button type="button" class="btn" data-plan-remove="${esc(st.shop_id)}">حذف</button>
        </div>
        <div id="where-${esc(st.shop_id)}"></div>
      </article>`;
  }).join("");
  const when = ctx.day == null ? "الان" : `${DAYS_FA[ctx.day]} ساعت ${num(ctx.hour ?? 11)}`;
  $view.innerHTML = `
    ${backLink()}
    <h1>برنامه‌ی بازدید</h1>
    <p class="muted small">شروع ${esc(start)}، ${esc(when)} · ${num(pl.stops.length)} توقف · ${num(pl.total_walk_m)} متر پیاده · پایان حدود ساعت ${esc(pl.finish)}
      · <a href="javascript:void 0" data-open-sheet>تغییر زمان یا محل شروع</a></p>
    <p class="muted small">ترتیب: نزدیک‌ترین توقف بعدی؛ فروشگاه‌های یک ساختمان پشت سر هم و از طبقه‌ی پایین به بالا. ۱۰ دقیقه برای هر توقف.</p>
    ${warn}${stops}`;
}

// ---------- passage page: what is inside, floor by floor ----------
async function viewPassage(name) {
  loading();
  let p;
  const at = visitISO();
  try { p = await getJSON(`/api/passages/${encodeURIComponent(name)}${at ? "?at=" + at : ""}`); } catch (e) { return failed(e); }
  const when = ctx.day == null ? "الان" : `${DAYS_FA[ctx.day]} ساعت ${num(ctx.hour ?? 11)}`;
  const floors = p.floors.map((f, i) => `
    <details class="card" ${i < 2 ? "open" : ""}>
      <summary><strong>${esc(faDigits(f.label))}</strong> <span class="muted small">(${num(f.shops.length)} فروشگاه)</span></summary>
      ${f.shops.map((s) => `
        <a class="alt" href="#/s/${esc(s.shop_id)}" style="display:block;color:inherit">
          <div class="between"><span><strong>${esc(s.unit ? faDigits(s.unit) : "واحد نامشخص")}</strong> · ${esc(s.name || "")}</span>${openPill(s.open_now, s.hours_status)}</div>
          <div class="muted small">${s.categories.length ? esc(s.categories.join("، ")) : "زمینه‌ی فعالیت ثبت نشده"}${s.n_offers ? ` · ${num(s.n_offers)} کالا در ترب` : " · کالایی ثبت نکرده"}</div>
        </a>`).join("")}
    </details>`).join("");
  $view.innerHTML = `
    ${backLink()}
    <section class="card">
      <h1 style="margin-top:0">${esc(p.kind || "پاساژ")} ${esc(p.name)}</h1>
      <p class="muted small" style="margin:0">${num(p.shops)} فروشگاه در داده‌ی ترب · ${num(p.open_now)} باز در ${esc(when)}${p.area ? ` · محله ${esc(p.area)}` : ""}</p>
      <div class="chips" style="margin-top:8px">${p.top_categories.slice(0, 8).map((c) => `<span class="chip">${esc(c)}</span>`).join("")}</div>
      <div class="actions">
        <button type="button" class="btn primary" data-search-in="${esc(p.name)}" data-lat="${p.lat ?? ""}" data-lon="${p.lon ?? ""}">جست‌وجو فقط در این پاساژ</button>
        ${p.lat ? `<a class="btn" target="_blank" rel="noopener" href="${neshan(p.lat, p.lon)}">مسیر تا پاساژ</a>` : ""}
      </div>
    </section>
    ${floors}`;
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-search-in]");
  if (b) {
    ctx = { ...ctx, place: { kind: "passage", name: b.dataset.searchIn, lat: Number(b.dataset.lat) || null, lon: Number(b.dataset.lon) || null } };
    saveCtx();
    renderCtxBar();
    $q.value = "";
    $q.placeholder = `در ${b.dataset.searchIn} دنبال چه هستید؟`;
    $q.focus();
  }
});

// ---------- R26: where this kind of product is sold («بورس»), with a location widget ----------
// A self-drawn mini-map from our own data (no map tiles: works offline and where tile servers are blocked).
function miniMapSVG(center, places, you, label) {
  const W = 320, H = 220, pad = 22;
  const mPerDegLat = 111320, mPerDegLon = 111320 * Math.cos(center.lat * Math.PI / 180);
  const others = places.filter((p) => p.name !== label).slice(0, 10);
  const pts = [...others, ...(you && you.lat != null ? [you] : [])];
  // fit the scale to what is shown (at least 150 m around the target)
  const reach = Math.max(150, ...pts.map((p) => Math.max(Math.abs((p.lon - center.lon) * mPerDegLon), Math.abs((p.lat - center.lat) * mPerDegLat) * W / H)));
  const scale = (W / 2 - pad) / (reach * 1.1); // px per metre
  const xy = (p) => [W / 2 + (p.lon - center.lon) * mPerDegLon * scale, H / 2 - (p.lat - center.lat) * mPerDegLat * scale];
  const placed = [[W / 2 - 40, H / 2 - 34, W / 2 + 40, H / 2 - 16]]; // the target's own label
  const free = (x, y, w) => {
    const box = [x - w / 2, y - 18, x + w / 2, y - 6];
    if (box[0] < 2 || box[2] > W - 2 || box[1] < 2) return false;
    if (placed.some((b) => !(box[2] < b[0] || box[0] > b[2] || box[3] < b[1] || box[1] > b[3]))) return false;
    placed.push(box);
    return true;
  };
  let me = "";
  if (you && you.lat != null) {
    const [x, y] = xy(you);
    const below = free(x, y + 26, 22); // "you" label under the dot when there is room
    me = `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6" fill="#2563eb"/>` +
      (below ? `<text x="${x.toFixed(1)}" y="${(y + 18).toFixed(1)}" font-size="10" text-anchor="middle" fill="#2563eb">شما</text>` : "");
  }
  const dots = others.map((p) => {
    const [x, y] = xy(p);
    const label = free(x, y, p.name.length * 5.6) ? `<text x="${x.toFixed(1)}" y="${(y - 8).toFixed(1)}" font-size="9" text-anchor="middle" fill="#475569">${esc(p.name)}</text>` : "";
    return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${Math.min(7, 2.5 + Math.sqrt(p.shops) / 3).toFixed(1)}" fill="#94a3b8" opacity=".7"/>${label}`;
  }).join("");
  const barM = reach > 600 ? 500 : reach > 250 ? 200 : 100;
  const bar = barM * scale;
  return `<svg viewBox="0 0 ${W} ${H}" class="minimap" direction="ltr" role="img" aria-label="${esc(label)}">
    <rect width="${W}" height="${H}" rx="12" fill="#eef2f6"/>
    ${dots}${me}
    <circle cx="${W / 2}" cy="${H / 2}" r="9" fill="#0f766e"/><circle cx="${W / 2}" cy="${H / 2}" r="15" fill="none" stroke="#0f766e" stroke-width="2" opacity=".5"/>
    <text x="${W / 2}" y="${H / 2 - 20}" font-size="12" font-weight="700" text-anchor="middle" fill="#0f766e">${esc(label)}</text>
    <line x1="${pad}" y1="${H - 12}" x2="${pad + bar}" y2="${H - 12}" stroke="#334155" stroke-width="2"/>
    <text x="${pad + bar / 2}" y="${H - 16}" font-size="9" text-anchor="middle" fill="#334155">${faDigits(barM)} متر</text>
    <text x="${W - 8}" y="16" font-size="10" text-anchor="end" fill="#334155">شمال ↑</text>
  </svg>`;
}

async function mapWidget(lat, lon, label) {
  let places = [];
  try { places = (await getJSON(`/api/nearby?lat=${lat}&lon=${lon}`)).places; } catch { /* draw the target alone */ }
  return `<div class="mapw">
      ${miniMapSVG({ lat, lon }, places, ctx.place, label)}
      <div class="actions">
        <a class="btn primary" target="_blank" rel="noopener" href="${neshan(lat, lon)}">مسیریابی با نشان</a>
        <a class="btn" target="_blank" rel="noopener" href="${gmaps(lat, lon)}">گوگل مپ</a>
      </div>
      <p class="muted small" style="margin:4px 0 0">نقشه‌ی ساده از روی داده‌ی ترب: نقطه‌ی سبز مقصد، نقطه‌های خاکستری پاساژهای اطراف${ctx.place ? "، نقطه‌ی آبی محل انتخابی شما" : ""}.</p>
    </div>`;
}
function placeSearchLink(name) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name + " تهران")}`;
}

function hubsHTML(h, intro) {
  const data = (h.data_hubs || []).map((x, i) => `
    <div class="alt">
      <div class="between"><strong>${esc(x.kind === "passage" ? `${x.passage_kind || "پاساژ"} ${x.name}` : `محله ${x.name}`)}</strong>
        <span class="chip">${num(x.shops)} فروشنده${x.open ? ` · ${num(x.open)} باز` : ""}</span></div>
      <div class="actions">
        ${x.kind === "passage" ? `<a class="btn" href="#/passage/${encodeURIComponent(x.name)}">داخل پاساژ</a>` : ""}
        ${x.lat ? `<button type="button" class="btn" data-map="${x.lat},${x.lon}" data-map-label="${esc(x.name)}" data-map-box="hubmap-${i}">نقشه</button>` : ""}
      </div>
      <div id="hubmap-${i}"></div>
    </div>`).join("");
  const known = h.known ? `<div class="alt"><div class="small"><strong>بورس‌های شناخته‌شده‌ی «${esc(h.known.label)}» در تهران:</strong></div>
      <div class="chips" style="margin-top:4px">${h.known.places.map((p) => `<a class="chip" target="_blank" rel="noopener" href="${placeSearchLink(p)}">${esc(p)}</a>`).join("")}</div>
      <p class="muted small" style="margin:4px 0 0">منبع: بلاگ «بلد» — بیرون از داده‌ی ترب.</p></div>` : "";
  const llm = h.llm ? `<div class="alt"><div class="small"><strong>پیشنهاد دستیار هوشمند:</strong></div>
      <div class="chips" style="margin-top:4px">${h.llm.places.map((p) => `<a class="chip" target="_blank" rel="noopener" href="${placeSearchLink(p)}">${esc(p)}</a>`).join("")}</div>
      <p class="muted small" style="margin:4px 0 0">${esc(h.llm.note)}</p></div>` : "";
  if (!data && !known && !llm) return "";
  return `<section class="card">
      <h2 style="margin-top:0">${esc(intro)}</h2>
      ${data ? `<p class="muted small" style="margin:0">از داده‌ی ترب: جاهایی که بیشترین فروشنده‌ی این دسته را دارند.</p>${data}` : ""}
      ${known}${llm}
    </section>`;
}

async function loadHubs(boxId, params, intro) {
  const box = document.getElementById(boxId);
  if (!box) return;
  const at = visitISO();
  try {
    const h = await getJSON(`/api/hubs?${new URLSearchParams(params)}${at ? "&at=" + at : ""}`);
    box.innerHTML = hubsHTML(h, intro);
  } catch { box.innerHTML = ""; }
}
document.addEventListener("click", (e) => {
  const m = e.target.closest("[data-map]");
  if (m) {
    const [lat, lon] = m.dataset.map.split(",").map(Number);
    const box = document.getElementById(m.dataset.mapBox);
    if (box) { if (box.innerHTML) box.innerHTML = ""; else mapWidget(lat, lon, m.dataset.mapLabel).then((h) => { box.innerHTML = h; }); }
  }
});

// ---------- R27: two-sided contact — the seller answers in one tap (mock channel) ----------
const SELLER_WAIT_S = 30;

async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

function rememberReply(offerId, reply, shopName) {
  contacts[offerId] = { status: reply.status, facts: reply.facts, at: Date.now(), shop: shopName };
  saveContacts();
}

// Send to the seller's inbox; wait for a one-tap answer; after SELLER_WAIT_S fall back to the automatic demo reply.
async function askSeller(offerId, questions, chat) {
  const res = await postJSON("/api/contact", { offer_id: offerId, questions, visit_at: visitISO(), mode: "seller", request_id: `${offerId}-${Date.now()}` });
  const panel = `<a target="_blank" rel="noopener" href="/#/seller/${encodeURIComponent(res.shop_id)}">پنل فروشنده (نمایشی) را باز کنید</a>`;
  if (res.status === "reused") {
    chat.innerHTML = bubble(res.message, true) + bubble(res.reply.text, false,
      "این فروشنده کمتر از ۳ ساعت پیش به همین سؤال جواب داده؛ دوباره مزاحمش نشدیم.");
    rememberReply(offerId, res.reply, res.shop_name);
    return;
  }
  chat.innerHTML = bubble(res.message, true, `فرستاده شد به ${res.channel}`) +
    `<div class="typing">… منتظر جواب فروشنده (${num(SELLER_WAIT_S)} ثانیه)</div><p class="small muted">برای دیدن طرف فروشنده: ${panel}</p>`;
  const id = res.request.id;
  for (let waited = 0; waited < SELLER_WAIT_S; waited += 2) {
    await sleep(2000);
    if (!document.getElementById("chat")) return; // sheet closed
    let st;
    try { st = await getJSON(`/api/contact/${encodeURIComponent(id)}`); } catch { continue; }
    if (st.status === "answered") {
      chat.innerHTML = bubble(res.message, true) + bubble(st.reply.text, false, "پاسخ فروشنده از پنل فروشنده (نمایشی)");
      rememberReply(offerId, st.reply, res.shop_name);
      return;
    }
  }
  const auto = await sendContact(offerId, questions); // falls back to the automatic simulated reply
  chat.innerHTML = bubble(res.message, true) + bubble(auto.reply.text, false, `فروشنده در ${num(SELLER_WAIT_S)} ثانیه جواب نداد؛ ${auto.note}`);
}

let sellerTimer = null;
let sellerSig = "";
async function viewSeller(shopId, refresh = false) {
  clearTimeout(sellerTimer);
  let d;
  try { d = await getJSON(`/api/seller/${encodeURIComponent(shopId)}/inbox`); } catch (e) { if (refresh) return; return failed(e); }
  const sig = d.requests.map((r) => r.id + r.status).join("|");
  const busy = document.activeElement && $view.contains(document.activeElement) && document.activeElement.matches("input, select");
  const again = () => { sellerTimer = setTimeout(() => { if (location.hash.startsWith("#/seller/")) viewSeller(shopId, true); }, 4000); };
  if (refresh && (sig === sellerSig || busy)) return again(); // never redraw under the seller's finger
  sellerSig = sig;
  const hours = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21];
  const items = d.requests.map((r) => {
    const qs = r.questions.map((q) => QUESTIONS_FA[q] || q).join(" · ");
    const head = `<div class="between"><strong>${esc(r.product_title || "کالا")}</strong><span class="chip ${r.status === "waiting" ? "pill-warn" : "pill-open"}">${r.status === "waiting" ? "منتظر جواب شما" : "جواب داده شد"}</span></div>
      <div class="muted small">قیمت ثبت‌شده‌ی شما: ${r.recorded_price ? esc(toman(r.recorded_price)) : "ثبت نشده"} · سؤال‌ها: ${esc(qs)}</div>`;
    if (r.status !== "waiting") {
      const a = r.answer;
      return `<article class="card">${head}<div class="small" style="margin-top:6px">جواب شما: ${a.in_stock ? "موجود" : "ناموجود"}${a.price_now ? ` · ${esc(toman(a.price_now))}` : ""}${a.hold_until ? ` · نگه‌داری تا ${esc(a.hold_until)}` : ""}</div></article>`;
    }
    return `<article class="card" data-req="${esc(r.id)}">${head}
      <div class="actions">
        <button type="button" class="btn primary" data-answer="same">✅ موجود، همان قیمت</button>
        <button type="button" class="btn" data-answer="none">❌ ندارم</button>
      </div>
      <div class="actions">
        <input type="number" inputmode="numeric" placeholder="قیمت امروز (تومان)" class="price-in" style="flex:1;min-width:0;padding:8px;border:1px solid var(--line);border-radius:10px">
        <button type="button" class="btn" data-answer="price">✅ موجود، با این قیمت</button>
      </div>
      <label class="small" style="display:block;margin-top:6px">نگه می‌دارم تا ساعت
        <select class="hold-in"><option value="">نه</option>${hours.map((h) => `<option value="${h}:00">${num(h)}</option>`).join("")}</select></label>
    </article>`;
  }).join("");
  $view.innerHTML = `
    ${backLink()}
    <section class="card">
      <h1 style="margin-top:0">پنل فروشنده (نمایشی)</h1>
      <p class="small" style="margin:0"><strong>${esc(d.shop.name || "")}</strong>${d.shop.passage ? ` · ${esc(d.shop.passage)}` : ""}</p>
      <p class="muted small">در نسخه‌ی واقعی این سؤال‌ها به‌صورت اعلان در اپ فروشنده یا پیامک می‌رسد. فروشنده بدون تماس تلفنی، با یک لمس جواب می‌دهد؛ اگر به همین سؤال تازه جواب داده باشد، دستیار دوباره نمی‌پرسد.</p>
    </section>
    ${items || `<div class="card empty-state">سؤالی از خریداران نیست. از صفحه‌ی کالا «از فروشنده بپرس» را بزنید.</div>`}`;
  if (location.hash.startsWith("#/seller/")) again();
}
document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-answer]");
  if (!b) return;
  const card = b.closest("[data-req]");
  const kind = b.dataset.answer;
  const price = Number(card.querySelector(".price-in").value) || null;
  if (kind === "price" && !price) { card.querySelector(".price-in").focus(); return; }
  b.disabled = true;
  try {
    await postJSON("/api/seller/reply", { request_id: card.dataset.req, in_stock: kind !== "none",
      price_now: kind === "price" ? price : null, hold_until: card.querySelector(".hold-in").value || null });
  } catch { b.disabled = false; return; }
  viewSeller(location.hash.slice("#/seller/".length));
});

// ---------- R29: review without a reviews dataset — market signals + labeled AI summary ----------
async function loadReview(productId) {
  const box = document.getElementById("reviewBox");
  if (!box) return;
  let r;
  try { r = await getJSON(`/api/products/${encodeURIComponent(productId)}/review`); } catch { return; }
  const notes = r.signals.notes.map((n) => `<li class="${n.kind === "warn" ? "warn-text" : ""}">${esc(faDigits(n.text))}</li>`).join("");
  const aiPart = (ai) => ai ? `
      <div style="margin-top:8px">
        ${ai.good_for ? `<p class="small" style="margin:0 0 4px"><strong>مناسب برای:</strong> ${esc(ai.good_for)}</p>` : ""}
        ${ai.strengths.length ? `<p class="small" style="margin:4px 0 0"><strong>نقاط قوت</strong></p><ul class="small" style="margin:0;padding-inline-start:18px">${ai.strengths.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        ${ai.weaknesses.length ? `<p class="small" style="margin:4px 0 0"><strong>نقاط ضعف</strong></p><ul class="small" style="margin:0;padding-inline-start:18px">${ai.weaknesses.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        ${ai.check_in_shop.length ? `<p class="small" style="margin:4px 0 0"><strong>در مغازه این‌ها را چک کنید</strong></p><ul class="small" style="margin:0;padding-inline-start:18px">${ai.check_in_shop.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        <p class="muted small" style="margin:6px 0 0">${esc(ai.label)}</p>
      </div>` : "";
  box.innerHTML = `<section class="card">
      <h2 style="margin-top:0">بررسی کالا</h2>
      <p class="muted small" style="margin:0">از داده‌ی ترب (نشانه‌های بازار، نه نظر کاربران):</p>
      <ul class="small" style="margin:4px 0 0;padding-inline-start:18px">${notes || "<li>نشانه‌ی خاصی نیست.</li>"}</ul>
      <div id="aiReview">${r.ai ? aiPart(r.ai) : r.llm_available ? `<button type="button" class="btn" id="aiReviewBtn" style="margin-top:8px">✨ جمع‌بندی هوشمند: نقاط قوت، ضعف و چک‌لیست خرید</button>` : ""}</div>
    </section>`;
  const btn = document.getElementById("aiReviewBtn");
  if (btn) btn.onclick = async () => {
    btn.disabled = true;
    btn.textContent = "⏳ در حال جمع‌بندی…";
    try {
      const x = await getJSON(`/api/products/${encodeURIComponent(productId)}/review?llm=1`);
      document.getElementById("aiReview").innerHTML = x.ai ? aiPart(x.ai) : `<p class="muted small">جمع‌بندی هوشمند در دسترس نیست.</p>`;
    } catch { btn.disabled = false; btn.textContent = "دوباره امتحان کنید"; }
  };
}

// ---------- R30: colour / size chips (clothing, shoes, any product whose sellers list variants) ----------
let variantPick = { color: null, size: null };
function variantChips(p) {
  const v = p.variants || { colors: [], sizes: [] };
  if (!v.colors.length && !v.sizes.length) return "";
  const group = (axis, title, items) => items.length ? `
    <div style="margin-top:6px"><span class="small muted">${title}:</span>
      <div class="chips" style="margin-top:4px">${items.map((x) => `<button type="button" class="chip ${variantPick[axis] === x.value ? "pill-open" : ""}" data-variant="${axis}" data-value="${esc(x.value)}">${esc(faDigits(x.value))} <span class="muted">(${num(x.sellers)})</span></button>`).join("")}</div></div>` : "";
  return `<section class="card">
      <strong>رنگ و سایز</strong> <span class="muted small">از عنوان‌هایی که فروشنده‌ها ثبت کرده‌اند؛ عدد = چند فروشنده</span>
      ${group("size", "سایز", v.sizes)}${group("color", "رنگ", v.colors)}
      ${variantPick.color || variantPick.size ? `<p class="small" style="margin:6px 0 0">فقط فروشنده‌هایی که «${esc(faDigits([variantPick.size, variantPick.color].filter(Boolean).join(" / ")))}» را ثبت کرده‌اند نشان داده می‌شوند. <a href="javascript:void 0" data-variant-clear>همه</a></p>` : ""}
    </section>`;
}
function offerMatchesVariant(o) {
  return (!variantPick.color || o.color === variantPick.color) && (!variantPick.size || o.size === variantPick.size);
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-variant]");
  if (b) {
    const axis = b.dataset.variant;
    variantPick[axis] = variantPick[axis] === b.dataset.value ? null : b.dataset.value;
    route();
  }
  if (e.target.closest("[data-variant-clear]")) { variantPick = { color: null, size: null }; route(); }
});

// ---------- data ----------
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}
function loading() { $view.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>'; }
function backLink() { return `<a class="back" href="javascript:history.back()">→ بازگشت</a>`; }
function failed(err) {
  $view.innerHTML = `${backLink()}<div class="card empty-state">مشکلی پیش آمد (${esc(err.message)}). دوباره امتحان کنید.</div>`;
}

// ---------- views ----------
function viewHome() {
  $q.value = "";
  $view.innerHTML = "";
  const above = document.getElementById("homeAbove");
  const below = document.getElementById("homeBelow");
  above.hidden = false;
  below.hidden = false;
  above.innerHTML = `
    <h1 class="home-title">دستیار خرید حضوری در تهران</h1>
    <p class="home-lead">کالا را پیدا کنید، فروشنده‌ها را مقایسه کنید، بروید.</p>`;
  below.innerHTML = `
    <div id="homeLocation" class="home-location">${homeLocationHTML()}</div>
    <div class="chips home-examples">${EXAMPLES.slice(0, 4).map((e) => `<button type="button" class="chip" data-ask="${esc(e)}">${esc(e)}</button>`).join("")}</div>
    <p class="home-note">قیمت‌ها ثبت‌شده‌ی ترب‌اند · موجودی را قبل از رفتن بپرسید</p>
    ${agentHomeCard()}`;
  if (ctx.place?.lat != null) loadNearbyChips();
}

function homeLocationHTML() {
  const pl = ctx.place;
  if (pl?.lat != null) {
    const label = pl.kind === "me" ? "موقعیت شما" : pl.name;
    return `<div class="home-loc-row"><span>📍 ${esc(label)}</span>
      <button type="button" class="home-loc-btn" data-use-location>${pl.kind === "me" ? "به‌روزرسانی" : "استفاده از موقعیت من"}</button>
      <button type="button" class="home-loc-btn" data-clear-ctx="place">پاک کردن</button></div>
      <div class="chips home-nearby" id="homeNearby"></div>`;
  }
  return `<button type="button" class="home-loc-main" data-use-location>📍 موقعیت من را پیدا کن</button>
    <p class="home-loc-hint">تا نزدیک‌ترین فروشگاه‌ها و پاساژها را نشان دهم · <button type="button" class="home-loc-link" data-open-sheet>انتخاب دستی محله</button></p>`;
}

// Passages within walking range of the shopper's point, as one-tap "search around there" chips.
async function loadNearbyChips() {
  const box = document.getElementById("homeNearby");
  if (!box) return;
  try {
    const { places } = await getJSON(`/api/nearby?lat=${ctx.place.lat}&lon=${ctx.place.lon}&radius_m=1500`);
    if (!places.length) { box.remove(); return; }
    box.innerHTML = `<span class="small">نزدیک شما:</span>` + places.slice(0, 5).map((p) =>
      `<button type="button" class="chip" data-pick-area="passage|${esc(p.name)}|${p.lat}|${p.lon}">${esc(p.name)} · ${esc(faDigits(fmtDistance(p.distance_m)))}</button>`).join("");
  } catch { box.remove(); }
}

async function viewSearch(q) {
  $q.value = lastAsk && lastAsk.query === q ? lastAsk.text : q;
  if (!q.trim()) return viewHome();
  loading();
  let data;
  const allCats = new URLSearchParams(location.hash.split("?")[1] || "").get("all") === "1";
  try { data = await getJSON(`/api/search?q=${encodeURIComponent(q)}&${filterParams()}${allCats ? "&all_cats=1" : ""}`); } catch (e) { return failed(e); }
  if (!data.items.length) {
    const hint = data.filters_active
      ? `<p>با شرایطی که انتخاب کرده‌اید فروشنده‌ای پیدا نشد.</p>
         <div class="actions" style="justify-content:center">${(data.relax || []).map((r) => `<button class="btn" data-relax="${esc(r.filter)}">بدون «${esc(r.label)}»: ${num(r.products)} کالا</button>`).join("")}</div>
         <button class="btn primary" data-open-sheet>تغییر شرایط</button>`
      : "<p>کلمه‌ی کوتاه‌تر یا نام دیگری امتحان کنید.</p>";
    $view.innerHTML = backLink() + understoodBanner(q) + `<div id="aiBox"></div><div class="card empty-state">برای «${esc(q)}» چیزی پیدا نشد.${hint}</div><div id="hubsBox"></div>`;
    aiSearch(q);
    loadHubs("hubsBox", { q, llm: 1 }, data.filters_active ? "جاهایی که این کالا معمولاً فروخته می‌شود:" : "این کالا را در فروشگاه‌های داده پیدا نکردیم؛ بورسش در تهران:");
    return;
  }
  const loose = data.mode === "or" ? `<div class="notice">همه‌ی کلمه‌ها با هم پیدا نشد؛ نتایج نزدیک را نشان می‌دهیم.</div>` : "";
  const scope = data.filters_active ? " · فقط کالاهایی که فروشنده‌ای با شرایط شما دارند" : "";
  const focus = data.focus_category
    ? `<p class="small">فقط دسته‌ی «${esc(data.focus_category)}» · <a href="#/search?q=${encodeURIComponent(q)}&all=1">همه‌ی دسته‌ها</a></p>` : "";
  const few = (data.relax || []).length
    ? `<div class="card small">فقط ${num(data.items.length)} کالا با همه‌ی شرایط شما. با برداشتن یکی:
        <div class="actions">${data.relax.map((r) => `<button class="btn" data-relax="${esc(r.filter)}">بدون «${esc(r.label)}»: ${num(r.products)} کالا</button>`).join("")}</div></div>` : "";
  const guideLink = !(lastAsk && lastAsk.query === q && lastAsk.intent === "choose")
    ? `<p class="small"><a href="#/guide?q=${encodeURIComponent(q)}">مدلش را نمی‌دانید؟ با چند سؤال کمکتان می‌کنم ←</a></p>` : "";
  const fixedWords = Object.entries(data.corrected || {});
  const typo = fixedWords.length
    ? `<p class="small">نتایج برای ${fixedWords.map(([a, b]) => `«${esc(b)}» (به‌جای «${esc(a)}»)`).join("، ")}</p>` : "";
  $view.innerHTML = backLink() + understoodBanner(q) + typo + `<div id="aiBox"></div>` + loose + focus + few + guideLink + `<p class="muted small">مرتب‌شده بر اساس شباهت و تعداد فروشنده${scope}</p>` +
    data.items.map((p) => productCard(p, data.filters_active)).join("") + `<div id="hubsBox"></div>`;
  if (data.mode === "or") loadHubs("hubsBox", { q, llm: 1 }, "دقیقاً همین را پیدا نکردیم؛ بورس این کالا در تهران:");
  aiSearch(q);
}

function productCard(p, filtered) {
  const from = filtered ? p.match_min_price : p.min_price;
  const price = from != null
    ? `<span class="price">از ${esc(tomanShort(from))}</span>`
    : unknown("قیمت ثبت نشده");
  const sellers = filtered ? `${num(p.match_shops)} از ${num(p.n_shops)} فروشنده با شرایط شما` : `${num(p.n_shops)} فروشنده`;
  const open = p.open_shops ? `<div class="small" style="color:var(--open)">${num(p.open_shops)} فروشنده باز در زمان بازدید</div>` : "";
  return `
    <article class="card product-card">
      <a class="product-link" href="#/p/${esc(p.product_id)}">
        ${thumb(p.image, p.title)}
        <div class="grow">
          <div class="title-2">${esc(p.title)}</div>
          <div class="muted small">${esc(p.category || "")}${p.brand ? " · " + esc(p.brand) : ""}</div>
          <div class="between">${price}<span class="chip">${sellers}</span></div>
          ${open || ""}
        </div>
      </a>
      <div class="actions" style="margin-top:8px">${compareBtn(p.product_id, p.title)}</div>
    </article>`;
}

let variantProduct = null;
async function viewProduct(id) {
  if (variantProduct !== id) { variantPick = { color: null, size: null }; variantProduct = id; }
  loading();
  let p;
  try { p = await getJSON(`/api/products/${encodeURIComponent(id)}?${filterParams()}`); } catch (e) { return failed(e); }
  const img = p.images.length ? `<img class="hero-img" src="${esc(p.images[0])}" alt="${esc(p.title)}">` : "";
  const specs = p.specs.length
    ? `<details class="card"><summary>مشخصات فنی (${num(p.specs.length)})</summary><dl class="facts">${
        p.specs.slice(0, 60).map((s) => `<dt>${esc(s.key)}</dt><dd>${esc(s.value)}</dd>`).join("")}</dl></details>`
    : `<div class="card muted small">مشخصات فنی برای این کالا ثبت نشده.</div>`;
  const summary = [
    `${num(p.sellers_total)} فروشنده`,
    p.min_price != null ? `کمترین ${tomanShort(p.min_price)}` : null,
    p.median_price != null && p.sellers_total > 2 ? `میانه ${tomanShort(p.median_price)}` : null,
  ].filter(Boolean).join(" · ");
  $view.innerHTML = `
    ${backLink()}
    <section class="card">
      ${img}
      <h1>${esc(p.title)}</h1>
      <div class="chips">
        ${p.category ? `<span class="chip">${esc(p.category)}</span>` : ""}
        <span class="chip">برند: ${p.brand ? esc(p.brand) : "نامشخص"}</span>
        <span class="chip">نام انگلیسی/مدل: ${p.english_name ? esc(p.english_name) : "ثبت نشده"}</span>
      </div>
      <div class="between" style="margin-top:8px"><span class="muted small">${esc(summary)}</span>${compareBtn(p.product_id, p.title)}</div>
    </section>
    ${specs}
    <div id="reviewBox"></div>
    <div class="notice">موجودی تأیید نشده است: هر فروشنده این کالا را در ترب ثبت کرده، اما موجود بودن آن امروز معلوم نیست. قیمت‌ها «قیمت ثبت‌شده» با زمان آخرین تغییر هستند.</div>
    ${p.price_spread && p.price_spread > 3 ? `<div class="notice">قیمت‌ها تا ${num(Math.round(p.price_spread))} برابر با هم فرق دارند. ممکن است واحد فروش (عدد، متر، حلقه، بسته) یا اصل/غیراصل بودن کالا فرق کند؛ واحد فروش در داده ثبت نشده. قبل از خرید بپرسید.</div>` : ""}
    <h2>فروشنده‌ها (${ctx.sort === "distance" && ctx.place ? "نزدیک‌ترین اول" : "ارزان‌ترین اول"})</h2>
    ${filterSummary(p)}
    ${pickCard(p)}
    ${p.sellers.length ? `<div class="actions" style="margin-bottom:10px"><button type="button" class="btn primary" id="askTop">🤖 از ${num(Math.min(3, p.sellers.length))} فروشنده‌ی اول بپرس</button></div><div id="agentBox"></div>` : ""}
    ${variantChips(p)}
    ${p.sellers
      .map((e) => ({ ...e, offers: e.offers.filter(offerMatchesVariant) }))
      .filter((e) => e.offers.length)
      .map((e) => sellerCard({ ...e, product_id: p.product_id, product_title: p.title })).join("")}
    <div id="hubsBox"></div>`;
  if (p.category) loadHubs("hubsBox", { category: p.category, q: p.title }, `بورس «${p.category}» در تهران`);
  loadReview(p.product_id);
  aiPick(p.product_id);
  const askBtn = document.getElementById("askTop");
  if (askBtn) askBtn.onclick = () => { askBtn.disabled = true; askTopSellers(p); };
}

function pickCard(p) {
  if (!p.pick) return "";
  const e = p.sellers.find((x) => x.shop.shop_id === p.pick.shop_id);
  if (!e) return "";
  return `<section class="card pick">
    <div class="small" style="color:var(--primary);font-weight:700">⭐ پیشنهاد دستیار</div>
    <div class="between"><a href="#/s/${esc(e.shop.shop_id)}"><strong>${esc(e.shop.name)}</strong></a><span class="price">${esc(toman(e.best_price))}</span></div>
    <div class="muted small">${esc(e.shop.location_short || e.shop.area || "")}</div>
    <ul class="small" style="margin:6px 0 0;padding-inline-start:18px">${p.pick.why.map((w) => `<li class="${w.startsWith("احتیاط") ? "warn-text" : ""}">${esc(faDigits(w))}</li>`).join("")}</ul>
    <div id="aiPickBox"></div>
    <div class="actions">
      <button type="button" class="btn primary" data-contact="${esc(e.offers[0].offer_id)}" data-shop-name="${esc(e.shop.name)}" data-product-id="${esc(p.product_id)}" data-shop-id="${esc(e.shop.shop_id)}">از این فروشنده بپرس</button>
      ${planBtn(e.shop.shop_id, e.shop.name, p.title, p.product_id, e.offers[0].offer_id)}
    </div>
  </section>`;
}

function filterSummary(p) {
  if (!p.filters_active) return "";
  if (!p.sellers.length) {
    const relax = p.relax.map((r) => `<button class="btn" data-relax="${esc(r.filter)}">بدون «${esc(r.label)}»: ${num(r.sellers)} فروشنده</button>`).join("");
    return `<div class="card">
      <p style="margin-top:0">هیچ‌کدام از ${num(p.sellers_total)} فروشنده با همه‌ی شرایط شما جور نیست.</p>
      ${relax ? `<p class="muted small">با برداشتن یکی از این شرایط:</p><div class="actions">${relax}</div>` : ""}
      <div class="actions"><button class="btn primary" data-open-sheet>تغییر شرایط</button></div>
    </div>`;
  }
  return `<p class="muted small">${num(p.sellers.length)} از ${num(p.sellers_total)} فروشنده با شرایط شما · <a href="javascript:void 0" data-open-sheet>تغییر</a></p>`;
}

function sellerCard(entry) {
  const s = entry.shop;
  const best = entry.offers[0];
  const priceLine = best.price != null
    ? `<span class="price-big">${esc(toman(best.price))}</span>`
    : `<span class="chip pill-unknown">${esc(best.price_note || "قیمت نامشخص")}</span>`;
  const note = best.price != null && best.price_note ? `<div><span class="chip pill-warn">${esc(best.price_note)}</span></div>` : "";
  const age = ageDays(entry.last_change);
  const ageText = entry.last_change
    ? `آخرین تغییر قیمت: ${esc(ago(entry.last_change))}${age > 90 ? " — شاید قدیمی باشد" : ""}`
    : "زمان تغییر قیمت ثبت نشده";
  const variants = entry.offers.length > 1 ? `<span class="chip">${num(entry.offers.length)} مدل/رنگ</span>` : "";
  const warranty = best.warranty_kind === "yes" ? `گارانتی: ${esc(best.warranty_text)}`
    : best.warranty_kind === "none" ? "بدون گارانتی (اعلام فروشنده)" : "گارانتی: نامشخص";
  const pay = (s.payment || []).map((p) => `<span class="chip" title="${esc(p.channel_text)}">${esc(p.provider)}${p.channel === "in_person" ? " · حضوری" : ""}</span>`).join("");
  return `
    <article class="card">
      <div class="between">
        <a href="#/s/${esc(s.shop_id)}"><strong>${esc(s.name || "بدون نام")}</strong></a>
        ${openPill(s.open_now, s.hours_status)}
      </div>
      <div class="muted small">${s.location_short ? esc(s.location_short) : "محل دقیق در آدرس پیدا نشد"}${s.area ? " · محله " + esc(s.area) : ""} ${nameBadge(s)}</div>
      <div class="between" style="margin-top:6px">${priceLine}${variants}</div>
      ${note}
      ${entry.distance_m != null ? `<div class="small">📍 ${esc(faDigits(fmtDistance(entry.distance_m)))} ${ctx.place?.kind === "me" ? "تا شما" : "تا " + esc(ctx.place?.name || "")}</div>` : ""}
      <div class="muted small">${ageText}</div>
      <div class="small">${warranty}</div>
      ${(entry.reasons || []).length ? `<div class="reasons">${entry.reasons.map((r) => `<span class="chip reason-${r.kind}">${esc(faDigits(r.text))}</span>`).join("")}</div>` : ""}
      ${pay ? `<div class="chips" style="margin-top:6px">${pay}</div>` : ""}
      ${best.seller_title ? `<div class="muted small">عنوان فروشنده: ${esc(best.seller_title)}</div>` : ""}
      ${contacts[best.offer_id] ? `<div style="margin-top:6px">${contactChip(best.offer_id)}</div>` : ""}
      <div class="actions">
        <button type="button" class="btn primary" data-contact="${esc(best.offer_id)}" data-shop-name="${esc(s.name)}" data-product-id="${esc(entry.product_id)}" data-shop-id="${esc(s.shop_id)}">از فروشنده بپرس</button>
        ${planBtn(s.shop_id, s.name, entry.product_title, entry.product_id, best.offer_id)}
        <a class="btn" href="#/s/${esc(s.shop_id)}">فروشگاه</a>
        ${s.lat ? `<a class="btn" target="_blank" rel="noopener" href="${neshan(s.lat, s.lon)}">مسیر</a>` : ""}
        ${s.open_now === false || (contacts[best.offer_id] && (contacts[best.offer_id].status === "no_answer" || !contacts[best.offer_id].facts.in_stock))
          ? `<button type="button" class="btn" data-alts="${esc(entry.product_id)}" data-shop-id="${esc(s.shop_id)}" data-reason="${s.open_now === false ? "closed" : "no_answer"}">جایگزین‌ها</button>` : ""}
      </div>
      <div id="alts-${esc(s.shop_id)}"></div>
    </article>`;
}

async function viewShop(id) {
  loading();
  let s;
  try { s = await getJSON(`/api/shops/${encodeURIComponent(id)}`); } catch (e) { return failed(e); }
  const todayIdx = (tehranNow().getUTCDay() + 1) % 7; // JS Sun=0 → Iranian Sat=0 (same as visitISO)
  const hours = s.hours_week.length
    ? `<table class="hours">${s.hours_week.map((h, i) => `<tr class="${i === todayIdx ? "today" : ""}"><td>${esc(h.day)}</td><td>${esc(h.text)}</td></tr>`).join("")}</table>
       <p class="muted small">ساعت‌ها را فروشنده اعلام کرده؛ تعطیلات رسمی در داده نیست.</p>`
    : unknown("ساعت کاری ثبت نشده؛ قبل از رفتن تماس بگیرید.");
  const pay = s.payment.length
    ? s.payment.map((p) => `<li>${esc(p.provider)} ${p.installments ? "(اقساطی)" : ""} — <span class="muted">${esc(p.channel_text)}</span></li>`).join("")
    : `<li>${unknown("روش پرداخت خاصی (ترب‌پی، اقساط) ثبت نشده")}</li>`;
  const fast = s.fast_delivery === 1 ? "دارد (اعلام فروشنده)" : s.fast_delivery === 0 ? "ندارد" : "نامشخص";
  const links = [
    s.instagram ? `<a class="btn" target="_blank" rel="noopener" href="${esc(s.instagram)}">اینستاگرام</a>` : "",
    s.website ? `<a class="btn" target="_blank" rel="noopener" href="${esc(s.website)}">وب‌سایت</a>` : "",
  ].join("");
  $view.innerHTML = `
    ${backLink()}
    <section class="card">
      <div class="between"><h1>${esc(s.name || "بدون نام")}</h1>${openPill(s.open_now, s.hours_status)}</div>
      ${nameBadge(s)}
      <dl class="facts">
        <dt>پاساژ/ساختمان</dt><dd>${s.passage ? `<a href="#/passage/${encodeURIComponent(s.passage)}">${esc(`${s.passage_kind} ${s.passage}`)}</a> <span class="muted small">(همه‌ی فروشگاه‌های این پاساژ)</span>` : unknown()}</dd>
        <dt>طبقه</dt><dd>${s.location_short && s.floor != null ? esc(s.location_short.split("، ").find((x) => x.includes("طبقه") || x === "همکف") || "") : unknown()}</dd>
        <dt>واحد/پلاک</dt><dd>${s.unit ? "واحد " + esc(s.unit) : s.plaque ? "پلاک " + esc(s.plaque) : unknown()}</dd>
        <dt>محله</dt><dd>${s.area ? esc(s.area) : unknown()}</dd>
        <dt>آدرس کامل</dt><dd>${s.address ? esc(s.address) : unknown()}</dd>
      </dl>
      <div class="actions">
        ${s.lat ? `<a class="btn primary" target="_blank" rel="noopener" href="${neshan(s.lat, s.lon)}">مسیریابی با نشان</a>
        <a class="btn" target="_blank" rel="noopener" href="${gmaps(s.lat, s.lon)}">گوگل مپ</a>` : ""}
        ${s.phone ? `<a class="btn" href="tel:${esc(s.phone)}" title="شماره‌ها در داده‌ی مسابقه ساختگی‌اند">تماس (شماره نمایشی)</a>` : ""}
        <a class="btn" href="#/seller/${encodeURIComponent(s.shop_id)}" title="طرف فروشنده: سؤال‌های خریداران و جواب با یک لمس">پنل فروشنده (نمایشی)</a>
        ${links}
      </div>
    </section>
    <section class="card"><h2 style="margin-top:0">کجای پاساژ؟</h2><div id="where-${esc(s.shop_id)}"><button type="button" class="btn" data-where="${esc(s.shop_id)}">نشان بده</button></div></section>
    <section class="card"><h2 style="margin-top:0">ساعت کاری</h2>${hours}</section>
    <section class="card">
      <h2 style="margin-top:0">شرایط خرید</h2>
      <ul style="margin:0;padding-inline-start:18px">${pay}</ul>
      <dl class="facts">
        <dt>ارسال فوری</dt><dd>${esc(fast)}</dd>
        <dt>کالابرگ</dt><dd>${unknown("اطلاعاتی در داده نیست")}</dd>
        <dt>پیام‌رسان (واتساپ، بله)</dt><dd>${unknown("ثبت نشده؛ فقط تلفن")}</dd>
        <dt>سابقه در ترب، مجوزها</dt><dd>${unknown("در داده نیست")}</dd>
        <dt>تصویر و معرفی فروشگاه</dt><dd>${unknown("در داده نیست")}</dd>
      </dl>
    </section>
    ${s.categories.length ? `<section class="card"><h2 style="margin-top:0">زمینه‌ی فعالیت</h2><div class="chips">${s.categories.slice(0, 30).map((c) => `<span class="chip">${esc(c)}</span>`).join("")}</div>
      ${s.n_offers === 0 ? `<p class="notice" style="margin-top:10px">این فروشگاه کالای مشخصی در ترب ثبت نکرده؛ فقط زمینه‌ی فعالیتش معلوم است. موجود بودن کالا را باید پرسید.</p>` : ""}</section>` : ""}
    <h2>کالاهای ثبت‌شده در این فروشگاه (${num(s.n_offers)})</h2>
    ${s.products.map((p) => `
      <a class="card product-card" href="#/p/${esc(p.product_id)}">
        ${thumb(p.image, p.title)}
        <div class="grow">
          <div class="title-2">${esc(p.title)}</div>
          <div class="between">${p.price != null ? `<span class="price">${esc(toman(p.price))}</span>` : unknown("قیمت ثبت نشده")}
          ${p.variants > 1 ? `<span class="chip">${num(p.variants)} مدل/رنگ</span>` : ""}</div>
          <div class="muted small">${p.last_change ? "آخرین تغییر قیمت: " + esc(ago(p.last_change)) : ""}</div>
        </div>
      </a>`).join("") || `<div class="card muted">کالایی ثبت نشده.</div>`}`;
}

// ---------- router ----------
function isHomeRoute(path) {
  return !path || path === "/";
}

function setHomeChrome(on) {
  document.body.classList.toggle("is-home", on);
  if (!on) {
    const above = document.getElementById("homeAbove");
    const below = document.getElementById("homeBelow");
    if (above) { above.hidden = true; above.innerHTML = ""; }
    if (below) { below.hidden = true; below.innerHTML = ""; }
  }
}

function route() {
  document.getElementById("sheet")?.open && document.getElementById("sheet").close();
  renderTray();
  const hash = location.hash || "#/";
  const [path, query] = hash.slice(1).split("?");
  const params = new URLSearchParams(query || "");
  const home = isHomeRoute(path) || (path.startsWith("/search") && !params.get("q")?.trim());
  setHomeChrome(home);
  renderCtxBar();
  window.scrollTo(0, 0);
  if (path.startsWith("/search")) return viewSearch(params.get("q") || "");
  if (path.startsWith("/p/")) return viewProduct(decodeURIComponent(path.slice(3)));
  if (path.startsWith("/s/")) return viewShop(decodeURIComponent(path.slice(3)));
  if (path.startsWith("/compare")) return viewCompare();
  if (path.startsWith("/guide")) return viewGuide(params);
  if (path.startsWith("/plan")) return viewPlan();
  if (path.startsWith("/seller/")) return viewSeller(decodeURIComponent(path.slice(8)));
  if (path.startsWith("/passage/")) return viewPassage(decodeURIComponent(path.slice(9)));
  return viewHome();
}

document.getElementById("searchForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $q.value.trim();
  if (q) ask(q);
});
window.addEventListener("hashchange", route);

renderCtxBar();
renderPlanLink();
getJSON("/api/meta").then((m) => {
  if (m.snapshot) $foot.textContent = `داده: نمونه‌ی ترب از فروشگاه‌های تهران · آخرین تغییر قیمت ثبت‌شده: ${dateFmt.format(new Date(m.snapshot))}`;
}).catch(() => {});
route();

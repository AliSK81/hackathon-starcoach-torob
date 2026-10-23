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
function toman(n) { return n == null ? null : `${num(n)} تومان`; }
function tomanShort(n) {
  if (n == null) return null;
  if (n >= 1e9) return `${new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 2 }).format(n / 1e9)} میلیارد تومان`;
  if (n >= 1e6) return `${new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 }).format(n / 1e6)} میلیون تومان`;
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
  return shop.name_is_real ? "" : `<span class="chip pill-unknown" title="در داده‌ی مسابقه، نام بیشتر فروشگاه‌ها ساختگی است">نام نمایشی</span>`;
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

function renderCtxBar() {
  const pl = ctx.place;
  const place = pl ? (pl.kind === "me" ? "نزدیک من" : pl.name) + (ctx.radius_m ? ` · ${RADII.find((r) => r[0] === ctx.radius_m)?.[1] || ""}` : "") : "همه‌ی محله‌ها";
  const budget = ctx.min_price && ctx.max_price ? `${tomanShort(ctx.min_price)} تا ${tomanShort(ctx.max_price)}`
    : ctx.max_price ? `تا ${tomanShort(ctx.max_price)}` : ctx.min_price ? `از ${tomanShort(ctx.min_price)} به بالا` : "هر بودجه";
  const when = ctx.day == null ? "الان" : `${DAYS_FA[ctx.day]} ساعت ${num(ctx.hour ?? 11)}`;
  const conds = CONDITIONS.filter(([k]) => ctx[k]).map(([, l]) => l);
  const chip = (on, text) => `<button type="button" class="ctxchip ${on ? "on" : ""}" data-open-sheet>${esc(text)}</button>`;
  document.getElementById("ctxbar").innerHTML =
    chip(Boolean(pl), "📍 " + place) + chip(Boolean(ctx.max_price || ctx.min_price), "💰 " + budget) +
    chip(ctx.day != null, "🕒 " + when) + chip(conds.length > 0, "💳 " + (conds.length ? conds.join("، ") : "شرایط خرید"));
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
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ kind: "me", name: "نزدیک من", lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => { alert("دسترسی به موقعیت داده نشد؛ یک محله یا پاساژ انتخاب کنید."); resolve(null); },
      { timeout: 8000 },
    );
  });
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
  if (e.target.closest("[data-open-sheet]")) openSheet();
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
    $view.innerHTML = `<div class="card empty-state">برای مقایسه حداقل ۲ کالا انتخاب کنید (دکمه‌ی «+ مقایسه» روی هر کالا).</div>`;
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
  lastAsk = { text, query: r.query || text, understood: r.understood, ambiguous: r.ambiguous, patch, intent: r.intent, category: r.category };
  const target = `#/search?q=${encodeURIComponent(lastAsk.query)}`;
  if (location.hash === target) route(); else location.hash = target;
}

function understoodBanner(q) {
  if (!lastAsk || lastAsk.query !== q || (!lastAsk.understood.length && lastAsk.intent === "search")) return "";
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
  return `<div class="card small"><div class="muted">از جمله‌ی شما فهمیدم${lastAsk.query ? ` — کالا: «${esc(lastAsk.query)}»` : ""}:</div>
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

// ---------- data ----------
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}
function loading() { $view.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>'; }
function failed(err) {
  $view.innerHTML = `<div class="card empty-state">مشکلی پیش آمد (${esc(err.message)}). دوباره امتحان کنید.</div>`;
}

// ---------- views ----------
function viewHome() {
  $q.value = "";
  $view.innerHTML = `
    <section class="card">
      <h1>دستیار خرید حضوری در تهران</h1>
      <p class="muted">کالا را پیدا کنید، فروشنده‌ها را مقایسه کنید، فروشگاهِ باز و نزدیک را انتخاب کنید و بعد بروید.</p>
      <p class="small" style="margin:0 0 6px">مثل یک فروشنده با من حرف بزنید؛ بودجه، محله، زمان و شرط پرداخت را از جمله‌تان برمی‌دارم:</p>
      <div class="chips">${EXAMPLES.map((e) => `<button type="button" class="chip" data-ask="${esc(e)}">${esc(e)}</button>`).join("")}</div>
    </section>
    <section class="notice info">
      قیمت‌ها همان قیمتی است که فروشنده در ترب ثبت کرده، با زمان آخرین تغییر. موجودی کالا را هیچ‌جا تأیید شده نشان نمی‌دهیم؛ قبل از رفتن بپرسید.
    </section>`;
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
    $view.innerHTML = understoodBanner(q) + `<div class="card empty-state">برای «${esc(q)}» چیزی پیدا نشد.${hint}</div>`;
    return;
  }
  const loose = data.mode === "or" ? `<div class="notice">همه‌ی کلمه‌ها با هم پیدا نشد؛ نتایج نزدیک را نشان می‌دهیم.</div>` : "";
  const scope = data.filters_active ? " · فقط کالاهایی که فروشنده‌ای با شرایط شما دارند" : "";
  const focus = data.focus_category
    ? `<p class="small">فقط دسته‌ی «${esc(data.focus_category)}» · <a href="#/search?q=${encodeURIComponent(q)}&all=1">همه‌ی دسته‌ها</a></p>` : "";
  const few = (data.relax || []).length
    ? `<div class="card small">فقط ${num(data.items.length)} کالا با همه‌ی شرایط شما. با برداشتن یکی:
        <div class="actions">${data.relax.map((r) => `<button class="btn" data-relax="${esc(r.filter)}">بدون «${esc(r.label)}»: ${num(r.products)} کالا</button>`).join("")}</div></div>` : "";
  $view.innerHTML = understoodBanner(q) + loose + focus + few + `<p class="muted small">مرتب‌شده بر اساس شباهت و تعداد فروشنده${scope}</p>` +
    data.items.map((p) => productCard(p, data.filters_active)).join("");
}

function productCard(p, filtered) {
  const from = filtered ? p.match_min_price : p.min_price;
  const price = from != null
    ? `<span class="price">از ${esc(tomanShort(from))}</span>`
    : unknown("قیمت ثبت نشده");
  const sellers = filtered ? `${num(p.match_shops)} از ${num(p.n_shops)} فروشنده با شرایط شما` : `${num(p.n_shops)} فروشنده`;
  const open = p.open_shops ? `<div class="small" style="color:var(--open)">${num(p.open_shops)} فروشنده باز در زمان بازدید</div>` : "";
  return `
    <a class="card product-card" href="#/p/${esc(p.product_id)}">
      ${thumb(p.image, p.title)}
      <div class="grow">
        <div class="title-2">${esc(p.title)}</div>
        <div class="muted small">${esc(p.category || "")}${p.brand ? " · " + esc(p.brand) : ""}</div>
        <div class="between">${price}<span class="chip">${sellers}</span></div>
        <div class="between">${open || "<span></span>"}${compareBtn(p.product_id, p.title)}</div>
      </div>
    </a>`;
}

async function viewProduct(id) {
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
    <a class="back" href="javascript:history.back()">→ بازگشت</a>
    <section class="card">
      ${img}
      <h1>${esc(p.title)}</h1>
      <div class="chips">
        ${p.category ? `<span class="chip">${esc(p.category)}</span>` : ""}
        <span class="chip">برند: ${p.brand ? esc(p.brand) : "نامشخص"}</span>
      </div>
      <div class="between" style="margin-top:8px"><span class="muted small">${esc(summary)}</span>${compareBtn(p.product_id, p.title)}</div>
    </section>
    <div class="notice">موجودی تأیید نشده است: هر فروشنده این کالا را در ترب ثبت کرده، اما موجود بودن آن امروز معلوم نیست. قیمت‌ها «قیمت ثبت‌شده» با زمان آخرین تغییر هستند.</div>
    <h2>فروشنده‌ها (${ctx.sort === "distance" && ctx.place ? "نزدیک‌ترین اول" : "ارزان‌ترین اول"})</h2>
    ${filterSummary(p)}
    ${p.sellers.map(sellerCard).join("")}
    ${specs}`;
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
      <div class="muted small">${ageText}</div>
      <div class="small">${warranty}</div>
      ${(entry.reasons || []).length ? `<div class="reasons">${entry.reasons.map((r) => `<span class="chip reason-${r.kind}">${esc(r.text)}</span>`).join("")}</div>` : ""}
      ${pay ? `<div class="chips" style="margin-top:6px">${pay}</div>` : ""}
      ${best.seller_title ? `<div class="muted small">عنوان فروشنده: ${esc(best.seller_title)}</div>` : ""}
      <div class="actions">
        <a class="btn primary" href="#/s/${esc(s.shop_id)}">فروشگاه</a>
        ${s.lat ? `<a class="btn" target="_blank" rel="noopener" href="${neshan(s.lat, s.lon)}">مسیر (نشان)</a>` : ""}
      </div>
    </article>`;
}

async function viewShop(id) {
  loading();
  let s;
  try { s = await getJSON(`/api/shops/${encodeURIComponent(id)}`); } catch (e) { return failed(e); }
  const todayIdx = (new Date().getDay() + 1) % 7; // JS: Sun=0 → Iranian week: Sat=0
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
    <a class="back" href="javascript:history.back()">→ بازگشت</a>
    <section class="card">
      <div class="between"><h1>${esc(s.name || "بدون نام")}</h1>${openPill(s.open_now, s.hours_status)}</div>
      ${nameBadge(s)}
      <dl class="facts">
        <dt>پاساژ/ساختمان</dt><dd>${s.passage ? esc(`${s.passage_kind} ${s.passage}`) : unknown()}</dd>
        <dt>طبقه</dt><dd>${s.location_short && s.floor != null ? esc(s.location_short.split("، ").find((x) => x.includes("طبقه") || x === "همکف") || "") : unknown()}</dd>
        <dt>واحد/پلاک</dt><dd>${s.unit ? "واحد " + esc(s.unit) : s.plaque ? "پلاک " + esc(s.plaque) : unknown()}</dd>
        <dt>محله</dt><dd>${s.area ? esc(s.area) : unknown()}</dd>
        <dt>آدرس کامل</dt><dd>${s.address ? esc(s.address) : unknown()}</dd>
      </dl>
      <div class="actions">
        ${s.lat ? `<a class="btn primary" target="_blank" rel="noopener" href="${neshan(s.lat, s.lon)}">مسیریابی با نشان</a>
        <a class="btn" target="_blank" rel="noopener" href="${gmaps(s.lat, s.lon)}">گوگل مپ</a>` : ""}
        ${s.phone ? `<a class="btn" href="tel:${esc(s.phone)}" title="شماره‌ها در داده‌ی مسابقه ساختگی‌اند">تماس (شماره نمایشی)</a>` : ""}
        ${links}
      </div>
    </section>
    <section class="card"><h2 style="margin-top:0">ساعت کاری</h2>${hours}</section>
    <section class="card">
      <h2 style="margin-top:0">شرایط خرید</h2>
      <ul style="margin:0;padding-inline-start:18px">${pay}</ul>
      <dl class="facts">
        <dt>ارسال فوری</dt><dd>${esc(fast)}</dd>
        <dt>کالابرگ</dt><dd>${unknown("اطلاعاتی در داده نیست")}</dd>
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
function route() {
  renderTray();
  const hash = location.hash || "#/";
  const [path, query] = hash.slice(1).split("?");
  const params = new URLSearchParams(query || "");
  window.scrollTo(0, 0);
  if (path.startsWith("/search")) return viewSearch(params.get("q") || "");
  if (path.startsWith("/p/")) return viewProduct(decodeURIComponent(path.slice(3)));
  if (path.startsWith("/s/")) return viewShop(decodeURIComponent(path.slice(3)));
  if (path.startsWith("/compare")) return viewCompare();
  return viewHome();
}

document.getElementById("searchForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $q.value.trim();
  if (q) ask(q);
});
window.addEventListener("hashchange", route);

renderCtxBar();
getJSON("/api/meta").then((m) => {
  if (m.snapshot) $foot.textContent = `داده: نمونه‌ی ترب از فروشگاه‌های تهران · آخرین تغییر قیمت ثبت‌شده: ${dateFmt.format(new Date(m.snapshot))}`;
}).catch(() => {});
route();

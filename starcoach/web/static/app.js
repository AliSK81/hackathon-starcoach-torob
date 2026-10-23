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
  lastAsk = { text, query: r.query || text, understood: r.understood, ambiguous: r.ambiguous, patch, intent: r.intent,
    category: r.category, source: r.source, thinking: Boolean(r.rules_struggled && r.llm_available) };
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
    $view.innerHTML = `<div class="card empty-state">برای «${esc(q)}» دسته‌ای پیدا نشد. نام کالا را ساده‌تر بنویسید (مثلاً «هندزفری»).</div>`;
    return;
  }
  const link = (qid, value) => {
    const next = new URLSearchParams({ q });
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
      <div class="actions">${compareBtn(p.product_id, p.title)}<a class="btn" href="#/p/${esc(p.product_id)}">فروشنده‌ها</a></div>
    </article>`).join("");
  const compareAll = g.suggestions.length >= 2
    ? `<button type="button" class="btn primary" data-compare-set='${esc(JSON.stringify(g.suggestions.map((p) => ({ id: p.product_id, title: p.title }))))}'>مقایسه‌ی این ${num(g.suggestions.length)} مدل</button>` : "";
  $view.innerHTML = `
    <section class="card">
      <h1 style="margin-top:0">راهنمای انتخاب: ${esc(g.category)}</h1>
      <p class="muted small" style="margin:0">سؤال‌ها از روی همین ${num(g.products)} مدلِ موجود در فروشگاه‌ها ساخته شده؛ عدد کنار هر گزینه یعنی چند مدل با آن جور است.</p>
    </section>
    ${questions}
    <h2>${num(g.matching)} مدل با جواب‌های شما · ۳ پیشنهاد</h2>
    ${sugg || `<div class="card muted">مدلی با این جواب‌ها نماند؛ یکی از جواب‌ها را «مهم نیست» کنید.</div>`}
    <div class="actions">${compareAll}<a class="btn" href="#/search?q=${encodeURIComponent(q)}">همه‌ی نتایج «${esc(q)}»</a></div>`;
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
      await sendContact(offerId, qs.length ? qs : defaults, (step, res) => {
        if (step === "sent") chat.innerHTML = bubble(res.message, true, `${res.channel} به ${res.to || "فروشنده"} (نمایشی)`) + `<div class="typing">… در انتظار پاسخ</div>`;
        else chat.innerHTML = bubble(res.message, true) + bubble(res.reply.text, false, res.note);
      });
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
    <div class="alt"><a href="#/p/${esc(p.product_id)}"><strong>${esc(p.title)}</strong></a>
      <div class="reasons">${p.why.map((w) => `<span class="chip reason-info">${esc(w)}</span>`).join("")}</div></div>`).join("");
  return `<div class="card small" style="margin-top:8px">
      <strong>${esc(title)}</strong> <span class="muted">(${num(a.sellers_total)} فروشنده‌ی باز)</span>
      ${sellers || `<p class="muted">فروشنده‌ی باز دیگری برای همین کالا نیست.</p>`}
      ${subs ? `<p style="margin:8px 0 4px"><strong>کالاهای مشابه:</strong></p>${subs}` : ""}
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
    <div class="muted">آدرس ثبت‌شده: ${esc(w.address || "نامشخص")}</div></div>`;
}

async function viewPlan() {
  if (!planList.length) {
    $view.innerHTML = `<div class="card empty-state">برنامه‌ی بازدید خالی است. روی کارت هر فروشنده «+ برنامه‌ی بازدید» را بزنید.</div>`;
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
    <h1>برنامه‌ی بازدید</h1>
    <p class="muted small">شروع ${esc(start)}، ${esc(when)} · ${num(pl.stops.length)} توقف · ${num(pl.total_walk_m)} متر پیاده · پایان حدود ساعت ${esc(pl.finish)}
      · <a href="javascript:void 0" data-open-sheet>تغییر زمان یا محل شروع</a></p>
    <p class="muted small">ترتیب: نزدیک‌ترین توقف بعدی؛ فروشگاه‌های یک ساختمان پشت سر هم و از طبقه‌ی پایین به بالا. ۱۰ دقیقه برای هر توقف.</p>
    ${warn}${stops}`;
}

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
  const guideLink = !(lastAsk && lastAsk.query === q && lastAsk.intent === "choose")
    ? `<p class="small"><a href="#/guide?q=${encodeURIComponent(q)}">مدلش را نمی‌دانید؟ با چند سؤال کمکتان می‌کنم ←</a></p>` : "";
  $view.innerHTML = understoodBanner(q) + loose + focus + few + guideLink + `<p class="muted small">مرتب‌شده بر اساس شباهت و تعداد فروشنده${scope}</p>` +
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
        <span class="chip">نام انگلیسی/مدل: ${p.english_name ? esc(p.english_name) : "ثبت نشده"}</span>
      </div>
      <div class="between" style="margin-top:8px"><span class="muted small">${esc(summary)}</span>${compareBtn(p.product_id, p.title)}</div>
    </section>
    <div class="notice">موجودی تأیید نشده است: هر فروشنده این کالا را در ترب ثبت کرده، اما موجود بودن آن امروز معلوم نیست. قیمت‌ها «قیمت ثبت‌شده» با زمان آخرین تغییر هستند.</div>
    ${p.price_spread && p.price_spread > 3 ? `<div class="notice">قیمت‌ها تا ${num(Math.round(p.price_spread))} برابر با هم فرق دارند. ممکن است واحد فروش (عدد، متر، حلقه، بسته) یا اصل/غیراصل بودن کالا فرق کند؛ واحد فروش در داده ثبت نشده. قبل از خرید بپرسید.</div>` : ""}
    <h2>فروشنده‌ها (${ctx.sort === "distance" && ctx.place ? "نزدیک‌ترین اول" : "ارزان‌ترین اول"})</h2>
    ${filterSummary(p)}
    ${p.sellers.length ? `<div class="actions" style="margin-bottom:10px"><button type="button" class="btn primary" id="askTop">🤖 از ${num(Math.min(3, p.sellers.length))} فروشنده‌ی اول بپرس</button></div><div id="agentBox"></div>` : ""}
    ${p.sellers.map((e) => sellerCard({ ...e, product_id: p.product_id, product_title: p.title })).join("")}
    ${specs}`;
  const askBtn = document.getElementById("askTop");
  if (askBtn) askBtn.onclick = () => { askBtn.disabled = true; askTopSellers(p); };
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
  if (path.startsWith("/guide")) return viewGuide(params);
  if (path.startsWith("/plan")) return viewPlan();
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

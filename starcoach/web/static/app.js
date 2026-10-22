"use strict";
// StarCoach web app: hash routes, plain DOM, no library.
// Every value from the API is escaped with esc() before it goes into HTML.

const $view = document.getElementById("view");
const $q = document.getElementById("q");
const $foot = document.getElementById("foot");

const EXAMPLES = [
  "گوشی سامسونگ S25 FE",
  "شارژر اپل ۲۰ وات",
  "هندزفری بلوتوث",
  "دزدگیر اماکن",
  "محافظ برق کولر",
  "اسپیکر جی بی ال",
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
      <div class="chips">${EXAMPLES.map((e) => `<a class="chip" href="#/search?q=${encodeURIComponent(e)}">${esc(e)}</a>`).join("")}</div>
    </section>
    <section class="notice info">
      قیمت‌ها همان قیمتی است که فروشنده در ترب ثبت کرده، با زمان آخرین تغییر. موجودی کالا را هیچ‌جا تأیید شده نشان نمی‌دهیم؛ قبل از رفتن بپرسید.
    </section>`;
}

async function viewSearch(q) {
  $q.value = q;
  if (!q.trim()) return viewHome();
  loading();
  let data;
  try { data = await getJSON(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { return failed(e); }
  if (!data.items.length) {
    $view.innerHTML = `<div class="card empty-state">برای «${esc(q)}» چیزی پیدا نشد. کلمه‌ی کوتاه‌تر یا نام دیگری امتحان کنید.</div>`;
    return;
  }
  const loose = data.mode === "or" ? `<div class="notice">همه‌ی کلمه‌ها با هم پیدا نشد؛ نتایج نزدیک را نشان می‌دهیم.</div>` : "";
  $view.innerHTML = loose + `<p class="muted small">${num(data.total)} کالا · مرتب‌شده بر اساس شباهت و تعداد فروشنده</p>` +
    data.items.map(productCard).join("");
}

function productCard(p) {
  const price = p.min_price != null
    ? `<span class="price">از ${esc(tomanShort(p.min_price))}</span>`
    : unknown("قیمت ثبت نشده");
  const sellers = p.n_shops > 1 ? `${num(p.n_shops)} فروشنده` : "۱ فروشنده";
  return `
    <a class="card product-card" href="#/p/${esc(p.product_id)}">
      ${thumb(p.image, p.title)}
      <div class="grow">
        <div class="title-2">${esc(p.title)}</div>
        <div class="muted small">${esc(p.category || "")}${p.brand ? " · " + esc(p.brand) : ""}</div>
        <div class="between">${price}<span class="chip">${sellers}</span></div>
      </div>
    </a>`;
}

async function viewProduct(id) {
  loading();
  let p;
  try { p = await getJSON(`/api/products/${encodeURIComponent(id)}`); } catch (e) { return failed(e); }
  const img = p.images.length ? `<img class="hero-img" src="${esc(p.images[0])}" alt="${esc(p.title)}">` : "";
  const specs = p.specs.length
    ? `<details class="card"><summary>مشخصات فنی (${num(p.specs.length)})</summary><dl class="facts">${
        p.specs.slice(0, 60).map((s) => `<dt>${esc(s.key)}</dt><dd>${esc(s.value)}</dd>`).join("")}</dl></details>`
    : `<div class="card muted small">مشخصات فنی برای این کالا ثبت نشده.</div>`;
  const summary = [
    `${num(p.sellers.length)} فروشنده`,
    p.min_price != null ? `کمترین ${tomanShort(p.min_price)}` : null,
    p.median_price != null && p.sellers.length > 2 ? `میانه ${tomanShort(p.median_price)}` : null,
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
      <p class="muted small" style="margin:8px 0 0">${esc(summary)}</p>
    </section>
    <div class="notice">موجودی تأیید نشده است: هر فروشنده این کالا را در ترب ثبت کرده، اما موجود بودن آن امروز معلوم نیست. قیمت‌ها «قیمت ثبت‌شده» با زمان آخرین تغییر هستند.</div>
    <h2>فروشنده‌ها (ارزان‌ترین اول)</h2>
    ${p.sellers.map(sellerCard).join("")}
    ${specs}`;
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
  const hash = location.hash || "#/";
  const [path, query] = hash.slice(1).split("?");
  const params = new URLSearchParams(query || "");
  window.scrollTo(0, 0);
  if (path.startsWith("/search")) return viewSearch(params.get("q") || "");
  if (path.startsWith("/p/")) return viewProduct(decodeURIComponent(path.slice(3)));
  if (path.startsWith("/s/")) return viewShop(decodeURIComponent(path.slice(3)));
  return viewHome();
}

document.getElementById("searchForm").addEventListener("submit", (e) => {
  e.preventDefault();
  const q = $q.value.trim();
  if (q) location.hash = `#/search?q=${encodeURIComponent(q)}`;
});
window.addEventListener("hashchange", route);

getJSON("/api/meta").then((m) => {
  if (m.snapshot) $foot.textContent = `داده: نمونه‌ی ترب از فروشگاه‌های تهران · آخرین تغییر قیمت ثبت‌شده: ${dateFmt.format(new Date(m.snapshot))}`;
}).catch(() => {});
route();

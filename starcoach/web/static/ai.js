"use strict";
// The AI layer of the web app. It runs NEXT TO the rule-based screens, never in front of them: every screen paints
// from the rules first, then these functions fill in "✨" cards when the LLM answers (cached, async).
// Loaded before app.js; it uses app.js helpers (esc, getJSON, ctx, productCard, ...) only when called.

// The ✨ parts show only when the server says it has the AI routes (`ai`); an older server with this newer script
// then simply shows the rule-based app instead of 404s. AI_ON also needs the LLM (`llm`); the chat works without it.
const aiReady = fetch("/health").then((r) => r.json()).then((h) => {
  AI_ON = Boolean(h.llm && h.ai);
  if (h.ai) document.body.classList.add("ai-ready");
}).catch(() => {});
let AI_ON = false;

function aiWait(text) {
  return `<div class="card ai-card ai-wait"><span class="ai-spark">✨</span> ${esc(text)}</div>`;
}

// ---------- search: reading of the request, wider candidates, ranked picks with reasons ----------
async function aiSearch(q) {
  await aiReady;
  const box = document.getElementById("aiBox");
  if (!AI_ON || !box) return;
  box.dataset.q = q;
  box.innerHTML = aiWait("دستیار هوشمند دارد جست‌وجو را بررسی می‌کند… (نتایج پایین همین حالا آماده‌اند)");
  let r;
  try { r = await getJSON(`/api/ai/search?q=${encodeURIComponent(q)}&${filterParams()}`); } catch { r = null; }
  const cur = document.getElementById("aiBox");
  if (!cur || cur.dataset.q !== q) return; // the user moved on
  cur.innerHTML = r && r.ok ? aiSearchHTML(q, r) : "";
}

function aiPickCard(p) {
  const tag = p.ai_new ? `<span class="chip pill-open">فقط با دستیار پیدا شد</span>` : "";
  return `<div class="ai-pick">${productCard(p, filtersActive())}
    <div class="ai-why">✨ ${esc(p.ai_reason || "مناسب درخواست شما")} ${tag}</div></div>`;
}

function aiSearchHTML(q, r) {
  const chips = (items) => items.map((t) => `<button type="button" class="chip" data-ask="${esc(t)}">${esc(t)}</button>`).join("");
  const clarifyChips = r.clarify
    ? `<div class="ai-clarify"><strong>${esc(r.clarify.question)}</strong><div class="chips" style="margin-top:6px">${
        r.clarify.options.map((o) => `<button type="button" class="chip" data-ask="${esc(o.query)}">${esc(o.label)}</button>`).join("")}</div></div>` : "";
  const related = r.queries.length ? `<div class="small" style="margin-top:8px">جست‌وجوهای نزدیک:</div><div class="chips" style="margin-top:4px">${chips(r.queries)}</div>` : "";
  const picks = r.picks.length
    ? `<div class="small" style="margin:10px 0 6px"><strong>${num(r.picks.length)} انتخاب دستیار برای شما</strong>${r.new_count ? ` · ${num(r.new_count)} مورد را جست‌وجوی ساده پیدا نکرده بود` : ""}</div>${r.picks.map(aiPickCard).join("")}`
    : "";
  return `<section class="card ai-card">
      <div class="ai-head"><span class="ai-spark">✨</span> دستیار هوشمند</div>
      ${r.interpretation ? `<p style="margin:6px 0 0">برداشت من: ${esc(r.interpretation)}</p>` : ""}
      ${clarifyChips}${picks}${related}
      <div class="actions"><button type="button" class="btn" data-agent-say="${esc(q)}">ادامه با دستیار گفت‌وگو</button></div>
      <p class="muted small" style="margin:6px 0 0">انتخاب هوش مصنوعی از میان کالاهای داده‌ی ترب؛ قیمت‌ها «قیمت ثبت‌شده»اند و موجودی تأیید نشده است.</p>
    </section>`;
}

// ---------- a product page: why this seller, in words ----------
async function aiPick(productId) {
  await aiReady;
  const box = document.getElementById("aiPickBox");
  if (!AI_ON || !box) return;
  box.dataset.pid = productId;
  box.innerHTML = `<div class="ai-wait small"><span class="ai-spark">✨</span> دستیار دارد توضیح می‌نویسد…</div>`;
  let r;
  try { r = await getJSON(`/api/ai/pick?product_id=${encodeURIComponent(productId)}&${filterParams()}`); } catch { r = null; }
  const cur = document.getElementById("aiPickBox");
  if (!cur || cur.dataset.pid !== productId) return;
  const pick = r && r.pick;
  cur.innerHTML = pick
    ? `<div class="ai-note"><span class="ai-spark">✨</span> ${esc(pick.summary)}${pick.ask.length
        ? `<div class="small" style="margin-top:4px"><strong>قبل از رفتن بپرسید:</strong> ${pick.ask.map(esc).join(" · ")}</div>` : ""}</div>` : "";
}

// ---------- guided choice: say what you need in your own words ----------
function aiGuideBox(q, category, said) {
  if (!AI_ON) return "";
  return `<section class="card ai-card">
      <div class="ai-head"><span class="ai-spark">✨</span> نیازتان را با کلمات خودتان بگویید</div>
      <form class="searchbox ai-guide-form" data-q="${esc(q)}" data-cat="${esc(category)}" style="margin-top:8px">
        <input name="t" value="${esc(said)}" placeholder="مثلاً: برای ورزش، ضد عرق و ارزان" autocomplete="off">
        <button type="submit">انتخاب کن</button>
      </form>
      <div class="ai-guide-reply small" style="margin-top:6px"></div>
      <div id="aiGuidePicks"></div>
    </section>`;
}

document.addEventListener("submit", async (e) => {
  const form = e.target.closest(".ai-guide-form");
  if (!form) return;
  e.preventDefault();
  const text = form.t.value.trim();
  const reply = form.parentElement.querySelector(".ai-guide-reply");
  if (!text) {
    reply.textContent = "ابتدا نیازتان را بنویسید (مثلاً همان متن نمونه بالا).";
    form.t.focus();
    return;
  }
  reply.innerHTML = `<span class="ai-wait"><span class="ai-spark">✨</span> دارم جواب‌ها را از حرف شما درمی‌آورم…</span>`;
  let r;
  try { r = await getJSON(`/api/ai/guide/answers?q=${encodeURIComponent(form.dataset.q)}&cat=${encodeURIComponent(form.dataset.cat)}&text=${encodeURIComponent(text)}&${filterParams()}`); } catch { r = null; }
  const next = new URLSearchParams({ q: form.dataset.q, t: text });
  for (const [k, v] of Object.entries((r && r.answers) || {})) next.set(`a.${k}`, v);
  location.hash = `#/guide?${next}`;
});

async function aiGuide(q, category, answers, said) {
  await aiReady;
  if (!AI_ON) return;
  const qs = new URLSearchParams({ q, cat: category, text: said });
  for (const [k, v] of Object.entries(answers)) qs.set(`a.${k}`, v);
  if (said) aiGuidePicks(qs.toString(), said);
  const slots = [...document.querySelectorAll("[data-ai-why]")];
  slots.forEach((el) => { el.innerHTML = `<span class="ai-wait small"><span class="ai-spark">✨</span> …</span>`; });
  let r;
  try { r = await getJSON(`/api/ai/guide/why?${qs}&${filterParams()}`); } catch { r = null; }
  for (const el of slots) {
    if (!el.isConnected) continue;
    const why = r && r.why && r.why[el.dataset.aiWhy];
    el.innerHTML = why ? `<span class="ai-spark">✨</span> ${esc(why)}` : "";
  }
}

async function aiGuidePicks(qs, said) {
  const box = document.getElementById("aiGuidePicks");
  if (!box) return;
  box.innerHTML = `<div class="ai-wait small" style="margin-top:8px"><span class="ai-spark">✨</span> دارم از میان مدل‌ها، بهترینِ نیاز شما را انتخاب می‌کنم…</div>`;
  let r;
  try { r = await getJSON(`/api/ai/guide/picks?${qs}&${filterParams()}`); } catch { r = null; }
  const cur = document.getElementById("aiGuidePicks");
  if (!cur) return;
  cur.innerHTML = r && r.picks.length
    ? `<div class="small" style="margin:10px 0 6px"><strong>بهترین‌ها برای «${esc(said)}»</strong> (انتخاب هوش مصنوعی از روی مشخصات)</div>${r.picks.map((p) => aiPickCard({ ...p, ai_new: false })).join("")}` : "";
}

// ---------- alternatives and in-passage directions: filled in when they appear on screen ----------
async function aiHydrate(el) {
  el.dataset.aiDone = "1";
  await aiReady;
  if (!AI_ON) return;
  if (el.dataset.ai === "alt") {
    const at = visitISO();
    let r;
    try {
      r = await getJSON(`/api/ai/alternatives?product_id=${encodeURIComponent(el.dataset.product)}&shop_id=${encodeURIComponent(el.dataset.shop)}&reason=${encodeURIComponent(el.dataset.reason)}${at ? "&at=" + at : ""}`);
    } catch { return; }
    if (!el.isConnected) return;
    const rows = new Map([...el.querySelectorAll(".alt[data-pid]")].map((n) => [n.dataset.pid, n]));
    for (const [pid, why] of Object.entries(r.why || {})) {
      const row = rows.get(pid);
      if (row && why) row.querySelector(".ai-why").innerHTML = `<span class="ai-spark">✨</span> ${esc(why)}`;
    }
    for (const pid of r.order || []) { const row = rows.get(pid); if (row) el.insertBefore(row, el.querySelector(".ai-advice")); }
    if (r.advice) el.querySelector(".ai-advice").innerHTML = `<div class="ai-note"><span class="ai-spark">✨</span> ${esc(r.advice)}</div>`;
  } else if (el.dataset.ai === "dir") {
    let r;
    try { r = await getJSON(`/api/ai/directions/${encodeURIComponent(el.dataset.shop)}`); } catch { return; }
    if (el.isConnected && r && r.text) el.innerHTML = `<div class="ai-note"><span class="ai-spark">✨</span> ${esc(r.text)}</div>`;
  }
}
new MutationObserver(() => {
  document.querySelectorAll("[data-ai]:not([data-ai-done])").forEach(aiHydrate);
}).observe(document.documentElement, { childList: true, subtree: true });

// ---------- the agent: a chat that searches, compares, asks the shops and says where to go ----------
const AGENT_EXAMPLES = [
  "نمیدونم چه هندزفری‌ای بخرم؛ برای ورزش، حدود ۳ میلیون",
  "شارژر اپل ۲۰ وات قسطی نزدیک علاءالدین، از چند فروشنده بپرس موجوده؟",
  "کت و شلوار مردانه کجا بخرم؟",
];
const AGENT_KEY = "sc_agent";
let agentChat = (() => { try { return JSON.parse(localStorage.getItem(AGENT_KEY) || "null") || { msgs: [], state: null }; } catch { return { msgs: [], state: null }; } })();
let agentBusy = false;
let agentStatus = "";
let agentCtxDirty = false;
const agentAltHtml = new Map(); // message slot -> rendered alternatives card

function agentSave() {
  try {
    const msgs = agentChat.msgs.filter((m) => !m.error).slice(-14).map((m, i, all) => (i < all.length - 6 ? { ...m, blocks: undefined } : m));
    localStorage.setItem(AGENT_KEY, JSON.stringify({ msgs, state: agentChat.state }));
  } catch { /* private mode or full */ }
}

function agentHomeCard() {
  return `<div class="home-ai ai-only">
      <button type="button" class="btn home-ai-btn" data-agent-open>✨ گفت‌وگو با دستیار</button>
    </div>`;
}

function agentShell() {
  if (document.getElementById("aiPanel")) return;
  document.body.insertAdjacentHTML("beforeend", `
    <button id="aiFab" class="ai-fab ai-only" type="button" aria-label="دستیار هوشمند">✨ دستیار</button>
    <section id="aiPanel" class="ai-panel" hidden aria-label="دستیار هوشمند خرید">
      <header class="ai-panel-head"><strong><span class="ai-spark">✨</span> دستیار خرید</strong>
        <span><button type="button" class="btn" id="aiReset">گفت‌وگوی تازه</button> <button type="button" class="btn" id="aiClose">بستن</button></span></header>
      <div id="aiMsgs" class="ai-msgs"></div>
      <div id="aiSugg" class="chips ai-sugg"></div>
      <form id="aiForm" class="ai-form"><input id="aiInput" placeholder="مثلاً: هندزفری برای ورزش زیر ۳ میلیون…" autocomplete="off" enterkeyhint="send"><button type="submit">بفرست</button></form>
      <p class="ai-foot">قیمت‌ها «قیمت ثبت‌شده‌ی فروشنده» هستند؛ موجودی فقط با پرسیدن تأیید می‌شود. پاسخ فروشنده‌ها در این نسخه نمایشی است.</p>
    </section>`);
  document.getElementById("aiFab").onclick = () => agentOpen();
  document.getElementById("aiClose").onclick = agentClose;
  document.getElementById("aiReset").onclick = () => { if (!agentBusy) { agentChat = { msgs: [], state: null }; agentSave(); agentRender(); } };
  document.getElementById("aiForm").onsubmit = (e) => {
    e.preventDefault();
    const input = document.getElementById("aiInput");
    const text = input.value;
    input.value = "";
    agentSend(text);
  };
}

function agentOpen(say) {
  agentShell();
  document.getElementById("aiPanel").hidden = false;
  document.getElementById("aiFab").hidden = true;
  document.body.classList.add("ai-open");
  agentRender();
  if (say) agentSend(say);
  else document.getElementById("aiInput").focus();
}

function agentClose() {
  document.getElementById("aiPanel").hidden = true;
  document.getElementById("aiFab").hidden = false;
  document.body.classList.remove("ai-open");
  if (agentCtxDirty) { agentCtxDirty = false; route(); }
}

document.addEventListener("click", (e) => {
  const say = e.target.closest("[data-agent-say]");
  if (say) { agentOpen(say.dataset.agentSay); return; }
  if (e.target.closest("[data-agent-open]")) { agentOpen(); return; }
  const chip = e.target.closest("[data-agent-chip]");
  if (chip) { agentSend(chip.dataset.agentChip); return; }
  // a link or "full compare" inside the chat leaves the chat and shows that page
  const link = e.target.closest("#aiPanel a[href^='#/']");
  if (link) agentClose();
  if (e.target.closest("#aiPanel [data-compare-set]")) agentClose();
});

function patchNote(patch, clear) {
  const notes = [];
  if ("max_price" in patch || "min_price" in patch) {
    notes.push(patch.max_price && patch.min_price ? `بودجه ${tomanShort(patch.min_price)} تا ${tomanShort(patch.max_price)}`
      : patch.max_price ? `بودجه تا ${tomanShort(patch.max_price)}` : `از ${tomanShort(patch.min_price)} به بالا`);
  }
  if (patch.place) notes.push(patch.place.kind === "me" ? "نزدیک من" : patch.place.name);
  if ("day" in patch) notes.push(`${DAYS_FA[patch.day]} ساعت ${num(patch.hour ?? 11)}`);
  for (const [k, label] of CONDITIONS) if (patch[k]) notes.push(label);
  if (patch.sort === "distance") notes.push("نزدیک‌ترین اول");
  const cleared = clear.filter((k) => ["max_price", "place", "day", ...CONDITIONS.map((c) => c[0])].includes(k));
  return { applied: notes, cleared: cleared.length > 0 };
}

function agentApply(ev) {
  const patch = ev.ctx_patch || {}, clear = ev.ctx_clear || [];
  if (!Object.keys(patch).length && !clear.length) return null;
  for (const k of clear) ctx[k] = DEFAULT_CTX[k];
  if ("max_price" in patch || "min_price" in patch) { ctx.max_price = null; ctx.min_price = null; }
  ctx = { ...ctx, ...patch };
  saveCtx();
  renderCtxBar();
  agentCtxDirty = true;
  return patchNote(patch, clear);
}

function compareMini(b) {
  const P = b.table.products;
  const row = (label, f) => `<tr><th>${label}</th>${P.map((p) => `<td>${f(p)}</td>`).join("")}</tr>`;
  return `<div class="cmp-wrap"><table class="cmp-table"><thead><tr><th></th>${P.map((p) => `<th>${esc(p.title)}</th>`).join("")}</tr></thead><tbody>
      ${row("کمترین قیمت ثبت‌شده", (p) => (p.min_price != null ? esc(tomanShort(p.min_price)) : "—"))}
      ${row("فروشنده‌ی مطابق شرایط", (p) => num(p.sellers_match))}
      ${row("نزدیک‌ترین", (p) => (p.nearest_m != null ? esc(faDigits(fmtDistance(p.nearest_m))) : "—"))}
      ${row("فروشنده‌ی اقساطی", (p) => num(p.installment_sellers))}
      </tbody></table></div>
    <div class="actions"><button type="button" class="btn primary" data-compare-set='${esc(JSON.stringify(b.products.map((p) => ({ id: p.id, title: p.title }))))}'>مقایسه‌ی کامل</button></div>`;
}

function contactsMini(b) {
  for (const r of b.results) {
    contacts[r.offer_id] = { status: r.status, facts: { in_stock: r.in_stock, price_now: r.price_now, price_changed: r.price_changed, hold_until: r.hold_until }, at: Date.now(), shop: r.name };
  }
  saveContacts();
  return `<div class="card small"><strong>پاسخ فروشنده‌ها (نمایشی)</strong>
      ${b.results.map((r) => `<div class="alt"><div class="between"><a href="#/s/${esc(r.shop_id)}"><strong>${esc(r.name)}</strong></a>${contactChip(r.offer_id)}</div>
        <div class="bubble">${esc(r.reply)}</div></div>`).join("")}
      <p class="muted small" style="margin:6px 0 0">${esc(b.note)}</p></div>`;
}

function blockHTML(b, slot) {
  if (b.type === "product") return `<div class="ai-pick">${productCard(b.item, filtersActive())}${b.note ? `<div class="ai-why">✨ ${esc(b.note)}</div>` : ""}</div>`;
  if (b.type === "seller") return `${sellerCard({ ...b.entry, product_id: b.product_id, product_title: b.product_title })}${b.note ? `<div class="ai-why">✨ ${esc(b.note)}</div>` : ""}`;
  if (b.type === "compare") return compareMini(b);
  if (b.type === "contacts") return contactsMini(b);
  if (b.type === "hubs") return `<div id="aiHub-${slot}"></div>`;
  if (b.type === "alternatives") return `<div id="aiAlt-${slot}"></div>`;
  if (b.type === "guide") return `<div class="actions"><a class="btn primary" href="#/guide?q=${encodeURIComponent(b.q)}">راهنمای انتخاب مدل</a></div>`;
  if (b.type === "plan") return `<div class="actions"><a class="btn primary" href="#/plan">برنامه‌ی بازدید</a></div>`;
  return "";
}

function agentRender() {
  const box = document.getElementById("aiMsgs");
  if (!box) return;
  const msgs = agentChat.msgs;
  let html = "";
  if (!msgs.length) {
    html = `<div class="bubble">سلام! من دستیار خرید حضوری‌ام. بگویید چه می‌خواهید؛ اگر مدلش را نمی‌دانید همین را بگویید. من می‌گردم، فروشنده‌ها را از نظر قیمت ثبت‌شده، فاصله و ساعت کاری مقایسه می‌کنم، از آن‌ها می‌پرسم و می‌گویم کجا بروید.</div>
      <div class="chips" style="margin-top:8px">${AGENT_EXAMPLES.map((t) => `<button type="button" class="chip" data-agent-chip="${esc(t)}">${esc(t)}</button>`).join("")}</div>`;
  }
  const slots = [];
  msgs.forEach((m, i) => {
    if (m.role === "user") { html += `<div class="bubble mine">${esc(m.text)}</div>`; return; }
    const note = m.patch && (m.patch.applied.length || m.patch.cleared)
      ? `<div class="ai-patch small">شرایط اعمال شد: ${m.patch.applied.map((t) => `<span class="chip reason-good">${esc(t)}</span>`).join(" ")}${m.patch.cleared ? ` <span class="chip reason-info">بعضی شرایط برداشته شد</span>` : ""}</div>` : "";
    const blocks = (m.blocks || []).map((b, j) => { slots.push([b, `${i}-${j}`]); return blockHTML(b, `${i}-${j}`); }).join("");
    html += `<div class="bubble">${esc(m.text).replace(/\n/g, "<br>")}${m.degraded ? `<div class="bubble-note">دستیار هوشمند در دسترس نبود؛ جست‌وجوی ساده نشان داده شد.</div>` : ""}</div>${note}${blocks}`;
  });
  if (agentBusy) html += `<div class="typing" id="aiTyping">✨ ${esc(agentStatus || "دارم فکر می‌کنم…")}</div>`;
  box.innerHTML = html;
  for (const [b, slot] of slots) {
    if (b.type === "hubs") loadHubs(`aiHub-${slot}`, { q: b.q }, `کجا بروید: ${b.q}`);
    if (b.type === "alternatives") {
      const put = (h) => { const el = document.getElementById(`aiAlt-${slot}`); if (el) el.innerHTML = h; };
      if (agentAltHtml.has(slot)) put(agentAltHtml.get(slot)); // a re-render must not ask the server again
      else alternativesHTML(b.product_id, b.shop_id, "closed").then((h) => { agentAltHtml.set(slot, h); put(h); });
    }
  }
  const last = msgs[msgs.length - 1];
  const sugg = !agentBusy && last && last.role === "assistant" ? last.suggestions || [] : [];
  document.getElementById("aiSugg").innerHTML = sugg.map((t) => `<button type="button" class="chip" data-agent-chip="${esc(t)}">${esc(t)}</button>`).join("");
  box.scrollTop = box.scrollHeight;
}

async function agentSend(text) {
  text = (text || "").trim();
  if (!text || agentBusy) return;
  agentBusy = true;
  agentStatus = "";
  const history = agentChat.msgs.filter((m) => !m.error).slice(-8).map((m) => ({ role: m.role, text: m.text }));
  agentChat.msgs.push({ role: "user", text });
  agentRender();
  const body = { text, history, filters: Object.fromEntries(new URLSearchParams(filterParams())), state: agentChat.state, stream: true };
  let final = null;
  try {
    const r = await fetch("/api/agent", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (r.status === 404) throw new Error("دستیار روی این سرور فعال نیست؛ سرور را دوباره راه‌اندازی کنید");
    if (!r.ok) throw new Error(`${r.status}`);
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let cut;
      while ((cut = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, cut);
        buf = buf.slice(cut + 2);
        if (!chunk.startsWith("data: ")) continue;
        const ev = JSON.parse(chunk.slice(6));
        if (ev.event === "step") { agentStatus = ev.label; const t = document.getElementById("aiTyping"); if (t) t.textContent = `✨ ${ev.label}`; }
        else if (ev.event === "final") final = ev;
      }
    }
  } catch (e) {
    final = null;
    agentChat.msgs.push({ role: "assistant", error: true, text: `مشکلی پیش آمد (${e.message}). دوباره امتحان کنید.`, suggestions: [text] });
  }
  agentBusy = false;
  if (final) {
    const patch = agentApply(final);
    agentChat.state = final.state;
    agentChat.msgs.push({ role: "assistant", text: final.reply, blocks: final.blocks, suggestions: final.suggestions, patch, degraded: final.degraded });
  }
  agentSave();
  agentRender();
}

agentShell();

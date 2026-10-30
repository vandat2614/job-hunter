"use strict";

const PAGE = 10;
const MAX_CV_BYTES = 2 * 1024 * 1024;
const $ = (id) => document.getElementById(id);
const state = {
  token: sessionStorage.getItem("token"),
  email: sessionStorage.getItem("email"),
  offset: 0,
};

/* ---------- helpers ---------- */

// Build DOM with textContent only: job titles, CV text and URLs come from outside
// and must never be parsed as HTML.
function el(tag, { text, cls, attrs } = {}, ...children) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (cls) node.className = cls;
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  node.append(...children);
  return node;
}

// Only http(s) links: a "javascript:" URL from a crawled page would otherwise run script.
function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch (_) {
    return null;
  }
}

const splitList = (v) => v.split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);

function formatSalary(min, max, currency) {
  if (min == null && max == null) return null;
  const n = (v) => v.toLocaleString("en-US");
  const c = currency ? ` ${currency}` : "";
  if (min != null && max != null) return min === max ? `${n(min)}${c}` : `${n(min)} - ${n(max)}${c}`;
  return min != null ? `from ${n(min)}${c}` : `up to ${n(max)}${c}`;
}

function notify(message, isError = false) {
  const box = $("status");
  box.textContent = message;
  box.className = message ? (isError ? "error" : "ok") : "";
}

async function guard(fn) {
  try {
    notify("");
    await fn();
  } catch (e) {
    notify(e.message, true);
  }
}

function httpError(status, message) {
  const e = new Error(message);
  e.status = status;
  return e;
}

function describeError(status, data) {
  const d = data && data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return d.map((e) => e.msg).join("; ");
  return `Request failed (HTTP ${status})`;
}

async function api(path, { method = "GET", json, form } = {}) {
  const headers = {};
  let body;
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form; // the browser sets the multipart boundary itself
  }
  const res = await fetch(path, { method, headers, body });
  if (res.status === 401 && state.token) {
    logout();
    throw httpError(401, "Session expired, please log in again.");
  }
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* body is not JSON */
  }
  if (!res.ok) throw httpError(res.status, describeError(res.status, data));
  return data;
}

/* ---------- session ---------- */

function showApp() {
  $("auth-view").hidden = true;
  $("app-view").hidden = false;
  $("session").hidden = false;
  $("who").textContent = state.email || "";
  guard(() => selectTab("jobs"));
}

function showAuth() {
  $("auth-view").hidden = false;
  $("app-view").hidden = true;
  $("session").hidden = true;
}

async function login(email, password) {
  const data = await api("/auth/login", { method: "POST", json: { email, password } });
  state.token = data.access_token;
  state.email = email;
  sessionStorage.setItem("token", state.token);
  sessionStorage.setItem("email", email);
  $("password").value = "";
  showApp();
}

function logout() {
  state.token = null;
  state.email = null;
  sessionStorage.clear();
  showAuth();
}

/* ---------- tabs ---------- */

async function selectTab(name) {
  for (const b of document.querySelectorAll("nav button")) {
    b.setAttribute("aria-selected", String(b.dataset.tab === name));
  }
  for (const s of document.querySelectorAll(".tab")) s.hidden = s.id !== `tab-${name}`;
  if (name === "jobs") await searchJobs(0);
  if (name === "cv") await loadCv();
  if (name === "subs") await loadSubs();
}

/* ---------- jobs ---------- */

async function searchJobs(offset) {
  const p = new URLSearchParams();
  const q = $("q").value.trim();
  if (q) p.set("q", q);
  for (const s of splitList($("skills").value)) p.append("skills", s);
  const location = $("location").value.trim();
  if (location) p.set("location", location);
  if ($("min-salary").value) p.set("min_salary", $("min-salary").value);
  if ($("currency").value) p.set("currency", $("currency").value);
  p.set("limit", PAGE);
  p.set("offset", offset);
  const data = await api(`/jobs?${p}`);
  state.offset = offset;
  renderJobs(data);
}

function jobCard(j) {
  const parts = [j.company, j.location, formatSalary(j.salary_min, j.salary_max, j.salary_currency)].filter(Boolean);
  const card = el("article", { cls: "card" }, el("h3", { text: j.title }), el("p", { cls: "meta" }, ...parts.map((x) => el("span", { text: x }))));
  if (j.skills.length) card.append(el("p", {}, ...j.skills.map((s) => el("span", { cls: "chip", text: s }))));
  const links = j.sources
    .map((s) => ({ name: s.source, href: safeUrl(s.url) }))
    .filter((x) => x.href)
    .map((x) => el("a", { text: x.name, attrs: { href: x.href, target: "_blank", rel: "noopener noreferrer" } }));
  if (links.length) card.append(el("p", { cls: "links" }, ...links));
  return card;
}

function renderJobs({ total, items, limit, offset }) {
  $("jobs-summary").textContent = `${total} job${total === 1 ? "" : "s"} found`;
  $("jobs-list").replaceChildren(...items.map(jobCard));
  $("prev").disabled = offset <= 0;
  $("next").disabled = offset + limit >= total;
}

/* ---------- CV ---------- */

function renderCv(cv) {
  $("cv-delete").hidden = !cv;
  if (!cv) {
    $("cv-current").replaceChildren(el("p", { cls: "hint", text: "No CV uploaded yet." }));
    return;
  }
  const meta = `${cv.filename} · ${cv.format.toUpperCase()} · ${cv.chars} characters · updated ${new Date(cv.updated_at).toLocaleString()}`;
  $("cv-current").replaceChildren(el("p", { cls: "meta", text: meta }), el("pre", { text: cv.preview }));
}

async function loadCv() {
  try {
    renderCv(await api("/cvs/me"));
  } catch (e) {
    if (e.status === 404) renderCv(null);
    else throw e;
  }
}

/* ---------- subscriptions ---------- */

function subCard(s) {
  const meta = [
    s.location ? `Location: ${s.location}` : "Any location",
    s.min_salary != null ? `Min salary: ${s.min_salary.toLocaleString("en-US")} ${s.currency || ""}`.trim() : "Any salary",
    s.telegram_chat_id ? `Telegram: ${s.telegram_chat_id}` : "No Telegram chat id",
  ];
  const del = el("button", { text: "Delete", cls: "danger" });
  del.addEventListener("click", () =>
    guard(async () => {
      if (!confirm("Delete this subscription?")) return;
      await api(`/subscriptions/${encodeURIComponent(s.subscription_id)}`, { method: "DELETE" });
      await loadSubs();
    }),
  );
  const card = el("article", { cls: "card" }, el("p", { cls: "meta" }, ...meta.map((x) => el("span", { text: x }))));
  card.append(
    s.skills.length
      ? el("p", {}, ...s.skills.map((x) => el("span", { cls: "chip", text: x })))
      : el("p", { cls: "hint", text: "No skills required" }),
    del,
  );
  return card;
}

async function loadSubs() {
  const subs = await api("/subscriptions");
  $("subs-list").replaceChildren(
    ...(subs.length ? subs.map(subCard) : [el("p", { cls: "hint", text: "No subscriptions yet." })]),
  );
}

/* ---------- events ---------- */

$("auth-form").addEventListener("submit", (e) => {
  e.preventDefault();
  guard(() => login($("email").value.trim(), $("password").value));
});

$("register").addEventListener("click", () =>
  guard(async () => {
    if (!$("auth-form").reportValidity()) return;
    const email = $("email").value.trim();
    const password = $("password").value;
    await api("/auth/register", { method: "POST", json: { email, password } });
    await login(email, password);
  }),
);

$("logout").addEventListener("click", logout);

for (const b of document.querySelectorAll("nav button")) {
  b.addEventListener("click", () => guard(() => selectTab(b.dataset.tab)));
}

$("jobs-form").addEventListener("submit", (e) => {
  e.preventDefault();
  guard(() => searchJobs(0));
});
$("prev").addEventListener("click", () => guard(() => searchJobs(Math.max(0, state.offset - PAGE))));
$("next").addEventListener("click", () => guard(() => searchJobs(state.offset + PAGE)));

$("cv-form").addEventListener("submit", (e) => {
  e.preventDefault();
  guard(async () => {
    const file = $("cv-file").files[0];
    if (!file) throw new Error("Choose a file first.");
    if (file.size > MAX_CV_BYTES) throw new Error("File too large (max 2 MB).");
    const form = new FormData();
    form.append("file", file);
    renderCv(await api("/cvs/me", { method: "PUT", form }));
    $("cv-file").value = "";
    notify("CV uploaded. New matches will be scored against it.");
  });
});

$("cv-delete").addEventListener("click", () =>
  guard(async () => {
    if (!confirm("Delete your CV?")) return;
    await api("/cvs/me", { method: "DELETE" });
    renderCv(null);
    notify("CV deleted.");
  }),
);

$("subs-form").addEventListener("submit", (e) => {
  e.preventDefault();
  guard(async () => {
    const min = $("sub-min-salary").value;
    await api("/subscriptions", {
      method: "POST",
      json: {
        skills: splitList($("sub-skills").value),
        location: $("sub-location").value.trim() || null,
        min_salary: min ? Number(min) : null,
        currency: $("sub-currency").value || null,
        telegram_chat_id: $("sub-chat").value.trim() || null,
      },
    });
    $("subs-form").reset();
    await loadSubs();
    notify("Subscription created.");
  });
});

state.token ? showApp() : showAuth();

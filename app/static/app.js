// Tiny helpers shared by all pages.

async function api(path, options = {}) {
  const opts = { headers: { "Content-Type": "application/json" }, ...options };
  if (opts.body && typeof opts.body !== "string" && !(opts.body instanceof FormData)) {
    opts.body = JSON.stringify(opts.body);
  }
  if (opts.body instanceof FormData) {
    delete opts.headers["Content-Type"]; // let the browser set the boundary
  }
  const response = await fetch(path, opts);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    throw new Error(`${response.status}: ${detail}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

function toast(message, kind = "ok", durationMs = 2400) {
  let el = document.querySelector(".toast");
  if (!el) {
    el = document.createElement("div");
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.className = `toast ${kind} visible`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    el.className = `toast ${kind}`;
  }, durationMs);
}

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

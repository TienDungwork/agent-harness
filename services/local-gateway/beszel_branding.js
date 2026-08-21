(() => {
  const BRAND = "Creanova";
  // Natural glyph proportions — do NOT use textLength (it stretches letters).
  // Height-only CSS; width follows viewBox aspect ratio.
  const LOGO_SVG =
    '<svg id="creanova-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 20" class="fill-foreground" aria-hidden="true" style="display:block;height:1.5rem;width:auto">' +
    '<defs><linearGradient id="creanova-logo-g" x1="0%" y1="20%" x2="100%" y2="120%">' +
    '<stop offset="10%" stop-color="#747bff"/><stop offset="90%" stop-color="#24eb5c"/>' +
    "</linearGradient></defs>" +
    '<text class="creanova-logo-base" x="0" y="15.5" fill="currentColor" ' +
    'font-family="ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif" ' +
    'font-size="16" font-weight="800" letter-spacing="-0.02em">' +
    BRAND +
    "</text>" +
    '<text class="creanova-logo-hover" x="0" y="15.5" fill="url(#creanova-logo-g)" opacity="0" ' +
    'font-family="ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif" ' +
    'font-size="16" font-weight="800" letter-spacing="-0.02em">' +
    BRAND +
    "</text></svg>";

  const BOOT_CSS =
    'a[aria-label="Home"]>svg:not(#creanova-logo){visibility:hidden!important;position:absolute!important;width:0!important;height:0!important;overflow:hidden!important}' +
    'a[aria-label="Home"]{margin-inline-end:0.15rem!important;padding-block:0.25rem!important;padding-inline:0!important}';

  function ensureBootCss() {
    if (document.getElementById("creanova-boot-css")) return;
    const style = document.createElement("style");
    style.id = "creanova-boot-css";
    style.textContent = BOOT_CSS;
    (document.head || document.documentElement).appendChild(style);
  }

  function brandTitle() {
    const raw = document.title || "";
    if (!raw) {
      document.title = BRAND;
      return;
    }
    if (raw.includes("Beszel")) {
      document.title = raw.replace(/Beszel/g, BRAND);
    }
  }

  function brandLogo() {
    const home = document.querySelector('a[aria-label="Home"]');
    if (!home) return;
    if (home.querySelector("#creanova-logo")) return;
    home.innerHTML = LOGO_SVG;
    if (!document.getElementById("creanova-logo-style")) {
      const style = document.createElement("style");
      style.id = "creanova-logo-style";
      style.textContent =
        'a[aria-label="Home"].group:hover .creanova-logo-base{opacity:0;transition:opacity .2s ease-out}' +
        'a[aria-label="Home"].group:hover .creanova-logo-hover{opacity:1;transition:opacity .2s ease-in-out}' +
        'a[aria-label="Home"] .creanova-logo-base{transition:opacity .2s ease-out}' +
        'a[aria-label="Home"] .creanova-logo-hover{transition:opacity .2s ease-in-out}';
      document.head.appendChild(style);
    }
  }

  function goHome(e) {
    if (e) e.preventDefault();
    const home = document.querySelector('a[aria-label="Home"]');
    if (home) {
      home.click();
      return;
    }
    const base = (globalThis.BESZEL && BESZEL.BASE_PATH) || "/";
    location.assign(base);
  }

  function mountAllSystems() {
    if (document.getElementById("creanova-beszel-home")) return;
    if (document.querySelector('a[aria-label="All Systems"]')) return;

    const HOME_SVG =
      '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="h-[1.2rem] w-[1.2rem]" aria-hidden="true"><path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>';

    const iconRow = Array.from(document.querySelectorAll("div")).find((d) => {
      if (!(d instanceof HTMLElement)) return false;
      const cn = d.className;
      if (!cn || typeof cn !== "string") return false;
      if (!cn.includes("md:flex") || !cn.includes("ms-auto")) return false;
      return !!d.querySelector('a[aria-label="Containers"]');
    });

    const logoHome = document.querySelector('a[aria-label="Home"]');
    if (!iconRow && (!logoHome || !logoHome.parentElement)) return;

    const a = document.createElement("a");
    a.id = "creanova-beszel-home";
    a.href = (logoHome && logoHome.getAttribute("href")) || "/";
    a.setAttribute("aria-label", "All Systems");
    a.setAttribute("title", "All Systems");
    a.innerHTML = HOME_SVG;
    a.addEventListener("click", goHome);

    if (iconRow) {
      const sib = iconRow.querySelector(
        'a[aria-label="Containers"], a[aria-label="Settings"]',
      );
      a.className = sib ? sib.className : "";
      if (!a.className) {
        a.style.cssText =
          "display:inline-flex;align-items:center;justify-content:center;height:2.25rem;width:2.25rem;border-radius:0.375rem;color:inherit;text-decoration:none;cursor:pointer";
      }
      iconRow.insertBefore(a, iconRow.firstChild);
      return;
    }

    a.style.cssText =
      "display:inline-flex;align-items:center;justify-content:center;height:2.25rem;width:2.25rem;margin-inline-end:0.25rem;border-radius:0.375rem;color:inherit;text-decoration:none;cursor:pointer";
    logoHome.parentElement.insertBefore(a, logoHome.nextSibling);
  }

  function hideDocumentation() {
    // Command palette / menus: hide Beszel docs entry (Creanova rebrand).
    const nodes = document.querySelectorAll(
      '[cmdk-item], [data-slot="command-item"], [role="option"], [role="menuitem"]',
    );
    for (const el of nodes) {
      if (!(el instanceof HTMLElement)) continue;
      if (el.dataset.creanovaDocsHidden === "1") continue;
      const text = (el.textContent || "").replace(/\s+/g, " ").trim();
      const isDocs =
        (text.includes("Documentation") && text.includes("beszel.dev")) ||
        !!el.querySelector('a[href*="beszel.dev/guide"]');
      if (!isDocs) continue;
      el.dataset.creanovaDocsHidden = "1";
      el.style.display = "none";
      el.setAttribute("aria-hidden", "true");
    }
  }

  // ── Pinned containers → local-gateway (per Creanova user) ─────────────────
  const GATEWAY_URL =
    (globalThis.__CREANOVA_GATEWAY_URL__ ||
      `http://${location.hostname}:18110`).replace(/\/$/, "");

  function pbAuth() {
    try {
      const raw = localStorage.getItem("pocketbase_auth");
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      const token = parsed?.token;
      const email = parsed?.record?.email || parsed?.model?.email;
      if (!token) return null;
      return { token, email };
    } catch {
      return null;
    }
  }

  async function gatewayFetch(path, opts = {}) {
    const auth = pbAuth();
    const headers = Object.assign(
      { "Content-Type": "application/json", Accept: "application/json" },
      opts.headers || {},
    );
    if (auth?.token) headers["X-Beszel-Token"] = auth.token;
    const res = await fetch(`${GATEWAY_URL}${path}`, {
      ...opts,
      headers,
      credentials: "include",
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`${res.status}: ${text.slice(0, 200)}`);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  function toast(msg, ok) {
    let el = document.getElementById("creanova-pin-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "creanova-pin-toast";
      el.style.cssText =
        "position:fixed;bottom:1rem;right:1rem;z-index:99999;padding:.6rem .9rem;" +
        "border-radius:.5rem;font:500 13px/1.3 system-ui,sans-serif;max-width:22rem;" +
        "box-shadow:0 8px 24px rgba(0,0,0,.25);color:#fff";
      document.body.appendChild(el);
    }
    el.style.background = ok ? "#15803d" : "#b91c1c";
    el.textContent = msg;
    clearTimeout(el._t);
    el._t = setTimeout(() => {
      el.remove();
    }, 3200);
  }

  function ensurePinCss() {
    if (document.getElementById("creanova-pin-css")) return;
    const style = document.createElement("style");
    style.id = "creanova-pin-css";
    style.textContent =
      ".creanova-pin-btn{margin-inline-start:.35rem;padding:.15rem .4rem;font:600 11px/1 system-ui,sans-serif;" +
      "border-radius:.35rem;border:1px solid currentColor;opacity:.75;cursor:pointer;background:transparent;color:inherit}" +
      ".creanova-pin-btn[data-pinned='1']{opacity:1;background:rgba(116,123,255,.2)}" +
      ".creanova-pin-btn:hover{opacity:1}" +
      "#creanova-pins-panel{position:fixed;bottom:1rem;left:1rem;z-index:99990;max-width:18rem;" +
      "background:rgba(15,15,20,.92);color:#eee;border-radius:.6rem;padding:.55rem .7rem;" +
      "font:13px/1.35 system-ui,sans-serif;box-shadow:0 8px 28px rgba(0,0,0,.35)}" +
      "#creanova-pins-panel h3{margin:0 0 .35rem;font-size:12px;letter-spacing:.04em;text-transform:uppercase;opacity:.8}" +
      "#creanova-pins-panel li{margin:.2rem 0;display:flex;gap:.4rem;align-items:baseline}" +
      "#creanova-pins-panel button{border:0;background:transparent;color:#f87171;cursor:pointer;font-size:12px}";
    document.head.appendChild(style);
  }

  let pinCache = null;
  let pinCacheAt = 0;

  async function loadPins(force) {
    if (!force && pinCache && Date.now() - pinCacheAt < 8000) return pinCache;
    try {
      const data = await gatewayFetch("/api/infra/pinned-containers");
      pinCache = data?.items || [];
      pinCacheAt = Date.now();
      return pinCache;
    } catch (e) {
      pinCache = [];
      pinCacheAt = Date.now();
      return pinCache;
    }
  }

  function pinKey(host, name) {
    return `${host}::${name}`.toLowerCase();
  }

  async function togglePin(host, name, btn) {
    const auth = pbAuth();
    if (!auth) {
      toast("Login Beszel (Keycloak) first to pin", false);
      return;
    }
    const pins = await loadPins(true);
    const existing = pins.find(
      (p) => pinKey(p.host, p.container_name) === pinKey(host, name),
    );
    try {
      if (existing) {
        await gatewayFetch(`/api/infra/pinned-containers/${existing.id}`, {
          method: "DELETE",
        });
        toast(`Unpinned ${name}`, true);
        if (btn) btn.dataset.pinned = "0";
      } else {
        await gatewayFetch("/api/infra/pinned-containers", {
          method: "POST",
          body: JSON.stringify({ host, container_name: name }),
        });
        toast(`Pinned ${name} @ ${host}`, true);
        if (btn) btn.dataset.pinned = "1";
      }
      await loadPins(true);
      renderPinsPanel();
      syncPinButtons();
    } catch (e) {
      toast(String(e.message || e), false);
    }
  }

  function syncPinButtons() {
    const pins = pinCache || [];
    const set = new Set(pins.map((p) => pinKey(p.host, p.container_name)));
    document.querySelectorAll(".creanova-pin-btn").forEach((btn) => {
      if (!(btn instanceof HTMLElement)) return;
      const host = btn.dataset.host || "";
      const name = btn.dataset.name || "";
      btn.dataset.pinned = set.has(pinKey(host, name)) ? "1" : "0";
      btn.textContent = btn.dataset.pinned === "1" ? "Pinned" : "Pin";
      btn.title =
        btn.dataset.pinned === "1"
          ? "Unpin for Creanova agent focus"
          : "Pin for Creanova agent focus";
    });
  }

  function mountPinButtons() {
    // Container name cells: span.truncate inside table rows.
    const rows = document.querySelectorAll("table tbody tr");
    rows.forEach((tr) => {
      if (!(tr instanceof HTMLElement)) return;
      if (tr.querySelector(".creanova-pin-btn")) return;
      const cells = tr.querySelectorAll("td");
      if (cells.length < 2) return;
      const nameEl = cells[0].querySelector("span.truncate, span.block.truncate");
      const sysEl = cells[1].querySelector("div.truncate, div.max-w-40");
      const name = (nameEl?.textContent || "").trim();
      const host = (sysEl?.textContent || "").trim();
      if (!name || !host) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "creanova-pin-btn";
      btn.dataset.host = host;
      btn.dataset.name = name;
      btn.dataset.pinned = "0";
      btn.textContent = "Pin";
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        togglePin(host, name, btn);
      });
      (nameEl || cells[0]).appendChild(btn);
    });
    syncPinButtons();
  }

  function renderPinsPanel() {
    const pins = pinCache || [];
    let panel = document.getElementById("creanova-pins-panel");
    if (!pins.length) {
      if (panel) panel.remove();
      return;
    }
    if (!panel) {
      panel = document.createElement("div");
      panel.id = "creanova-pins-panel";
      document.body.appendChild(panel);
    }
    const items = pins
      .slice(0, 12)
      .map(
        (p) =>
          `<li><span title="${p.host}">${p.container_name}</span>` +
          `<button type="button" data-id="${p.id}" aria-label="Unpin">×</button></li>`,
      )
      .join("");
    panel.innerHTML = `<h3>Agent pins (${pins.length})</h3><ul style="margin:0;padding:0;list-style:none">${items}</ul>`;
    panel.querySelectorAll("button[data-id]").forEach((b) => {
      b.addEventListener("click", async () => {
        try {
          await gatewayFetch(`/api/infra/pinned-containers/${b.dataset.id}`, {
            method: "DELETE",
          });
          await loadPins(true);
          renderPinsPanel();
          syncPinButtons();
          toast("Unpinned", true);
        } catch (e) {
          toast(String(e.message || e), false);
        }
      });
    });
  }

  let pinBooted = false;
  function tickPins() {
    ensurePinCss();
    if (!pbAuth()) return;
    mountPinButtons();
    if (!pinBooted) {
      pinBooted = true;
      loadPins(true).then(() => {
        renderPinsPanel();
        syncPinButtons();
      });
    }
  }

  function tick() {
    brandTitle();
    brandLogo();
    mountAllSystems();
    hideDocumentation();
    tickPins();
  }

  ensureBootCss();
  brandTitle();
  tick();

  const titleEl = document.querySelector("title");
  if (titleEl) {
    new MutationObserver(brandTitle).observe(titleEl, {
      childList: true,
      characterData: true,
      subtree: true,
    });
  }

  // Replace as soon as React mounts the navbar (no 400ms FOUC gap).
  const rootObs = new MutationObserver(() => {
    tick();
  });
  rootObs.observe(document.documentElement, { childList: true, subtree: true });
  setInterval(tick, 1000);
})();

(() => {
  const BRAND = "Creanova";
  // Natural glyph proportions — do NOT use textLength (it stretches letters).
  // Height-only CSS; width follows viewBox aspect ratio.
  const LOGO_SVG =
    '<svg id="creanova-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108 20" class="fill-foreground" aria-hidden="true" style="display:block;height:1.35rem;width:auto">' +
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
    'a[aria-label="Home"]{margin-inline-end:0.5rem!important;padding-block:0.25rem!important;padding-inline:0!important}';

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

  function tick() {
    brandTitle();
    brandLogo();
    mountAllSystems();
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

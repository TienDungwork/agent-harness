(() => {
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

  function mount() {
    if (document.getElementById("creanova-beszel-home")) return;
    const home = document.querySelector('a[aria-label="Home"]');
    if (!home || !home.parentElement) return;
    const a = document.createElement("a");
    a.id = "creanova-beszel-home";
    a.href = home.getAttribute("href") || "/";
    a.setAttribute("aria-label", "All Systems");
    a.textContent = "All Systems";
    a.style.cssText =
      "display:inline-flex;align-items:center;margin-inline-end:0.75rem;font-size:0.875rem;font-weight:500;opacity:0.9;text-decoration:none;color:inherit;cursor:pointer;white-space:nowrap";
    a.addEventListener("click", goHome);
    home.parentElement.insertBefore(a, home.nextSibling);
  }

  setInterval(mount, 400);
})();

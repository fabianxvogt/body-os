// Apply a remembered theme before first paint (no flash). Default: follow the system.
(function () {
  try {
    var t = localStorage.getItem("bos-theme");
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* storage unavailable: follow the system */ }
})();

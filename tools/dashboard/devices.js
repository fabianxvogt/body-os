/* body-os /devices — loopback-only page: QR code + copyable device link for phones in the LAN.
 * Data: GET /api/devices (loopback-only). QR: vendor/qrcode.js (qrcode-generator 1.4.4, MIT). */
(function () {
  "use strict";
  var TX = {
    en: {
      title: "Connect a phone", sub: "Scan the code with the phone's camera, then “Add to Home Screen”.",
      off: "LAN access is off.", off_hint: "Start the dashboard with `bos.py dashboard --lan` (or `bos.py service install --lan`), then reload this page.",
      link: "Device link", copy: "Copy", copied: "Copied", other: "Other addresses",
      warn: "Anyone with this link sees every profile in this household. Share it only with household members, only in your home network. This computer must be on and awake.",
      rotate: "Lost a phone? `bos.py dashboard --rotate-key` invalidates every paired device.",
      steps: ["Phone in the same Wi-Fi as this Mac.", "Scan the QR code (or open the link).", "Share → “Add to Home Screen”."],
      error: "Could not load device information", back: "← Dashboard"
    },
    de: {
      title: "Handy verbinden", sub: "Code mit der Handy-Kamera scannen, dann „Zum Home-Bildschirm“.",
      off: "LAN-Zugriff ist aus.", off_hint: "Dashboard mit `bos.py dashboard --lan` starten (oder `bos.py service install --lan`), dann diese Seite neu laden.",
      link: "Geräte-Link", copy: "Kopieren", copied: "Kopiert", other: "Weitere Adressen",
      warn: "Wer diesen Link hat, sieht alle Profile dieses Haushalts. Nur an Haushaltsmitglieder geben, nur im Heimnetz. Dieser Rechner muss laufen.",
      rotate: "Handy verloren? `bos.py dashboard --rotate-key` macht alle gekoppelten Geräte ungültig.",
      steps: ["Handy im selben WLAN wie dieser Mac.", "QR-Code scannen (oder Link öffnen).", "Teilen → „Zum Home-Bildschirm“."],
      error: "Geräte-Infos konnten nicht geladen werden", back: "← Dashboard"
    }
  };
  var T = TX.en;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function qrSvg(text) {
    var qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    var n = qr.getModuleCount(), q = 4, size = n + 2 * q, d = "";
    for (var r = 0; r < n; r++) for (var c = 0; c < n; c++) if (qr.isDark(r, c)) d += "M" + (c + q) + " " + (r + q) + "h1v1h-1z";
    var ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 " + size + " " + size);
    svg.setAttribute("class", "qr");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "QR code: " + text.replace(/key=.*/, "key=…"));
    svg.setAttribute("shape-rendering", "crispEdges");
    var bg = document.createElementNS(ns, "rect");
    bg.setAttribute("width", size); bg.setAttribute("height", size); bg.setAttribute("fill", "#fff");
    var p = document.createElementNS(ns, "path");
    p.setAttribute("d", d); p.setAttribute("fill", "#000");
    svg.appendChild(bg); svg.appendChild(p);
    return svg;
  }

  function render(info) {
    var card = document.getElementById("d-card");
    card.innerHTML = "";
    if (!info.lan || !info.links.length) {
      card.appendChild(el("h3", null, T.off));
      card.appendChild(el("p", "muted-text", T.off_hint));
      return;
    }
    var cur = info.links[0];
    var grid = el("div", "device-grid"), left = el("div", "qr-box"), right = el("div", "device-side");
    grid.appendChild(left); grid.appendChild(right); card.appendChild(grid);
    var ol = el("ol", "device-steps");
    T.steps.forEach(function (s) { ol.appendChild(el("li", null, s)); });
    right.appendChild(ol);
    var lab = el("label", "device-label", T.link);
    lab.htmlFor = "d-link";
    var row = el("div", "device-row"), inp = el("input", "device-link"), btn = el("button", "icon-btn device-copy", T.copy);
    inp.id = "d-link"; inp.readOnly = true; btn.type = "button";
    row.appendChild(inp); row.appendChild(btn);
    right.appendChild(lab); right.appendChild(row);
    var alts = el("div", "filters");
    function show(l) {
      cur = l;
      left.innerHTML = "";
      left.appendChild(qrSvg(l.link));
      inp.value = l.link;
      alts.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.textContent === l.host)); });
    }
    if (info.links.length > 1) {
      right.appendChild(el("p", "device-label", T.other));
      info.links.forEach(function (l) {
        var b = el("button", "filter", l.host);
        b.type = "button";
        b.addEventListener("click", function () { show(l); });
        alts.appendChild(b);
      });
      right.appendChild(alts);
    }
    btn.addEventListener("click", function () {
      var done = function () { btn.textContent = T.copied; setTimeout(function () { btn.textContent = T.copy; }, 1500); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(cur.link).then(done, function () { inp.select(); });
      else { inp.select(); try { document.execCommand("copy"); done(); } catch (e) { /* manual copy */ } }
    });
    inp.addEventListener("focus", function () { inp.select(); });
    var w = el("p", "banner device-warn");
    w.appendChild(el("b", null, "⚠"));
    w.appendChild(el("span", null, T.warn));
    card.appendChild(w);
    card.appendChild(el("p", "note", T.rotate));
    show(cur);
  }

  function getJSON(u) { return fetch(u, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); }

  getJSON("api/profiles").catch(function () { return {}; }).then(function (p) {
    T = TX[String(p.language || "en").slice(0, 2)] || TX.en;
    document.documentElement.lang = TX[String(p.language || "en").slice(0, 2)] ? String(p.language).slice(0, 2) : "en";
    document.getElementById("d-title").textContent = T.title;
    document.getElementById("d-sub").textContent = T.sub;
    document.getElementById("d-back").textContent = T.back;
    document.title = T.title + " · body-os";
    return getJSON("api/devices");
  }).then(render).catch(function (e) {
    var card = document.getElementById("d-card");
    card.innerHTML = "";
    card.appendChild(el("p", "muted-text", T.error + " (" + (e.message || e) + ")"));
  });
})();

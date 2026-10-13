/* body-os dashboard — small, safe Markdown renderer for reviews and the shopping list.
 * Safety model: every input character is HTML-escaped FIRST; only the tags generated below are
 * ever emitted. Links are kept only for http(s) URLs (opened with rel=noopener noreferrer); anything
 * else (javascript:, data:, relative) renders as plain text. Supported: headings, paragraphs, lists
 * (incl. [ ] / [x] checkboxes), pipe tables, blockquotes, horizontal rules, **bold**, *italic*,
 * `inline code`, [links](https://…). No raw HTML passes through. */
(function () {
  "use strict";

  var ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return ESC[c]; });
  }

  // `u` is already escaped; check the unescaped form, return the escaped form or null.
  function safeUrl(u) {
    var raw = u.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
    return /^https?:\/\/[^\s<>"'`]+$/i.test(raw) ? u : null;
  }

  function inline(text) {
    var keep = [];
    var hold = function (html) { keep.push(html); return "\u0001" + (keep.length - 1) + "\u0002"; };
    var s = esc(String(text == null ? "" : text).replace(/[\u0000-\u0002]/g, ""));
    s = s.replace(/`([^`]+)`/g, function (_, c) { return hold("<code>" + c + "</code>"); });
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (_, label, url) {
      var u = safeUrl(url);
      return u ? hold('<a href="' + u + '" target="_blank" rel="noopener noreferrer">') + label + hold("</a>") : label;
    });
    s = s.replace(/\*\*(?=\S)([^*]*?\S)\*\*|__(?=\S)([^_]*?\S)__/g, function (_, a, b) {
      return "<strong>" + (a || b) + "</strong>";
    });
    s = s.replace(/(^|[^\w*])\*(?=\S)([^*]*?\S)\*(?![\w*])/g, "$1<em>$2</em>");
    s = s.replace(/(^|[^\w])_(?=\S)([^_]*?\S)_(?!\w)/g, "$1<em>$2</em>");
    return s.replace(/\u0001(\d+)\u0002/g, function (_, i) { return keep[+i] || ""; });
  }

  var RE_HEAD = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
  var RE_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
  var RE_RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
  var RE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

  function cells(line) {
    var s = line.trim().replace(/^\|/, "").replace(/\|$/, "");
    return s.split(/(?<!\\)\|/).map(function (c) { return c.trim().replace(/\\\|/g, "|"); });
  }

  function isTable(lines, i) {
    return /\|/.test(lines[i]) && i + 1 < lines.length && RE_SEP.test(lines[i + 1]);
  }

  function isBlock(lines, i) {
    var l = lines[i];
    return RE_HEAD.test(l) || RE_ITEM.test(l) || RE_RULE.test(l) || /^\s*>/.test(l) || isTable(lines, i);
  }

  function item(text, indent) {
    var m = /^\[( |x|X)\]\s+(.*)$/.exec(text), cls = indent >= 2 ? ' class="md-sub"' : "";
    if (!m) return "<li" + cls + ">" + inline(text) + "</li>";
    var done = m[1] !== " ";
    return '<li class="md-task' + (done ? " done" : "") + (indent >= 2 ? " md-sub" : "") + '">' +
      '<span class="md-box" aria-hidden="true">' + (done ? "☑" : "☐") + "</span>" +
      '<span class="sr-only">' + (done ? "[x] " : "[ ] ") + "</span><span>" + inline(m[2]) + "</span></li>";
  }

  function render(md) {
    var lines = String(md == null ? "" : md).replace(/\r\n?/g, "\n").split("\n");
    var out = [], i = 0, n = lines.length, m;
    while (i < n) {
      var line = lines[i];
      if (!line.trim()) { i++; continue; }
      if ((m = RE_HEAD.exec(line))) {
        var lvl = Math.min(6, m[1].length + 2);
        out.push("<h" + lvl + ">" + inline(m[2]) + "</h" + lvl + ">");
        i++;
        continue;
      }
      if (RE_RULE.test(line)) { out.push("<hr>"); i++; continue; }
      if (isTable(lines, i)) {
        var head = cells(line), rows = [];
        i += 2;
        while (i < n && lines[i].trim() && /\|/.test(lines[i])) { rows.push(cells(lines[i])); i++; }
        var h = '<div class="md-table"><table><thead><tr>';
        head.forEach(function (c) { h += "<th>" + inline(c) + "</th>"; });
        h += "</tr></thead><tbody>";
        rows.forEach(function (r) {
          h += "<tr>";
          for (var k = 0; k < head.length; k++) h += "<td>" + inline(r[k] || "") + "</td>";
          h += "</tr>";
        });
        out.push(h + "</tbody></table></div>");
        continue;
      }
      if ((m = RE_ITEM.exec(line))) {
        var ordered = /\d/.test(m[2]), items = [];
        while (i < n) {
          var lm = RE_ITEM.exec(lines[i]);
          if (!lm) {
            if (items.length && lines[i].trim() && /^\s{2,}/.test(lines[i])) {
              items[items.length - 1].text += " " + lines[i].trim();
              i++;
              continue;
            }
            break;
          }
          if (/\d/.test(lm[2]) !== ordered && lm[1].length < 2) break;
          items.push({ text: lm[3], indent: lm[1].length });
          i++;
        }
        var tag = ordered ? "ol" : "ul";
        out.push("<" + tag + ">" + items.map(function (it) { return item(it.text, it.indent); }).join("") + "</" + tag + ">");
        continue;
      }
      if (/^\s*>/.test(line)) {
        var q = [];
        while (i < n && /^\s*>/.test(lines[i])) { q.push(lines[i].replace(/^\s*>\s?/, "")); i++; }
        out.push("<blockquote>" + render(q.join("\n")) + "</blockquote>");
        continue;
      }
      var para = [];
      while (i < n && lines[i].trim() && !(para.length && isBlock(lines, i))) { para.push(lines[i].trim()); i++; }
      out.push("<p>" + inline(para.join(" ")) + "</p>");
    }
    return out.join("");
  }

  window.BosMarkdown = { render: render, inline: inline, escape: esc };
})();

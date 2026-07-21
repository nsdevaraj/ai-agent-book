// Language switcher: populates a <select> dropdown in the header bar.
// Selecting an option navigates to the same page in that edition and
// rewrites all sidebar navigation links to match.
//
// Config injected by header template: window.LANG_CONFIG = {
//   zh:   { label: "中文",     prefix: "book/",          default: true },
//   zhtw: { label: "繁體中文",  prefix: "book-zhtw/",      suffix: ".zhtw" },
//   en:   { label: "English",  prefix: "-book-en/" },
//   ta:   { label: "தமிழ்",    prefix: "book-ta/",        suffix: ".ta" },
//   vi:   { label: "Tiếng Việt", prefix: "book-vi/",       suffix: ".vi" }
// };

(function () {
  "use strict";

  var cfg = window.LANG_CONFIG;
  if (!cfg) return;

  // ── helpers ───────────────────────────────────────────────

  /** Detect active language (longest prefix wins). */
  function detectLang(path) {
    var p = path.replace(/\/$/, "");
    var codes = Object.keys(cfg).sort(function (a, b) {
      return cfg[b].prefix.length - cfg[a].prefix.length;
    });
    for (var i = 0; i < codes.length; i++) {
      if (p.indexOf(cfg[codes[i]].prefix) !== -1) return codes[i];
    }
    for (var c in cfg) {
      if (cfg.hasOwnProperty(c) && cfg[c].default) return c;
    }
    return "zh";
  }

  /** Map current URL → target edition. */
  function mapUrl(currentPath, targetCode, currentLang) {
    if (targetCode === currentLang) return null;
    var src = cfg[currentLang];
    var dst = cfg[targetCode];
    var url = currentPath.replace(src.prefix, dst.prefix);
    if (src.suffix) url = url.replace(src.suffix + ".md", ".md");
    if (dst.suffix) url = url.replace(/\.md$/, dst.suffix + ".md");
    return (
      url ||
      dst.prefix + "introduction" + (dst.suffix || "") + ".md"
    );
  }

  // ── sidebar rewriting ─────────────────────────────────────

  /** Rewrite sidebar nav <a> hrefs for non-default editions. */
  function rewriteSidebar(targetCode) {
    var target = cfg[targetCode];
    var defCode = null;
    for (var c in cfg) { if (cfg[c].default) { defCode = c; break; } }
    defCode = defCode || "zh";
    var defCfg = cfg[defCode];

    var links = document.querySelectorAll(".md-nav__link");
    for (var i = 0; i < links.length; i++) {
      var el = links[i];
      var href = el.getAttribute("href");
      if (!href || href.indexOf("http") === 0 || href.charAt(0) === "#") continue;
      href = href.replace(/^\//, "");

      var defPrefix = (defCfg.prefix || "").replace(/\/$/, "");
      var tgtPrefix = (target.prefix || "").replace(/\/$/, "");

      if (defPrefix && href.indexOf(defPrefix) === 0) {
        href = tgtPrefix + href.slice(defPrefix.length);
      }
      var defSuf = defCfg.suffix || "";
      var tgtSuf = target.suffix || "";
      if (defSuf) href = href.replace(defSuf + ".html", ".html");
      if (tgtSuf && href.indexOf(".html") !== -1) {
        href = href.replace(/\.html$/, tgtSuf + ".html");
      }
      el.setAttribute("href", "/" + href);
    }
  }

  // ── render ────────────────────────────────────────────────

  function render() {
    var path = location.pathname;
    var activeLang = detectLang(path);

    var sel = document.getElementById("lang-selector");
    if (!sel) return;

    // Skip if already populated.
    if (sel.children.length > 0) return;

    // Build options.
    var codes = Object.keys(cfg);
    for (var idx = 0; idx < codes.length; idx++) {
      var code = codes[idx];
      var opt = document.createElement("option");
      opt.value = code;
      opt.textContent = cfg[code].label;
      opt.disabled = false;
      if (code === activeLang) {
        opt.selected = true;
        opt.disabled = true;  // can't select what you're already on
      }
      sel.appendChild(opt);
    }

    // Navigate on change.
    sel.addEventListener("change", function () {
      var target = sel.value;
      if (!target || target === activeLang) return;
      var url = mapUrl(path, target, activeLang);
      if (url) location.href = url;
    });

    // Rewrite sidebar for non-default languages.
    var defCode = null;
    for (var c in cfg) {
      if (cfg[c].default) { defCode = c; break; }
    }
    if (activeLang !== (defCode || "zh")) {
      rewriteSidebar(activeLang);
    }
  }

  // ── bootstrap ──────────────────────────────────────────────

  function boot() {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", render);
    } else {
      render();
    }
    document.addEventListener("locationchange", render);
    var _pushState = history.pushState;
    history.pushState = function () {
      _pushState.apply(this, arguments);
      setTimeout(render, 60);
    };
  }

  boot();
})();

/**
 * SITE-24 — mouse-following grid cursor (Direction A, paper/ink).
 * Shape reference: nikunjk.com. Color: site ink on paper, never neon.
 * Draws only in the side gutters; cells that intersect the main .page column stay empty.
 */
(function () {
  "use strict";

  var CELL = 24;
  var RING = 2;
  var CORNER_PX = 96;
  var RIPPLE_MS = 480;
  var RIPPLE_RINGS = 5;
  var HOT_FILL = 0.08;
  var HOT_FILL_DARK = 0.1;
  var STROKE = [0, 0.16, 0.09];

  var canvas = document.getElementById("grid-cursor");
  if (!canvas || !canvas.getContext) return;

  var fine = window.matchMedia("(pointer: fine)");
  var hover = window.matchMedia("(hover: hover)");
  var motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var desktop = window.matchMedia("(min-width: 901px)"); // CSS: max-width 900px hides canvas
  var ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;

  var active = false;
  var dpr = 1;
  var viewW = 0;
  var viewH = 0;
  var colLeft = 0;
  var colRight = 0;
  var mouseX = -1;
  var mouseY = -1;
  var hasPointer = false;
  var raf = 0;
  var ripples = [];
  var ink = { r: 28, g: 25, b: 20 };
  var themeObs = null;
  var colObs = null;
  var pageEl = null;

  function allowed() {
    return fine.matches && hover.matches && !motion.matches && desktop.matches;
  }

  function parseInk() {
    var raw = getComputedStyle(document.documentElement).getPropertyValue("--fg").trim() || "#1a180f";
    var hex = raw.replace("#", "");
    if (hex.length === 3) {
      hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
    }
    if (hex.length !== 6) {
      ink = { r: 26, g: 24, b: 15 };
      return;
    }
    var n = parseInt(hex, 16);
    ink = { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }

  function rgba(a) {
    return "rgba(" + ink.r + "," + ink.g + "," + ink.b + "," + a + ")";
  }

  function cacheColumn() {
    var el = document.querySelector("main.page") || document.querySelector(".page");
    if (!el) {
      colLeft = 0;
      colRight = viewW;
      return;
    }
    var rect = el.getBoundingClientRect();
    colLeft = rect.left;
    colRight = rect.right;
  }

  function cellInMargin(x) {
    return x + CELL <= colLeft || x >= colRight;
  }

  function cancelDraw() {
    if (raf) {
      cancelAnimationFrame(raf);
      raf = 0;
    }
  }

  function clearSurface() {
    cancelDraw();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function resize() {
    if (!active) return;
    if (!allowed()) {
      stop();
      return;
    }
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    viewW = window.innerWidth;
    viewH = window.innerHeight;
    canvas.width = Math.max(1, Math.floor(viewW * dpr));
    canvas.height = Math.max(1, Math.floor(viewH * dpr));
    canvas.style.width = viewW + "px";
    canvas.style.height = viewH + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    parseInk();
    cacheColumn();
    requestDraw();
  }

  function requestDraw() {
    if (!active || raf) return;
    raf = requestAnimationFrame(paint);
  }

  function strokeCell(x, y, alpha) {
    if (alpha <= 0.004 || !cellInMargin(x)) return;
    ctx.strokeStyle = rgba(alpha);
    ctx.strokeRect(x + 0.5, y + 0.5, CELL - 1, CELL - 1);
  }

  function fillCell(x, y, alpha) {
    if (alpha <= 0.004 || !cellInMargin(x)) return;
    ctx.fillStyle = rgba(alpha);
    ctx.fillRect(x + 1, y + 1, CELL - 2, CELL - 2);
  }

  function paint() {
    raf = 0;
    if (!active) return;
    ctx.clearRect(0, 0, viewW, viewH);
    ctx.lineWidth = 1 / dpr;

    var now = performance.now();
    var liveRipples = [];
    var i, r, t, radius, dx, dy, dist, col, row, x, y;

    if (hasPointer && mouseX >= 0) {
      col = Math.floor(mouseX / CELL);
      row = Math.floor(mouseY / CELL);
      var fillA = document.documentElement.classList.contains("dark") ? HOT_FILL_DARK : HOT_FILL;
      for (dy = -RING; dy <= RING; dy++) {
        for (dx = -RING; dx <= RING; dx++) {
          dist = Math.max(Math.abs(dx), Math.abs(dy));
          x = (col + dx) * CELL;
          y = (row + dy) * CELL;
          if (x < -CELL || y < -CELL || x > viewW || y > viewH) continue;
          if (dist === 0) fillCell(x, y, fillA);
          else strokeCell(x, y, STROKE[dist] || 0);
        }
      }
    }

    for (i = 0; i < ripples.length; i++) {
      r = ripples[i];
      t = (now - r.t0) / RIPPLE_MS;
      if (t >= 1) continue;
      liveRipples.push(r);
      radius = t * RIPPLE_RINGS;
      var alpha = (1 - t) * 0.1;
      var reach = Math.ceil(radius) + 1;
      for (dy = -reach; dy <= reach; dy++) {
        for (dx = -reach; dx <= reach; dx++) {
          dist = Math.max(Math.abs(dx), Math.abs(dy));
          if (Math.abs(dist - radius) > 0.65) continue;
          x = (r.col + dx) * CELL;
          y = (r.row + dy) * CELL;
          strokeCell(x, y, alpha);
        }
      }
    }
    ripples = liveRipples;
    if (!active) {
      ctx.clearRect(0, 0, viewW, viewH);
      return;
    }
    if (ripples.length) requestDraw();
  }

  function onMove(e) {
    if (!active) return;
    if (e.pointerType && e.pointerType !== "mouse") return;
    mouseX = e.clientX;
    mouseY = e.clientY;
    hasPointer = true;
    requestDraw();
  }

  function onLeave(e) {
    if (!active) return;
    if (e && e.relatedTarget) return;
    hasPointer = false;
    mouseX = -1;
    mouseY = -1;
    requestDraw();
  }

  function nearCorner(x, y) {
    var corners = [
      [0, 0],
      [viewW, 0],
      [0, viewH],
      [viewW, viewH],
    ];
    for (var i = 0; i < corners.length; i++) {
      var dx = x - corners[i][0];
      var dy = y - corners[i][1];
      if (dx * dx + dy * dy <= CORNER_PX * CORNER_PX) return true;
    }
    return false;
  }

  function onClick(e) {
    if (!active) return;
    if (!nearCorner(e.clientX, e.clientY)) return;
    ripples.push({
      col: Math.floor(e.clientX / CELL),
      row: Math.floor(e.clientY / CELL),
      t0: performance.now(),
    });
    requestDraw();
  }

  function onTheme() {
    if (!active) return;
    parseInk();
    requestDraw();
  }

  function onColumnResize() {
    if (!active) return;
    cacheColumn();
    requestDraw();
  }

  function bindInput() {
    window.addEventListener("resize", resize, { passive: true });
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("mousemove", onMove, { passive: true });
    document.addEventListener("mouseleave", onLeave, { passive: true });
    window.addEventListener("blur", onLeave);
    window.addEventListener("click", onClick, { passive: true });
  }

  function unbindInput() {
    window.removeEventListener("resize", resize);
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseleave", onLeave);
    window.removeEventListener("blur", onLeave);
    window.removeEventListener("click", onClick);
  }

  function bindObservers() {
    if (!themeObs) themeObs = new MutationObserver(onTheme);
    themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    if (typeof ResizeObserver === "undefined") return;
    pageEl = document.querySelector("main.page") || document.querySelector(".page");
    if (!pageEl) return;
    if (!colObs) colObs = new ResizeObserver(onColumnResize);
    colObs.observe(pageEl);
  }

  function unbindObservers() {
    if (themeObs) themeObs.disconnect();
    if (colObs && pageEl) colObs.unobserve(pageEl);
    pageEl = null;
  }

  function start() {
    if (active) return;
    active = true;
    bindInput();
    bindObservers();
    resize();
  }

  function stop() {
    if (!active) {
      cancelDraw();
      return;
    }
    active = false;
    hasPointer = false;
    mouseX = -1;
    mouseY = -1;
    ripples = [];
    unbindInput();
    unbindObservers();
    clearSurface();
  }

  function onPrefs() {
    if (allowed()) start();
    else stop();
  }

  function listenMq(mq) {
    if (typeof mq.addEventListener === "function") mq.addEventListener("change", onPrefs);
    else if (typeof mq.addListener === "function") mq.addListener(onPrefs);
  }

  listenMq(fine);
  listenMq(hover);
  listenMq(motion);
  listenMq(desktop);

  if (allowed()) start();
})();

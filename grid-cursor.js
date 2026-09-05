/**
 * SITE-24 — mouse-following grid cursor (Direction A, paper/ink).
 * Shape reference: nikunjk.com. Color: site ink on paper, never neon.
 * Dead space = viewport minus main.page content box (sides, top, bottom). Never under prose.
 * Touch: track any tap-and-drag; paint only while the pointer is in dead space.
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
  var TOUCH_MOUSE_GUARD_MS = 700;
  var GUTTER_DRAG_SLOP = 10;

  var canvas = document.getElementById("grid-cursor");
  if (!canvas || !canvas.getContext) return;

  var motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  var ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;

  var active = false;
  var dpr = 1;
  var viewW = 0;
  var viewH = 0;
  var contentL = 0;
  var contentR = 0;
  var contentT = 0;
  var contentB = 0;
  var mouseX = -1;
  var mouseY = -1;
  var hasPointer = false;
  var dragId = null;
  var dragStartX = 0;
  var dragStartY = 0;
  var dragClaimed = false;
  var panLocked = false;
  var ignoreMouseUntil = 0;
  var raf = 0;
  var ripples = [];
  var ink = { r: 28, g: 25, b: 20 };
  var themeObs = null;
  var colObs = null;
  var pageEl = null;
  var moveOpts = { passive: false, capture: true };

  function allowed() {
    return !motion.matches;
  }

  function isMouse(e) {
    return !e.pointerType || e.pointerType === "mouse";
  }

  function isTouchLike(e) {
    return e.pointerType === "touch" || e.pointerType === "pen";
  }

  function inDeadSpace(x, y) {
    return x < contentL || x >= contentR || y < contentT || y >= contentB;
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

  function cacheContentBox() {
    var el = document.querySelector("main.page");
    if (!el) {
      contentL = 0;
      contentR = viewW;
      contentT = 0;
      contentB = viewH;
      return;
    }
    var rect = el.getBoundingClientRect();
    var cs = getComputedStyle(el);
    var padL = parseFloat(cs.paddingLeft) || 0;
    var padR = parseFloat(cs.paddingRight) || 0;
    var padT = parseFloat(cs.paddingTop) || 0;
    var padB = parseFloat(cs.paddingBottom) || 0;
    contentL = rect.left + padL;
    contentR = rect.right - padR;
    contentT = rect.top + padT;
    contentB = rect.bottom - padB;
    if (contentR < contentL) {
      contentL = rect.left;
      contentR = rect.right;
    }
    if (contentB < contentT) {
      contentT = rect.top;
      contentB = rect.bottom;
    }
  }

  function cellInDeadSpace(x, y) {
    var r = x + CELL;
    var b = y + CELL;
    if (r <= contentL || x >= contentR || b <= contentT || y >= contentB) return true;
    return false;
  }

  function clipToDeadSpace() {
    ctx.beginPath();
    ctx.rect(0, 0, viewW, viewH);
    var w = contentR - contentL;
    var h = contentB - contentT;
    if (w > 0 && h > 0) ctx.rect(contentL, contentT, w, h);
    ctx.clip("evenodd");
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
    cacheContentBox();
    requestDraw();
  }

  function requestDraw() {
    if (!active || raf) return;
    raf = requestAnimationFrame(paint);
  }

  function strokeCell(x, y, alpha) {
    if (alpha <= 0.004 || !cellInDeadSpace(x, y)) return;
    ctx.strokeStyle = rgba(alpha);
    ctx.strokeRect(x + 0.5, y + 0.5, CELL - 1, CELL - 1);
  }

  function fillCell(x, y, alpha) {
    if (alpha <= 0.004 || !cellInDeadSpace(x, y)) return;
    ctx.fillStyle = rgba(alpha);
    ctx.fillRect(x + 1, y + 1, CELL - 2, CELL - 2);
  }

  function paint() {
    raf = 0;
    if (!active) return;
    cacheContentBox();
    ctx.clearRect(0, 0, viewW, viewH);
    ctx.save();
    clipToDeadSpace();
    ctx.lineWidth = 1 / dpr;

    var now = performance.now();
    var liveRipples = [];
    var i, r, t, radius, dx, dy, dist, col, row, x, y;

    if (hasPointer && mouseX >= 0 && inDeadSpace(mouseX, mouseY)) {
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
    ctx.restore();
    ripples = liveRipples;
    if (!active) {
      ctx.clearRect(0, 0, viewW, viewH);
      return;
    }
    if (ripples.length) requestDraw();
  }

  function follow(x, y) {
    mouseX = x;
    mouseY = y;
    hasPointer = true;
    requestDraw();
  }

  function clearFollow() {
    hasPointer = false;
    mouseX = -1;
    mouseY = -1;
    requestDraw();
  }

  function lockPan() {
    if (panLocked) return;
    panLocked = true;
    document.documentElement.style.touchAction = "none";
    if (document.body) document.body.style.touchAction = "none";
  }

  function unlockPan() {
    if (!panLocked) return;
    panLocked = false;
    document.documentElement.style.touchAction = "";
    if (document.body) document.body.style.touchAction = "";
  }

  function claimMarginGesture(e, x, y) {
    if (!e || !e.cancelable) return;
    if (inDeadSpace(x, y)) {
      dragClaimed = true;
      lockPan();
      e.preventDefault();
      return;
    }
    if (dragClaimed) {
      e.preventDefault();
      return;
    }
    var dx = x - dragStartX;
    var towardLeft = dx < -GUTTER_DRAG_SLOP && dragStartX < viewW / 2;
    var towardRight = dx > GUTTER_DRAG_SLOP && dragStartX >= viewW / 2;
    if (towardLeft || towardRight) {
      dragClaimed = true;
      lockPan();
      e.preventDefault();
    }
  }

  function beginTouchDrag(id, x, y) {
    cacheContentBox();
    dragId = id;
    dragStartX = x;
    dragStartY = y;
    dragClaimed = inDeadSpace(x, y);
    if (dragClaimed) lockPan();
    follow(x, y);
  }

  function endDrag() {
    dragId = null;
    dragClaimed = false;
    unlockPan();
    ignoreMouseUntil = performance.now() + TOUCH_MOUSE_GUARD_MS;
    clearFollow();
  }

  function onPointerDown(e) {
    if (!active || !isTouchLike(e)) return;
    if (dragId !== null) return;
    beginTouchDrag(e.pointerId, e.clientX, e.clientY);
    claimMarginGesture(e, e.clientX, e.clientY);
  }

  function onPointerMove(e) {
    if (!active) return;
    if (isTouchLike(e)) {
      if (dragId !== e.pointerId) return;
      follow(e.clientX, e.clientY);
      claimMarginGesture(e, e.clientX, e.clientY);
      return;
    }
    if (!isMouse(e)) return;
    if (dragId !== null || performance.now() < ignoreMouseUntil) return;
    follow(e.clientX, e.clientY);
  }

  function onPointerUp(e) {
    if (!active || dragId !== e.pointerId) return;
    endDrag();
  }

  function onPointerCancel(e) {
    if (!active || dragId !== e.pointerId) return;
    if (dragClaimed) return;
    endDrag();
  }

  function onMouseMove(e) {
    if (!active || dragId !== null || performance.now() < ignoreMouseUntil) return;
    follow(e.clientX, e.clientY);
  }

  function onLeave(e) {
    if (!active || dragId !== null) return;
    if (e && e.relatedTarget) return;
    clearFollow();
  }

  function touchId() {
    if (typeof dragId !== "string" || dragId.indexOf("touch:") !== 0) return NaN;
    return parseInt(dragId.slice(6), 10);
  }

  function findTouch(list, id) {
    if (!list) return null;
    for (var i = 0; i < list.length; i++) {
      if (list[i].identifier === id) return list[i];
    }
    return null;
  }

  function activeTouch(e) {
    var id = touchId();
    if (!isNaN(id)) {
      return findTouch(e.touches, id) || findTouch(e.changedTouches, id);
    }
    if (e.touches && e.touches.length) return e.touches[0];
    if (e.changedTouches && e.changedTouches.length) return e.changedTouches[0];
    return null;
  }

  function onTouchStart(e) {
    if (!active || !e.touches || !e.touches.length) return;
    var t = e.touches[0];
    if (dragId === null) beginTouchDrag("touch:" + t.identifier, t.clientX, t.clientY);
    claimMarginGesture(e, t.clientX, t.clientY);
  }

  function onTouchMove(e) {
    if (!active || dragId === null) return;
    var t = activeTouch(e);
    if (!t) return;
    follow(t.clientX, t.clientY);
    claimMarginGesture(e, t.clientX, t.clientY);
  }

  function onTouchEnd(e) {
    if (!active || dragId === null) return;
    if (e.touches && e.touches.length) return;
    endDrag();
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
    if (e.pointerType && e.pointerType !== "mouse") return;
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
    cacheContentBox();
    requestDraw();
  }

  function onScroll() {
    if (!active) return;
    cacheContentBox();
    requestDraw();
  }

  function bindInput() {
    window.addEventListener("resize", resize, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("pointerdown", onPointerDown, moveOpts);
    window.addEventListener("pointermove", onPointerMove, moveOpts);
    window.addEventListener("pointerup", onPointerUp, { passive: true });
    window.addEventListener("pointercancel", onPointerCancel, { passive: true });
    window.addEventListener("touchstart", onTouchStart, moveOpts);
    window.addEventListener("touchmove", onTouchMove, moveOpts);
    window.addEventListener("touchend", onTouchEnd, { passive: true });
    window.addEventListener("touchcancel", onTouchEnd, { passive: true });
    window.addEventListener("mousemove", onMouseMove, { passive: true });
    document.addEventListener("mouseleave", onLeave, { passive: true });
    window.addEventListener("blur", onLeave);
    window.addEventListener("click", onClick, { passive: true });
  }

  function unbindInput() {
    window.removeEventListener("resize", resize);
    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("pointerdown", onPointerDown, moveOpts);
    window.removeEventListener("pointermove", onPointerMove, moveOpts);
    window.removeEventListener("pointerup", onPointerUp);
    window.removeEventListener("pointercancel", onPointerCancel);
    window.removeEventListener("touchstart", onTouchStart, moveOpts);
    window.removeEventListener("touchmove", onTouchMove, moveOpts);
    window.removeEventListener("touchend", onTouchEnd);
    window.removeEventListener("touchcancel", onTouchEnd);
    window.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseleave", onLeave);
    window.removeEventListener("blur", onLeave);
    window.removeEventListener("click", onClick);
  }

  function bindObservers() {
    if (!themeObs) themeObs = new MutationObserver(onTheme);
    themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    if (typeof ResizeObserver === "undefined") return;
    pageEl = document.querySelector("main.page");
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
    dragId = null;
    dragClaimed = false;
    unlockPan();
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

  listenMq(motion);

  if (allowed()) start();
})();

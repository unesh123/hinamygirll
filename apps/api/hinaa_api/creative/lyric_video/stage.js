(function () {
"use strict";
const S = JSON.parse(document.getElementById("spec").textContent);
const W = S.width, H = S.height, FPS = S.fps, P = S.palette;
const PORTRAIT = H >= W * 1.2;
const U = Math.min(W, H);
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const eOutCubic = t => 1 - Math.pow(1 - clamp(t, 0, 1), 3);
const eOutBack = t => { t = clamp(t, 0, 1); const c = 1.9; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); };
const mod = (a, n) => ((a % n) + n) % n;
function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const NS = "http://www.w3.org/2000/svg";
const $ = (html, tag) => { const d = document.createElement(tag || "div"); d.innerHTML = html; return d.firstElementChild; };

const stage = document.getElementById("stage");
stage.style.width = W + "px"; stage.style.height = H + "px";
const world = document.getElementById("world");

/* ------------------------------------------------------------- particles */
const PETAL = '<svg width="40" height="40" viewBox="0 0 40 40"><path d="M20 3C32 8 36 24 20 37C4 24 8 8 20 3Z" fill="#ffb6d5"/><path d="M20 3C26 12 24 26 20 37" stroke="#ff8fc0" stroke-width="2" fill="none"/></svg>';
const HEART = '<svg width="40" height="40" viewBox="0 0 40 40"><path d="M20 35C5 24 3 14 9 9C14 5 19 8 20 12C21 8 26 5 31 9C37 14 35 24 20 35Z" fill="__C__"/><ellipse cx="13" cy="13" rx="3" ry="2" fill="#fff" opacity=".6"/></svg>';
const SPARK = '<svg width="40" height="40" viewBox="0 0 40 40"><path d="M20 0C22 14 26 18 40 20C26 22 22 26 20 40C18 26 14 22 0 20C14 18 18 14 20 0Z" fill="__C__"/></svg>';
const SNOW = '<svg width="40" height="40" viewBox="0 0 40 40"><circle cx="20" cy="20" r="16" fill="#fff"/></svg>';
function particles(layer, n, kind, seed, o) {
  const r = rng(seed), list = [];
  for (let i = 0; i < n; i++) {
    const el = document.createElement("div"); el.className = "p";
    let src = kind === "petal" ? PETAL : kind === "snow" ? SNOW : kind === "heart" ? HEART.replace("__C__", ["#ff5fa8", "#ff8ac4", "#ffd0e8", "#fff"][i % 4]) : SPARK.replace("__C__", ["#fff", "#fff6b0", "#ffd0f0"][i % 3]);
    el.innerHTML = src;
    const size = lerp(o.min, o.max, r());
    el.firstChild.setAttribute("width", size); el.firstChild.setAttribute("height", size);
    if (kind === "snow") el.style.opacity = lerp(.55, 1, r());
    layer.appendChild(el);
    list.push({ el, size, x: r() * W, y: r() * (H + 200), sp: lerp(o.spMin, o.spMax, r()), sw: lerp(20, 90, r()), f: lerp(.6, 1.8, r()), ph: r() * 6.28, rs: lerp(-90, 90, r()), tw: lerp(1.5, 4, r()) });
  }
  return t => {
    for (const p of list) {
      let x, y, sc = 1, rot = p.rs * t, op;
      if (kind === "heart") { y = H + 120 - mod(p.y + p.sp * t, H + 240); x = p.x + Math.sin(t * p.f + p.ph) * p.sw; rot = Math.sin(t * p.f + p.ph) * 18; sc = .8 + .2 * Math.sin(t * 4 + p.ph); }
      else if (kind === "spark") { x = p.x; y = p.y % H; const s = Math.sin(t * p.tw + p.ph); sc = clamp(s * .5 + .6, 0, 1.1); rot = 45 * s; }
      else { y = mod(p.y + p.sp * t, H + 200) - 100; x = p.x + Math.sin(t * p.f + p.ph) * p.sw + (o.wind || 0) * t; x = mod(x + 80, W + 160) - 80; if (kind === "petal") sc = Math.abs(Math.cos(t * p.f * 1.5 + p.ph)) * .6 + .4; }
      p.el.style.transform = "translate3d(" + x.toFixed(1) + "px," + y.toFixed(1) + "px,0) rotate(" + rot.toFixed(1) + "deg) scale(" + sc.toFixed(3) + ")";
    }
  };
}

/* ---------------------------------------------------------------- scenes */
function cloudPath(x, y, s) {
  return '<g class="cl" data-x="' + x + '" transform="translate(' + x + ' ' + y + ') scale(' + s + ')"><g>' +
    '<ellipse cx="0" cy="22" rx="150" ry="38" fill="#ffd9ec" opacity=".7"/>' +
    '<circle cx="-70" cy="0" r="46" fill="#fff"/><circle cx="-15" cy="-26" r="62" fill="#fff"/><circle cx="55" cy="-6" r="50" fill="#fff"/><circle cx="105" cy="10" r="34" fill="#fff"/>' +
    '<ellipse cx="0" cy="14" rx="145" ry="30" fill="#fff"/></g></g>';
}
function hillPath(yBase, amp, freq, ph, fill, extra) {
  let d = "M-10 " + (H + 10) + " L-10 " + yBase;
  for (let x = -10; x <= W + 10; x += 20) d += " L" + x + " " + (yBase + Math.sin(x / W * freq * 6.28 + ph) * amp + Math.sin(x / W * freq * 14 + ph * 2) * amp * .25).toFixed(1);
  return '<path d="' + d + ' L' + (W + 10) + ' ' + (H + 10) + ' Z" fill="' + fill + '"' + (extra || "") + "/>";
}
function sceneBase(inner, defs) {
  const el = document.createElement("div"); el.className = "scene";
  el.innerHTML = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '"><defs>' + (defs || "") + "</defs>" + inner + "</svg>";
  return el;
}
const grad = (id, stops, x2, y2) => '<linearGradient id="' + id + '" x1="0" y1="0" x2="' + (x2 || 0) + '" y2="' + (y2 === undefined ? 1 : y2) + '">' + stops.map(s => '<stop offset="' + s[0] + '" stop-color="' + s[1] + '"/>').join("") + "</linearGradient>";
function drift(el, speeds) {
  const cl = el.querySelectorAll(".cl");
  return t => cl.forEach((c, i) => {
    const x0 = +c.dataset.x, sp = speeds[i % speeds.length];
    const y = c.getAttribute("transform").match(/translate\([^ ]+ ([^)]+)\) scale\(([^)]+)\)/);
    c.setAttribute("transform", "translate(" + (mod(x0 + sp * t + 300, W + 600) - 300).toFixed(1) + " " + y[1] + ") scale(" + y[2] + ")");
  });
}
const SCENES = {
  "dreamy-sky"(k) {
    const el = sceneBase(
      '<rect width="' + W + '" height="' + H + '" fill="url(#g' + k + ')"/>' +
      '<circle cx="' + W * .78 + '" cy="' + H * .2 + '" r="' + U * .42 + '" fill="url(#s' + k + ')"/>' +
      cloudPath(W * .15, H * .12, U / 700) + cloudPath(W * .8, H * .3, U / 560) + cloudPath(W * .4, H * .62, U / 500) + cloudPath(W * .9, H * .8, U / 640) + cloudPath(W * .05, H * .88, U / 420),
      grad("g" + k, [[0, "#8fc9ff"], [.5, "#d6b9ff"], [1, "#ffc7e6"]]) + '<radialGradient id="s' + k + '"><stop offset="0" stop-color="#fffbe0" stop-opacity=".95"/><stop offset=".35" stop-color="#fff2c8" stop-opacity=".5"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>');
    const lay = document.createElement("div"); lay.className = "layer"; el.appendChild(lay);
    const a = drift(el, [14, -9, 18, -12, 8]), b = particles(lay, 22, "petal", 11 + k, { min: 26, max: 52, spMin: 70, spMax: 150, wind: 20 }), c = particles(lay, 16, "spark", 5 + k, { min: 18, max: 40, spMin: 0, spMax: 0 });
    return { el, update: t => { a(t); b(t); c(t); } };
  },
  "hills-day"(k) {
    const el = sceneBase(
      '<rect width="' + W + '" height="' + H + '" fill="url(#g' + k + ')"/>' +
      '<g id="sun' + k + '" transform="translate(' + W * .22 + ' ' + H * .17 + ')"><circle r="' + U * .34 + '" fill="#fff6c0" opacity=".45"/><circle r="' + U * .2 + '" fill="#ffe27a"/><circle r="' + U * .15 + '" fill="#fff3a8"/></g>' +
      cloudPath(W * .7, H * .14, U / 620) + cloudPath(W * .3, H * .36, U / 700) + cloudPath(W * .92, H * .5, U / 700) +
      hillPath(H * .56, H * .03, 1.2, 0, "#b5e8a0") + hillPath(H * .66, H * .035, 1.7, 2, "#8ede8c") + hillPath(H * .78, H * .03, 1.1, 4, "#67cf86") + hillPath(H * .9, H * .02, 1.5, 1, "#4fc07f") + flowers(k),
      grad("g" + k, [[0, "#7cc8ff"], [.55, "#c6ecff"], [1, "#fff4d6"]]));
    const lay = document.createElement("div"); lay.className = "layer"; el.appendChild(lay);
    const a = drift(el, [12, -8, 10]), b = particles(lay, 24, "petal", 21 + k, { min: 24, max: 48, spMin: 60, spMax: 130, wind: 30 }), c = particles(lay, 10, "spark", 3 + k, { min: 16, max: 32, spMin: 0, spMax: 0 });
    const sun = el.querySelector("#sun" + k);
    return { el, update: t => { a(t); b(t); c(t); const s = 1 + Math.sin(t * 1.6) * .03; sun.setAttribute("transform", "translate(" + W * .22 + " " + H * .17 + ") scale(" + s.toFixed(3) + ")"); } };
  },
  "starry-night-flags"(k) {
    const r = rng(77 + k); let stars = "";
    for (let i = 0; i < 90; i++) stars += '<circle class="st" cx="' + (r() * W).toFixed(0) + '" cy="' + (r() * H * .62).toFixed(0) + '" r="' + (1.5 + r() * 3.5).toFixed(1) + '" fill="#fff" data-ph="' + (r() * 6.28).toFixed(2) + '" data-f="' + (1 + r() * 3).toFixed(2) + '"/>';
    let flags = "";
    [[.2, .27, 11], [.28, .2, 9]].forEach((cfg, row) => {
      const x0 = -30, x1 = W + 30, y0 = H * cfg[0], y1 = H * (cfg[0] + .05), sag = H * .045, n = cfg[2], cols = ["#5aa9ff", "#ffffff", "#ff5f6d", "#5fe39a", "#ffd95a"];
      let d = "M" + x0 + " " + y0 + " Q" + (W / 2) + " " + (y0 + y1) / 2 + sag * 2 + " " + x1 + " " + y1;
      flags += '<path d="M' + x0 + " " + y0 + " Q" + W / 2 + " " + ((y0 + y1) / 2 + sag * 2) + " " + x1 + " " + y1 + '" stroke="#f3e3ff" stroke-width="3" fill="none"/>';
      for (let i = 0; i < n; i++) {
        const u = (i + .5) / n, x = lerp(x0, x1, u), y = (1 - u) * (1 - u) * y0 + 2 * u * (1 - u) * ((y0 + y1) / 2 + sag * 2) + u * u * y1, fw = W / n * .62;
        flags += '<g class="fl" data-ph="' + (i * .7 + row) + '" transform="translate(' + x.toFixed(1) + " " + y.toFixed(1) + ')"><path d="M' + (-fw / 2) + " 0 L" + (fw / 2) + " 0 L" + (fw / 2) + " " + fw * .9 + " L" + (-fw / 2) + " " + fw * .9 + 'Z" fill="' + cols[(i + row * 2) % 5] + '" opacity=".95"/></g>';
      }
    });
    const el = sceneBase(
      '<rect width="' + W + '" height="' + H + '" fill="url(#g' + k + ')"/>' + stars +
      '<circle cx="' + W * .76 + '" cy="' + H * .13 + '" r="' + U * .2 + '" fill="url(#m' + k + ')"/><circle cx="' + W * .76 + '" cy="' + H * .13 + '" r="' + U * .075 + '" fill="#fff8d8"/><circle cx="' + (W * .76 + U * .03) + '" cy="' + (H * .13 - U * .015) + '" r="' + U * .066 + '" fill="#e9dcff" opacity=".0"/>' +
      hillPath(H * .62, H * .035, 1.1, 1, "#5b3a9a") + hillPath(H * .72, H * .03, 1.6, 3, "#3d2575") + hillPath(H * .86, H * .025, 1.2, 0, "#271553") + flags,
      grad("g" + k, [[0, "#1a1250"], [.5, "#52298f"], [.85, "#c45fb0"], [1, "#ff9fc4"]]) + '<radialGradient id="m' + k + '"><stop offset="0" stop-color="#fff8d8" stop-opacity=".8"/><stop offset="1" stop-color="#fff8d8" stop-opacity="0"/></radialGradient>');
    const lay = document.createElement("div"); lay.className = "layer"; el.appendChild(lay);
    const st = el.querySelectorAll(".st"), fl = el.querySelectorAll(".fl");
    const c = particles(lay, 18, "spark", 9 + k, { min: 16, max: 38, spMin: 0, spMax: 0 }), b = particles(lay, 10, "petal", 4 + k, { min: 22, max: 40, spMin: 50, spMax: 100, wind: 25 });
    return { el, update: t => {
      st.forEach(s => s.setAttribute("opacity", (.45 + .55 * Math.abs(Math.sin(t * +s.dataset.f + +s.dataset.ph))).toFixed(2)));
      fl.forEach(f => { const m = f.getAttribute("transform").match(/translate\(([^ ]+) ([^)]+)\)/); f.setAttribute("transform", "translate(" + m[1] + " " + m[2] + ") rotate(" + (Math.sin(t * 3 + +f.dataset.ph) * 7).toFixed(2) + ")"); });
      c(t); b(t);
    } };
  },
  "snow-window"(k) {
    const m = U * .06, fw = U * .035;
    const el = sceneBase(
      '<rect width="' + W + '" height="' + H + '" fill="url(#g' + k + ')"/>' + bokeh(k) +
      '<rect x="' + (m + fw / 2) + '" y="' + (m + fw / 2) + '" width="' + (W - 2 * m - fw) + '" height="' + (H - 2 * m - fw) + '" rx="' + U * .08 + '" fill="none" stroke="#fff" stroke-width="' + fw + '" opacity=".95"/>' +
      '<rect x="' + (m - fw * .6) + '" y="' + (m - fw * .6) + '" width="' + (W - 2 * m + fw * 1.2) + '" height="' + (H - 2 * m + fw * 1.2) + '" rx="' + U * .09 + '" fill="none" stroke="#ffb3d6" stroke-width="' + fw * .6 + '"/>' +
      '<path d="M' + W / 2 + " " + m + " V" + (H - m) + " M" + m + " " + H * .42 + " H" + (W - m) + '" stroke="#fff" stroke-width="' + fw * .6 + '" opacity=".8"/>' +
      '<rect x="' + m + '" y="' + m + '" width="' + (W - 2 * m) + '" height="' + (H - 2 * m) + '" rx="' + U * .08 + '" fill="url(#f' + k + ')"/>',
      grad("g" + k, [[0, "#6fa8ff"], [.55, "#a9c4ff"], [1, "#ffc2e2"]]) + '<radialGradient id="f' + k + '"><stop offset=".7" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".35"/></radialGradient>');
    const lay = document.createElement("div"); lay.className = "layer"; el.appendChild(lay);
    const a = particles(lay, 70, "snow", 31 + k, { min: 6, max: 26, spMin: 60, spMax: 190, wind: 12 }), c = particles(lay, 12, "spark", 8 + k, { min: 18, max: 34, spMin: 0, spMax: 0 });
    const bk = el.querySelectorAll(".bk");
    return { el, update: t => { a(t); c(t); bk.forEach(b => b.setAttribute("opacity", (.35 + .3 * Math.sin(t * 1.4 + +b.dataset.ph)).toFixed(2))); } };
  },
  "love-burst"(k) {
    let rays = ""; const N = 18;
    for (let i = 0; i < N; i += 2) { const a0 = i / N * 6.2832, a1 = (i + 1) / N * 6.2832, R = Math.hypot(W, H); rays += '<path d="M0 0 L' + (Math.cos(a0) * R).toFixed(0) + " " + (Math.sin(a0) * R).toFixed(0) + " L" + (Math.cos(a1) * R).toFixed(0) + " " + (Math.sin(a1) * R).toFixed(0) + ' Z" fill="#fff" opacity=".16"/>'; }
    const el = sceneBase(
      '<rect width="' + W + '" height="' + H + '" fill="url(#g' + k + ')"/><g id="ry' + k + '" transform="translate(' + W / 2 + " " + H * .48 + ')">' + rays + "</g>" +
      '<g id="rg' + k + '" transform="translate(' + W / 2 + " " + H * .48 + ')"><circle r="10" fill="none" stroke="#fff" stroke-width="10" opacity=".5"/><circle r="10" fill="none" stroke="#fff" stroke-width="6" opacity=".5"/><circle r="10" fill="none" stroke="#ffd0ea" stroke-width="8" opacity=".5"/></g>',
      '<radialGradient id="g' + k + '" cx=".5" cy=".48" r=".75"><stop offset="0" stop-color="#ffd1ea"/><stop offset=".45" stop-color="#ff8cc6"/><stop offset="1" stop-color="#a95cff"/></radialGradient>');
    const lay = document.createElement("div"); lay.className = "layer"; el.appendChild(lay);
    const a = particles(lay, 26, "heart", 41 + k, { min: 28, max: 70, spMin: 90, spMax: 240 }), c = particles(lay, 22, "spark", 6 + k, { min: 16, max: 40, spMin: 0, spMax: 0 });
    const ry = el.querySelector("#ry" + k), rg = el.querySelector("#rg" + k).children;
    return { el, update: t => {
      ry.setAttribute("transform", "translate(" + W / 2 + " " + H * .48 + ") rotate(" + (t * 9).toFixed(2) + ")");
      for (let i = 0; i < 3; i++) { const u = mod(t * .45 + i / 3, 1); rg[i].setAttribute("r", (u * Math.hypot(W, H) * .6).toFixed(1)); rg[i].setAttribute("opacity", (.55 * (1 - u)).toFixed(2)); }
      a(t); c(t);
    } };
  }
};
function flowers(k) {
  const r = rng(300 + k); let s = "";
  for (let i = 0; i < 26; i++) { const x = r() * W, y = H * (.74 + r() * .24), c = ["#ff8fc0", "#fff", "#ffe27a", "#c9a0ff"][i % 4], z = U * (.008 + r() * .008); s += '<g transform="translate(' + x.toFixed(0) + " " + y.toFixed(0) + ')">' + [0, 72, 144, 216, 288].map(a => '<circle cx="' + (Math.cos(a * .01745) * z * 1.5).toFixed(1) + '" cy="' + (Math.sin(a * .01745) * z * 1.5).toFixed(1) + '" r="' + z + '" fill="' + c + '"/>').join("") + '<circle r="' + z * .8 + '" fill="#ffb020"/></g>'; }
  return s;
}
function bokeh(k) {
  const r = rng(500 + k); let s = "";
  for (let i = 0; i < 16; i++) s += '<circle class="bk" data-ph="' + (r() * 6).toFixed(2) + '" cx="' + (r() * W).toFixed(0) + '" cy="' + (r() * H).toFixed(0) + '" r="' + (U * (.03 + r() * .06)).toFixed(0) + '" fill="' + ["#ffb3d6", "#fff1a8", "#b3d8ff", "#fff"][i % 4] + '" opacity=".4"/>';
  return s;
}

/* ------------------------------------------------------------- character */
const CHAR_SVG = '<svg viewBox="0 0 400 640" xmlns="' + NS + '"><defs>' +
  '<linearGradient id="hairG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5a3f9e"/><stop offset="1" stop-color="#2d1d5e"/></linearGradient>' +
  '<linearGradient id="dressG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffa6d5"/><stop offset="1" stop-color="#ff6fb8"/></linearGradient>' +
  '<radialGradient id="irisG" cx=".5" cy=".3" r=".8"><stop offset="0" stop-color="#ffb8f0"/><stop offset=".55" stop-color="#9a6bff"/><stop offset="1" stop-color="#4a2fb0"/></radialGradient>' +
  '<radialGradient id="skinG" cx=".5" cy=".4" r=".7"><stop offset="0" stop-color="#fff0e6"/><stop offset="1" stop-color="#ffd3c0"/></radialGradient></defs>' +
  '<g stroke="#4a2a6a" stroke-width="4" stroke-linejoin="round" stroke-linecap="round">' +
  '<g id="tailL" style="transform-origin:128px 170px"><path d="M128 170C70 190 40 280 52 380C58 440 76 470 92 440C84 400 98 330 134 280Z" fill="url(#hairG)"/><path d="M70 300C64 340 66 380 76 410" stroke="#8f78d6" stroke-width="5" fill="none" opacity=".7"/></g>' +
  '<g id="tailR" style="transform-origin:272px 170px"><path d="M272 170C330 190 360 280 348 380C342 440 324 470 308 440C316 400 302 330 266 280Z" fill="url(#hairG)"/><path d="M330 300C336 340 334 380 324 410" stroke="#8f78d6" stroke-width="5" fill="none" opacity=".7"/></g>' +
  '<ellipse cx="200" cy="200" rx="112" ry="112" fill="url(#hairG)"/>' +
  '<g><path d="M178 310H222V340H178Z" fill="#ffd3c0"/>' +
  '<path d="M150 335C120 340 112 380 118 430L120 470C108 480 102 500 108 520C150 540 250 540 292 520C298 500 292 480 280 470L282 430C288 380 280 340 250 335Z" fill="url(#dressG)"/>' +
  '<path d="M114 505C130 525 150 505 166 525C182 505 200 525 216 505C232 525 250 505 266 525C276 515 284 510 292 508" stroke="#fff" stroke-width="7" fill="none"/>' +
  '<path d="M170 335L200 372L230 335Z" fill="#fff"/><path d="M200 372L168 400L232 400Z" fill="#fff" opacity="0"/></g>' +
  '<g><path d="M176 540V590" stroke="#ffd3c0" stroke-width="22" fill="none"/><path d="M224 540V590" stroke="#ffd3c0" stroke-width="22" fill="none"/>' +
  '<path d="M165 566H187V592H165Z M213 566H235V592H213Z" fill="#fff"/>' +
  '<ellipse cx="170" cy="606" rx="32" ry="17" fill="#c07bff"/><ellipse cx="230" cy="606" rx="32" ry="17" fill="#c07bff"/></g>' +
  '<g id="armL" style="transform-origin:150px 350px"><path d="M148 352C120 380 112 410 118 440" stroke="#ffd3c0" stroke-width="22" fill="none"/><circle cx="118" cy="446" r="16" fill="#ffd3c0"/><ellipse cx="146" cy="356" rx="22" ry="20" fill="#fff"/></g>' +
  '<g id="armR" style="transform-origin:252px 352px"><path d="M252 352C290 338 316 306 322 262" stroke="#ffd3c0" stroke-width="22" fill="none"/><circle cx="322" cy="254" r="17" fill="#ffd3c0"/><ellipse cx="254" cy="356" rx="22" ry="20" fill="#fff"/></g>' +
  '<path d="M178 372C186 392 214 392 222 372L212 358H188Z" fill="#c07bff"/><circle cx="200" cy="368" r="9" fill="#ff5fa8"/>' +
  '<ellipse cx="200" cy="226" rx="98" ry="90" fill="url(#skinG)"/>' +
  '<g id="eyeL" style="transform-origin:154px 238px"><ellipse cx="154" cy="238" rx="25" ry="31" fill="#fff"/><ellipse cx="154" cy="242" rx="20" ry="27" fill="url(#irisG)" stroke="none"/><ellipse cx="154" cy="244" rx="9" ry="14" fill="#2a1450" stroke="none"/><circle cx="146" cy="230" r="8" fill="#fff" stroke="none"/><circle cx="163" cy="256" r="4" fill="#fff" stroke="none"/><path d="M126 222C138 204 166 202 180 220" stroke-width="7" fill="none"/></g>' +
  '<g id="eyeR" style="transform-origin:246px 238px"><ellipse cx="246" cy="238" rx="25" ry="31" fill="#fff"/><ellipse cx="246" cy="242" rx="20" ry="27" fill="url(#irisG)" stroke="none"/><ellipse cx="246" cy="244" rx="9" ry="14" fill="#2a1450" stroke="none"/><circle cx="238" cy="230" r="8" fill="#fff" stroke="none"/><circle cx="255" cy="256" r="4" fill="#fff" stroke="none"/><path d="M220 220C234 202 262 204 274 222" stroke-width="7" fill="none"/></g>' +
  '<ellipse cx="124" cy="274" rx="19" ry="11" fill="#ff8fb5" opacity=".55" stroke="none"/><ellipse cx="276" cy="274" rx="19" ry="11" fill="#ff8fb5" opacity=".55" stroke="none"/>' +
  '<g id="mouth"><ellipse id="mouthO" cx="200" cy="282" rx="13" ry="7" fill="#c2255c" stroke-width="3"/><ellipse cx="200" cy="288" rx="7" ry="3" fill="#ff8fa8" stroke="none"/></g>' +
  '<path d="M104 215C110 140 160 108 200 108C246 108 292 142 296 218C278 196 268 168 254 150C240 178 190 192 150 186C132 190 118 204 104 215Z" fill="url(#hairG)"/>' +
  '<path d="M150 186C160 170 176 156 196 148C190 168 176 184 150 186Z M214 150C232 160 250 170 262 192C244 188 224 176 214 150Z" fill="#6b4fb8" stroke="none" opacity=".8"/>' +
  '<path d="M200 108C198 80 216 62 236 60C228 72 226 84 232 96" fill="none" stroke-width="5"/>' +
  '<g transform="translate(116 150)"><path d="M0 0L-26 -16V16Z M0 0L26 -16V16Z" fill="#ff5fa8"/><circle r="9" fill="#ff9fcb"/></g>' +
  '<g transform="translate(284 150)"><path d="M0 0L-26 -16V16Z M0 0L26 -16V16Z" fill="#c07bff"/><circle r="9" fill="#e0c0ff"/></g>' +
  '<path d="M262 112l5 12 13 2-10 9 3 13-11-7-11 7 3-13-10-9 13-2Z" fill="#ffe27a" stroke-width="3"/>' +
  "</g></svg>";

let charEl = document.getElementById("char"), charApi = null;
function buildChar() {
  if (S.character_data) { charEl.innerHTML = '<img src="' + S.character_data + '">'; return; }
  charEl.innerHTML = CHAR_SVG;
  const q = id => charEl.querySelector("#" + id);
  charApi = { tailL: q("tailL"), tailR: q("tailR"), armL: q("armL"), armR: q("armR"), eyeL: q("eyeL"), eyeR: q("eyeR"), mouthO: q("mouthO") };
}
const LAY = PORTRAIT
  ? { ch: Math.min(H * .43, W * .98 * 1.6), cx: .5, bottom: .8, topZone: [.07, .335], botZone: [.82, .96] }
  : { ch: H * .5, cx: .5, bottom: .8, topZone: [.075, .3], botZone: [.81, .95] };
const charH = LAY.ch, charW = charH * .625;
charEl.style.width = charW + "px"; charEl.style.height = charH + "px";
buildChar();
const charX = W * LAY.cx - charW / 2, charY = H * LAY.bottom - charH;

/* ------------------------------------------------------------------ text */
const FILLS = [P.text, P.accent, P.accent2];
const STROKES = [P.outline, "#ffffff", "#ffffff"];
function shade(hex, f) { const n = parseInt(hex.slice(1), 16); const c = i => Math.round(clamp(((n >> i) & 255) * f, 0, 255)); return "rgb(" + c(16) + "," + c(8) + "," + c(0) + ")"; }
const lineEls = S.lines.map((ln, li) => {
  const layer = document.createElement("div"); layer.className = "layer"; world.appendChild(layer);
  const words = ln.text.split(/\s+/).filter(Boolean);
  const half = words.length === 1 ? words.length : Math.ceil(words.length / 2);
  const groups = words.length === 1 ? [words] : [words.slice(0, half), words.slice(half)];
  const zones = [LAY.topZone, LAY.botZone];
  const base = U * (PORTRAIT ? .138 : .135);
  const out = [];
  const gap = clamp((ln.end - ln.start) * .62 / words.length, .1, .38);
  let wi = 0;
  groups.forEach((g, gi) => {
    const zone = zones[gi], zoneH = (zone[1] - zone[0]) * H, zoneTop = zone[0] * H;
    const rows = [[]], widths = [0];
    g.forEach(w => { const m = document.createElement("span"); m.className = "word"; m.style.cssText = "position:absolute;visibility:hidden;font-size:" + base + "px"; m.textContent = w; layer.appendChild(m); const est = m.getBoundingClientRect().width; layer.removeChild(m); if (widths[widths.length - 1] + est > W * .86 / .68 && rows[rows.length - 1].length) { rows.push([]); widths.push(0); } rows[rows.length - 1].push(w); widths[widths.length - 1] += est + base * .2; });
    const rowH = Math.min(zoneH / rows.length, base * 1.55);
    const block = rowH * rows.length;
    const y0 = gi === 0 ? zoneTop + zoneH - block : zoneTop;
    rows.forEach((rw, ri) => {
      const row = document.createElement("div"); row.className = "row"; row.style.top = (y0 + ri * rowH) + "px"; row.style.height = rowH + "px";
      const spans = rw.map(w => { const sp = document.createElement("span"); sp.className = "word"; sp.textContent = w; row.appendChild(sp); return sp; });
      layer.appendChild(row);
      const fs = Math.min(base * (1 + .1 * ((wi + li) % 2)), rowH * .84);
      spans.forEach(sp => sp.style.fontSize = fs + "px");
      let total = 0; spans.forEach(sp => total += sp.getBoundingClientRect().width); total += fs * .3 * (spans.length - 1);
      const k = Math.min(1, W * .86 / total); row.style.gap = (fs * k * .3) + "px";
      spans.forEach(sp => {
        const idx = wi++, fill = FILLS[(idx + li) % 3], stroke = STROKES[(idx + li) % 3];
        sp.style.fontSize = (fs * k) + "px"; sp.style.color = fill;
        const sw = Math.max(5, fs * k * .13);
        sp.style.webkitTextStroke = sw + "px " + (stroke === "#ffffff" ? P.outline : stroke);
        sp.style.textShadow = "0 " + fs * k * .07 + "px 0 " + shade(P.outline, .6) + ", 0 " + fs * k * .14 + "px " + fs * k * .16 + "px rgba(40,0,70,.45)";
        out.push({ el: sp, t0: ln.start + .06 + idx * gap, rot: ((idx * 37 + li * 11) % 7 - 3) * 1.3, ph: idx });
      });
    });
  });
  layer.style.display = "none";
  return { layer, words: out };
});

/* ---------------------------------------------------------------- extras */
const SPOTS = PORTRAIT ? [[.2, .5], [.8, .47], [.22, .64], [.78, .6]] : [[.2, .55], [.8, .5], [.18, .72], [.82, .68]];
const stickerEls = S.stickers.map((st, i) => {
  const el = document.createElement("div"); el.className = "sticker"; el.textContent = st.text; el.style.display = "none";
  el.style.fontSize = U * .042 + "px"; el.style.padding = ".3em .8em";
  world.appendChild(el);
  const sp = SPOTS[i % SPOTS.length];
  return { el, at: st.at, rot: (i % 2 ? 1 : -1) * (4 + (i * 3) % 5), x: sp[0] * W, y: sp[1] * H };
});
const titleEl = document.getElementById("title"); titleEl.textContent = "\u266A " + S.title; titleEl.style.fontSize = U * .03 + "px"; titleEl.style.top = H * .012 + "px";
const flash = document.getElementById("flash");

const scenes = S.lines.map((ln, i) => SCENES[ln.scene](i));
scenes.forEach((s, i) => { s.el.style.display = "none"; world.insertBefore(s.el, charEl); });
const TRANS = .45;

function lineIndexAt(t) { let idx = 0; for (let i = 0; i < S.lines.length; i++) if (t >= S.lines[i].start) idx = i; return idx; }

function render(t) {
  const li = lineIndexAt(t), ln = S.lines[li], loc = Math.max(0, t - ln.start), dur = ln.end - ln.start;
  /* scenes */
  scenes.forEach((s, i) => {
    const st = S.lines[i].start;
    const visible = i === li || (i === li - 1 && t - ln.start < TRANS);
    s.el.style.display = visible ? "block" : "none";
    if (!visible) return;
    s.update(t);
    if (i === li && i > 0 && t - st < TRANS) {
      const p = eOutCubic((t - st) / TRANS), r = p * Math.hypot(W, H) * .58;
      s.el.style.clipPath = "circle(" + r.toFixed(1) + "px at " + (W / 2).toFixed(0) + "px " + (H * .5).toFixed(0) + "px)";
    } else s.el.style.clipPath = "none";
  });
  /* camera: push in, punch on line start, alternate tilt */
  const push = .09 * eOutCubic(loc / Math.max(dur, .1)), punch = .13 * Math.exp(-loc * 7), dir = li % 2 ? 1 : -1;
  const sc = 1 + push + punch, rot = dir * (.9 * eOutCubic(loc / dur) - .5) , px = dir * lerp(-10, 14, eOutCubic(loc / dur)) * (W / 1080);
  world.style.transformOrigin = "50% 52%";
  world.style.transform = "translate3d(" + px.toFixed(1) + "px,0,0) rotate(" + rot.toFixed(3) + "deg) scale(" + sc.toFixed(4) + ")";
  /* character */
  const bob = Math.sin(t * 5.2) * charH * .012, squash = 1 + .05 * Math.exp(-loc * 8) * Math.cos(loc * 28);
  charEl.style.transform = "translate3d(" + charX.toFixed(1) + "px," + (charY + bob).toFixed(1) + "px,0) scale(" + (2 - squash).toFixed(4) + "," + squash.toFixed(4) + ")";
  if (charApi) {
    const sing = t >= ln.start && t <= ln.end ? Math.abs(Math.sin(t * 13)) : 0, blink = mod(t, 3.1) < .13 ? .08 : 1;
    charApi.tailL.style.transform = "rotate(" + (Math.sin(t * 3.1) * 4 + 1).toFixed(2) + "deg)";
    charApi.tailR.style.transform = "rotate(" + (Math.sin(t * 3.1 + 1.4) * -4 - 1).toFixed(2) + "deg)";
    charApi.armR.style.transform = "rotate(" + (Math.sin(t * 7) * 12).toFixed(2) + "deg)";
    charApi.armL.style.transform = "rotate(" + (Math.sin(t * 3.5 + 1) * 4).toFixed(2) + "deg)";
    charApi.eyeL.style.transform = charApi.eyeR.style.transform = "scaleY(" + blink + ")";
    charApi.mouthO.setAttribute("ry", (2 + sing * 9).toFixed(2));
    charApi.mouthO.setAttribute("rx", (11 + sing * 3).toFixed(2));
  }
  /* lyrics */
  lineEls.forEach((le, i) => {
    le.layer.style.display = i === li ? "block" : "none";
    if (i !== li) return;
    const exit = clamp((t - (ln.end - .16)) / .16, 0, 1);
    le.words.forEach(w => {
      const a = t - w.t0;
      if (a < 0) { w.el.style.opacity = 0; return; }
      const s = eOutBack(a / .3) * (1 - .25 * exit), wob = Math.sin(a * 22) * 7 * Math.exp(-a * 5);
      const fl = Math.sin(t * 3 + w.ph * 1.7) * U * .004;
      w.el.style.opacity = (1 - exit).toFixed(3);
      w.el.style.transform = "translateY(" + (fl + (1 - clamp(a / .3, 0, 1)) * U * .035).toFixed(1) + "px) rotate(" + (w.rot + wob).toFixed(2) + "deg) scale(" + s.toFixed(3) + ")";
    });
  });
  /* stickers */
  stickerEls.forEach(s => {
    const a = t - s.at, life = 2.6;
    if (a < 0 || a > life) { s.el.style.display = "none"; return; }
    s.el.style.display = "block";
    const sc = a < .35 ? eOutBack(a / .35) : a > life - .25 ? 1 - eOutCubic((a - (life - .25)) / .25) : 1 + Math.sin(a * 4) * .03;
    const w = s.el.offsetWidth, h = s.el.offsetHeight, sx = clamp(s.x, w / 2 + W * .05, W - w / 2 - W * .05);
    s.el.style.transform = "translate3d(" + (sx - w / 2).toFixed(1) + "px," + (s.y - h / 2 + Math.sin(a * 3) * 6).toFixed(1) + "px,0) rotate(" + s.rot + "deg) scale(" + Math.max(sc, 0).toFixed(3) + ")";
  });
  /* title chip and transition flash */
  const ta = t < 3 ? clamp(t / .3, 0, 1) * clamp((3 - t) / .4, 0, 1) : 0;
  titleEl.style.opacity = ta.toFixed(3);
  titleEl.style.transform = "translateX(-50%)";
  flash.style.opacity = li > 0 ? (.5 * Math.exp(-loc * 9)).toFixed(3) : "0";
}

window.__totalFrames = Math.round(S.total * FPS);
window.__setFrame = n => { render(n / FPS); return n; };
window.__ready = false;
(document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(() => {
  const img = charEl.querySelector("img");
  const done = () => { render(0); window.__ready = true; };
  if (img && !img.complete) img.onload = img.onerror = done; else done();
});
})();

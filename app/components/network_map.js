// Network map of the simulation workspace (Streamlit components v2; no external library, works offline).
//
// Draws only what Python sends: the dataset's building footprints, one receiver-grid layer of a computed
// result (or nothing), the site-rule candidate roofs, and the stations with their traced sector antennas.
// Every user action is one event; Python decides what it means (snapping to a roof, refusing a monument).
// Pan and zoom, hover readout and distance measurement stay in the browser (no rerun).

const HALF_BEAM_DEG = 32.5;          // half of the 65° half-power beamwidth of the 3GPP TR 38.901 element
const NO_PATH = -9999;               // outdoor cell the ray tracer did not reach (sent by Python)

export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  let st = parentElement.__bnsMap;
  if (!st || !st.root.isConnected) {
    st = create(parentElement);
    parentElement.__bnsMap = st;
  }
  st.emit = (event) => setTriggerValue("event", { ...event, n: Date.now() * 1000 + (st.seq = (st.seq + 1) % 1000) });
  update(st, data);
  return () => { if (!st.root.isConnected) st.observer.disconnect(); };
}

// ------------------------------------------------------------------ set-up
function create(parent) {
  const root = document.createElement("div");
  root.className = "bns-map";
  root.tabIndex = 0;
  root.innerHTML = `
    <canvas></canvas>
    <div class="toolbar" role="toolbar"></div>
    <div class="hint"></div>
    <div class="badge" hidden></div>
    <div class="legend" hidden></div>
    <div class="status" aria-live="polite"></div>`;
  parent.appendChild(root);
  const st = {
    root, canvas: root.querySelector("canvas"), toolbar: root.querySelector(".toolbar"),
    hint: root.querySelector(".hint"), badge: root.querySelector(".badge"), legend: root.querySelector(".legend"),
    status: root.querySelector(".status"), d: null, mode: "select", scale: 1, tx: 0, ty: 0, fitted: null,
    geomRev: null, buildings: [], groups: null, groupKey: null, rasterRev: null, raster: null, lut: null,
    drag: null, ghost: null, measure: [], hover: null, seq: 0, frame: 0, dpr: window.devicePixelRatio || 1,
  };
  st.ctx = st.canvas.getContext("2d");
  st.observer = new ResizeObserver(() => { resize(st); draw(st); });
  st.observer.observe(root);
  bindPointer(st);
  return st;
}

function update(st, d) {
  st.d = d;
  st.root.style.height = `${d.height || 640}px`;
  st.root.dir = d.rtl ? "rtl" : "ltr";
  if (d.geometry_rev !== st.geomRev) {
    st.buildings = parseBuildings(d.buildings);
    st.geomRev = d.geometry_rev;
    st.groups = null;
  }
  const boundsKey = JSON.stringify(d.bounds);
  if (st.fitted !== boundsKey) { st.fitted = boundsKey; resize(st); fit(st); }
  if (d.raster_rev !== st.rasterRev) { st.raster = buildRaster(d.raster); st.rasterRev = d.raster_rev; }
  if (d.mode_request && d.mode_request.n !== st.modeRequest) { st.modeRequest = d.mode_request.n; st.mode = d.mode_request.mode; }
  st.ghost = null;
  renderToolbar(st);
  renderLegend(st);
  renderBadge(st);
  draw(st);
}

function parseBuildings(b) {
  if (!b) return [];
  const out = [];
  for (let i = 0; i < b.id.length; i++) {
    const rings = b.rings[i].map((r) => Float64Array.from(r, (v) => v / 10));   // decimetres -> metres
    const ext = rings[0];
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let k = 0; k < ext.length; k += 2) {
      x0 = Math.min(x0, ext[k]); x1 = Math.max(x1, ext[k]); y0 = Math.min(y0, ext[k + 1]); y1 = Math.max(y1, ext[k + 1]);
    }
    out.push({ id: b.id[i], h: b.h[i], cat: b.cat[i], rings, bbox: [x0, y0, x1, y1] });
  }
  return out;
}

// ------------------------------------------------------------------ view transform (x east, y north; screen y down)
const X = (st, x) => x * st.scale + st.tx;
const Y = (st, y) => -y * st.scale + st.ty;
const toWorld = (st, px, py) => [(px - st.tx) / st.scale, -(py - st.ty) / st.scale];

function resize(st) {
  const w = st.root.clientWidth, h = st.root.clientHeight;
  if (!w || !h) return;
  st.dpr = window.devicePixelRatio || 1;
  st.canvas.width = Math.round(w * st.dpr);
  st.canvas.height = Math.round(h * st.dpr);
  st.canvas.style.width = `${w}px`;
  st.canvas.style.height = `${h}px`;
  st.w = w; st.h = h;
}

function fit(st) {
  const b = (st.d && (st.d.receiver || st.d.bounds)) || [-500, -500, 500, 500];
  const w = st.w || st.root.clientWidth || 800, h = st.h || st.root.clientHeight || 600;
  const pad = 28;
  st.scale = Math.min((w - 2 * pad) / (b[2] - b[0]), (h - 2 * pad - 30) / (b[3] - b[1]));
  st.tx = w / 2 - ((b[0] + b[2]) / 2) * st.scale;
  st.ty = (h - 30) / 2 + ((b[1] + b[3]) / 2) * st.scale;
}

function zoomAt(st, px, py, factor) {
  const [wx, wy] = toWorld(st, px, py);
  st.scale = Math.min(Math.max(st.scale * factor, 0.05), 40);
  st.tx = px - wx * st.scale;
  st.ty = py + wy * st.scale;
}

// ------------------------------------------------------------------ colours
function hexToRgb(h) {
  const v = parseInt(h.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

function ramp(stops, t) {
  const n = stops.length - 1, x = Math.min(Math.max(t, 0), 1) * n, i = Math.min(Math.floor(x), n - 1), f = x - i;
  const a = hexToRgb(stops[i]), b = hexToRgb(stops[i + 1]);
  return [0, 1, 2].map((k) => Math.round(a[k] + (b[k] - a[k]) * f));
}

const css = (rgb, a = 1) => `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a})`;

function buildRaster(r) {
  if (!r) return null;
  const c = document.createElement("canvas");
  c.width = r.nx; c.height = r.ny;
  const g = c.getContext("2d"), img = g.createImageData(r.nx, r.ny);
  const noPath = hexToRgb(r.no_path_color || "#cfccc2");
  const cats = (r.cat_colors || []).map(hexToRgb);
  let unreached = false;
  for (let i = 0; i < r.ny; i++) {
    for (let j = 0; j < r.nx; j++) {
      const v = r.values[i * r.nx + j];
      const o = ((r.ny - 1 - i) * r.nx + j) * 4;           // row 0 of the array is the south edge
      if (v === null || v === undefined) continue;       // indoor: transparent
      let rgb;
      if (v === NO_PATH) { rgb = noPath; unreached = true; }
      else if (r.kind === "cat") { if (v < 0 || v >= cats.length) continue; rgb = cats[v]; }
      else rgb = ramp(r.colors, (v - r.vmin) / (r.vmax - r.vmin));
      img.data[o] = rgb[0]; img.data[o + 1] = rgb[1]; img.data[o + 2] = rgb[2]; img.data[o + 3] = 255;
    }
  }
  g.putImageData(img, 0, 0);
  return { canvas: c, spec: r, unreached };
}

function buildingGroups(st) {
  const d = st.d, mode = d.building_fill || "plain";
  const key = `${st.geomRev}|${mode}|${!!d.raster}`;
  if (st.groupKey === key && st.groups) return st.groups;
  const groups = new Map();
  const hs = d.height_scale, cats = d.category_colors || {};
  for (const b of st.buildings) {
    let colour;
    if (mode === "height" && hs) colour = css(ramp(hs.colors, (b.h - hs.vmin) / (hs.vmax - hs.vmin)), 0.92);
    else if (mode === "category") colour = cats[b.cat] || "#b9b8b0";
    else colour = d.raster ? "rgba(120,118,110,0.62)" : "rgba(170,168,158,0.75)";
    if (!groups.has(colour)) groups.set(colour, new Path2D());
    const p = groups.get(colour);
    for (const ring of b.rings) {
      p.moveTo(ring[0], ring[1]);
      for (let k = 2; k < ring.length; k += 2) p.lineTo(ring[k], ring[k + 1]);
      p.closePath();
    }
  }
  st.groups = groups; st.groupKey = key;
  return groups;
}

// ------------------------------------------------------------------ drawing
function draw(st) {
  if (st.frame) return;
  st.frame = requestAnimationFrame(() => { st.frame = 0; paint(st); });
}

function paint(st) {
  const d = st.d, g = st.ctx, dpr = st.dpr;
  if (!d || !st.w) return;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = "#efeee9";
  g.fillRect(0, 0, st.w, st.h);

  if (d.receiver) {                                     // receiver area
    const [x0, y0, x1, y1] = d.receiver;
    g.fillStyle = "#f7f6f2";
    g.fillRect(X(st, x0), Y(st, y1), (x1 - x0) * st.scale, (y1 - y0) * st.scale);
  }
  if (st.raster) {
    const r = st.raster.spec, half = r.dx / 2;
    const x0 = r.x0 - half, y1 = r.y0 + (r.ny - 1) * r.dx + half;
    g.imageSmoothingEnabled = false;
    g.globalAlpha = r.stale ? 0.32 : 0.95;
    g.drawImage(st.raster.canvas, X(st, x0), Y(st, y1), r.nx * r.dx * st.scale, r.ny * r.dx * st.scale);
    g.globalAlpha = 1;
    if (r.stale) hatch(st, X(st, x0), Y(st, y1), r.nx * r.dx * st.scale, r.ny * r.dx * st.scale);
  }
  // buildings, in world coordinates
  g.setTransform(dpr * st.scale, 0, 0, -dpr * st.scale, dpr * st.tx, dpr * st.ty);
  for (const [colour, path] of buildingGroups(st)) { g.fillStyle = colour; g.fill(path, "evenodd"); }
  g.lineWidth = 0.6 / st.scale;
  g.strokeStyle = "rgba(70,68,60,0.55)";
  for (const [, path] of st.groups) g.stroke(path);
  const sel = d.selected || {};
  if (sel.kind === "building") {
    const b = st.buildings.find((x) => x.id === sel.id);
    if (b) {
      const p = new Path2D();
      for (const ring of b.rings) { p.moveTo(ring[0], ring[1]); for (let k = 2; k < ring.length; k += 2) p.lineTo(ring[k], ring[k + 1]); p.closePath(); }
      g.lineWidth = 2.5 / st.scale; g.strokeStyle = "#0b0b0b"; g.stroke(p);
    }
  }
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (d.receiver) {
    const [x0, y0, x1, y1] = d.receiver;
    g.setLineDash([5, 4]); g.lineWidth = 1; g.strokeStyle = "rgba(60,60,60,0.55)";
    g.strokeRect(X(st, x0), Y(st, y1), (x1 - x0) * st.scale, (y1 - y0) * st.scale);
    g.setLineDash([]);
  }
  for (const c of d.candidates || []) {                  // site-rule candidate roofs
    const sx = X(st, c.x), sy = Y(st, c.y);
    g.strokeStyle = "#5a5952"; g.lineWidth = 1.2; g.strokeRect(sx - 4, sy - 4, 8, 8);
  }
  if (sel.kind === "cell" && st.raster) {
    const r = st.raster.spec, half = r.dx / 2;
    g.strokeStyle = "#0b0b0b"; g.lineWidth = 2;
    g.strokeRect(X(st, sel.x - half), Y(st, sel.y + half), r.dx * st.scale, r.dx * st.scale);
  }
  for (const s of d.stations || []) drawStation(st, s, sel.kind === "station" && sel.id === s.id);
  if (st.ghost) drawGhost(st);
  drawMeasure(st);
  drawScale(st);
  drawNorth(st);
}

function hatch(st, x, y, w, h) {
  const g = st.ctx;
  g.save();
  g.beginPath(); g.rect(x, y, w, h); g.clip();
  g.strokeStyle = "rgba(120,90,30,0.18)"; g.lineWidth = 1;
  for (let k = -h; k < w; k += 14) { g.beginPath(); g.moveTo(x + k, y + h); g.lineTo(x + k + h, y); g.stroke(); }
  g.restore();
}

function wedge(g, sx, sy, bearingDeg, radius, colour, alpha) {
  const b = (bearingDeg * Math.PI) / 180, a = Math.atan2(-Math.cos(b), Math.sin(b));
  const h = (HALF_BEAM_DEG * Math.PI) / 180;
  g.beginPath(); g.moveTo(sx, sy); g.arc(sx, sy, radius, a - h, a + h); g.closePath();
  g.fillStyle = css(hexToRgb(colour), alpha); g.fill();
  g.strokeStyle = css(hexToRgb(colour), Math.min(alpha * 2.4, 1)); g.lineWidth = 1; g.stroke();
}

function drawStation(st, s, selected) {
  const g = st.ctx, sx = X(st, s.x), sy = Y(st, s.y), colour = s.enabled ? s.colour : "#9a9890";
  const radius = Math.min(Math.max(55 * st.scale, 18), 70);
  (s.bearings || []).forEach((b, k) => {
    const p = (s.sectors_xy || [])[k] || [s.x, s.y];
    wedge(g, X(st, p[0]), Y(st, p[1]), b, radius, colour, s.enabled ? 0.22 : 0.1);
  });
  for (const p of s.sectors_xy || []) {                  // traced antenna positions (roof edge)
    g.beginPath(); g.arc(X(st, p[0]), Y(st, p[1]), 2.2, 0, 2 * Math.PI); g.fillStyle = colour; g.fill();
  }
  if (selected) {
    g.beginPath(); g.arc(sx, sy, 13, 0, 2 * Math.PI);
    g.strokeStyle = "#0b0b0b"; g.lineWidth = 2; g.setLineDash([]); g.stroke();
  }
  g.beginPath();
  if (s.mount === "hypothetical") {                      // hollow diamond, dashed: not an assessed site
    g.moveTo(sx, sy - 8); g.lineTo(sx + 8, sy); g.lineTo(sx, sy + 8); g.lineTo(sx - 8, sy); g.closePath();
    g.fillStyle = "#ffffff"; g.fill(); g.setLineDash([2.5, 2]); g.strokeStyle = colour; g.lineWidth = 2.2; g.stroke();
    g.setLineDash([]);
  } else {
    g.moveTo(sx, sy - 9); g.lineTo(sx + 8, sy + 6); g.lineTo(sx - 8, sy + 6); g.closePath();
    g.fillStyle = colour; g.fill(); g.strokeStyle = "#111"; g.lineWidth = 1.2; g.stroke();
  }
  g.font = "600 12px system-ui, 'Segoe UI', sans-serif";
  g.lineWidth = 3; g.strokeStyle = "rgba(255,255,255,0.9)"; g.strokeText(s.label, sx + 10, sy - 8);
  g.fillStyle = s.enabled ? "#111" : "#77756d"; g.fillText(s.label, sx + 10, sy - 8);
}

function drawGhost(st) {
  const g = st.ctx, s = (st.d.stations || []).find((x) => x.id === st.ghost.id);
  if (!s) return;
  const ax = X(st, s.x), ay = Y(st, s.y), bx = X(st, st.ghost.x), by = Y(st, st.ghost.y);
  g.setLineDash([4, 3]); g.strokeStyle = "#111"; g.lineWidth = 1.2;
  g.beginPath(); g.moveTo(ax, ay); g.lineTo(bx, by); g.stroke(); g.setLineDash([]);
  g.beginPath(); g.arc(bx, by, 7, 0, 2 * Math.PI); g.strokeStyle = s.colour; g.lineWidth = 2.5; g.stroke();
}

function drawMeasure(st) {
  const m = st.measure;
  if (!m.length) return;
  const g = st.ctx;
  const pts = m.length === 1 && st.hover ? [m[0], st.hover.world] : m;
  g.strokeStyle = "#0b0b0b"; g.lineWidth = 1.6; g.setLineDash([6, 3]);
  g.beginPath(); g.moveTo(X(st, pts[0][0]), Y(st, pts[0][1]));
  if (pts[1]) g.lineTo(X(st, pts[1][0]), Y(st, pts[1][1]));
  g.stroke(); g.setLineDash([]);
  for (const p of pts) { g.beginPath(); g.arc(X(st, p[0]), Y(st, p[1]), 3.5, 0, 2 * Math.PI); g.fillStyle = "#0b0b0b"; g.fill(); }
  if (pts[1]) {
    const dist = Math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]);
    const tx = (X(st, pts[0][0]) + X(st, pts[1][0])) / 2, ty = (Y(st, pts[0][1]) + Y(st, pts[1][1])) / 2;
    const text = `${dist < 1000 ? dist.toFixed(1) : dist.toFixed(0)} m`;
    g.font = "600 12px system-ui, 'Segoe UI', sans-serif";
    const w = g.measureText(text).width + 10;
    g.fillStyle = "rgba(255,255,255,0.92)"; g.fillRect(tx - w / 2, ty - 20, w, 18);
    g.fillStyle = "#0b0b0b"; g.textAlign = "center"; g.fillText(text, tx, ty - 7); g.textAlign = "start";
  }
}

function drawScale(st) {
  const g = st.ctx, target = 110 / st.scale;
  const nice = [5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000].find((v) => v >= target * 0.6) || 2000;
  const px = nice * st.scale, x = st.d.rtl ? st.w - 16 - px : 16, y = st.h - 42;
  g.fillStyle = "rgba(255,255,255,0.85)"; g.fillRect(x - 6, y - 16, px + 12, 24);
  g.strokeStyle = "#111"; g.lineWidth = 2;
  g.beginPath(); g.moveTo(x, y - 4); g.lineTo(x, y); g.lineTo(x + px, y); g.lineTo(x + px, y - 4); g.stroke();
  g.font = "11px system-ui, 'Segoe UI', sans-serif"; g.fillStyle = "#111"; g.textAlign = "center";
  g.fillText(`${nice} m`, x + px / 2, y - 5); g.textAlign = "start";
}

function drawNorth(st) {
  const g = st.ctx, x = st.d.rtl ? 26 : st.w - 26, y = 56;
  g.fillStyle = "rgba(255,255,255,0.85)"; g.beginPath(); g.arc(x, y, 15, 0, 2 * Math.PI); g.fill();
  g.fillStyle = "#111"; g.beginPath(); g.moveTo(x, y - 11); g.lineTo(x + 5, y + 3); g.lineTo(x, y); g.lineTo(x - 5, y + 3);
  g.closePath(); g.fill();
  g.font = "600 10px system-ui, sans-serif"; g.textAlign = "center"; g.fillText("N", x, y + 13); g.textAlign = "start";
}

// ------------------------------------------------------------------ overlays (DOM)
const ICONS = {
  select: "M5 3l13 9-6 1.2L15 20l-2.4 1-3-6.6L5 18z",
  place: "M12 2a6 6 0 0 0-6 6c0 4.5 6 12 6 12s6-7.5 6-12a6 6 0 0 0-6-6zm0 3v6m-3-3h6",
  move: "M12 2l3 3h-2v6h6V9l3 3-3 3v-2h-6v6h2l-3 3-3-3h2v-6H5v2l-3-3 3-3v2h6V5H9z",
  measure: "M3 17L17 3l4 4L7 21zM7 13l2 2m1-5l2 2m1-5l2 2",
  fit: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
};

function svg(path) {
  return `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="${path}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function renderToolbar(st) {
  const t = st.d.texts || {};
  const tools = ["select", "place", "move", "measure"];
  st.toolbar.innerHTML = tools.map((m) =>
    `<button type="button" data-mode="${m}" class="${st.mode === m ? "on" : ""}" aria-pressed="${st.mode === m}" title="${t["tip_" + m] || ""}">${svg(ICONS[m])}<span>${t[m] || m}</span></button>`).join("")
    + `<span class="sep"></span><button type="button" data-action="fit" title="${t.tip_fit || ""}">${svg(ICONS.fit)}<span>${t.fit || "Fit"}</span></button>`;
  st.toolbar.querySelectorAll("button[data-mode]").forEach((b) => {
    b.onclick = () => { setMode(st, b.dataset.mode); };
  });
  st.toolbar.querySelector("button[data-action=fit]").onclick = () => { fit(st); draw(st); };
  st.hint.textContent = t["hint_" + st.mode] || "";
  st.root.dataset.mode = st.mode;
}

function setMode(st, mode) {
  st.mode = mode;
  if (mode !== "measure") st.measure = [];
  renderToolbar(st);
  draw(st);
}

function renderBadge(st) {
  const r = st.d.raster, t = st.d.texts || {};
  if (r && r.stale) { st.badge.hidden = false; st.badge.textContent = t.stale || "stale"; }
  else st.badge.hidden = true;
}

function renderLegend(st) {
  const d = st.d, r = d.raster, el = st.legend;
  let html = "";
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  if (r) {
    html += `<div class="title">${esc(r.title)}${r.unit ? ` <bdi>[${esc(r.unit)}]</bdi>` : ""}</div>`;
    if (r.kind === "cat") {
      html += (r.ticktext || []).map((label, k) => `<div class="sw"><i style="background:${r.cat_colors[k]}"></i><bdi>${esc(label)}</bdi></div>`).join("");
    } else {
      const grad = `linear-gradient(to right, ${r.colors.join(",")})`;
      const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => r.vmin + f * (r.vmax - r.vmin));
      html += `<div class="bar" style="background:${grad}"></div><div class="ticks" dir="ltr">${ticks.map((v) => `<span>${fmt(v, r.decimals)}</span>`).join("")}</div>`;
      if (r.below_note) html += `<div class="note">${esc(r.below_note)}</div>`;
    }
    if (st.raster && st.raster.unreached && d.texts) html += `<div class="sw"><i style="background:${r.no_path_color}"></i>${esc(d.texts.no_path)}</div>`;
  } else if (d.building_fill === "height" && d.height_scale) {
    const hs = d.height_scale;
    html += `<div class="title">${esc(hs.title)} <bdi>[m]</bdi></div><div class="bar" style="background:linear-gradient(to right, ${hs.colors.join(",")})"></div>`
      + `<div class="ticks" dir="ltr">${[0, 0.5, 1].map((f) => `<span>${fmt(hs.vmin + f * (hs.vmax - hs.vmin), 0)}</span>`).join("")}</div>`;
  } else if (d.building_fill === "category" && d.category_labels) {
    html += `<div class="title">${esc(d.category_title)}</div>` + Object.entries(d.category_labels)
      .map(([k, label]) => `<div class="sw"><i style="background:${d.category_colors[k]}"></i>${esc(label)}</div>`).join("");
  }
  if (d.legend_note) html += `<div class="note">${esc(d.legend_note)}</div>`;
  el.hidden = !html;
  el.innerHTML = html;
}

function fmt(v, decimals) {
  return Number.isFinite(v) ? v.toFixed(decimals === undefined ? 0 : decimals) : "—";
}

// ------------------------------------------------------------------ hit tests
function inRing(ring, x, y) {
  let inside = false;
  for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) {
    const xi = ring[i], yi = ring[i + 1], xj = ring[j], yj = ring[j + 1];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function hitBuilding(st, x, y) {
  for (const b of st.buildings) {
    const [x0, y0, x1, y1] = b.bbox;
    if (x < x0 || x > x1 || y < y0 || y > y1) continue;
    let inside = false;
    for (const ring of b.rings) if (inRing(ring, x, y)) inside = !inside;    // holes flip it back
    if (inside) return b;
  }
  return null;
}

function hitStation(st, px, py) {
  let best = null, bestD = 12;
  for (const s of st.d.stations || []) {
    const dd = Math.hypot(X(st, s.x) - px, Y(st, s.y) - py);
    if (dd < bestD) { best = s; bestD = dd; }
  }
  return best;
}

function cellAt(st, x, y) {
  const r = st.raster && st.raster.spec;
  if (!r) return null;
  const j = Math.round((x - r.x0) / r.dx), i = Math.round((y - r.y0) / r.dx);
  if (i < 0 || j < 0 || i >= r.ny || j >= r.nx) return null;
  return { i, j, x: r.x0 + j * r.dx, y: r.y0 + i * r.dx, v: r.values[i * r.nx + j] };
}

function inReceiver(st, x, y) {
  const b = st.d.receiver;
  return b && x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3];
}

// ------------------------------------------------------------------ pointer and keyboard
function bindPointer(st) {
  const c = st.canvas;
  c.addEventListener("pointerdown", (e) => {
    c.setPointerCapture(e.pointerId);
    st.root.focus({ preventScroll: true });
    const hit = st.mode === "move" ? hitStation(st, e.offsetX, e.offsetY) : null;
    st.drag = { sx: e.offsetX, sy: e.offsetY, tx0: st.tx, ty0: st.ty, moved: false, station: hit };
  });
  c.addEventListener("pointermove", (e) => {
    const world = toWorld(st, e.offsetX, e.offsetY);
    st.hover = { px: e.offsetX, py: e.offsetY, world };
    if (st.drag) {
      const dx = e.offsetX - st.drag.sx, dy = e.offsetY - st.drag.sy;
      if (Math.hypot(dx, dy) > 3) st.drag.moved = true;
      if (st.drag.moved && st.drag.station) st.ghost = { id: st.drag.station.id, x: world[0], y: world[1] };
      else if (st.drag.moved) { st.tx = st.drag.tx0 + dx; st.ty = st.drag.ty0 + dy; }
    }
    readout(st, world, e.offsetX, e.offsetY);
    draw(st);
  });
  c.addEventListener("pointerup", (e) => {
    const drag = st.drag;
    st.drag = null;
    if (!drag) return;
    const [x, y] = toWorld(st, e.offsetX, e.offsetY);
    if (drag.moved && drag.station) { st.emit({ type: "move", id: drag.station.id, x, y }); return; }
    if (!drag.moved) click(st, e.offsetX, e.offsetY, x, y);
  });
  c.addEventListener("pointerleave", () => { st.hover = null; st.status.textContent = ""; draw(st); });
  c.addEventListener("wheel", (e) => {
    e.preventDefault();
    zoomAt(st, e.offsetX, e.offsetY, Math.exp(-e.deltaY * 0.0015));
    draw(st);
  }, { passive: false });
  c.addEventListener("dblclick", (e) => { zoomAt(st, e.offsetX, e.offsetY, 1.8); draw(st); });
  st.root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { st.measure = []; setMode(st, "select"); }
    const sel = (st.d && st.d.selected) || {};
    if ((e.key === "Delete" || e.key === "Backspace") && sel.kind === "station") st.emit({ type: "delete", id: sel.id });
  });
}

function click(st, px, py, x, y) {
  const sel = st.d.selected || {};
  if (st.mode === "measure") {
    st.measure = st.measure.length >= 2 ? [[x, y]] : [...st.measure, [x, y]];
    draw(st);
    return;
  }
  if (st.mode === "place") { st.emit({ type: "place", x, y }); return; }
  const s = hitStation(st, px, py);
  if (s) { st.emit({ type: "select_station", id: s.id }); return; }
  if (st.mode === "move") {
    if (sel.kind === "station") st.emit({ type: "move", id: sel.id, x, y });
    return;
  }
  const b = hitBuilding(st, x, y);
  if (b) { st.emit({ type: "select_building", id: b.id, x, y }); return; }
  if (inReceiver(st, x, y)) { st.emit({ type: "inspect", x, y }); return; }
  st.emit({ type: "clear" });
}

function readout(st, [x, y], px, py) {
  const t = st.d.texts || {}, parts = [`x ${x.toFixed(0)} m · y ${y.toFixed(0)} m`];
  const cell = cellAt(st, x, y);
  if (cell && st.raster) {
    const r = st.raster.spec;
    let value;
    if (cell.v === null || cell.v === undefined) value = t.indoor || "indoor";
    else if (cell.v === NO_PATH) value = t.no_path || "no path";
    else if (r.kind === "cat") value = (r.ticktext || [])[cell.v] ?? "—";
    else value = `${cell.v.toFixed(r.decimals ?? 1)}${r.unit ? " " + r.unit : ""}`;
    parts.push(`${r.title}: ${value}${r.stale ? ` (${t.stale_short || "stale"})` : ""}`);
  }
  const s = hitStation(st, px, py);
  if (s) parts.push(s.hover);
  else {
    const b = hitBuilding(st, x, y);
    if (b) parts.push(`${b.id} · ${b.h.toFixed(1)} m · ${(st.d.category_labels || {})[b.cat] || b.cat}`);
  }
  st.status.replaceChildren(...parts.map((p, k) => {
    const span = document.createElement("bdi");
    span.textContent = (k ? " · " : "") + p;
    return span;
  }));
}

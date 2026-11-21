/* Inside PDX: the terminal as a raised model, drawn from building outlines in meters (x east, y south).
   Concourses and the main terminal can be picked from the model or the buttons above it. */
(function () {
  "use strict";
  const host = document.getElementById("terminal-model");
  const source = document.getElementById("terminal-data");
  if (!host || !source) return;
  const DATA = JSON.parse(source.textContent);
  const NS = "http://www.w3.org/2000/svg";

  /* view: turned so the curb side faces you, squashed for the tilt, heights in meters lifted a little */
  const VIEW = 32 * Math.PI / 180, SQUASH = 0.55, LIFT = 1.15;
  const HEIGHT = { "Main terminal": 22, P1: 21, P2: 21, P3: 14, "Control tower": 8 };
  const iso = ([x, y], z = 0) => {
    const rx = x * Math.cos(VIEW) - y * Math.sin(VIEW), ry = x * Math.sin(VIEW) + y * Math.cos(VIEW);
    return [rx, ry * SQUASH - z * LIFT];
  };
  const depth = ([x, y]) => x * Math.sin(VIEW) + y * Math.cos(VIEW);

  function el(name, attrs, parent) {
    const e = document.createElementNS(NS, name);
    for (const k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  const pts2 = pts => pts.map(p => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
  const centroid = pts => { let x = 0, y = 0; pts.forEach(p => { x += p[0]; y += p[1]; }); return [x / pts.length, y / pts.length]; };
  function inside(pt, pts) {
    let c = false;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      const [xi, yi] = pts[i], [xj, yj] = pts[j];
      if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi) c = !c;
    }
    return c;
  }
  function label(parent, x, y, str, attrs) {
    const t = el("text", Object.assign({ x, y }, attrs), parent);
    t.textContent = str;
    return t;
  }

  const shapes = DATA.shapes;
  const hall = shapes.find(s => s.name === "Main terminal");
  const hallC = centroid(hall.pts);
  const concourses = shapes.filter(s => s.kind === "terminal" && s.name.startsWith("Concourse")).map(s => {
    /* main axis of the concourse, pointing away from the main terminal */
    const m = centroid(s.pts);
    let sxx = 0, syy = 0, sxy = 0;
    s.pts.forEach(([x, y]) => { sxx += (x - m[0]) ** 2; syy += (y - m[1]) ** 2; sxy += (x - m[0]) * (y - m[1]); });
    const a = 0.5 * Math.atan2(2 * sxy, sxx - syy);
    let d = [Math.cos(a), Math.sin(a)];
    if ((m[0] - hallC[0]) * d[0] + (m[1] - hallC[1]) * d[1] < 0) d = [-d[0], -d[1]];
    return Object.assign({}, s, { letter: s.name.slice(-1), mid: m, dir: d });
  });
  const byLetter = Object.fromEntries(concourses.map(c => [c.letter, c]));

  /* parked aircraft: illustrative, nose in at about four gates in five */
  const HALF = [[18, 0], [15, 1.8], [4, 2.1], [0.5, 16.5], [-3, 16.5], [-4.5, 2.1], [-13, 1.9], [-16, 6.5], [-18.2, 6.5], [-17.2, 1.2], [-18.4, 0]];
  const PLANE = HALF.concat(HALF.slice(1, -1).reverse().map(([x, y]) => [x, -y]));
  const planes = [];
  DATA.gates.forEach((g, i) => {
    const c = byLetter[g.ref[0]];
    if (!c || i % 5 === 2) return;
    const t = (g.p[0] - c.mid[0]) * c.dir[0] + (g.p[1] - c.mid[1]) * c.dir[1];
    let n = [g.p[0] - (c.mid[0] + c.dir[0] * t), g.p[1] - (c.mid[1] + c.dir[1] * t)];
    const len = Math.hypot(n[0], n[1]);
    if (len < 1) return;
    n = [n[0] / len, n[1] / len];
    const k = c.letter === "B" ? 0.8 : 1, size = 36 * k;
    const ctr = [g.p[0] + n[0] * (size / 2 + 9), g.p[1] + n[1] * (size / 2 + 9)];
    if (planes.some(p => Math.hypot(p.c[0] - ctr[0], p.c[1] - ctr[1]) < 27)) return;
    if (shapes.some(s => s.kind === "terminal" && inside(ctr, s.pts))) return;
    const a = Math.atan2(-n[1], -n[0]), ca = Math.cos(a), sa = Math.sin(a);
    planes.push({ c: ctr, area: c.letter, pts: PLANE.map(([x, y]) => [ctr[0] + (x * ca - y * sa) * k, ctr[1] + (x * sa + y * ca) * k]) });
  });

  /* solids, drawn far to near */
  const solids = shapes.filter(s => s.kind !== "canopy").map(s => ({
    s, h: HEIGHT[s.name] || (s.kind === "terminal" ? 12 : 18),
    area: s.name === "Main terminal" ? "main" : s.name.startsWith("Concourse") ? s.name.slice(-1) : "",
  }));
  solids.sort((a, b) => Math.max(...a.s.pts.map(depth)) - Math.max(...b.s.pts.map(depth)));

  /* fit the view to the buildings and the tower */
  let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
  const grow = ([X, Y]) => { minX = Math.min(minX, X); maxX = Math.max(maxX, X); minY = Math.min(minY, Y); maxY = Math.max(maxY, Y); };
  /* frame the terminal; garages may run off the edge */
  solids.filter(o => o.s.kind === "terminal").forEach(o => o.s.pts.forEach(p => { grow(iso(p)); grow(iso(p, o.h)); }));
  planes.forEach(p => p.pts.forEach(q => grow(iso(q))));
  const tower = shapes.find(s => s.kind === "tower"), towerC = tower ? centroid(tower.pts) : null;
  if (towerC) grow(iso(towerC, 82));
  const pad = 24;
  const vb = [minX - pad, minY - pad, maxX - minX + pad * 2, maxY - minY + pad * 2].map(v => Math.round(v));
  const root = el("svg", { viewBox: vb.join(" "), role: "img", "aria-label": "Raised model of the PDX terminal: the main terminal in the middle, Concourses C and D to the north, E to the east, B to the south." });

  const defs = el("defs", {}, root);
  const lattice = el("pattern", { id: "roof-lattice", width: 14, height: 14, patternUnits: "userSpaceOnUse", patternTransform: "rotate(-28)" }, defs);
  el("rect", { width: 14, height: 14, class: "tm-roof" }, lattice);
  el("path", { d: "M0 0 L14 0 M0 7 L14 7 M0 0 L0 14 M7 0 L7 14", class: "tm-roof-line" }, lattice);

  el("rect", { x: vb[0], y: vb[1], width: vb[2], height: vb[3], class: "tm-ground" }, root);
  const planeLayer = el("g", {}, root);
  planes.forEach(p => el("polygon", { points: pts2(p.pts.map(q => iso(q))), class: "tm-plane", "data-area": p.area }, planeLayer));

  const groups = {};
  solids.forEach(o => {
    const g = el("g", { class: o.area ? "tm-area" : "", "data-area": o.area }, root);
    if (o.area) groups[o.area] = g;
    const pts = o.s.pts;
    const area = pts.reduce((acc, p, i) => { const q = pts[(i + 1) % pts.length]; return acc + p[0] * q[1] - q[0] * p[1]; }, 0);
    const glassy = o.s.kind === "terminal";
    const walls = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const a = pts[i], b = pts[i + 1], ex = b[0] - a[0], ey = b[1] - a[1];
      const nx = area > 0 ? ey : -ey, ny = area > 0 ? -ex : ex;
      if (nx * Math.sin(VIEW) + ny * Math.cos(VIEW) <= 0) continue;
      walls.push({ a, b, d: (depth(a) + depth(b)) / 2, lit: (nx * Math.cos(VIEW) - ny * Math.sin(VIEW)) < 0 });
    }
    walls.sort((p, q) => p.d - q.d).forEach(w => {
      el("polygon", { points: pts2([iso(w.a), iso(w.b), iso(w.b, o.h), iso(w.a, o.h)]), class: glassy ? (w.lit ? "tm-wall-lit" : "tm-wall") : "tm-block-wall" }, g);
      if (glassy) { const m1 = iso(w.a, o.h * 0.45), m2 = iso(w.b, o.h * 0.45); el("line", { x1: m1[0], y1: m1[1], x2: m2[0], y2: m2[1], class: "tm-mullion" }, g); }
    });
    const roofClass = o.area === "main" ? "tm-hall-roof" : glassy ? "tm-con-roof" : "tm-block-roof";
    el("polygon", { points: pts2(pts.map(p => iso(p, o.h))), class: roofClass, fill: o.area === "main" ? "url(#roof-lattice)" : null }, g);
    if (o.area === "main") {
      /* skylights down the middle of the roof */
      for (let i = -4; i <= 4; i++) {
        const p = [hallC[0] + i * 13, hallC[1] - i * 22.4];
        if (!inside(p, pts)) continue;
        const sq = [[-6, -3], [6, -3], [6, 3], [-6, 3]].map(([dx, dy]) => iso([p[0] + dx * 0.86 + dy * 0.5, p[1] + dx * 0.5 - dy * 0.86], o.h + 0.5));
        el("polygon", { points: pts2(sq), class: "tm-skylight" }, g);
      }
    }
  });

  /* control tower */
  if (towerC) {
    const base = iso(towerC, 8), top = iso(towerC, 70), cab = iso(towerC, 76);
    el("rect", { x: base[0] - 4, y: top[1], width: 8, height: base[1] - top[1], class: "tm-wall" }, root);
    el("ellipse", { cx: cab[0], cy: cab[1] + 4, rx: 11, ry: 7, class: "tm-wall-lit" }, root);
    el("ellipse", { cx: cab[0], cy: cab[1] - 1, rx: 12, ry: 5, class: "tm-cab" }, root);
    label(root, cab[0] + 18, cab[1] + 4, "Control tower", { class: "tm-note" });
  }

  /* labels last, so nothing covers them */
  const labels = el("g", {}, root);
  concourses.forEach(c => {
    const o = solids.find(x => x.area === c.letter);
    const at = iso([c.mid[0] + c.dir[0] * 30, c.mid[1] + c.dir[1] * 30], o.h + 14);
    const g = el("g", { class: "tm-badge", "data-area": c.letter }, labels);
    el("circle", { cx: at[0], cy: at[1], r: 17 }, g);
    label(g, at[0], at[1] + 7, c.letter, {});
  });
  const hallLabel = iso(hallC, 30);
  label(labels, hallLabel[0], hallLabel[1] - 4, "Main terminal", { class: "tm-hall-label" });
  (DATA.pins || []).forEach(p => {
    const m = iso(p.p, 2);
    el("circle", { cx: m[0], cy: m[1], r: 6, class: "tm-pin" }, labels);
    label(labels, m[0] + 10, m[1] + 5, p.name.replace(" station", ""), { class: "tm-pin-label" });
  });

  host.appendChild(root);

  /* picking an area */
  const caption = document.getElementById("model-caption");
  const chips = document.querySelectorAll(".model-chips .area-chip");
  const articles = document.querySelectorAll(".area[data-area]");
  const restingCaption = caption ? caption.textContent : "";
  function pick(key) {
    chips.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.area === key)));
    if (key) root.setAttribute("data-pick", key); else root.removeAttribute("data-pick");
    root.querySelectorAll("[data-area]").forEach(n => n.classList.toggle("off", !!key && n.dataset.area !== key));
    articles.forEach(a => a.classList.toggle("current", a.dataset.area === key));
    if (!caption) return;
    if (!key) { caption.textContent = restingCaption; return; }
    const a = DATA.areas[key];
    caption.textContent = "";
    const strong = document.createElement("strong");
    strong.textContent = a.title;
    caption.append(strong);
    const bits = [a.gateSpan ? "Gates " + a.gateSpan : "Check in, security and bags"];
    if (a.airlines.length) bits.push(a.airlines.join(", "));
    caption.append(" · " + bits.join(" · ") + " · ");
    const link = document.createElement("a");
    link.href = "#" + a.anchor;
    link.textContent = "What's there";
    caption.append(link);
  }
  chips.forEach(b => b.addEventListener("click", () => pick(b.dataset.area)));
  Object.entries(groups).forEach(([key, g]) => {
    g.setAttribute("tabindex", "0");
    g.setAttribute("role", "button");
    g.setAttribute("aria-label", DATA.areas[key] ? DATA.areas[key].title : key);
    g.addEventListener("click", () => pick(key));
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(key); } });
  });
  root.querySelectorAll(".tm-badge").forEach(b => b.addEventListener("click", () => pick(b.dataset.area)));
})();

/* Inside PDX: the terminal as a raised model, drawn from building outlines in meters (x east, y south).
   NSPTerminal.draw(host, data, options) draws one model; the page wiring at the bottom adds picking a
   concourse and moving its card to the top. Roof styles: cassettes (the site's), grid, woven, waves, plain. */
(function () {
  "use strict";
  const NS = "http://www.w3.org/2000/svg";
  const VIEW = 32 * Math.PI / 180, SQUASH = 0.55, LIFT = 1.15;
  const HEIGHT = { "Main terminal": 22, P1: 21, P2: 21, P3: 14, "Control tower": 8 };
  let uid = 0;

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
  /* long axis of a footprint */
  function axis(pts) {
    const m = centroid(pts);
    let sxx = 0, syy = 0, sxy = 0;
    pts.forEach(([x, y]) => { sxx += (x - m[0]) ** 2; syy += (y - m[1]) ** 2; sxy += (x - m[0]) * (y - m[1]); });
    const a = 0.5 * Math.atan2(2 * sxy, sxx - syy);
    return { mid: m, angle: a, dir: [Math.cos(a), Math.sin(a)] };
  }
  /* a point and heading a given distance along a polyline */
  function along(line, dist) {
    let left = dist;
    for (let i = 0; i < line.length - 1; i++) {
      const a = line[i], b = line[i + 1], seg = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (seg && left <= seg) { const t = left / seg; return { p: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], d: [(b[0] - a[0]) / seg, (b[1] - a[1]) / seg] }; }
      left -= seg;
    }
    const a = line[line.length - 2], b = line[line.length - 1], seg = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    return { p: b, d: [(b[0] - a[0]) / seg, (b[1] - a[1]) / seg] };
  }

  /* walls facing the viewer, then the top: the basic block of the model */
  function prism(g, pts, h, cls, z0 = 0) {
    const area = pts.reduce((acc, p, i) => { const q = pts[(i + 1) % pts.length]; return acc + p[0] * q[1] - q[0] * p[1]; }, 0);
    const closed = pts[0][0] === pts[pts.length - 1][0] && pts[0][1] === pts[pts.length - 1][1];
    const ring = closed ? pts : pts.concat([pts[0]]);
    const walls = [];
    for (let i = 0; i < ring.length - 1; i++) {
      const a = ring[i], b = ring[i + 1], ex = b[0] - a[0], ey = b[1] - a[1];
      const nx = area > 0 ? ey : -ey, ny = area > 0 ? -ex : ex;
      if (nx * Math.sin(VIEW) + ny * Math.cos(VIEW) <= 0) continue;
      walls.push({ a, b, d: (depth(a) + depth(b)) / 2, lit: (nx * Math.cos(VIEW) - ny * Math.sin(VIEW)) < 0 });
    }
    const band = (w, k, c, g2) => { const m1 = iso(w.a, z0 + h * k), m2 = iso(w.b, z0 + h * k); el("line", { x1: m1[0], y1: m1[1], x2: m2[0], y2: m2[1], class: c }, g2); };
    walls.sort((p, q) => p.d - q.d).forEach(w => {
      el("polygon", { points: pts2([iso(w.a, z0), iso(w.b, z0), iso(w.b, z0 + h), iso(w.a, z0 + h)]), class: w.lit ? cls.lit : cls.wall }, g);
      if (cls.mullion) band(w, 0.45, cls.mullion, g);
      if (cls.windows) band(w, 0.68, cls.windows, g);
      if (cls.stripe) band(w, 0.3, cls.stripe, g);
    });
    return el("polygon", { points: pts2(pts.map(p => iso(p, z0 + h))), class: cls.top }, g);
  }

  /* ---------- roof styles for the main terminal ---------- */
  function roofLines(g, pts, h, ax, angle, spacing, cls) {
    /* parallel lines in ground meters at an angle to the building's axis, clipped to the roof */
    const a = ax.angle + angle, d = [Math.cos(a), Math.sin(a)], n = [-d[1], d[0]];
    const reach = Math.max(...pts.map(p => Math.hypot(p[0] - ax.mid[0], p[1] - ax.mid[1]))) + spacing;
    for (let s = -reach; s <= reach; s += spacing) {
      const c = [ax.mid[0] + n[0] * s, ax.mid[1] + n[1] * s];
      const p1 = iso([c[0] - d[0] * reach, c[1] - d[1] * reach], h), p2 = iso([c[0] + d[0] * reach, c[1] + d[1] * reach], h);
      el("line", { x1: p1[0], y1: p1[1], x2: p2[0], y2: p2[1], class: cls }, g);
    }
  }
  function skylights(g, pts, h, ax, rows, step = 24) {
    const d = ax.dir, n = [-d[1], d[0]];
    const len = Math.max(...pts.map(p => Math.abs((p[0] - ax.mid[0]) * d[0] + (p[1] - ax.mid[1]) * d[1])));
    rows.forEach((off, r) => {
      for (let t = -len + (r % 2) * step / 2; t <= len; t += step) {
        const c = [ax.mid[0] + d[0] * t + n[0] * off, ax.mid[1] + d[1] * t + n[1] * off];
        const corners = [[-5, -2.5], [5, -2.5], [5, 2.5], [-5, 2.5]].map(([u, v]) => [c[0] + d[0] * u + n[0] * v, c[1] + d[1] * u + n[1] * v]);
        if (!corners.every(q => inside(q, pts))) continue;
        el("polygon", { points: pts2(corners.map(q => iso(q, h + 0.4))), class: "tm-skylight" }, g);
      }
    });
  }
  const ROOFS = {
    grid(g, pts, h, ax) { roofLines(g, pts, h, ax, 0, 8, "tm-roof-line"); roofLines(g, pts, h, ax, Math.PI / 2, 8, "tm-roof-line"); skylights(g, pts, h, ax, [0]); },
    woven(g, pts, h, ax) { roofLines(g, pts, h, ax, 0.7, 9, "tm-roof-line"); roofLines(g, pts, h, ax, -0.7, 9, "tm-roof-line"); skylights(g, pts, h, ax, [-22, 22], 30); },
    cassettes(g, pts, h, ax) {
      roofLines(g, pts, h, ax, 0, 4.5, "tm-roof-grain");
      roofLines(g, pts, h, ax, Math.PI / 2, 38, "tm-roof-seam");
    },
    waves(g, pts, h, ax) { roofLines(g, pts, h, ax, Math.PI / 2, 16, "tm-roof-wave"); roofLines(g, pts, h, ax, Math.PI / 2, 16, "tm-roof-crest"); skylights(g, pts, h, ax, [0], 32); },
    plain(g, pts, h, ax) { skylights(g, pts, h, ax, [-36, -12, 12, 36], 26); },
  };

  /* ---------- the model ---------- */
  function draw(host, DATA, opts) {
    opts = opts || {};
    const id = "tm" + (++uid);
    const shapes = DATA.shapes;
    const hall = shapes.find(s => s.name === "Main terminal");
    const hallAxis = axis(hall.pts), hallC = hallAxis.mid;
    const concourses = shapes.filter(s => s.kind === "terminal" && s.name.startsWith("Concourse")).map(s => {
      const ax = axis(s.pts);
      let d = ax.dir;
      if ((ax.mid[0] - hallC[0]) * d[0] + (ax.mid[1] - hallC[1]) * d[1] < 0) d = [-d[0], -d[1]];
      return Object.assign({}, s, { letter: s.name.slice(-1), mid: ax.mid, dir: d });
    });
    const byLetter = Object.fromEntries(concourses.map(c => [c.letter, c]));

    /* parked aircraft: illustrative, nose in at about four gates in five */
    const HALF = [[18, 0], [15, 1.8], [4, 2.1], [0.5, 16.5], [-3, 16.5], [-4.5, 2.1], [-13, 1.9], [-16, 6.5], [-18.2, 6.5], [-17.2, 1.2], [-18.4, 0]];
    const PLANE = HALF.concat(HALF.slice(1, -1).reverse().map(([x, y]) => [x, -y]));
    const planes = [];
    DATA.gates.forEach((gate, i) => {
      const c = byLetter[gate.ref[0]];
      if (!c || i % 5 === 2 || (DATA.noAircraft || []).includes(gate.ref)) return;
      const t = (gate.p[0] - c.mid[0]) * c.dir[0] + (gate.p[1] - c.mid[1]) * c.dir[1];
      let n = [gate.p[0] - (c.mid[0] + c.dir[0] * t), gate.p[1] - (c.mid[1] + c.dir[1] * t)];
      const len = Math.hypot(n[0], n[1]);
      if (len < 1) return;
      n = [n[0] / len, n[1] / len];
      const k = c.letter === "B" ? 0.8 : 1, size = 36 * k;
      const ctr = [gate.p[0] + n[0] * (size / 2 + 9), gate.p[1] + n[1] * (size / 2 + 9)];
      if (planes.some(p => Math.hypot(p.c[0] - ctr[0], p.c[1] - ctr[1]) < 27)) return;
      if (shapes.some(s => s.kind === "terminal" && inside(ctr, s.pts))) return;
      const a = Math.atan2(-n[1], -n[0]), ca = Math.cos(a), sa = Math.sin(a);
      planes.push({ c: ctr, area: c.letter, pts: PLANE.map(([x, y]) => [ctr[0] + (x * ca - y * sa) * k, ctr[1] + (x * sa + y * ca) * k]) });
    });

    /* solids: buildings, plus a two car MAX train waiting at the station */
    const solids = shapes.filter(s => s.kind !== "canopy").map(s => ({
      kind: s.kind, name: s.name, pts: s.pts, h: HEIGHT[s.name] || (s.kind === "terminal" ? 12 : 18),
      area: s.name === "Main terminal" ? "main" : s.name.startsWith("Concourse") ? s.name.slice(-1) : "",
    }));
    const rail = DATA.rail || [];
    if (rail.length) {
      /* drawn a little larger than life (real cars are about 2.7 m wide) so it reads at this scale */
      [[3, 32], [33.5, 62]].forEach(([s0, s1]) => {
        const a = along(rail[0], s0), b = along(rail[0], s1), n = [-a.d[1], a.d[0]], w = 2.2;
        solids.push({ kind: "train", h: 5.5, z0: 0.4, area: "",
          pts: [[a.p[0] + n[0] * w, a.p[1] + n[1] * w], [b.p[0] + n[0] * w, b.p[1] + n[1] * w], [b.p[0] - n[0] * w, b.p[1] - n[1] * w], [a.p[0] - n[0] * w, a.p[1] - n[1] * w]] });
      });
    }
    solids.sort((a, b) => Math.max(...a.pts.map(depth)) - Math.max(...b.pts.map(depth)));

    /* frame the terminal; garages and tracks may run off the edge */
    let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
    const grow = ([X, Y]) => { minX = Math.min(minX, X); maxX = Math.max(maxX, X); minY = Math.min(minY, Y); maxY = Math.max(maxY, Y); };
    const framed = opts.crop === "hall" ? solids.filter(o => o.area === "main") : solids.filter(o => o.kind === "terminal");
    framed.forEach(o => o.pts.forEach(p => { grow(iso(p)); grow(iso(p, o.h)); }));
    if (opts.crop !== "hall") planes.forEach(p => p.pts.forEach(q => grow(iso(q))));
    const tower = shapes.find(s => s.kind === "tower"), towerC = tower ? centroid(tower.pts) : null;
    if (towerC && opts.crop !== "hall") grow(iso(towerC, 82));
    const pad = opts.crop === "hall" ? 10 : 24;
    const vb = [minX - pad, minY - pad, maxX - minX + pad * 2, maxY - minY + pad * 2].map(v => Math.round(v));
    const root = el("svg", { viewBox: vb.join(" "), role: "img", "aria-label": opts.label || "Raised model of the PDX terminal: the main terminal in the middle, Concourses C and D to the north, E to the east, B to the south, and the MAX station by B." });
    const defs = el("defs", {}, root);
    el("rect", { x: vb[0], y: vb[1], width: vb[2], height: vb[3], class: "tm-ground" }, root);

    /* MAX tracks: two thin rails per track on a pale bed, fading as they leave */
    const tracks = el("g", { class: "tm-tracks" }, root);
    rail.forEach(line => {
      let dist = 0;
      for (let i = 0; i < line.length - 1; i++) {
        const a = line[i], b = line[i + 1], len = Math.hypot(b[0] - a[0], b[1] - a[1]);
        const fade = Math.max(0, 1 - Math.max(0, dist - 150) / 650);
        dist += len;
        if (!fade) break;
        if (len < 0.1) continue;
        const n = [-(b[1] - a[1]) / len, (b[0] - a[0]) / len];
        const g = el("g", { opacity: fade.toFixed(2) }, tracks);
        el("line", { x1: iso(a)[0], y1: iso(a)[1], x2: iso(b)[0], y2: iso(b)[1], class: "tm-rail-bed" }, g);
        [-0.75, 0.75].forEach(o => {
          const p = iso([a[0] + n[0] * o, a[1] + n[1] * o]), q = iso([b[0] + n[0] * o, b[1] + n[1] * o]);
          el("line", { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: "tm-rail" }, g);
        });
      }
    });

    planes.forEach(p => el("polygon", { points: pts2(p.pts.map(q => iso(q))), class: "tm-plane", "data-area": p.area }, root));

    const groups = {};
    solids.forEach(o => {
      const g = el("g", { class: o.area ? "tm-area" : o.kind === "train" ? "tm-max" : "", "data-area": o.area || null }, root);
      if (o.area) groups[o.area] = g;
      if (o.kind === "train") {
        prism(g, o.pts, o.h, { wall: "tm-train", lit: "tm-train-lit", top: "tm-train-roof", stripe: "tm-train-stripe", windows: "tm-train-windows" }, o.z0);
        return;
      }
      const glassy = o.kind === "terminal";
      const cls = glassy ? { wall: "tm-wall", lit: "tm-wall-lit", top: o.area === "main" ? "tm-hall-roof" : "tm-con-roof", mullion: "tm-mullion" }
        : { wall: "tm-block-wall", lit: "tm-block-wall", top: "tm-block-roof" };
      prism(g, o.pts, o.h, cls);
      if (o.area === "main") {
        const clip = el("clipPath", { id: id + "-roof" }, defs);
        el("polygon", { points: pts2(o.pts.map(p => iso(p, o.h))) }, clip);
        const roof = el("g", { "clip-path": `url(#${id}-roof)` }, g);
        (ROOFS[opts.roof] || ROOFS.cassettes)(roof, o.pts, o.h, hallAxis);
      }
    });

    if (towerC && opts.crop !== "hall") {
      const base = iso(towerC, 8), top = iso(towerC, 70), cab = iso(towerC, 76);
      el("rect", { x: base[0] - 4, y: top[1], width: 8, height: base[1] - top[1], class: "tm-wall" }, root);
      el("ellipse", { cx: cab[0], cy: cab[1] + 4, rx: 11, ry: 7, class: "tm-wall-lit" }, root);
      el("ellipse", { cx: cab[0], cy: cab[1] - 1, rx: 12, ry: 5, class: "tm-cab" }, root);
      if (!opts.quiet) label(root, cab[0] - 18, cab[1] + 4, "Control tower", { class: "tm-note", "text-anchor": "end" });
    }

    if (!opts.quiet) {
      const labels = el("g", {}, root);
      concourses.forEach(c => {
        const o = solids.find(x => x.area === c.letter);
        const at = iso([c.mid[0] + c.dir[0] * 30, c.mid[1] + c.dir[1] * 30], o.h + 14);
        const g = el("g", { class: "tm-badge", "data-area": c.letter }, labels);
        el("circle", { cx: at[0], cy: at[1], r: 17 }, g);
        label(g, at[0], at[1] + 7, c.letter, {});
      });
      const hl = iso(hallC, 30);
      label(labels, hl[0], hl[1] - 4, "Main terminal", { class: "tm-hall-label" });
      (DATA.pins || []).forEach(p => {
        const m = iso(p.p, 6);
        label(labels, m[0] + 14, m[1] + 4, p.name.replace(" station", ""), { class: "tm-pin-label" });
      });
    }

    host.appendChild(root);
    return { root, groups };
  }

  window.NSPTerminal = { draw, roofs: Object.keys(ROOFS) };

  /* ---------- the Inside PDX page ---------- */
  const host = document.getElementById("terminal-model");
  const source = document.getElementById("terminal-data");
  if (!host || !source) return;
  const DATA = JSON.parse(source.textContent);
  const { root, groups } = draw(host, DATA, { roof: host.dataset.roof });

  const caption = document.getElementById("model-caption");
  const chips = document.querySelectorAll(".model-chips .area-chip");
  const list = document.querySelector(".areas");
  const original = list ? Array.from(list.children) : [];
  const restingCaption = caption ? caption.textContent : "";
  const still = window.matchMedia("(prefers-reduced-motion: reduce)");

  /* move the picked card to the top of the list, sliding the others into place */
  function reorder(key) {
    if (!list) return;
    const cards = Array.from(list.children);
    const before = new Map(cards.map(c => [c, c.getBoundingClientRect().top]));
    const picked = key && cards.find(c => c.dataset.area === key);
    if (picked) list.prepend(picked); else original.forEach(c => list.appendChild(c));
    if (still.matches) return;
    cards.forEach(c => {
      const dy = before.get(c) - c.getBoundingClientRect().top;
      if (Math.abs(dy) > 1 && c.animate) c.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 380, easing: "cubic-bezier(.2,.7,.2,1)" });
    });
  }

  function pick(key) {
    chips.forEach(b => b.setAttribute("aria-pressed", String(b.dataset.area === key)));
    if (key) root.setAttribute("data-pick", key); else root.removeAttribute("data-pick");
    root.querySelectorAll("[data-area]").forEach(n => n.classList.toggle("off", !!key && n.dataset.area !== key));
    if (list) Array.from(list.children).forEach(a => a.classList.toggle("current", !!key && a.dataset.area === key));
    reorder(key);
    if (!caption) return;
    if (!key) { caption.textContent = restingCaption; return; }
    const a = DATA.areas[key];
    caption.textContent = "";
    const strong = document.createElement("strong");
    strong.textContent = a.title;
    caption.append(strong);
    const bits = [a.gateSpan ? "Gates " + a.gateSpan : "Check in, security and bags"];
    if (a.airlines.length) bits.push(a.airlines.join(", "));
    caption.append(" · " + bits.join(" · "));
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

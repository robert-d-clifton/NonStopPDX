/* The overview map: every nonstop from PDX on a flat Natural Earth projection, after design study 4.
   Needs d3 (loaded first) and the #map-points JSON the page renders. */
(function () {
  const script = document.currentScript;
  const svgEl = document.getElementById("overview-map");
  const pointsEl = document.getElementById("map-points");
  if (!svgEl || !pointsEl || !window.d3) return;

  const POINTS = JSON.parse(pointsEl.textContent);
  const PDX = [-122.5975, 45.5887];
  const W = 1000, H = 640;
  const WEST_MILES = 1150;
  const LABELS = {
    world: ["LHR", "FRA", "AMS", "KEF", "HNL", "ANC", "FAI", "MEX", "GDL", "BOS", "MIA", "JFK", "CUN", "LIH", "ATL", "YYC"],
    west: ["SEA", "PDT", "BOI", "SFO", "LAX", "LAS", "PHX", "SLC", "DEN", "YVR", "RNO", "SAN", "BZN", "MFR", "PSC", "SBA", "MSO"]
  };
  // Fewer labels when the map is small, like on a phone.
  const LABELS_SMALL = {
    world: ["LHR", "KEF", "HNL", "ANC", "MEX", "BOS", "MIA", "ATL"],
    west: ["SEA", "PDT", "BOI", "SFO", "LAX", "LAS", "PHX", "SLC", "DEN"]
  };
  const BIG_RIVERS = ["Columbia", "Snake", "Willamette", "Colorado", "Rio Grande", "Missouri", "Mississippi", "Sacramento", "Fraser", "Yukon"];
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const byCode = Object.fromEntries(POINTS.map(p => [p.code, p]));

  let world = null, detail = null, detailLoading = null;
  let zoom = "world", selected = null;
  const svg = d3.select(svgEl);

  /* flip tiles for the selected airport code */
  const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  function flapRow(row, text) {
    if (row.children.length !== text.length) {
      row.innerHTML = "";
      for (const ch of text) { const s = document.createElement("span"); s.className = "flap"; s.textContent = ch; row.appendChild(s); }
      if (reduceMotion) return;
    }
    [...row.children].forEach((s, i) => {
      if (reduceMotion) { s.textContent = text[i]; return; }
      let steps = 4 + i * 3;
      const t = setInterval(() => {
        if (--steps <= 0) { clearInterval(t); s.textContent = text[i]; return; }
        s.textContent = CHARS[Math.floor(Math.random() * CHARS.length)];
      }, 50);
    });
  }

  function tree(g, x, y, s, cls) {
    const t = g.append("g").attr("transform", `translate(${x},${y}) scale(${s})`);
    t.append("rect").attr("class", "trunk").attr("x", -1.6).attr("y", 0).attr("width", 3.2).attr("height", 7);
    t.append("path").attr("class", cls).attr("d", "M0 -22 L9 0 L-9 0 Z");
    t.append("path").attr("class", cls).attr("d", "M0 -30 L7 -12 L-7 -12 Z");
  }

  function riverLabels(proj) {
    const best = {};
    detail.rivers.features.forEach(f => {
      const name = f.properties.n;
      if (!BIG_RIVERS.includes(name)) return;
      const parts = f.geometry.type === "LineString" ? [f.geometry.coordinates] : f.geometry.coordinates;
      parts.forEach(part => {
        const pts = part.map(c => proj(c)).filter(p => p && p[0] > 20 && p[0] < W - 20 && p[1] > 20 && p[1] < H - 20);
        if (pts.length < 4) return;
        let len = 0;
        for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
        if (len > 140 && (!best[name] || len > best[name].len)) best[name] = { len, pts };
      });
    });
    return Object.entries(best).map(([name, { pts }]) => {
      const cum = [0];
      for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
      const total = cum[cum.length - 1], half = Math.min(60, total / 2);
      const at = t => {
        t = Math.max(0, Math.min(total, t));
        const i = cum.findIndex(c => c >= t);
        if (i <= 0) return pts[Math.max(0, i)];
        const f = (t - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
        return [pts[i - 1][0] + f * (pts[i][0] - pts[i - 1][0]), pts[i - 1][1] + f * (pts[i][1] - pts[i - 1][1])];
      };
      // The middle of the visible stretch first, then spots further along, for when the middle is crowded.
      // Each spot can sit above the river (baseline 7 units up) or below it (17 units down).
      const candidates = [0.5, 0.45, 0.55, 0.4, 0.6, 0.35, 0.65, 0.3, 0.7, 0.25, 0.75, 0.2, 0.8, 0.15, 0.85].flatMap(frac => {
        const mid = total * frac, a = at(mid - half), b = at(mid + half);
        let ang = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
        if (ang > 90) ang -= 180;
        if (ang < -90) ang += 180;
        return [-7, 17].map(baseline => ({ m: at(mid), ang, baseline }));
      });
      return { name, candidates };
    });
  }

  function draw() {
    const west = zoom === "west" && detail;
    // The map scales with the page, so grow text and tap targets back up on narrow screens.
    const k = Math.max(1, Math.min(2.4, W / (svgEl.clientWidth || W)));
    const small = k > 1.6;
    svg.selectAll("*").remove();
    const defs = svg.append("defs");
    defs.append("clipPath").attr("id", "map-clip").append("rect").attr("width", W).attr("height", H).attr("rx", 14);
    const wobble = defs.append("filter").attr("id", "map-wobble").attr("x", "-2%").attr("y", "-2%").attr("width", "104%").attr("height", "104%");
    wobble.append("feTurbulence").attr("type", "fractalNoise").attr("baseFrequency", 0.018).attr("numOctaves", 2).attr("seed", 7).attr("result", "n");
    wobble.append("feDisplacementMap").attr("in", "SourceGraphic").attr("in2", "n").attr("scale", 4).attr("xChannelSelector", "R").attr("yChannelSelector", "G");

    const shown = west ? POINTS.filter(p => p.miles !== null && p.miles < WEST_MILES) : POINTS;
    const proj = d3.geoNaturalEarth1().rotate([west ? 114 : 75, 0]);
    proj.fitExtent([[70, 56], [W - 70, H - 56]], { type: "MultiPoint", coordinates: [PDX, ...shown.map(p => [p.lon, p.lat])] });
    // Trim shapes to the frame, or Safari drops filtered layers that are far bigger than the map.
    proj.clipExtent([[-8, -8], [W + 8, H + 8]]);
    const path = d3.geoPath(proj);
    const inView = ([x, y]) => x > 4 && x < W - 4 && y > 4 && y < H - 4;

    svg.append("rect").attr("class", "ocean").attr("width", W).attr("height", H).attr("rx", 14);
    const g = svg.append("g").attr("clip-path", "url(#map-clip)");
    g.append("path").attr("class", "grat").attr("d", path(d3.geoGraticule().step([15, 15])()));
    const geo = west ? detail : world;
    const landG = g.append("g").attr("filter", "url(#map-wobble)");
    landG.selectAll("path.land").data(geo.land.features).join("path").attr("class", "land").attr("d", path);
    landG.selectAll("path.lake").data(geo.lakes.features).join("path").attr("class", "lake").attr("d", path);
    if (west) {
      landG.append("g").selectAll("path").data(detail.states.features).join("path").attr("class", "stateline").attr("d", path);
      landG.append("g").selectAll("path").data(detail.rivers.features).join("path")
        .attr("class", f => "river" + (BIG_RIVERS.includes(f.properties.n) ? " big" : "")).attr("d", path);
    }

    const vis = POINTS.filter(p => inView(proj([p.lon, p.lat])));
    g.selectAll("path.spoke").data(vis).join("path")
      .attr("class", p => "spoke" + (p.yearRound ? "" : " seasonal") + (p.code === selected ? " on" : ""))
      .attr("d", p => path({ type: "LineString", coordinates: [PDX, [p.lon, p.lat]] }));

    const p0 = proj(PDX);
    const trees = g.append("g");
    [[-34, -14, 1.0, "t-a"], [-18, -34, 0.8, "t-b"], [26, -26, 0.9, "t-a"], [36, 6, 0.75, "t-b"], [-30, 26, 0.7, "t-a"]]
      .forEach(([x, y, s, c]) => tree(trees, p0[0] + x, p0[1] + y, s, c));

    const dots = g.append("g");
    const wanted = [];
    const labelSet = (small ? LABELS_SMALL : LABELS)[west ? "west" : "world"];
    vis.forEach(p => {
      const [x, y] = proj([p.lon, p.lat]);
      const node = dots.append("g").attr("tabindex", 0).attr("role", "button")
        .attr("aria-label", `${p.name}, ${p.miles !== null ? p.miles.toLocaleString("en-US") + " miles" : ""}`)
        .on("click", () => select(p.code))
        .on("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(p.code); } });
      node.append("circle").attr("class", "hit").attr("cx", x).attr("cy", y).attr("r", 11 * k);
      node.append("circle").attr("class", "dest" + (p.code === selected ? " on" : "")).attr("cx", x).attr("cy", y)
        .attr("r", (p.code === selected ? 6 : 3.6) * Math.min(k, 1.6));
      if (labelSet.includes(p.code) || p.code === selected) wanted.push({ x, y, sel: p.code === selected, text: p.name, right: x < W * 0.82 });
    });
    svg.append("circle").attr("class", "pdx-dot").attr("cx", p0[0]).attr("cy", p0[1]).attr("r", 8 * Math.min(k, 1.6));

    // Labels sit above the clipped layers and step aside when they would overlap.
    const labels = svg.append("g");
    const placed = [];
    const hits = (a, b) => a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
    const pdx = labels.append("text").attr("class", "label").attr("x", p0[0] + 12 * k).attr("y", p0[1] + 26 * k).attr("font-size", 22 * k).text("PDX");
    placed.push(pdx.node().getBBox());
    wanted.sort((a, b) => b.sel - a.sel).forEach(w => {
      const t = labels.append("text").attr("class", "label").attr("x", w.x + (w.right ? 8 : -8) * k)
        .attr("text-anchor", w.right ? "start" : "end").attr("font-size", (w.sel ? 19 : 14) * k).text(w.text);
      let box;
      for (const step of [0, -1, 1, -2, 2]) {
        t.attr("y", w.y + 5 * k + step * 15 * k);
        box = t.node().getBBox();
        if (!placed.some(p => hits(box, p))) break;
      }
      placed.push(box);
    });

    // River names go last, at the first spot along the river that covers no dot and no other label.
    if (west && !small) {
      const points = vis.map(p => proj([p.lon, p.lat])).concat([p0]);
      riverLabels(proj).forEach(r => {
        const t = labels.append("text").attr("class", "rlabel").attr("text-anchor", "middle");
        let half;
        const halfH = 8;
        const frame = c => {
          const a = c.ang * Math.PI / 180, cos = Math.cos(a), sin = Math.sin(a);
          const off = c.baseline - 4;  // the middle of the text sits about 4 units above its baseline
          return { cos, sin, cx: c.m[0] - off * sin, cy: c.m[1] + off * cos };
        };
        const clear = c => {
          const { cos, sin, cx, cy } = frame(c);
          const covers = ([x, y], pad) => {
            const dx = x - cx, dy = y - cy;
            return Math.abs(dx * cos + dy * sin) <= half + pad && Math.abs(-dx * sin + dy * cos) <= halfH + pad;
          };
          if (points.some(pt => covers(pt, 4))) return false;
          for (let u = -1; u <= 1; u += 0.25) {
            for (const v of [-halfH, 0, halfH]) {
              const x = cx + u * half * cos - v * sin, y = cy + u * half * sin + v * cos;
              if (placed.some(b => x >= b.x && x <= b.x + b.width && y >= b.y && y <= b.y + b.height)) return false;
            }
          }
          return true;
        };
        // Try the full name first, then just the river's name, which fits in tighter spots.
        let spot;
        for (const text of [r.name + " River", r.name]) {
          t.text(text);
          half = t.node().getComputedTextLength() / 2 + 6;
          spot = r.candidates.find(clear);
          if (spot) break;
        }
        if (!spot) { t.remove(); return; }
        t.attr("transform", `translate(${spot.m[0].toFixed(1)},${spot.m[1].toFixed(1)}) rotate(${spot.ang.toFixed(1)}) translate(0,${spot.baseline})`);
        const { cos, sin, cx, cy } = frame(spot);
        const xs = [-1, 1].flatMap(u => [-1, 1].map(v => cx + u * half * cos - v * halfH * sin));
        const ys = [-1, 1].flatMap(u => [-1, 1].map(v => cy + u * half * sin + v * halfH * cos));
        placed.push({ x: Math.min(...xs), y: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) });
      });
    }
  }

  const roCode = document.getElementById("readout-code");
  function select(code) {
    selected = code;
    const p = byCode[code];
    flapRow(roCode, code);
    document.getElementById("readout-name").textContent = p.name;
    const miles = p.miles !== null ? `${p.miles.toLocaleString("en-US")} miles · about ${p.flight}` : "";
    document.getElementById("readout-meta").textContent = [miles, p.airlines.join(", "), p.service].filter(Boolean).join(" · ");
    draw();
  }

  function loadDetail() {
    if (!detailLoading) detailLoading = fetch(script.dataset.detail).then(r => r.json()).then(d => { detail = d; });
    return detailLoading;
  }

  document.querySelectorAll("[data-zoom]").forEach(b => b.addEventListener("click", async () => {
    document.querySelectorAll("[data-zoom]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    zoom = b.dataset.zoom;
    if (zoom === "west") {
      if (selected && byCode[selected].miles >= WEST_MILES) selected = null;
      svgEl.setAttribute("aria-busy", "true");
      try { await loadDetail(); } finally { svgEl.removeAttribute("aria-busy"); }
    }
    draw();
  }));

  let lastWidth = svgEl.clientWidth;
  window.addEventListener("resize", () => {
    clearTimeout(window.__nspResize);
    window.__nspResize = setTimeout(() => { if (world && svgEl.clientWidth !== lastWidth) { lastWidth = svgEl.clientWidth; draw(); } }, 150);
  });

  fetch(script.dataset.world).then(r => r.json()).then(w => { world = w; draw(); })
    .catch(() => { svgEl.insertAdjacentHTML("afterend", '<p class="map-fallback">The map couldn\'t load. Every destination is in the departures list below.</p>'); });
})();

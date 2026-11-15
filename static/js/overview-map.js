/* The overview map: every nonstop from PDX on a flat Natural Earth projection, after design study 4.
   Needs d3 and map-common.js (loaded first) and the #map-points JSON the page renders.

   On the home page (data-zoomable="true") it zooms: scroll wheel, drag, double click and the zoom
   buttons on a computer, and a two finger pinch on a phone, so one finger still scrolls the page.
   Zooming only scales and shifts one projection, so the coastlines, borders and grid are drawn once
   and moved with a transform (line widths held steady). Routes and dots redraw every frame from the
   zoomed projection, and labels come back once a gesture pauses. */
(function () {
  const script = document.currentScript;
  const svgEl = document.getElementById("overview-map");
  const pointsEl = document.getElementById("map-points");
  if (!svgEl || !pointsEl || !window.d3 || !window.NSPMap) return;
  const M = window.NSPMap;

  const POINTS = JSON.parse(pointsEl.textContent);
  const W = 1000, H = 640;
  const WEST_MILES = 1150;
  const ZOOMABLE = svgEl.dataset.zoomable === "true";
  const MAX_ZOOM = 14;
  const DETAIL_ZOOM = 2.5;   // past this, the finer North American outlines, when looking at North America
  const WOBBLE_ZOOM = 1.2;   // the hand cut wobble only at the full view: it's costly, and Safari drops it on big layers
  const LABEL_PAUSE_MS = 140;
  const NORTH_AMERICA = { west: -170, south: 10, east: -50, north: 72 };
  const LABELS = {
    world: ["LHR", "FRA", "AMS", "KEF", "HNL", "ANC", "FAI", "MEX", "GDL", "BOS", "MIA", "JFK", "CUN", "LIH", "ATL", "YYC"],
    west: ["SEA", "PDT", "BOI", "SFO", "LAX", "LAS", "PHX", "SLC", "DEN", "YVR", "RNO", "SAN", "BZN", "MFR", "PSC", "SBA", "MSO"]
  };
  // Fewer labels when the map is small, like on a phone.
  const LABELS_SMALL = {
    world: ["LHR", "KEF", "HNL", "ANC", "MEX", "BOS", "MIA", "ATL"],
    west: ["SEA", "PDT", "BOI", "SFO", "LAX", "LAS", "PHX", "SLC", "DEN"]
  };
  const byCode = Object.fromEntries(POINTS.map(p => [p.code, p]));
  const WEST_POINTS = POINTS.filter(p => p.miles !== null && p.miles < WEST_MILES);
  // An airline with only a few routes gets every destination labeled.
  const LABEL_ALL = POINTS.length <= 24;
  const svg = d3.select(svgEl);
  let world = null, detail = null;
  let view = "world", selected = null;  // view: the fixed maps' choice, or the zoom shortcut last used

  function fitted(west) {
    const shown = west ? WEST_POINTS : POINTS;
    return d3.geoNaturalEarth1().rotate([west ? 114 : 75, 0])
      .fitExtent([[70, 56], [W - 70, H - 56]], { type: "MultiPoint", coordinates: [M.PDX, ...shown.map(p => [p.lon, p.lat])] });
  }
  function loadDetail() {
    return M.loadJSON(script.dataset.detail).then(d => { detail = d; return d; }).catch(() => null);
  }

  /* Routes, dots and labels, drawn from a projection into the given groups. Shared by both kinds of map. */
  function drawRoutes(g, labelsG, proj, { withLabels, labelKey, labelEvery }) {
    const k = M.scaleFor(svgEl, W);
    const small = k > 1.6;
    const path = d3.geoPath(proj);
    const inView = ([x, y]) => x > 4 && x < W - 4 && y > 4 && y < H - 4;
    const vis = POINTS.filter(p => inView(proj([p.lon, p.lat])));
    g.selectAll("path.spoke").data(vis).join("path")
      .attr("class", p => "spoke" + (p.yearRound ? "" : " seasonal") + (p.code === selected ? " on" : ""))
      .attr("d", p => path({ type: "LineString", coordinates: [M.PDX, [p.lon, p.lat]] }));
    const p0 = proj(M.PDX);
    M.treesAround(g.append("g"), p0);
    const dots = g.append("g");
    const labelSet = (small ? LABELS_SMALL : LABELS)[labelKey];
    const wanted = [];
    vis.forEach(p => {
      const [x, y] = proj([p.lon, p.lat]);
      const node = dots.append("g").attr("tabindex", 0).attr("role", "button")
        .attr("aria-label", `${p.name}, ${p.miles !== null ? p.miles.toLocaleString("en-US") + " miles" : ""}`)
        .on("click", () => select(p.code))
        .on("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(p.code); } });
      node.append("circle").attr("class", "hit").attr("cx", x).attr("cy", y).attr("r", 11 * k);
      node.append("circle").attr("class", "dest" + (p.code === selected ? " on" : "")).attr("cx", x).attr("cy", y)
        .attr("r", (p.code === selected ? 6 : 3.6) * Math.min(k, 1.6));
      if (labelEvery || labelSet.includes(p.code) || p.code === selected) wanted.push({ x, y, sel: p.code === selected, text: p.name, right: x < W * 0.82, code: p.code, miles: p.miles || 0 });
    });
    g.append("circle").attr("class", "pdx-dot").attr("cx", p0[0]).attr("cy", p0[1]).attr("r", 8 * Math.min(k, 1.6));
    if (!withLabels) return;

    const placed = [];
    // The zoom buttons sit on top of the map, so no label goes underneath them.
    const buttons = svgEl.parentElement.querySelector(".zoom-buttons");
    if (buttons) {
      const b = buttons.getBoundingClientRect(), s = svgEl.getBoundingClientRect(), f = W / (s.width || W);
      placed.push({ x: (b.left - s.left) * f - 6, y: (b.top - s.top) * f - 6, width: b.width * f + 12, height: b.height * f + 12 });
    }
    const dotsXY = vis.map(p => proj([p.lon, p.lat]));
    if (inView(p0)) M.placeLabel(labelsG, placed, { x: p0[0], y: p0[1] + 18 * k, text: "PDX", size: 22 * k, k, dots: dotsXY, force: true, bounds: [W, H] });
    // The selected city first, then the label list's order, then the farthest, so the most useful names win a crowded spot.
    const rank = w => { const i = labelSet.indexOf(w.code); return i < 0 ? labelSet.length : i; };
    wanted.sort((a, b) => (b.sel - a.sel) || (rank(a) - rank(b)) || (b.miles - a.miles))
      .forEach(w => M.placeLabel(labelsG, placed, { ...w, size: (w.sel ? 19 : 14) * k, k, dots: dotsXY, force: w.sel, bounds: [W, H] }));
  }

  /* ---------- the fixed map, on airline pages ---------- */
  function drawFixed() {
    if (!world) return;
    const west = view === "west" && detail && WEST_POINTS.length >= 2;
    const proj = fitted(west);
    const { g, labels } = M.drawBase(svg, { proj, W, H, geo: west ? detail : world, id: "overview", graticule: true });
    drawRoutes(g, labels(), proj, { withLabels: true, labelKey: west ? "west" : "world", labelEvery: LABEL_ALL });
  }

  /* ---------- the zoomable map, on the home page ---------- */
  // Everything but the labels lives in one layer drawn in the full view's coordinates: coastlines, routes,
  // dots and the PDX trees. A zoom moves that layer with one transform, keeps line widths steady with
  // non scaling strokes, and shrinks dots and trees back to size. Nothing is rebuilt while a gesture moves.
  const BASE = fitted(false);  // the full view; every zoom is this projection scaled and shifted
  let t = d3.zoomIdentity;
  let layers = null, builtGeo = null, routesFor = null;
  function zoomedProjection() {
    const [tx, ty] = BASE.translate();
    return d3.geoNaturalEarth1().rotate([75, 0]).scale(BASE.scale() * t.k).translate([t.x + tx * t.k, t.y + ty * t.k]);
  }
  function inNorthAmerica([lon, lat]) {
    return lon >= NORTH_AMERICA.west && lon <= NORTH_AMERICA.east && lat >= NORTH_AMERICA.south && lat <= NORTH_AMERICA.north;
  }
  function setupLayers() {
    svg.selectAll("*").remove();
    const defs = svg.append("defs");
    defs.append("clipPath").attr("id", "overview-clip").append("rect").attr("width", W).attr("height", H).attr("rx", 14);
    const wobble = defs.append("filter").attr("id", "overview-wobble").attr("x", "-2%").attr("y", "-2%").attr("width", "104%").attr("height", "104%");
    wobble.append("feTurbulence").attr("type", "fractalNoise").attr("baseFrequency", 0.018).attr("numOctaves", 2).attr("seed", 7).attr("result", "n");
    wobble.append("feDisplacementMap").attr("in", "SourceGraphic").attr("in2", "n").attr("scale", 4).attr("xChannelSelector", "R").attr("yChannelSelector", "G");
    svg.append("rect").attr("class", "ocean").attr("width", W).attr("height", H).attr("rx", 14);
    const zoomed = svg.append("g").attr("clip-path", "url(#overview-clip)").append("g").attr("class", "zoom-base");
    layers = { base: zoomed, coast: zoomed.append("g"), routes: zoomed.append("g"), labels: svg.append("g") };
  }
  // The coastline layer, drawn once per data set.
  function buildCoast(geo) {
    builtGeo = geo;
    const path = d3.geoPath(BASE);
    const c = layers.coast;
    c.selectAll("*").remove();
    c.append("path").attr("class", "grat").attr("d", path(d3.geoGraticule().step([15, 15])()));
    const land = c.append("g").attr("class", "zoom-land");
    land.selectAll("path.land").data(geo.land.features).join("path").attr("class", "land").attr("d", path);
    land.selectAll("path.lake").data(geo.lakes.features).join("path").attr("class", "lake").attr("d", path);
    if (geo.states) land.append("g").selectAll("path").data(geo.states.features).join("path").attr("class", "stateline").attr("d", path);
    if (geo.countries) land.append("g").selectAll("path").data(geo.countries.features).join("path").attr("class", "countryline").attr("d", path);
  }
  // Routes, dots and the PDX trees, drawn once per selection and screen size. Sizes are stored and divided by the zoom.
  function buildRoutes() {
    const k = M.scaleFor(svgEl, W);
    routesFor = { selected, k };
    const path = d3.geoPath(BASE);
    const r = layers.routes;
    r.selectAll("*").remove();
    r.selectAll("path.spoke").data(POINTS).join("path")
      .attr("class", p => "spoke" + (p.yearRound ? "" : " seasonal") + (p.code === selected ? " on" : ""))
      .attr("d", p => path({ type: "LineString", coordinates: [M.PDX, [p.lon, p.lat]] }));
    const p0 = BASE(M.PDX);
    M.treesAround(r.append("g").attr("class", "zoom-trees").attr("data-x", p0[0]).attr("data-y", p0[1]).append("g"), [0, 0]);
    const dots = r.append("g");
    POINTS.forEach(p => {
      const [x, y] = BASE([p.lon, p.lat]);
      const node = dots.append("g").attr("tabindex", 0).attr("role", "button")
        .attr("aria-label", `${p.name}, ${p.miles !== null ? p.miles.toLocaleString("en-US") + " miles" : ""}`)
        .on("click", () => select(p.code))
        .on("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(p.code); } });
      node.append("circle").attr("class", "hit").attr("cx", x).attr("cy", y).attr("data-r", 11 * k);
      node.append("circle").attr("class", "dest" + (p.code === selected ? " on" : "")).attr("cx", x).attr("cy", y)
        .attr("data-r", (p.code === selected ? 6 : 3.6) * Math.min(k, 1.6));
    });
    r.append("circle").attr("class", "pdx-dot").attr("cx", p0[0]).attr("cy", p0[1]).attr("data-r", 8 * Math.min(k, 1.6));
  }
  // The cheap part of every frame: move the layer and size its dots and trees for this zoom.
  function applyZoom() {
    layers.base.attr("transform", t.toString());
    const inv = 1 / t.k;
    layers.routes.selectAll("circle[data-r]").attr("r", function () { return this.dataset.r * inv; });
    const trees = layers.routes.select(".zoom-trees");
    trees.attr("transform", `translate(${trees.attr("data-x")},${trees.attr("data-y")}) scale(${inv})`);
  }
  function wantedGeo() {
    const middle = zoomedProjection().invert([W / 2, H / 2]);
    return t.k >= DETAIL_ZOOM && detail && middle && inNorthAmerica(middle) ? detail : world;
  }
  // Labels, in screen coordinates, placed once the map is still.
  function drawLabels() {
    const k = M.scaleFor(svgEl, W);
    const small = k > 1.6;
    const proj = zoomedProjection();
    const inView = ([x, y]) => x > 4 && x < W - 4 && y > 4 && y < H - 4;
    const vis = POINTS.filter(p => inView(proj([p.lon, p.lat])));
    const labelSet = (small ? LABELS_SMALL : LABELS)[view === "west" ? "west" : "world"];
    const every = LABEL_ALL || t.k >= 1.6;
    const placed = [];
    const buttons = svgEl.parentElement.querySelector(".zoom-buttons");
    if (buttons) {
      const b = buttons.getBoundingClientRect(), s = svgEl.getBoundingClientRect(), f = W / (s.width || W);
      placed.push({ x: (b.left - s.left) * f - 6, y: (b.top - s.top) * f - 6, width: b.width * f + 12, height: b.height * f + 12 });
    }
    const dotsXY = vis.map(p => proj([p.lon, p.lat]));
    const p0 = proj(M.PDX);
    if (inView(p0)) M.placeLabel(layers.labels, placed, { x: p0[0], y: p0[1] + 18 * k, text: "PDX", size: 22 * k, k, dots: dotsXY, force: true, bounds: [W, H] });
    const rank = w => { const i = labelSet.indexOf(w.code); return i < 0 ? labelSet.length : i; };
    vis.map((p, i) => ({ x: dotsXY[i][0], y: dotsXY[i][1], sel: p.code === selected, text: p.name, right: dotsXY[i][0] < W * 0.82, code: p.code, miles: p.miles || 0 }))
      .filter(w => every || labelSet.includes(w.code) || w.sel)
      .sort((a, b) => (b.sel - a.sel) || (rank(a) - rank(b)) || (b.miles - a.miles))
      .forEach(w => M.placeLabel(layers.labels, placed, { ...w, size: (w.sel ? 19 : 14) * k, k, dots: dotsXY, force: w.sel, bounds: [W, H] }));
  }
  // A light frame while moving; a settled frame with labels, finer outlines and the wobble once still.
  function frameZoomable({ settled }) {
    if (!world) return;
    if (!layers) setupLayers();
    if (!builtGeo) buildCoast(world);
    const k = M.scaleFor(svgEl, W);
    if (!routesFor || routesFor.selected !== selected || routesFor.k !== k) buildRoutes();
    layers.labels.selectAll("*").remove();
    if (settled) {
      const geo = wantedGeo();
      if (geo !== builtGeo) buildCoast(geo);
    }
    layers.coast.select(".zoom-land").attr("filter", settled && t.k < WOBBLE_ZOOM ? "url(#overview-wobble)" : null);
    applyZoom();
    if (settled) drawLabels();
  }

  const draw = ZOOMABLE ? () => frameZoomable({ settled: true }) : drawFixed;

  const roCode = document.getElementById("readout-code");
  const roLink = document.getElementById("readout-link");
  function select(code) {
    selected = code;
    const p = byCode[code];
    M.flapRow(roCode, code);
    document.getElementById("readout-name").textContent = p.name;
    const miles = p.miles !== null ? `${p.miles.toLocaleString("en-US")} miles · about ${p.flight}` : "";
    document.getElementById("readout-meta").textContent = [miles, p.airlines.join(", "), p.service].filter(Boolean).join(" · ");
    if (roLink && p.url) { roLink.href = p.url; roLink.textContent = `More about ${p.name}`; roLink.hidden = false; }
    draw();
  }
  function pressViewButtons() {
    document.querySelectorAll("[data-zoom]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.zoom === view)));
  }

  if (ZOOMABLE) {
    // While a gesture moves: one light frame per animation frame (no labels, no coastline swap).
    // Once it pauses or ends: the full frame with labels.
    let frame = null, settleTimer = null, pinching = false;
    const settle = () => {
      clearTimeout(settleTimer); settleTimer = null;
      if (frame) { cancelAnimationFrame(frame); frame = null; }  // or a queued moving frame would wipe the labels
      svgEl.classList.remove("moving");
      frameZoomable({ settled: true });
    };
    const moved = () => {
      svgEl.classList.add("moving");  // the grid and borders sit out while moving: they're half of each frame's painting
      if (!frame) frame = requestAnimationFrame(() => { frame = null; frameZoomable({ settled: false }); });
      clearTimeout(settleTimer);
      settleTimer = setTimeout(settle, LABEL_PAUSE_MS);
    };
    const zoomer = d3.zoom()
      .scaleExtent([1, MAX_ZOOM])
      .extent([[0, 0], [W, H]])
      .translateExtent([[0, 0], [W, H]])
      // Mouse and scroll wheel only; phones use the two finger pinch below, so one finger scrolls the page.
      .filter(e => !e.type.startsWith("touch") && (!e.ctrlKey || e.type === "wheel") && !e.button)
      .on("start", e => {
        if (e.sourceEvent) { view = null; pressViewButtons(); }  // a person moved the map by hand
        if (!detail) loadDetail();
      })
      .on("zoom", e => { t = e.transform; moved(); })
      .on("end", () => {
        if (pinching) return;
        if (t.k < 1.02 && view === null) { view = "world"; pressViewButtons(); }
      });
    svg.call(zoomer);

    // Two finger pinch and drag for touch screens. Finger positions are read against the map's own box,
    // which zooming never moves, so the math can't feed back on itself.
    let pinch = null;
    const toMap = touch => {
      const r = svgEl.getBoundingClientRect();
      return [(touch.clientX - r.left) * W / r.width, (touch.clientY - r.top) * H / r.height];
    };
    const midpoint = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    svgEl.addEventListener("touchstart", e => {
      if (e.touches.length !== 2) return;
      const a = toMap(e.touches[0]), b = toMap(e.touches[1]);
      pinch = { dist: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1, anchor: t.invert(midpoint(a, b)), k: t.k };
      pinching = true; view = null; pressViewButtons();
      if (!detail) loadDetail();
    }, { passive: true });
    svgEl.addEventListener("touchmove", e => {
      if (!pinch || e.touches.length !== 2) return;
      e.preventDefault();
      const a = toMap(e.touches[0]), b = toMap(e.touches[1]);
      const k = Math.max(1, Math.min(MAX_ZOOM, pinch.k * Math.hypot(a[0] - b[0], a[1] - b[1]) / pinch.dist));
      const [mx, my] = midpoint(a, b);
      const next = d3.zoomIdentity.translate(mx - pinch.anchor[0] * k, my - pinch.anchor[1] * k).scale(k);
      // Keep d3's record of the zoom in step without its events, then draw the light frame.
      t = zoomer.constrain()(next, [[0, 0], [W, H]], [[0, 0], [W, H]]);
      svgEl.__zoom = t;
      moved();
    }, { passive: false });
    const endPinch = e => {
      if (!pinch || e.touches.length >= 2) return;
      pinch = null; pinching = false;
      if (t.k < 1.02) { view = "world"; pressViewButtons(); }
      settle();
    };
    svgEl.addEventListener("touchend", endPinch);
    svgEl.addEventListener("touchcancel", endPinch);

    // Buttons: zoom in and out, back to everywhere, and a glide to the West.
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const glide = (next, ms = 650) => svg.transition().duration(reduce ? 0 : ms).call(zoomer.transform, next);
    const westView = () => {
      const pts = [M.PDX, ...WEST_POINTS.map(p => [p.lon, p.lat])].map(c => BASE(c));
      const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
      const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      const k = Math.min(MAX_ZOOM, 0.85 * Math.min(W / (x1 - x0), H / (y1 - y0)));
      return d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    };
    document.querySelectorAll("[data-zoom]").forEach(b => b.addEventListener("click", async () => {
      view = b.dataset.zoom; pressViewButtons();
      if (view === "west") {
        if (!detail) { svgEl.setAttribute("aria-busy", "true"); await loadDetail(); svgEl.removeAttribute("aria-busy"); }
        glide(westView());
      } else glide(d3.zoomIdentity);
    }));
    const byButton = factor => { view = null; pressViewButtons(); svg.transition().duration(reduce ? 0 : 300).call(zoomer.scaleBy, factor); };
    const zin = document.getElementById("zoom-in"), zout = document.getElementById("zoom-out");
    if (zin) zin.addEventListener("click", () => byButton(1.8));
    if (zout) zout.addEventListener("click", () => byButton(1 / 1.8));
  } else {
    document.querySelectorAll("[data-zoom]").forEach(b => b.addEventListener("click", async () => {
      view = b.dataset.zoom; pressViewButtons();
      if (view === "west") {
        if (selected && byCode[selected].miles >= WEST_MILES) selected = null;
        svgEl.setAttribute("aria-busy", "true");
        await loadDetail();
        svgEl.removeAttribute("aria-busy");
      }
      draw();
    }));
  }

  M.onResize(svgEl, () => draw());
  Promise.all([M.loadJSON(script.dataset.world), M.fontsReady()]).then(([w]) => { world = w; draw(); })
    .catch(() => { svgEl.insertAdjacentHTML("afterend", '<p class="map-fallback">The map couldn\'t load. Every destination is in the departures list below.</p>'); });
})();

/* Shared pieces for the NonStopPDX maps, after design study 4. Needs d3, loaded first. */
window.NSPMap = (function () {
  const PDX = [-122.5975, 45.5887];
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const cache = {};

  function loadJSON(url) {
    if (!cache[url]) cache[url] = fetch(url).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
    return cache[url];
  }

  /* Flip tiles for an airport code, flipping through letters before they land. */
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

  function treesAround(g, [x, y], k = 1) {
    [[-34, -14, 1.0, "t-a"], [-18, -34, 0.8, "t-b"], [26, -26, 0.9, "t-a"], [36, 6, 0.75, "t-b"], [-30, 26, 0.7, "t-a"]]
      .forEach(([dx, dy, s, c]) => tree(g, x + dx * k, y + dy * k, s * k, c));
  }

  /* How much to grow text and tap targets, since the map shrinks with the page on narrow screens. */
  function scaleFor(svgEl, W) {
    return Math.max(1, Math.min(2.4, W / (svgEl.clientWidth || W)));
  }

  /* Clears the svg and draws ocean, land, lakes, and state and country lines when the geography has them.
     Returns the clipped group to draw routes into, and a labels group above everything. */
  function drawBase(svg, { proj, W, H, geo, id, graticule = false, radius = 14 }) {
    // Trim shapes to the frame, or Safari drops filtered layers that are far bigger than the map.
    proj.clipExtent([[-8, -8], [W + 8, H + 8]]);
    const path = d3.geoPath(proj);
    svg.selectAll("*").remove();
    const defs = svg.append("defs");
    defs.append("clipPath").attr("id", `${id}-clip`).append("rect").attr("width", W).attr("height", H).attr("rx", radius);
    const wobble = defs.append("filter").attr("id", `${id}-wobble`).attr("x", "-2%").attr("y", "-2%").attr("width", "104%").attr("height", "104%");
    wobble.append("feTurbulence").attr("type", "fractalNoise").attr("baseFrequency", 0.018).attr("numOctaves", 2).attr("seed", 7).attr("result", "n");
    wobble.append("feDisplacementMap").attr("in", "SourceGraphic").attr("in2", "n").attr("scale", 4).attr("xChannelSelector", "R").attr("yChannelSelector", "G");

    svg.append("rect").attr("class", "ocean").attr("width", W).attr("height", H).attr("rx", radius);
    const g = svg.append("g").attr("clip-path", `url(#${id}-clip)`).append("g").attr("class", "map-content");
    if (graticule) g.append("path").attr("class", "grat").attr("d", path(d3.geoGraticule().step([15, 15])()));
    const land = g.append("g").attr("filter", `url(#${id}-wobble)`);
    land.selectAll("path.land").data(geo.land.features).join("path").attr("class", "land").attr("d", path);
    land.selectAll("path.lake").data(geo.lakes.features).join("path").attr("class", "lake").attr("d", path);
    if (geo.states) land.append("g").selectAll("path").data(geo.states.features).join("path").attr("class", "stateline").attr("d", path);
    if (geo.countries) land.append("g").selectAll("path").data(geo.countries.features).join("path").attr("class", "countryline").attr("d", path);
    return { g, path, labels: () => svg.append("g") };
  }

  const boxesHit = (a, b) => a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;

  /* Label sizes come from the font's measured width, cached, so finding a free spot doesn't make the
     browser lay out every candidate. Matches svg text.label: Jost 500, capitals, 0.08em letter spacing. */
  const measure = document.createElement("canvas").getContext("2d");
  const widths = new Map();
  let fit = null;  // how the browser's drawn label compares with the canvas measurement, found once per page
  function calibrate(labels) {
    const sample = "SALT LAKE CITY";
    const t = labels.append("text").attr("class", "label").attr("font-size", 100).attr("x", 0).attr("y", 0).text(sample);
    const b = t.node().getBBox();
    t.remove();
    measure.font = '500 100px Jost, Futura, "Century Gothic", sans-serif';
    const guess = measure.measureText(sample).width + 0.08 * 100 * sample.length;
    fit = b.width > 0 ? { width: b.width / guess, top: -b.y / 100, height: b.height / 100 } : { width: 1.05, top: 0.95, height: 1.25 };
  }
  function labelBox(labels, text, size, start, x, y) {
    if (!fit) calibrate(labels);
    const key = size.toFixed(2) + "|" + text;
    let w = widths.get(key);
    if (w === undefined) {
      measure.font = `500 ${size}px Jost, Futura, "Century Gothic", sans-serif`;
      w = (measure.measureText(text.toUpperCase()).width + 0.08 * size * text.length) * fit.width;
      widths.set(key, w);
    }
    return { x: start ? x : x - w, y: y - fit.top * size, width: w, height: fit.height * size };
  }

  /* A city label beside its dot. It tries the preferred side, then the other side, each a little up or down,
     and takes the first spot that covers no placed label and no other dot, inside bounds when given.
     With no clear spot it's left off, unless force is set (the selected city always keeps its name). */
  function placeLabel(labels, placed, { x, y, text, size, right = true, k = 1, cls = "label", dots = [], force = false, bounds = null }) {
    const pad = 2 * k;
    const coversDot = box => dots.some(([dx, dy]) => (dx !== x || dy !== y) &&
      dx > box.x - pad && dx < box.x + box.width + pad && dy > box.y - pad && dy < box.y + box.height + pad);
    const inside = box => !bounds || (box.x >= 2 && box.y >= 2 && box.x + box.width <= bounds[0] - 2 && box.y + box.height <= bounds[1] - 2);
    let chosen = null, first = null;
    for (const side of [right, !right]) {
      for (const step of [0, -1, 1, -2, 2]) {
        const lx = x + (side ? 8 : -8) * k, ly = y + 5 * k + step * 14 * k;
        const box = labelBox(labels, text, size, side, lx, ly);
        const spot = { side, lx, ly, box };
        if (!first) first = spot;
        if (inside(box) && !placed.some(p => boxesHit(box, p)) && !coversDot(box)) { chosen = spot; break; }
      }
      if (chosen) break;
    }
    if (!chosen && !force) return null;
    const spot = chosen || first;
    placed.push(spot.box);
    return labels.append("text").attr("class", cls).attr("font-size", size).attr("x", spot.lx).attr("y", spot.ly)
      .attr("text-anchor", spot.side ? "start" : "end").text(text);
  }

  /* Destination drawings from data/drawings.json: shapes in a 100 by 100 box centered on 0,0,
     colored with the site palette. Same shape types as the motif editor. */
  const STROKED = new Set(["wave", "line"]);
  function smooth(pts) {
    if (pts.length < 2) return "";
    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`;
    }
    return d;
  }
  function shapeCenter(s) {
    if (s.t === "circle" || s.t === "ellipse") return [s.cx, s.cy];
    if (s.t === "rect") return [s.x + s.w / 2, s.y + s.h / 2];
    const xs = s.pts.map(p => p[0]), ys = s.pts.map(p => p[1]);
    if (s.t === "hill") ys.push(s.base);
    return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
  }
  function drawShapes(g, shapes) {
    shapes.forEach(s => {
      let e;
      if (s.t === "circle") e = g.append("circle").attr("cx", s.cx).attr("cy", s.cy).attr("r", s.r);
      else if (s.t === "ellipse") e = g.append("ellipse").attr("cx", s.cx).attr("cy", s.cy).attr("rx", s.rx).attr("ry", s.ry);
      else if (s.t === "rect") e = g.append("rect").attr("x", s.x).attr("y", s.y).attr("width", s.w).attr("height", s.h).attr("rx", s.rx || 0);
      else if (s.t === "poly") e = g.append("polygon").attr("points", s.pts.map(p => p.join(",")).join(" "));
      else if (s.t === "hill") {
        const first = s.pts[0], last = s.pts[s.pts.length - 1];
        e = g.append("path").attr("d", `${smooth(s.pts)} L${last[0]},${s.base} L${first[0]},${s.base} Z`);
      } else if (s.t === "wave") e = g.append("path").attr("d", smooth(s.pts));
      else if (s.t === "line") e = g.append("polyline").attr("points", s.pts.map(p => p.join(",")).join(" "));
      else return;
      const color = `var(--${s.c || "ink"})`;
      if (STROKED.has(s.t)) e.style("fill", "none").style("stroke", color).attr("stroke-width", s.w || 2).attr("stroke-linecap", "round").attr("stroke-linejoin", "round");
      else e.style("fill", color);
      if (s.op != null && s.op < 1) e.attr("opacity", s.op);
      if (s.rot) { const [cx, cy] = shapeCenter(s); e.attr("transform", `rotate(${s.rot} ${cx} ${cy})`); }
    });
  }

  /* Labels are measured to keep them apart, so wait for the page's fonts first, or a fallback font gets measured. */
  function fontsReady() {
    return document.fonts && document.fonts.ready ? document.fonts.ready.catch(() => {}) : Promise.resolve();
  }

  /* Redraw when the map's width changes, since text and tap targets scale with it. */
  function onResize(svgEl, redraw) {
    let last = svgEl.clientWidth, timer = null;
    window.addEventListener("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { if (svgEl.clientWidth !== last) { last = svgEl.clientWidth; redraw(); } }, 150);
    });
  }

  return { PDX, loadJSON, flapRow, tree, treesAround, scaleFor, drawBase, placeLabel, onResize, fontsReady, drawShapes };
})();

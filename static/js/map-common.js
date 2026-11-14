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
    const g = svg.append("g").attr("clip-path", `url(#${id}-clip)`);
    if (graticule) g.append("path").attr("class", "grat").attr("d", path(d3.geoGraticule().step([15, 15])()));
    const land = g.append("g").attr("filter", `url(#${id}-wobble)`);
    land.selectAll("path.land").data(geo.land.features).join("path").attr("class", "land").attr("d", path);
    land.selectAll("path.lake").data(geo.lakes.features).join("path").attr("class", "lake").attr("d", path);
    if (geo.states) land.append("g").selectAll("path").data(geo.states.features).join("path").attr("class", "stateline").attr("d", path);
    if (geo.countries) land.append("g").selectAll("path").data(geo.countries.features).join("path").attr("class", "countryline").attr("d", path);
    return { g, path, labels: () => svg.append("g") };
  }

  const boxesHit = (a, b) => a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;

  /* A city label beside its dot. It tries the preferred side, then the other side, each a little up or down,
     and takes the first spot that covers no placed label and no other dot. With no clear spot it's left off,
     unless force is set (the selected city always keeps its name). Returns the text, or null. */
  function placeLabel(labels, placed, { x, y, text, size, right = true, k = 1, cls = "label", dots = [], force = false }) {
    const t = labels.append("text").attr("class", cls).attr("font-size", size).text(text);
    const pad = 2 * k;
    const coversDot = box => dots.some(([dx, dy]) => (dx !== x || dy !== y) &&
      dx > box.x - pad && dx < box.x + box.width + pad && dy > box.y - pad && dy < box.y + box.height + pad);
    const spots = [];
    for (const side of [right, !right]) for (const step of [0, -1, 1, -2, 2]) spots.push({ side, step });
    let first = null;
    for (const { side, step } of spots) {
      t.attr("x", x + (side ? 8 : -8) * k).attr("text-anchor", side ? "start" : "end").attr("y", y + 5 * k + step * 14 * k);
      const box = t.node().getBBox();
      if (!first) first = { side, step, box };
      if (!placed.some(p => boxesHit(box, p)) && !coversDot(box)) { placed.push(box); return t; }
    }
    if (!force) { t.remove(); return null; }
    t.attr("x", x + (first.side ? 8 : -8) * k).attr("text-anchor", first.side ? "start" : "end").attr("y", y + 5 * k + first.step * 14 * k);
    placed.push(first.box);
    return t;
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

  return { PDX, loadJSON, flapRow, tree, treesAround, scaleFor, drawBase, placeLabel, onResize, fontsReady };
})();

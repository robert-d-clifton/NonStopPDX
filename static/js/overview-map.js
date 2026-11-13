/* The overview map: every nonstop from PDX on a flat Natural Earth projection, after design study 4.
   Needs d3 and map-common.js (loaded first) and the #map-points JSON the page renders. */
(function () {
  const script = document.currentScript;
  const svgEl = document.getElementById("overview-map");
  const pointsEl = document.getElementById("map-points");
  if (!svgEl || !pointsEl || !window.d3 || !window.NSPMap) return;
  const M = window.NSPMap;

  const POINTS = JSON.parse(pointsEl.textContent);
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
  const byCode = Object.fromEntries(POINTS.map(p => [p.code, p]));
  const svg = d3.select(svgEl);
  let world = null, detail = null;
  let zoom = "world", selected = null;

  function draw() {
    const west = zoom === "west" && detail;
    const k = M.scaleFor(svgEl, W);
    const small = k > 1.6;

    const shown = west ? POINTS.filter(p => p.miles !== null && p.miles < WEST_MILES) : POINTS;
    const proj = d3.geoNaturalEarth1().rotate([west ? 114 : 75, 0]);
    proj.fitExtent([[70, 56], [W - 70, H - 56]], { type: "MultiPoint", coordinates: [M.PDX, ...shown.map(p => [p.lon, p.lat])] });
    const { g, path, labels } = M.drawBase(svg, { proj, W, H, geo: west ? detail : world, id: "overview", graticule: true });
    const inView = ([x, y]) => x > 4 && x < W - 4 && y > 4 && y < H - 4;

    const vis = POINTS.filter(p => inView(proj([p.lon, p.lat])));
    g.selectAll("path.spoke").data(vis).join("path")
      .attr("class", p => "spoke" + (p.yearRound ? "" : " seasonal") + (p.code === selected ? " on" : ""))
      .attr("d", p => path({ type: "LineString", coordinates: [M.PDX, [p.lon, p.lat]] }));

    const p0 = proj(M.PDX);
    M.treesAround(g.append("g"), p0);

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
    const lg = labels();
    const placed = [];
    const pdx = lg.append("text").attr("class", "label").attr("x", p0[0] + 12 * k).attr("y", p0[1] + 26 * k).attr("font-size", 22 * k).text("PDX");
    placed.push(pdx.node().getBBox());
    wanted.sort((a, b) => b.sel - a.sel).forEach(w => M.placeLabel(lg, placed, { ...w, size: (w.sel ? 19 : 14) * k, k }));
  }

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

  document.querySelectorAll("[data-zoom]").forEach(b => b.addEventListener("click", async () => {
    document.querySelectorAll("[data-zoom]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    zoom = b.dataset.zoom;
    if (zoom === "west") {
      if (selected && byCode[selected].miles >= WEST_MILES) selected = null;
      svgEl.setAttribute("aria-busy", "true");
      try { detail = await M.loadJSON(script.dataset.detail); } catch (e) { detail = null; } finally { svgEl.removeAttribute("aria-busy"); }
    }
    draw();
  }));

  M.onResize(svgEl, () => { if (world) draw(); });
  M.loadJSON(script.dataset.world).then(w => { world = w; draw(); })
    .catch(() => { svgEl.insertAdjacentHTML("afterend", '<p class="map-fallback">The map couldn\'t load. Every destination is in the departures list below.</p>'); });
})();

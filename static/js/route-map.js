/* A destination page's route map: one arc from PDX, framed to fit, with state and country lines.
   Needs d3 and map-common.js (loaded first) and the #route-point JSON the page renders. */
(function () {
  const script = document.currentScript;
  const svgEl = document.getElementById("route-map");
  const pointEl = document.getElementById("route-point");
  if (!svgEl || !pointEl || !window.d3 || !window.NSPMap) return;
  const M = window.NSPMap;

  const DEST = JSON.parse(pointEl.textContent);
  const W = 1000;
  const MAX_HEIGHT_PX = 420;  // on wide screens the map gets wider, not taller
  let H = 560;
  // The finer North American map covers Alaska and Hawaii to the Caribbean; routes beyond it use the world map.
  const NORTH_AMERICA = { west: -170, south: 10, east: -50, north: 72 };
  const near = DEST.lon >= NORTH_AMERICA.west && DEST.lon <= NORTH_AMERICA.east && DEST.lat >= NORTH_AMERICA.south && DEST.lat <= NORTH_AMERICA.north;
  const svg = d3.select(svgEl);
  let world = null, detail = null;

  function draw() {
    const width = svgEl.clientWidth || W;
    H = Math.round(Math.min(560, W * MAX_HEIGHT_PX / width));
    svgEl.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const k = M.scaleFor(svgEl, W);
    const line = { type: "LineString", coordinates: [M.PDX, [DEST.lon, DEST.lat]] };
    const proj = d3.geoMercator().rotate([-(M.PDX[0] + DEST.lon) / 2, 0]);
    const pad = Math.max(90, 170 - (DEST.miles || 0) / 40);
    proj.fitExtent([[pad + 60, pad], [W - pad - 60, H - pad]], line);
    const { g, path, labels } = M.drawBase(svg, { proj, W, H, geo: detail || world, id: "route", radius: 0 });

    g.append("path").attr("class", "routeline" + (DEST.yearRound ? "" : " seasonal")).attr("d", path(line));
    const a = proj(M.PDX), b = proj([DEST.lon, DEST.lat]);
    M.treesAround(g.append("g"), a, Math.min(k, 1.4));
    g.append("circle").attr("class", "wash").attr("cx", b[0]).attr("cy", b[1]).attr("r", 54 * Math.min(k, 1.6))
      .style("fill", DEST.regionColor);
    svg.append("circle").attr("class", "pdx-dot").attr("cx", a[0]).attr("cy", a[1]).attr("r", 8 * Math.min(k, 1.6));
    svg.append("circle").attr("class", "pdx-dot").attr("cx", b[0]).attr("cy", b[1]).attr("r", 8 * Math.min(k, 1.6));

    const lg = labels();
    const placed = [];
    const below = (x, y, text) => {
      const t = lg.append("text").attr("class", "label").attr("x", x).attr("y", y + 34 * k).attr("text-anchor", "middle")
        .attr("font-size", 22 * k).text(text);
      placed.push(t.node().getBBox());
    };
    below(a[0], a[1], "PDX");
    below(b[0], b[1], DEST.code);
  }

  const tiles = document.getElementById("dest-code");
  if (tiles) M.flapRow(tiles, DEST.code);

  M.onResize(svgEl, () => { if (world || detail) draw(); });
  const geo = near ? M.loadJSON(script.dataset.detail).then(d => { detail = d; }) : M.loadJSON(script.dataset.world).then(w => { world = w; });
  geo.then(draw).catch(() => {
    // Fall back to the world map if the finer one fails, and say so only if that fails too.
    M.loadJSON(script.dataset.world).then(w => { world = w; detail = null; draw(); })
      .catch(() => svgEl.insertAdjacentHTML("afterend", '<p class="map-fallback">The route map couldn\'t load.</p>'));
  });
})();

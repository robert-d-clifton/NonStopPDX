# Map geography

- `world-110m.json`: world land and lakes for the overview map.
- `north-america-50m.json`: finer North American land and lakes, plus rivers and state and province lines, for close up views. It loads only when a page needs it.

Both come from [Natural Earth](https://www.naturalearthdata.com/) (public domain), trimmed to the areas we use and rounded to keep them small. They were built from the files in `design/studies/shared/`, the same data the design studies use.

One fix on top of Natural Earth: it names the Snake River, from Idaho to where it meets the Columbia at Pasco, as part of the Columbia. Those stretches are split out under Snake in `north-america-50m.json`, so river labels land on the right river.

`static/vendor/d3-7.8.5.min.js` is [d3](https://d3js.org/) 7.8.5 (ISC license), hosted with the site so pages don't depend on a third party being up.

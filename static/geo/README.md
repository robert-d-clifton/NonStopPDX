# Map geography

- `world-110m.json`: world land, lakes and country lines, plus US and Canada state lines, for the overview map and long routes.
- `north-america-50m.json`: finer North American land, lakes and country lines, plus US, Canada and Mexico state lines, for routes within North America and the West view. It loads only when a page needs it.

Both come from [Natural Earth](https://www.naturalearthdata.com/) 5.1.2 (public domain), trimmed to the areas we use and rounded to keep them small. Rebuild them with:

```sh
python3 tools/build_geo.py
```

`static/vendor/d3-7.8.5.min.js` is [d3](https://d3js.org/) 7.8.5 (ISC license), hosted with the site so pages don't depend on a third party being up.

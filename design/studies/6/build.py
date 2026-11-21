"""Build index.html for the roof options study from the site's own CSS, model script and terminal data.
Run: python3 design/studies/6/build.py"""
import json
from pathlib import Path
here = Path(__file__).resolve().parent
root = here.parent.parent.parent
t = json.loads((root / "data" / "terminal.json").read_text(encoding="utf-8"))
data = {"shapes": t["shapes"], "gates": t["gates"], "rail": t.get("rail", []),
        "pins": [{"name": p["name"], "p": p["p"]} for p in t["places"] if p["category"] == "transit"], "areas": {}}
css = (root / "static" / "css" / "site.css").read_text(encoding="utf-8")
js = (root / "static" / "js" / "terminal-model.js").read_text(encoding="utf-8")
html = (here / "source.html").read_text(encoding="utf-8")
html = html.replace("/*SITECSS*/", css, 1).replace("/*MODELJS*/", js, 1).replace("/*DATA*/", json.dumps(data, separators=(",", ":")), 1)
(here / "index.html").write_text(html, encoding="utf-8")
print("Wrote", here / "index.html", len(html), "bytes")

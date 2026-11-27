"""Build index.html for the control tower options from the site's CSS, model script and terminal data, with the
reference photo inlined when it is present locally (it is kept out of git). Run: python3 design/studies/8/build.py"""
import base64, json
from pathlib import Path
here = Path(__file__).resolve().parent
root = here.parent.parent.parent
t = json.loads((root / "data" / "terminal.json").read_text(encoding="utf-8"))
c = json.loads((root / "data" / "concourses.json").read_text(encoding="utf-8"))
data = {"shapes": t["shapes"], "gates": t["gates"], "rail": t.get("rail", []), "noAircraft": c.get("no_aircraft", []),
        "groundBoarding": c.get("ground_boarding", []), "pins": [], "areas": {}}
# The reference photo isn't ours to publish, so it stays out of git; without it the page shows no photo.
ref = here / "reference.webp"
photo = "data:image/webp;base64," + base64.b64encode(ref.read_bytes()).decode() if ref.exists() else ""
html = (here / "source.html").read_text(encoding="utf-8")
html = html.replace("/*SITECSS*/", (root / "static" / "css" / "site.css").read_text(encoding="utf-8"), 1)
html = html.replace("/*MODELJS*/", (root / "static" / "js" / "terminal-model.js").read_text(encoding="utf-8"), 1)
html = html.replace("/*DATA*/", json.dumps(data, separators=(",", ":")), 1).replace("/*PHOTO*/", photo, 1)
(here / "index.html").write_text(html, encoding="utf-8")
print("Wrote", here / "index.html", len(html), "bytes")

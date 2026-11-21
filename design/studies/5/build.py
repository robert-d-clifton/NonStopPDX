"""Build index.html from source.html with terminal.json inlined. Run: python3 design/studies/5/build.py"""
from pathlib import Path
here = Path(__file__).resolve().parent
html = (here / "source.html").read_text(encoding="utf-8")
data = (here / "terminal.json").read_text(encoding="utf-8").strip()
(here / "index.html").write_text(html.replace("/*DATA*/", data, 1), encoding="utf-8")
print("Wrote", here / "index.html")

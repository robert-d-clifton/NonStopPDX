"""Build index.html for the Old Town options from source.html and options.json. Run: python3 design/studies/7/build.py"""
from pathlib import Path
here = Path(__file__).resolve().parent
html = (here / "source.html").read_text(encoding="utf-8").replace("/*DATA*/", (here / "options.json").read_text(encoding="utf-8"), 1)
(here / "index.html").write_text(html, encoding="utf-8")
print("Wrote", here / "index.html")

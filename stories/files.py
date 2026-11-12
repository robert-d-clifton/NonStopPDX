"""Read and write stories/<IATA>.md: a few fields between --- lines, then the story in Markdown."""

from __future__ import annotations

from pathlib import Path

FIELDS = ("iata", "city", "status", "headline", "photo", "photo_credit", "credits")


def parse(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("A story file starts with a --- line")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise ValueError("A story file needs a second --- line after its fields") from None
    fields = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1:]).strip("\n")
    return fields, body


def render(fields: dict, body: str) -> str:
    head = "\n".join(f"{k}: {fields.get(k, '')}".rstrip() for k in FIELDS)
    return f"---\n{head}\n---\n\n{body.strip()}\n"


def read_dir(folder: Path) -> list[tuple[Path, dict, str]]:
    out = []
    for path in sorted(folder.glob("*.md")):
        if path.stem == "README":
            continue
        fields, body = parse(path.read_text(encoding="utf-8"))
        out.append((path, fields, body))
    return out

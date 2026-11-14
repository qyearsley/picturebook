"""Write text-and-prompts.md for a book project, in the V5 layout.

Usage:
    picturebook prompts [project-dir ...]

The markdown is generated from book-data.json, so the two never drift. Edit
the JSON, then run this again. Do not edit the markdown by hand.

The layout is built for browsing a story fast. It has four sections:

    1. A one or two sentence synopsis, plus a one-line facts strip.
    2. The whole English text, page by page, with no Chinese in the way.
    3. The whole Chinese text, page by page.
    4. One pre-assembled single-line image prompt per page.

V4 interleaved each English page with its Chinese page. That made it hard to
read either language straight through.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .bookdata import load_book
from .generate import style_block


def facts_line(data: dict) -> str:
    """A single line of the things you want to see before you read."""
    background = data.get("background", {})
    bits = []
    if background.get("setting"):
        bits.append(background["setting"])
    if background.get("cast"):
        bits.append(background["cast"])
    if background.get("shape"):
        bits.append(background["shape"])
    return "  ·  ".join(bits)


def numbered(pages: list[dict], key: str) -> list[str]:
    out: list[str] = []
    for i, page in enumerate(pages):
        n = page.get("n", i + 1)
        lines = (page.get(key) or "").split("\n")
        out.append(f"**{n}.**  {lines[0]}")
        for line in lines[1:]:
            out.append(f"{line}")
        out.append("")
    return out


def render(data: dict) -> str:
    title = data.get("title", {})
    background = data.get("background", {})
    # The same colour block picturebook generate sends, so the two cannot drift.
    style = style_block(data, "color")
    pages = data.get("pages", [])
    out: list[str] = []

    out.append(f"# {title.get('en', '')} / {title.get('zh', '')}")
    out.append("")
    if background.get("synopsis"):
        out.append(background["synopsis"])
        out.append("")
    facts = facts_line(data)
    if facts:
        out.append(f"*{facts}*")
        out.append("")

    out.append("## English")
    out.append("")
    out.extend(numbered(pages, "en"))

    out.append("## 中文")
    out.append("")
    out.extend(numbered(pages, "zh"))

    out.append("## Illustration prompts")
    out.append("")
    out.append("Each prompt below already has the master style block on the front.")
    out.append("These are the colour prompts. `picturebook generate` adjusts them for line art.")
    out.append("")
    cover = data.get("cover") or {}
    if cover.get("prompt"):
        out.append(f"**Cover.**  {style} {cover['prompt'].strip()}")
        out.append("")
    for page in pages:
        prompt = (page.get("prompt") or "").strip()
        out.append(f"**{page.get('n')}.**  {style} {prompt}")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def export(project: Path) -> Path:
    data = load_book(project)
    out = project / "text-and-prompts.md"
    out.write_text(render(data), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Write text-and-prompts.md from book-data.json.")
    ap.add_argument("projects", nargs="*", default=["."], type=Path)
    args = ap.parse_args(argv)
    for project in args.projects:
        print(f"  wrote {export(Path(project).expanduser().resolve())}")

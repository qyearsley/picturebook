"""Set each page's text_position from the negative space its prompt asks for.

Usage:
    picturebook text-positions [project-dir ...]

Every image prompt ends with a sentence that starts "Keep", naming the part of
the frame to leave quiet for the text. This script reads that sentence. If it
asks for the top of the frame, the page gets "text_position": "top". If it
asks for the bottom, a "top" set earlier is cleared, so the page uses the
book's default band. If it asks for neither, or there is no Keep sentence, the
page keeps whatever text_position it has, including one set by hand.

Before it rewrites book-data.json it copies the file to book-data.json.bak.

Run it after you edit a prompt, so the layout and the artwork never disagree.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from .bookdata import CHARACTERS_KEY, load_book

# A "Keep ..." sentence naming the bottom wins, so "the lower third of the
# table top" is read as the bottom rather than being caught by the word "top".
WANTS_BOTTOM = re.compile(r"\b(bottom|lower|foreground|floor|ground along)\b", re.IGNORECASE)
WANTS_TOP = re.compile(r"\b(top|upper|sky)\b", re.IGNORECASE)


def keep_sentence(prompt: str) -> str:
    """The last sentence of the prompt that starts with Keep."""
    sentences = re.split(r"(?<=\.)\s+", prompt or "")
    keeps = [s for s in sentences if s.strip().startswith("Keep")]
    return keeps[-1] if keeps else ""


def apply(project: Path) -> tuple[list[int], list[int]]:
    """Update text_position from the Keep sentences. Returns (top pages, pages with no Keep)."""
    data_file = project / "book-data.json"
    data = load_book(project)

    top, missing = [], []
    for page in data.get("pages", []):
        sentence = keep_sentence(page.get("prompt", ""))
        if not sentence:
            missing.append(page.get("n"))
        if WANTS_BOTTOM.search(sentence):
            page.pop("text_position", None)
        elif WANTS_TOP.search(sentence):
            page["text_position"] = "top"
        if page.get("text_position") == "top":
            top.append(page.get("n"))

    data.pop(CHARACTERS_KEY, None)
    new_text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if new_text != data_file.read_text(encoding="utf-8"):
        shutil.copyfile(data_file, data_file.with_name(data_file.name + ".bak"))
        data_file.write_text(new_text, encoding="utf-8")
    return top, missing


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projects", nargs="*", default=["."], type=Path)
    args = ap.parse_args(argv)
    for project in args.projects:
        p = Path(project).expanduser().resolve()
        top, missing = apply(p)
        print(f"  {p.name}: text band at top on pages {top or 'none'}")
        if missing:
            print(f"    no 'Keep ...' sentence on pages {missing}")

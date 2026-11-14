"""Set each page's text_position from the negative space its prompt asks for.

Usage:
    picturebook text-positions [project-dir ...]

Every image prompt ends with a sentence that starts "Keep", naming the part of
the frame to leave quiet for the text. This script reads that sentence. If it
asks for the top of the frame, the page gets "text_position": "top". Otherwise
the page uses the book's default band, which is the bottom.

Run it after you edit a prompt, so the layout and the artwork never disagree.
"""

from __future__ import annotations

import argparse
import json
import re
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
    data_file = project / "book-data.json"
    data = load_book(project)

    top, missing = [], []
    for page in data.get("pages", []):
        sentence = keep_sentence(page.get("prompt", ""))
        if not sentence:
            missing.append(page.get("n"))
        if not WANTS_BOTTOM.search(sentence) and WANTS_TOP.search(sentence):
            page["text_position"] = "top"
            top.append(page.get("n"))
        else:
            page.pop("text_position", None)

    data.pop(CHARACTERS_KEY, None)
    data_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
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

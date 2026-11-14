"""Small helpers that every book script shares.

Each of these was copied into several scripts before, and the copies had
started to disagree. Keep them here, and import them.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Files a book can share with other books: the character bible and the cast
# page crops. See shared_file().
SHARED_DIR = "shared"

# Colour art is filed apart from the line art, which it would otherwise
# overwrite: images/ holds the line art, images/color/ the colour art.
COLOR_DIR = "color"

# JPEG quality for the --web builds. On 5 October 2026 a 2x zoom of the colour
# art showed no visible loss at 85, and a colour book went from 37 MB to 4 MB.
WEB_JPEG_QUALITY = 85

# Han characters: extension A, the unified ideographs, compatibility ideographs.
HAN_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))


# load_book() puts the parsed characters.json under this key, so the prompt
# code can reach it without a project path. Strip it before you write
# book-data.json back.
CHARACTERS_KEY = "_characters"


def load_book(project: Path) -> dict:
    """The parsed book-data.json of a project. Exits if there is none.

    The book's characters.json, if there is one, comes along under
    CHARACTERS_KEY. See shared_file() for where it is looked for.
    """
    data_file = project / "book-data.json"
    if not data_file.exists():
        sys.exit(f"error: no book-data.json in {project}")
    try:
        data = json.loads(data_file.read_text(encoding="utf-8"))
    except ValueError as err:
        sys.exit(f"error: {data_file} is not valid JSON: {err}")
    characters = shared_file(project, "characters.json")
    data[CHARACTERS_KEY] = (
        json.loads(characters.read_text(encoding="utf-8")) if characters else {})
    return data


def shared_file(project: Path, name: str) -> Path | None:
    """Find a file such as characters.json for a book, or return None.

    The book folder wins. Then each parent folder is tried for a `shared/`
    folder that holds the file, so several books in one workspace can share
    one character bible.
    """
    if (project / name).is_file():
        return project / name
    for parent in project.resolve().parents:
        candidate = parent / SHARED_DIR / name
        if candidate.is_file():
            return candidate
    return None


def images_dir(project: Path, color: bool = False) -> Path:
    """images/ for line art, images/color/ for colour art."""
    images = project / "images"
    return images / COLOR_DIR if color else images


def is_han(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in HAN_RANGES)


def parse_ratio(aspect: str) -> tuple[float, float] | None:
    """"2:3" -> (2.0, 3.0). None if it is not a ratio of two positive numbers."""
    try:
        w, h = (float(part) for part in aspect.split(":", 1))
    except ValueError:
        return None
    return (w, h) if w > 0 and h > 0 else None


def back_up(path: Path) -> Path:
    """Move a file into _replaced/ beside it, with a timestamp, and return where.

    Nothing that files or edits art deletes the old version. This is how.
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    kept = path.parent / "_replaced" / f"{path.stem}.{stamp}{path.suffix}"
    kept.parent.mkdir(parents=True, exist_ok=True)
    path.replace(kept)
    return kept

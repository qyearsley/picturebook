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


# What a book gets for the page, layout and fonts it leaves out. These are the
# values of examples/pip-forgets, minus its square-art settings, so a book
# with only a title and pages still builds. A field a book sets wins.
DEFAULTS: dict = {
    "page": {"width_in": 8.0, "height_in": 10.6667},
    "layout": {
        "margin_in": 0.55,
        "image_height_frac": 0.6,
        "image_fit": "cover",
        "text_placement": "overlay",
        "gutter_in": 0.3,
        "background": "#fdfcf8",
        "overlay": {"color": "#fdfcf8", "alpha": 0.92, "padding_in": 0.34,
                    "band_height_frac": 0.3, "position": "bottom"},
        "en": {"size": 18, "leading": 24, "color": "#20242b", "align": "center"},
        "zh": {"size": 20, "leading": 32, "color": "#3c4450", "align": "center"},
        "show_page_numbers": True,
    },
    "fonts": {
        "en": ["/System/Library/Fonts/Supplemental/Georgia.ttf",
               "C:/Windows/Fonts/georgia.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
               "Times-Roman"],
        "zh": ["/System/Library/Fonts/STHeiti Medium.ttc:1",
               "/System/Library/Fonts/Supplemental/Songti.ttc:6",
               "C:/Windows/Fonts/simhei.ttf",
               "/usr/share/fonts/truetype/arphic/uming.ttc",
               "STSong-Light"],
    },
}

# Numeric fields the PDF code does arithmetic on, as paths into the book.
NUMBER_FIELDS = (
    ("page", "width_in"), ("page", "height_in"), ("layout", "margin_in"),
    ("layout", "en", "size"), ("layout", "en", "leading"),
    ("layout", "zh", "size"), ("layout", "zh", "leading"),
)


def merge_defaults(defaults: dict, book: dict) -> dict:
    """A copy of `defaults` with the fields of `book` laid over it, level by level."""
    out = {key: (dict(value) if isinstance(value, dict) else value)
           for key, value in defaults.items()}
    for key, value in book.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_defaults(out[key], value)
        else:
            out[key] = value
    return out


def with_defaults(data: dict) -> dict:
    """The book with DEFAULTS filled in for page, layout and fonts.

    A copy. load_book() does not do this itself, because text-positions writes
    its result back to book-data.json, and the defaults must not land there.
    """
    out = dict(data)
    for key, value in DEFAULTS.items():
        given = data.get(key)
        if given is None:
            out[key] = merge_defaults(value, {})
        elif isinstance(given, dict):
            out[key] = merge_defaults(value, given)
        # Anything else stays as written, so problems() can name it.
    return out


def problems(data: dict, need_zh: bool = False) -> list[str]:
    """What is wrong with a book, once its defaults are filled in.

    Each message names the field, and the page when there is one.
    """
    data = with_defaults(data)
    out: list[str] = []
    wrong = {key for key in DEFAULTS if not isinstance(data.get(key), dict)}
    out += [f"{key} must be an object" for key in sorted(wrong)]
    for path in NUMBER_FIELDS:
        if path[0] in wrong:
            continue
        value = data
        for part in path:
            value = value.get(part) if isinstance(value, dict) else None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            out.append(f"{'.'.join(path)} must be a number, got {value!r}")
    for name, value in (data["fonts"].items() if "fonts" not in wrong else []):
        if not isinstance(value, list) or not all(isinstance(f, str) for f in value):
            out.append(f"fonts.{name} must be a list of font names or paths")
    pages = data.get("pages")
    if not isinstance(pages, list) or not pages:
        out.append("pages must be a list with at least one page")
        return out
    for position, page in enumerate(pages, 1):
        if not isinstance(page, dict):
            out.append(f"page {position}: must be an object")
            continue
        label = f"page {page['n']}" if isinstance(page.get("n"), int) else f"page {position}"
        if not isinstance(page.get("n"), int) or isinstance(page.get("n"), bool):
            out.append(f"{label}: needs a whole number in n")
        for field in ("en", "zh") if need_zh else ("en",):
            if not isinstance(page.get(field), str):
                out.append(f"{label}: needs text in {field}")
    return out


def require_valid(data: dict, project: Path, need_zh: bool = False) -> None:
    """Exit with every problem listed, or return if the book is fine."""
    found = problems(data, need_zh)
    if found:
        sys.exit(f"error: {project / 'book-data.json'} is not usable:\n  "
                 + "\n  ".join(found))


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


def use_color(project: Path, color: bool, line: bool) -> bool:
    """--color or --line when given; otherwise colour art if images/color/ exists.

    `generate` makes colour art by default, so a book that has any gets it from
    a plain `import` or `pdf` too.
    """
    if color or line:
        return color
    return images_dir(project, color=True).is_dir()


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

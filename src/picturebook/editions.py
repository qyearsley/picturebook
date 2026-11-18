"""Build the print editions of one or more books into one folder.

Usage:
    picturebook print BOOK [BOOK ...] [--out DIR] [--activity] [--cast-page]
                      [--only VARIANT]

By default each book gets the two colour editions. `--activity` adds the
black-and-white editions: draw-in, colouring and write-in. `--only draw-in`
builds just the draw-in editions, which need no art, so a new book can print
before it has any. Each book gets its own folder in print/ (or DIR), and
print/README.txt says what each file is and how to print it. The files are
rebuilt every run, so a later art fix is one command.

A book does not need line art. An edition is built only when the art it uses
is there for every page:

- colour editions: colour art on every page, and none older than its line
  art where line art exists, so a stale colour page never reaches the
  printer;
- colouring and write-in: line art on every page;
- draw-in: no art.

`--cast-page` adds the cast page after the cover, from the crops in
cast-sheets.json.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import pdf as generate_pdf
from .bookdata import images_dir, load_book

# (file suffix, size, variant, booklet, art, what it is)
# art is "color", "line", or None for an edition that prints no pictures.
EDITIONS = [
    ("draw-in-booklet", "half-letter", "draw-in", True, None,
     "Words with empty boxes to draw in. Folds into a half-letter booklet."),
    ("draw-in-letter", "letter", "draw-in", False, None,
     "Words with empty boxes to draw in. One page per letter sheet, bigger boxes."),
    ("coloring-booklet", "half-letter", "full", True, "line",
     "The line art and the words, to colour in. Folds into a half-letter booklet."),
    ("coloring-letter", "letter", "full", False, "line",
     "The line art and the words, to colour in. One page per letter sheet."),
    ("write-in-letter", "letter", "write-in", False, "line",
     "The line art with handwriting lines and 田字格 squares for the words."),
    ("color-booklet", "half-letter", "full", True, "color",
     "The finished book in colour. Folds into a half-letter booklet."),
    ("color-letter", "letter", "full", False, "color",
     "The finished book in colour. One page per letter sheet."),
]

README = """\
Print editions, built by `picturebook print`.

Every file starts with the cover. Some builds add a page of the characters
("Who is in this book?") after it.

{editions}

How to print

  *-booklet.pdf   Double-sided on letter paper, flipped on the SHORT edge.
                  Each book is 3 sheets. Fold the stack in half and staple
                  twice along the fold. Do not choose "booklet" or
                  "2 pages per sheet" at the printer; the file already is.
  *-letter.pdf    Double-sided on letter paper, flipped on the long edge
                  (the usual setting). Staple at the left edge or bind.

Markers show through ordinary copy paper on a double-sided sheet. Ask for
heavier paper (about 28-32 lb), or use crayons and pencils.
"""


def page_images(project: Path) -> list[str]:
    """The image file names book-data.json lists, cover included."""
    data = load_book(project)
    return [entry["image"] for entry in [data.get("cover") or {}, *data.get("pages", [])]
            if entry.get("image")]


def color_is_current(project: Path) -> bool:
    """True if every page has colour art, and none is older than its line art.

    A page with no line art is fine: the colour art can come straight from a
    text prompt.
    """
    for name in page_images(project):
        line, color = images_dir(project) / name, images_dir(project, color=True) / name
        if not color.exists():
            return False
        if line.exists() and color.stat().st_mtime < line.stat().st_mtime:
            return False
    return True


def line_is_complete(project: Path) -> bool:
    """True if every page has line art."""
    return all((images_dir(project) / name).exists() for name in page_images(project))


def wanted(edition: tuple, activity: bool, only: str | None) -> bool:
    """Whether the options ask for this edition."""
    variant, art = edition[2], edition[4]
    if only:
        return variant == only
    return art == "color" or activity


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="picturebook print",
                                 description="Build the print editions into one folder.")
    ap.add_argument("books", nargs="+", type=Path, help="book folders")
    ap.add_argument("--out", type=Path, default=Path("print"),
                    help="output folder (default: print/ in the current folder)")
    ap.add_argument("--activity", action="store_true",
                    help="also build the draw-in, colouring and write-in editions")
    ap.add_argument("--cast-page", action="store_true",
                    help="add the cast page after the cover (needs cast-sheets.json)")
    ap.add_argument("--only", choices=sorted({e[2] for e in EDITIONS}),
                    help="build only the editions of this variant")
    args = ap.parse_args(argv)

    for project in (p.expanduser().resolve() for p in args.books):
        load_book(project)  # exits with a clear error if it is not a book
        book = project.name
        ready = {None: True, "color": color_is_current(project),
                 "line": line_is_complete(project)}
        reasons = {"color": "colour art is not finished",
                   "line": "line art is not finished"}
        skipped = set()
        for edition in EDITIONS:
            suffix, size, variant, booklet, art, _ = edition
            if not wanted(edition, args.activity, args.only):
                continue
            out = args.out / book / f"{book}-{suffix}.pdf"
            if not ready[art]:
                out.unlink(missing_ok=True)  # an older file would be stale
                skipped.add(art)
                continue
            # Colour art embeds as JPEG; as PNG one book is about 37 MB.
            color = art == "color"
            generate_pdf.build(project, out, cover=True, draft=False, size=size,
                               profile="activity", variant=variant, color=color,
                               web=color, cast_page=args.cast_page, booklet=booklet)
            print(f"  wrote {out.relative_to(args.out)}")
        for art in sorted(skipped):
            print(f"  {book}: {reasons[art]}, so no {'colour' if art == 'color' else 'line-art'} editions")

    lines = "\n".join(f"  *-{suffix + '.pdf':<22}{about}" for suffix, *_, about in EDITIONS)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "README.txt").write_text(README.format(editions=lines), encoding="utf-8")
    print(f"  wrote README.txt in {args.out}")

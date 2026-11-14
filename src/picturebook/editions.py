"""Build the print editions of one or more books into one folder.

Usage:
    picturebook print BOOK [BOOK ...] [--out DIR] [--only VARIANT]

`--only draw-in` builds just the draw-in editions, which need no art, so a new
book can print before it has any. Each book gets its own folder in print/ (or
DIR), and print/README.txt says what each file is and how to print it. The
files are rebuilt every run, so a later art fix is one command.

Every edition carries the cast page after the cover, if the book has cast
crops in cast-sheets.json. A book gets the colour editions only when every
page has colour art newer than its line art, so a stale colour page never
reaches the printer.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import pdf as generate_pdf
from .bookdata import images_dir, load_book

# (file suffix, size, variant, booklet, colour, what it is)
EDITIONS = [
    ("draw-in-booklet", "half-letter", "draw-in", True, False,
     "Words with empty boxes to draw in. Folds into a half-letter booklet."),
    ("draw-in-letter", "letter", "draw-in", False, False,
     "Words with empty boxes to draw in. One page per letter sheet, bigger boxes."),
    ("coloring-booklet", "half-letter", "full", True, False,
     "The line art and the words, to colour in. Folds into a half-letter booklet."),
    ("coloring-letter", "letter", "full", False, False,
     "The line art and the words, to colour in. One page per letter sheet."),
    ("write-in-letter", "letter", "write-in", False, False,
     "The line art with handwriting lines and 田字格 squares for the words."),
    ("color-booklet", "half-letter", "full", True, True,
     "The finished book in colour. Folds into a half-letter booklet."),
    ("color-letter", "letter", "full", False, True,
     "The finished book in colour. One page per letter sheet."),
]

README = """\
Print editions, built by `picturebook print`.

Each book has five black-and-white files, and two colour ones once its colour
art is finished. Every file starts with the cover, and then a page of the
characters ("Who is in this book?") if the book has one.

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


def color_is_current(project: Path) -> bool:
    """True if every page has colour art, and none is older than its line art.

    The pages are the ones book-data.json lists, cover included. A page with
    no line art yet cannot have current colour art either.
    """
    data = load_book(project)
    names = [entry["image"] for entry in [data.get("cover") or {}, *data.get("pages", [])]
             if entry.get("image")]
    for name in names:
        line, color = images_dir(project) / name, images_dir(project, color=True) / name
        if not (line.exists() and color.exists()):
            return False
        if color.stat().st_mtime < line.stat().st_mtime:
            return False
    return True


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="picturebook print",
                                 description="Build every print edition into one folder.")
    ap.add_argument("books", nargs="+", type=Path, help="book folders")
    ap.add_argument("--out", type=Path, default=Path("print"),
                    help="output folder (default: print/ in the current folder)")
    ap.add_argument("--only", choices=sorted({e[2] for e in EDITIONS}),
                    help="build only the editions of this variant")
    args = ap.parse_args(argv)

    for project in (p.expanduser().resolve() for p in args.books):
        load_book(project)  # exits with a clear error if it is not a book
        book = project.name
        with_color = color_is_current(project) and args.only is None
        if not with_color and args.only is None:
            print(f"  {book}: colour art is not finished, so no colour editions")
        for suffix, size, variant, booklet, color, _ in EDITIONS:
            if args.only and variant != args.only:
                continue
            out = args.out / book / f"{book}-{suffix}.pdf"
            if color and not with_color:
                out.unlink(missing_ok=True)  # an older colour file would be stale
                continue
            # Colour art embeds as JPEG; as PNG one book is about 37 MB.
            generate_pdf.build(project, out, cover=True, draft=False, size=size,
                               profile="activity", variant=variant, color=color,
                               web=color, cast_page=bool(generate_pdf.cast_sheet(project)),
                               booklet=booklet)
            print(f"  wrote {out.relative_to(args.out)}")

    lines = "\n".join(f"  *-{suffix + '.pdf':<22}{about}" for suffix, *_, about in EDITIONS)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "README.txt").write_text(README.format(editions=lines), encoding="utf-8")
    print(f"  wrote README.txt in {args.out}")

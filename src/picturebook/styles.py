"""Try several art styles on a few pages of one book, side by side.

Usage:
    picturebook styles BOOK [--model flux-1.1-pro] [--pages 1,3,9]
                     [--seeds 1234,1235] [--styles house,cartoon] [--delay 11]
                     [--dry-run]

Each style block below goes on the front of each page's colour `prompt`. Every
style uses the same pinned seeds, so a difference between rows comes from the
style and not from luck. The images go to `images/_styles/`, named
`<style>-page-NN-sSEED.png`, and `index.html` there shows one row per style
and one column per page and seed. A file that already exists is not sent
again, so an interrupted run is free to resume.

The "house" style is the book's own colour block: `style_blocks.color` in
book-data.json, else the one in characters.json. Without `--pages`, it tries
pages 1, 3 and 9, leaving out any the book does not have.

To use a winner, copy its block into the book's `style_blocks.color`.

"""

from __future__ import annotations

import argparse
import html
import time
from pathlib import Path

from .backends import Job, PredictionFailed, ReplicateBackend
from .bookdata import load_book
from .generate import aspect_ratio, parse_pages, style_block

# Described, not named after an artist or a film, so the look comes from the
# words and nothing is borrowed by name.
STYLES = {
    "house": None,  # the book's own colour block from characters.json
    "watercolour": (
        "Children's picture book illustration in loose, scratchy pen and ink "
        "with splashy watercolour washes. Energetic wobbly lines, lots of white "
        "paper showing, comic and lively."
    ),
    "cartoon": (
        "Bold flat cartoon illustration with thick clean black outlines and "
        "flat bright saturated colours, no texture. Simple shapes and big "
        "expressive faces, like a Saturday-morning animated TV show."
    ),
    "gouache": (
        "Mid-century children's book illustration in gouache. A limited "
        "palette of five colours, visible brush texture, simple stylised "
        "shapes, a 1950s storybook look."
    ),
    "poster": (
        "1980s painted movie poster illustration, airbrushed. Dramatic rim "
        "lighting, glowing highlights, rich saturated colours. Cinematic and "
        "heroic, but playful."
    ),
    "storybook": (
        "Richly painted fantasy storybook illustration. Warm candlelight and "
        "deep shadows, detailed castle interiors, soft oil paint texture. Cosy "
        "and magical."
    ),
    # The four below look drawn by, or for, a child. They are easy to copy in
    # the draw-in edition.
    "kid-pencil": (
        "A drawing made by a seven-year-old child with coloured pencils on "
        "white paper. Wobbly uneven outlines, round heads, thin arms and legs, "
        "scribbly colouring that goes outside the lines, flat with no "
        "perspective, lots of white paper showing."
    ),
    "stick": (
        "A simple stick figure drawing in black felt-tip pen on white paper, "
        "with a few bright coloured pencil accents. Round heads, dot eyes, "
        "single-line bodies, arms and legs, big simple props. Funny and "
        "minimal, easy for a child to copy."
    ),
    "crayon": (
        "A child's wax crayon drawing on paper. Thick waxy strokes, bright "
        "colours, naive simple shapes, uneven colouring with paper texture "
        "showing through."
    ),
    "doodle": (
        "A simple, naive picture book drawing with wobbly felt-tip outlines and "
        "flat coloured pencil fill. Chunky simple characters with dot eyes and "
        "a minimal background, drawn so a child could copy it."
    ),
}


DEFAULT_PAGES = "1,3,9"


def choose_pages(data: dict, value: str) -> set[str]:
    """The pages to try. The default skips pages the book lacks; a named page must exist."""
    have = {str(page.get("n")) for page in data.get("pages", [])} | {"cover"}
    if not value:
        return {p.zfill(2) for p in parse_pages(DEFAULT_PAGES) if p in have}
    wanted = parse_pages(value)
    unknown = sorted(p for p in wanted if p.lstrip("0") not in have)
    if unknown:
        raise SystemExit(f"error: the book has no page {', '.join(unknown)}")
    return {p.zfill(2) if p.isdigit() else p for p in wanted}


def page_entries(data: dict, pages: set[str]) -> list[tuple[str, dict]]:
    out = []
    for entry in data.get("pages", []):
        key = f"{int(entry['n']):02d}"
        if key in pages and entry.get("prompt"):
            out.append((key, entry))
    if "cover" in pages and (data.get("cover") or {}).get("prompt"):
        out.append(("cover", data["cover"]))
    return out


def write_index(out_dir: Path, styles: list[str], cells: list[tuple[str, int]],
                model: str) -> Path:
    head = "".join(f"<th>{'cover' if p == 'cover' else 'page ' + p.lstrip('0')}"
                   f"<br><small>seed {s}</small></th>" for p, s in cells)
    rows = []
    for style in styles:
        tds = []
        for page, seed in cells:
            name = f"{style}-page-{page}-s{seed}.png"
            if (out_dir / name).exists():
                tds.append(f"<td><a href='{name}'><img src='{name}'></a></td>")
            else:
                tds.append("<td class='gap'>missing</td>")
        rows.append(f"<tr><th>{html.escape(style)}</th>{''.join(tds)}</tr>")
    page = f"""<!doctype html><meta charset="utf-8"><title>Style test</title>
<style>
body {{ font-family: -apple-system, sans-serif; margin: 1rem; }}
table {{ border-collapse: collapse; }}
th, td {{ padding: 4px; vertical-align: middle; }}
img {{ width: 240px; display: block; }}
.gap {{ width: 240px; height: 240px; background: #eee; text-align: center; color: #888; }}
</style>
<h1>Style test — {html.escape(model)}</h1>
<table><tr><th></th>{head}</tr>{''.join(rows)}</table>
"""
    index = out_dir / "index.html"
    index.write_text(page, encoding="utf-8")
    return index


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("project", type=Path)
    ap.add_argument("--model", default="flux-1.1-pro")
    ap.add_argument("--pages", default="",
                    help=f"page numbers, or cover (default: {DEFAULT_PAGES}, "
                         "leaving out any the book lacks)")
    ap.add_argument("--seeds", default="1234,1235")
    ap.add_argument("--styles", default=",".join(STYLES),
                    help=f"comma-separated, from: {', '.join(STYLES)}")
    ap.add_argument("--delay", type=float, default=11,
                    help="seconds between predictions (Replicate allows 6 a minute under $5 credit)")
    ap.add_argument("--dry-run", action="store_true", help="print the prompts and send nothing")
    args = ap.parse_args(argv)

    styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    unknown = [s for s in styles if s not in STYLES]
    if unknown:
        raise SystemExit(f"error: unknown style(s) {unknown}. Known: {', '.join(STYLES)}")
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]

    data = load_book(args.project)
    house = style_block(data, "color")  # the book's own block, else characters.json's
    pages = choose_pages(data, args.pages)
    entries = page_entries(data, pages)
    if not entries:
        raise SystemExit("error: none of those pages has a colour prompt")
    aspect = aspect_ratio(data.get("page", {}))
    out_dir = args.project / "images" / "_styles"
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = []
    for style in styles:
        block = STYLES[style] or house
        for page, entry in entries:
            for seed in seeds:
                name = f"{style}-page-{page}-s{seed}.png"
                text = f"{block} {entry['prompt'].strip()}"
                todo.append((name, seed, Job(page=page, image=name, text=text, aspect=aspect)))

    print(f"\n=== {args.project.name} — {len(styles)} style(s) x {len(entries)} page(s) "
          f"x {len(seeds)} seed(s), {args.model} ===")
    sent = failed = skipped = 0
    for name, seed, job in todo:
        target = out_dir / name
        if target.exists():
            skipped += 1
            continue
        if args.dry_run:
            print(f"\n  {name}\n    {job.text}")
            continue
        if sent or failed:
            time.sleep(args.delay)
        backend = ReplicateBackend(model=args.model, variants=1, seed=seed)
        try:
            result = backend.submit(job, out_dir)
        except PredictionFailed as err:
            print(f"  {name:40} failed: {err}")
            failed += 1
            continue
        if not result.files:
            print(f"  {name:40} {result.note}")
            failed += 1
            continue
        result.files[0].rename(target)  # submit names it name.1.png
        for extra in result.files[1:]:
            extra.unlink()
        print(f"  {name:40} done")
        sent += 1

    if args.dry_run:
        print(f"\n  dry run — {len(todo) - skipped} to send, nothing written")
        return
    cells = [(page, seed) for page, _ in entries for seed in seeds]
    index = write_index(out_dir, styles, cells, args.model)
    print(f"  {sent} sent, {failed} failed, {skipped} already there")
    print(f"\n  compare: open {index}")

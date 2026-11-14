"""Write placeholder PNGs into a project's images/ folder, in the book's art shape.

Usage:
    picturebook placeholders [project-dir]

This is a proofing aid, not part of the book. It lets you check the page
layout and the text wrapping before the real art exists. Each file is named to
match book-data.json, so downloading the real image over it needs no other
change.

It never overwrites a file that is already there, so it is safe to run on a
book that has some real art. Pass `--force` to replace the existing files. They
move to `images/_replaced/` first.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .bookdata import back_up, load_book
from .importer import target_size

# The label font. The first one found wins; Pillow's own font is the fallback.
FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
PALETTE = [
    "#dfe7e3", "#e6e2d6", "#dde3ec", "#e9e0dc", "#dae5df", "#e7e6dc",
    "#dce4ea", "#e4dfe8", "#dfe6e0", "#eae3d8", "#dee6ea",
]


def font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def render(path: Path, label: str, caption: str, color: str, force: bool,
           size: tuple[int, int] = (1200, 1600)) -> None:
    if path.exists():
        if not force:
            print(f"   {path.name} exists, kept")
            return
        back_up(path)
    width, height = size
    scale = width / 1200
    img = Image.new("RGB", (width, height), color)
    d = ImageDraw.Draw(img)
    d.rectangle([24, 24, width - 24, height - 24], outline="#ffffff", width=6)
    d.text((width // 2, height // 2 - round(50 * scale)), label,
           font=font(round(64 * scale)), fill="#6d7683", anchor="mm")
    d.text((width // 2, height // 2 + round(40 * scale)), caption,
           font=font(round(34 * scale)), fill="#8d95a0", anchor="mm")
    d.text((width // 2, height - round(90 * scale)), "PLACEHOLDER — replace with final art",
           font=font(round(26 * scale)), fill="#a0a7b0", anchor="mm")
    img.save(path)
    print(f"   {path.name}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Write placeholder images for a book project.")
    ap.add_argument("project", nargs="?", default=".", type=Path)
    ap.add_argument("--force", action="store_true",
                    help="replace existing images, keeping them in images/_replaced/")
    args = ap.parse_args(argv)

    project = args.project.expanduser().resolve()
    data = load_book(project)

    images = project / "images"
    images.mkdir(parents=True, exist_ok=True)
    size = target_size(data.get("page", {}))

    cover = (data.get("cover") or {}).get("image")
    if cover:
        render(images / cover, "Cover", data.get("title", {}).get("en", ""), PALETTE[0],
               args.force, size)
    for i, page in enumerate(data.get("pages", [])):
        if page.get("image"):
            render(images / page["image"], f"Page {page['n']}",
                   (page.get("en") or "")[:44], PALETTE[(i + 1) % len(PALETTE)], args.force, size)

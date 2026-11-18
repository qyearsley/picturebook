"""Build a portrait PDF from a book project's book-data.json and images.

Usage:
    picturebook pdf [project-dir] [--out FILE] [--no-cover] [--draft]
                    [--size NAME] [--profile NAME] [--variant NAME] [--color]
                    [--web] [--cast-page] [--booklet]

The project directory must contain book-data.json, an images/ folder and a
build/ folder. If a page image is missing, the script draws a labelled
placeholder box so you can proof the text layout before the art arrives.

English text wraps on word boundaries. Chinese text wraps on characters and
respects the basic line-break rules for CJK punctuation. If a text block is
too tall for its area, the script shrinks the type until it fits.

Every Han character has its pinyin above it, in the style of <ruby> text. The
pinyin comes from pinyin.py, the same code as the HTML reader. Each
character gets a column as wide as its pinyin, so the Chinese is spaced out.

`--size`, `--profile` and `--variant` are render-time overrides. They change
the PDF and never touch book-data.json, so one book can print as a 6 x 9
picture book and as a letter-paper worksheet without keeping two copies of the
text.

`--color` takes the art from `images/color/` instead of the line art in
`images/`, and adds `-color` to the file name. A page not yet coloured is
drawn as a placeholder, so the gaps show.

`--web` embeds each image as a JPEG instead of a PNG, and adds `-web` to the
file name. A colour book drops from about 37 MB to a size a website can serve.

`--cast-page` adds a page after the cover that shows the book's characters,
cropped from art the book already has: the line art, or the colour art for a
page with no line art. `cast-sheets.json` lists the crops. It gives a child something to copy from in the draw-in edition.

`--booklet` lays the half-letter pages out two to a landscape letter sheet, in
the order that folds into a stapled booklet. Print it double-sided, flipped on
the short edge, then fold the stack in half. It implies `--size half-letter`.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from .bookdata import (
    CHARACTERS_KEY,
    HAN_RANGES,
    WEB_JPEG_QUALITY,
    images_dir,
    load_book,
    require_valid,
    shared_file,
    with_defaults,
)
from .pinyin import cells as pinyin_cells

CAST_SHEETS = "cast-sheets.json"

# Built-in PDF fonts need no file and always load.
BUILTIN_FONTS = {
    "Helvetica", "Helvetica-Bold", "Helvetica-Oblique",
    "Times-Roman", "Times-Bold", "Times-Italic", "Courier",
}

# ReportLab's built-in Chinese font. It needs no font file, so it works on any
# system, but the PDF reader supplies the glyphs, and they look plainer than a
# real font. It is the last resort for Chinese text.
CID_FONTS = {"STSong-Light"}

# Characters that must not start a line.
NO_LINE_START = set("。，、；：！？）〕］｝」』”’》〉…—·%")
# Characters that must not end a line.
NO_LINE_END = set("（〔［｛「『“‘《〈")

# The pinyin font needs the tone marks ā á ǎ à. Georgia and Arial have them.
DEFAULT_PINYIN_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
]
# Pinyin is this fraction of the Chinese type size.
PINYIN_RATIO = 0.5
# Extra space around each character, as a fraction of the Chinese type size.
CELL_PAD = 0.16

# Text with any of these in it wraps by character, not by word.
CJK_RANGES = HAN_RANGES + (
    (0x3000, 0x303F),   # CJK punctuation
    (0xFF00, 0xFFEF),   # fullwidth forms
)

# --------------------------------------------------------------------------
# Render presets
# --------------------------------------------------------------------------

# A trim size and the layout fields that depend on it, kept together on
# purpose: if you change only the page size, the PDF still builds and the type
# silently shrinks to fit the narrower column.
#
# `en` and `zh` are type sizes. Leading is derived from them at the ratios the
# books already use, 1.34 for English and 1.6 for Chinese.
SIZES = {
    "8x10.67":     {"w": 8.0,  "h": 10.6667, "margin": 0.55, "padding": 0.34,
                    "band": 0.30, "en": 18, "zh": 20},
    "letter":      {"w": 8.5,  "h": 11.0,    "margin": 0.50, "padding": 0.34,
                    "band": 0.30, "en": 18, "zh": 20},
    "a4":          {"w": 8.27, "h": 11.69,   "margin": 0.50, "padding": 0.33,
                    "band": 0.30, "en": 18, "zh": 20},
    "half-letter": {"w": 5.5,  "h": 8.5,     "margin": 0.40, "padding": 0.24,
                    "band": 0.36, "en": 14, "zh": 15},
    "6x9":         {"w": 6.0,  "h": 9.0,     "margin": 0.45, "padding": 0.26,
                    "band": 0.36, "en": 16, "zh": 17},
    "8x10":        {"w": 8.0,  "h": 10.0,    "margin": 0.55, "padding": 0.34,
                    "band": 0.32, "en": 18, "zh": 20},
    "7x7":         {"w": 7.0,  "h": 7.0,     "margin": 0.50, "padding": 0.30,
                    "band": 0.38, "en": 16, "zh": 17},
}

# What kind of object the page is. A picture book is read; a worksheet is
# printed at home and worked on with a pencil, so it wants ink-light margins
# and square art that prints the same on any paper size.
PROFILES = {
    "picturebook": {
        "text_placement": "overlay",
        "image_fit": "cover",
        "image_square": False,
    },
    "activity": {
        "text_placement": "below",
        "image_fit": "contain",
        "image_square": True,
        "image_height_frac": 0.68,
        "background": "#ffffff",
    },
}

# Which half of the page is left for the child to fill in.
#
#   full      the reference copy: the art and both languages
#   write-in  the art, with writing guides where the words belong
#   draw-in   the words, with an empty box where the art belongs
#
# `image_height_frac` overrides the layout's own value, because writing guides
# need more room than printed type does.
VARIANTS = {
    "full":     {"art": "image", "text": "print"},
    "write-in": {"art": "image", "text": "guides", "image_height_frac": 0.62},
    "draw-in":  {"art": "box",   "text": "print"},
}


def is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in CJK_RANGES)


def has_cjk(text: str) -> bool:
    return any(is_cjk(c) for c in text)


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------

def resolve_font(alias: str, candidates: list[str], fallback: str = "Helvetica") -> str:
    """Register the first candidate that loads and return its PDF font name.

    A candidate is a built-in font name, "STSong-Light", a path to a .ttf, or a
    path to a .ttc collection written as "path:index".
    """
    for spec in [*candidates, fallback]:
        if spec in BUILTIN_FONTS:
            if spec == fallback and spec not in candidates:
                print(f"  warning: no font loaded for '{alias}', falling back to {spec}",
                      file=sys.stderr)
            return spec
        if spec in CID_FONTS:
            pdfmetrics.registerFont(UnicodeCIDFont(spec))
            return spec
        path, _, index = spec.rpartition(":")
        if path and index.isdigit():
            font_path, subfont = Path(path), int(index)
        else:
            font_path, subfont = Path(spec), 0
        if not font_path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(alias, str(font_path), subfontIndex=subfont))
            return alias
        except Exception as exc:  # noqa: BLE001 - any font error means "try the next one"
            print(f"  note: could not load {spec} ({exc})", file=sys.stderr)
    return "Helvetica"


# --------------------------------------------------------------------------
# Line breaking
# --------------------------------------------------------------------------

def _greedy_latin(words: list[str], font: str, size: float, max_width: float) -> list[str]:
    """Fill each line as far as it goes. Break inside a word only if it cannot fit."""
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(trial, font, size) <= max_width:
            current = trial
            continue
        if current:
            lines.append(current)
        # The word alone may still be too wide; chop it.
        while pdfmetrics.stringWidth(word, font, size) > max_width and len(word) > 1:
            cut = len(word)
            while cut > 1 and pdfmetrics.stringWidth(word[:cut], font, size) > max_width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines


def wrap_latin(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Wrap on word boundaries, then balance the lines of each paragraph.

    A paragraph that wraps keeps its line count, but its lines are narrowed
    until they are about equal. That stops a verse line leaving one word
    alone on the second line ("mud,").
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        wrapped = _greedy_latin(words, font, size, max_width)
        if len(wrapped) > 1:
            low = max(pdfmetrics.stringWidth(w, font, size) for w in words)
            high = max_width
            for _ in range(24):
                mid = (low + high) / 2
                if len(_greedy_latin(words, font, size, mid)) <= len(wrapped):
                    high = mid
                else:
                    low = mid
            wrapped = _greedy_latin(words, font, size, high)
        lines.extend(wrapped)
    return lines


def break_cjk(paragraph, ch_of, fits) -> list[list]:
    """Break one paragraph of items into lines, honouring CJK punctuation rules.

    `ch_of(item)` gives the character an item stands for. `fits(items)` says
    whether a run of items is narrow enough for a line.
    """
    lines: list[list] = []
    current: list = []
    for item in paragraph:
        ch = ch_of(item)
        trial = current + [item]
        if fits(trial):
            current = trial
            continue
        if ch in NO_LINE_START:
            # Let the line run slightly long rather than orphan the mark.
            lines.append(trial)
            current = []
            continue
        if current and ch_of(current[-1]) in NO_LINE_END:
            # Carry the opening mark down to the next line.
            lines.append(current[:-1])
            current = [current[-1], item]
            continue
        lines.append(current)
        current = [item]
    if current:
        lines.append(current)
    return lines


def wrap_cjk(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Wrap character by character, honouring CJK line-break punctuation rules."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        broken = break_cjk(
            paragraph, lambda ch: ch,
            lambda run: pdfmetrics.stringWidth("".join(run), font, size) <= max_width)
        lines.extend("".join(line) for line in broken)
    return lines


def wrap(text: str, font: str, size: float, max_width: float) -> list[str]:
    return wrap_cjk(text, font, size, max_width) if has_cjk(text) else wrap_latin(text, font, size, max_width)


def fit_block(text, font, size, leading, max_width, max_height, min_scale=0.6):
    """Shrink the type until the wrapped block fits max_height.

    Returns (lines, size, leading).
    """
    scale = 1.0
    while True:
        s, lead = size * scale, leading * scale
        lines = wrap(text, font, s, max_width)
        if len(lines) * lead <= max_height or scale <= min_scale:
            return lines, s, lead
        scale -= 0.04


# --------------------------------------------------------------------------
# Chinese with pinyin
# --------------------------------------------------------------------------

def py_size_of(size: float) -> float:
    return size * PINYIN_RATIO


def cell_width(cell, fonts, size: float) -> float:
    """The width of one (character, pinyin) column.

    A Han character is as wide as its pinyin or itself, whichever is wider,
    plus a little air. Punctuation keeps its own width.
    """
    ch, py = cell
    width = pdfmetrics.stringWidth(ch, fonts["zh"], size)
    if not py:
        return width
    py_w = pdfmetrics.stringWidth(py, fonts["py"], py_size_of(size))
    return max(width, py_w) + size * CELL_PAD


def wrap_ruby(text: str, fonts, overrides, size: float, max_width: float) -> list[list]:
    """Wrap Chinese text into lines of (character, pinyin) cells."""
    lines: list[list] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append([])
            continue
        run = pinyin_cells(paragraph, overrides)
        lines.extend(break_cjk(
            run, lambda cell: cell[0],
            lambda items: sum(cell_width(c, fonts, size) for c in items) <= max_width))
    return lines


def ruby_pitch(size: float, leading: float) -> float:
    """The height of one line of ruby: the usual leading plus the pinyin row."""
    return leading + py_size_of(size) * 0.9


def fit_ruby(text, fonts, overrides, size, leading, max_width, max_height, min_scale=0.6):
    """Shrink the type until the ruby block fits max_height.

    Returns (lines, size, pitch).
    """
    scale = 1.0
    while True:
        s, lead = size * scale, leading * scale
        lines = wrap_ruby(text, fonts, overrides, s, max_width)
        pitch = ruby_pitch(s, lead)
        if len(lines) * pitch <= max_height or scale <= min_scale:
            return lines, s, pitch
        scale -= 0.04


def draw_ruby_lines(c, lines, fonts, size, pitch, color, box, align="center"):
    """Draw ruby lines top-down inside box = (x, y, width, height)."""
    x, y, width, height = box
    py_size = py_size_of(size)
    c.setFillColor(HexColor(color))
    top = y + height
    for line in lines:
        widths = [cell_width(cell, fonts, size) for cell in line]
        total = sum(widths)
        if align == "center":
            cx = x + (width - total) / 2
        elif align == "right":
            cx = x + width - total
        else:
            cx = x
        py_base = top - py_size
        ch_base = top - py_size * 1.1 - size * 0.88
        for (ch, py), cw in zip(line, widths):
            if py:
                c.setFont(fonts["py"], py_size)
                c.drawCentredString(cx + cw / 2, py_base, py)
            c.setFont(fonts["zh"], size)
            c.drawCentredString(cx + cw / 2, ch_base, ch)
            cx += cw
        top -= pitch


def draw_ruby_line(c, text, fonts, overrides, size, color, cx, top, width):
    """Draw one centred line of ruby with its top edge at `top`. Return its height."""
    lines = wrap_ruby(text, fonts, overrides, size, width)
    pitch = ruby_pitch(size, size * 1.2)
    draw_ruby_lines(c, lines, fonts, size, pitch, color,
                    (cx - width / 2, top - pitch * len(lines), width, pitch * len(lines)))
    return pitch * len(lines)


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------

def draw_lines(c, lines, font, size, leading, color, box, align="center"):
    """Draw wrapped lines top-down inside box = (x, y, width, height)."""
    x, y, width, height = box
    c.setFont(font, size)
    c.setFillColor(HexColor(color))
    baseline = y + height - size
    for line in lines:
        if align == "center":
            c.drawCentredString(x + width / 2, baseline, line)
        elif align == "right":
            c.drawRightString(x + width, baseline, line)
        else:
            c.drawString(x, baseline, line)
        baseline -= leading


# --------------------------------------------------------------------------
# Fill-in guides
#
# These draw the space where the words go instead of the words themselves.
# English gets primary handwriting rules: a top line, a dashed midline for
# x-height, and a baseline. Chinese gets 田字格 practice squares, one square
# per character, which is how children are taught to write characters.
# --------------------------------------------------------------------------

GUIDE_SOLID = "#b9b3a6"
GUIDE_DASH = "#dcd7cb"

# The share of a rule's height that is the writing zone. The rest is the gap
# below it, which holds the descenders and keeps two rules from reading as one
# block of four lines.
EN_ZONE = 0.60


def draw_en_rules(c, count, box, rule_h) -> None:
    """Draw `count` primary handwriting rules, top-down inside box.

    Each rule occupies rule_h: a baseline, a top line at EN_ZONE above it, and
    a dashed midline halfway between for the x-height.
    """
    x, y, width, height = box
    c.saveState()
    c.setLineWidth(0.7)
    top = y + height
    for i in range(count):
        base = top - (i + 1) * rule_h
        c.setStrokeColor(HexColor(GUIDE_SOLID))
        c.setDash()
        c.line(x, base, x + width, base)
        c.line(x, base + rule_h * EN_ZONE, x + width, base + rule_h * EN_ZONE)
        c.setStrokeColor(HexColor(GUIDE_DASH))
        c.setDash(2, 3)
        c.line(x, base + rule_h * EN_ZONE / 2, x + width, base + rule_h * EN_ZONE / 2)
    c.restoreState()


def zh_rows(text: str, width: float, cell_in: float,
            min_cell_in: float = 0.40) -> tuple[list[int], float]:
    """Split Chinese text into rows of practice squares.

    Returns (rows, cell). `rows` holds the number of squares in each row and
    `cell` is the square's side in points.

    One verse line is one row, because the line is the unit a child copies.
    The square shrinks to keep a long line whole, down to min_cell_in — about
    10 mm, which is still comfortable for a five-year-old. A line too long
    even for that wraps into evenly sized rows, so a 16-character line reads
    as 8 and 8 rather than as a full row and an orphaned 4.
    """
    lines = [[ch for ch in p if not ch.isspace()] for p in text.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return [], cell_in * inch

    longest = max(len(line) for line in lines)
    cell = min(cell_in * inch, width / longest)
    if cell < min_cell_in * inch:
        cell = min(cell_in * inch, width)  # keep the comfortable size and wrap

    per_row = max(int(width // cell), 1)
    rows: list[int] = []
    for chars in lines:
        count = len(chars)
        n_rows = -(-count // per_row)  # ceiling division
        base, extra = divmod(count, n_rows)
        rows.extend(base + 1 if i < extra else base for i in range(n_rows))
    return rows, cell


def zh_row_pinyin(text: str, rows: list[int], overrides) -> list[list[str]]:
    """Split the pinyin of `text` into the same rows as its squares."""
    flat = [py for ch, py in pinyin_cells(text, overrides) if not ch.isspace()]
    out, at = [], 0
    for count in rows:
        out.append(flat[at:at + count])
        at += count
    return out


def zh_pinyin_h(cell: float) -> float:
    """The height of the pinyin row above a row of squares."""
    return cell * 0.26


def draw_zh_boxes(c, rows: list[int], box, cell: float, row_gap: float,
                  pinyin_rows=None, py_font=None) -> None:
    """Draw rows of 田字格 squares, top-down inside box, each row centred.

    With `pinyin_rows`, each square has its pinyin above it.
    """
    x, y, width, height = box
    c.saveState()
    c.setLineWidth(0.7)
    top = y + height
    py_h = zh_pinyin_h(cell) if pinyin_rows else 0.0
    for i, count in enumerate(rows):
        row_y = top - (i + 1) * (cell + py_h) - i * row_gap
        start = x + max((width - cell * count) / 2, 0)
        if pinyin_rows:
            c.setFillColor(HexColor("#3c4450"))
            c.setFont(py_font, cell * 0.21)
            for j, py in enumerate(pinyin_rows[i]):
                if py:
                    c.drawCentredString(start + (j + 0.5) * cell, row_y + cell + py_h * 0.22, py)
        for j in range(count):
            cx = start + j * cell
            c.setStrokeColor(HexColor(GUIDE_SOLID))
            c.setDash()
            c.rect(cx, row_y, cell, cell, stroke=1, fill=0)
            c.setStrokeColor(HexColor(GUIDE_DASH))
            c.setDash(2, 3)
            c.line(cx, row_y + cell / 2, cx + cell, row_y + cell / 2)
            c.line(cx + cell / 2, row_y, cx + cell / 2, row_y + cell)
    c.restoreState()


def draw_empty_box(c, box) -> None:
    """Draw the frame the child draws inside, where the art would have been."""
    x, y, width, height = box
    c.saveState()
    c.setStrokeColor(HexColor(GUIDE_SOLID))
    c.setLineWidth(1.0)
    c.setDash()
    c.roundRect(x, y, width, height, 10, stroke=1, fill=0)
    c.restoreState()


def draw_image(c, image_path: Path, box, label: str, fit: str = "contain",
               jpeg_quality: int | None = None) -> None:
    """Draw the image inside box, centred. Placeholder if the file is missing.

    fit="contain" fits the whole image and leaves margins.
    fit="cover" fills the box and crops the overflow.
    """
    x, y, width, height = box
    if not image_path.exists():
        c.saveState()
        c.setStrokeColor(HexColor("#c9c4b8"))
        c.setFillColor(HexColor("#f1efe8"))
        c.setDash(6, 4)
        c.setLineWidth(1)
        c.roundRect(x, y, width, height, 8, stroke=1, fill=1)
        c.setDash()
        c.setFillColor(HexColor("#8b8578"))
        c.setFont("Helvetica", 11)
        c.drawCentredString(x + width / 2, y + height / 2 + 6, "missing image")
        c.drawCentredString(x + width / 2, y + height / 2 - 10, label)
        c.restoreState()
        return

    if jpeg_quality:
        # reportlab embeds a JPEG as it is, so this sets the PDF's image size.
        buf = io.BytesIO()
        with Image.open(image_path) as img:
            img.convert("RGB").save(buf, "JPEG", quality=jpeg_quality, optimize=True)
        buf.seek(0)
        reader = ImageReader(buf)
    else:
        reader = ImageReader(str(image_path))
    img_w, img_h = reader.getSize()
    ratio = max if fit == "cover" else min
    scale = ratio(width / img_w, height / img_h)
    draw_w, draw_h = img_w * scale, img_h * scale

    c.saveState()
    if fit == "cover":
        clip = c.beginPath()
        clip.rect(x, y, width, height)
        c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(
        reader,
        x + (width - draw_w) / 2,
        y + (height - draw_h) / 2,
        width=draw_w,
        height=draw_h,
        mask="auto",
    )
    c.restoreState()


def draw_cover(c, data, fonts, images_dir, page_w, page_h, margin, variant=None):
    variant = variant or VARIANTS["full"]
    layout = data["layout"]
    c.setFillColor(HexColor(layout.get("background", "#ffffff")))
    c.rect(0, 0, page_w, page_h, stroke=0, fill=1)

    cover_image = (data.get("cover") or {}).get("image")
    text_top = page_h - margin
    # The cover keeps its title in every variant, so the child can tell which
    # book the worksheet belongs to. Only the art is taken away.
    if cover_image or variant.get("art") == "box":
        img_h = page_h * 0.55
        img_y = page_h - margin - img_h
        img_box = (margin, img_y, page_w - 2 * margin, img_h)
        if variant.get("art") == "box":
            draw_empty_box(c, img_box)
        else:
            draw_image(c, images_dir / cover_image, img_box,
                       cover_image, layout.get("image_fit", "contain"),
                       layout.get("jpeg_quality"))
        text_top = img_y - 0.45 * inch

    content_w = page_w - 2 * margin
    title = data.get("title", {})

    en_lines, en_size, en_leading = fit_block(
        title.get("en", ""), fonts["en"], layout["en"]["size"] * 2.0,
        layout["en"]["leading"] * 2.0, content_w, 2.0 * inch,
    )
    draw_lines(c, en_lines, fonts["en"], en_size, en_leading,
               layout["en"]["color"], (margin, text_top - 2.0 * inch, content_w, 2.0 * inch))

    zh_top = text_top - en_size - (len(en_lines) - 1) * en_leading - 0.35 * inch
    zh_lines, zh_size, zh_pitch = fit_ruby(
        title.get("zh", ""), fonts, data.get("pinyin_overrides"), layout["zh"]["size"] * 1.9,
        layout["zh"]["leading"] * 1.9, content_w, 2.0 * inch,
    )
    draw_ruby_lines(c, zh_lines, fonts, zh_size, zh_pitch,
                    layout["zh"]["color"], (margin, zh_top - 2.0 * inch, content_w, 2.0 * inch))

    author = data.get("author")
    if author:
        c.setFont(fonts["en"], layout["en"]["size"] * 0.85)
        c.setFillColor(HexColor(layout["en"]["color"]))
        c.drawCentredString(page_w / 2, margin + 0.3 * inch, author)
    c.showPage()


def draw_page(c, page, data, fonts, images_dir, page_w, page_h, margin, draft,
              variant=None):
    variant = variant or VARIANTS["full"]
    layout = data["layout"]
    gutter = layout.get("gutter_in", 0.3) * inch
    image_fit = layout.get("image_fit", "contain")
    content_w = page_w - 2 * margin
    content_h = page_h - 2 * margin

    guides = variant.get("text") == "guides"
    empty_art = variant.get("art") == "box"
    # Writing guides under a band of text over full-bleed art are unreadable,
    # and an empty drawing box behind that band is not a page. Either one puts
    # the text below the art, whatever the book normally does.
    placement = "below" if (guides or empty_art) else layout.get("text_placement", "below")

    c.setFillColor(HexColor(layout.get("background", "#ffffff")))
    c.rect(0, 0, page_w, page_h, stroke=0, fill=1)

    image_name = page.get("image") or ""
    overlay = placement == "overlay"
    band = layout.get("overlay", {})
    band_pos = page.get("text_position") or band.get("position", "bottom")
    img_frac = variant.get("image_height_frac") or layout.get("image_height_frac", 0.6)
    en_cfg, zh_cfg = layout["en"], layout["zh"]
    en_text, zh_text = page.get("en", ""), page.get("zh", "")
    overrides = data.get("pinyin_overrides")
    gap = 0.18 * inch

    # In write-in mode the guides are the point of the page, so measure them
    # first and let the art take whatever height is left. A page whose verse
    # runs long then gets a smaller picture, rather than guides that run off
    # the bottom of the sheet. A verse of 7+7 characters a line needs this;
    # 5+5 never touches it.
    plan = None
    if guides:
        writing = layout.get("writing", {})
        rule_h = writing.get("en_rule_in", 0.55) * inch
        # Wrap English at the print size. It is a fair guess at how many lines
        # a child needs, and it keeps the guide count honest per page.
        en_lines = wrap(en_text, fonts["en"], en_cfg["size"], content_w) if en_text else []
        rows, cell = zh_rows(zh_text, content_w, writing.get("zh_cell_in", 0.60))
        row_gap = cell * 0.18
        en_h = len(en_lines) * rule_h
        zh_h = len(rows) * (cell + zh_pinyin_h(cell)) + max(len(rows) - 1, 0) * row_gap
        plan = {
            "en_lines": en_lines, "rule_h": rule_h, "en_h": en_h,
            "rows": rows, "cell": cell, "row_gap": row_gap, "zh_h": zh_h,
            "pinyin": zh_row_pinyin(zh_text, rows, overrides),
            "block_h": en_h + zh_h + (gap if en_lines and rows else 0),
        }

    if overlay:
        # Full-bleed art. The text sits in a band over one end of the image.
        if image_name:
            draw_image(c, images_dir / image_name, (0, 0, page_w, page_h), image_name, "cover",
                       layout.get("jpeg_quality"))
        text_h = page_h * band.get("band_height_frac", 0.26) - margin * 0.5
        text_w = content_w
        text_x = margin
        text_top = page_h - margin if band_pos == "top" else text_h + margin * 0.5
    else:
        number_space = 0.28 * inch if layout.get("show_page_numbers", True) else 0.0
        img_h = content_h * img_frac
        if plan:
            room = content_h - plan["block_h"] - gutter - number_space
            # Never shrink the art away entirely; warn instead, below.
            img_h = max(min(img_h, room), content_h * 0.25)
        img_x, img_w = margin, content_w
        if layout.get("image_square"):
            # Square art prints the same on letter, A4 or half-letter, so one
            # generated image serves every paper size.
            side = min(content_w, img_h)
            img_x, img_w, img_h = margin + (content_w - side) / 2, side, side
        img_y = page_h - margin - img_h
        if empty_art:
            draw_empty_box(c, (img_x, img_y, img_w, img_h))
        elif image_name:
            draw_image(c, images_dir / image_name, (img_x, img_y, img_w, img_h),
                       image_name, image_fit, layout.get("jpeg_quality"))
        text_top = img_y - gutter
        text_h = text_top - margin - number_space
        text_w = content_w
        text_x = margin

    if guides:
        cursor = text_top - max((text_h - plan["block_h"]) / 2, 0)
        if plan["en_lines"]:
            draw_en_rules(c, len(plan["en_lines"]),
                          (text_x, cursor - plan["en_h"], text_w, plan["en_h"]),
                          plan["rule_h"])
            cursor -= plan["en_h"] + gap
        if plan["rows"]:
            draw_zh_boxes(c, plan["rows"],
                          (text_x, cursor - plan["zh_h"], text_w, plan["zh_h"]),
                          plan["cell"], plan["row_gap"], plan["pinyin"], fonts["py"])
        if plan["block_h"] > text_h + 0.01:
            print(f"  warning: page {page.get('n', '?')} writing guides need "
                  f"{plan['block_h'] / inch:.2f} in but only {text_h / inch:.2f} in is free",
                  file=sys.stderr)
    else:
        # Give English the space it needs, then let Chinese use the rest.
        en_lines, en_size, en_leading = fit_block(
            en_text, fonts["en"], en_cfg["size"], en_cfg["leading"], text_w, text_h * 0.55,
        ) if en_text else ([], en_cfg["size"], en_cfg["leading"])
        en_h = len(en_lines) * en_leading

        zh_space = text_h - en_h - (gap if en_lines else 0)
        zh_lines, zh_size, zh_pitch = fit_ruby(
            zh_text, fonts, overrides, zh_cfg["size"], zh_cfg["leading"], text_w,
            max(zh_space, ruby_pitch(zh_cfg["size"], zh_cfg["leading"])),
        ) if zh_text else ([], zh_cfg["size"], zh_cfg["leading"])
        zh_h = len(zh_lines) * zh_pitch

        block_h = en_h + zh_h + (gap if en_lines and zh_lines else 0)

        if overlay and block_h:
            pad = band.get("padding_in", 0.32) * inch
            band_h = block_h + 2 * pad
            band_y = page_h - band_h if band_pos == "top" else 0
            c.saveState()
            c.setFillColor(HexColor(band.get("color", "#fdfcf8")))
            c.setFillAlpha(band.get("alpha", 0.9))
            c.rect(0, band_y, page_w, band_h, stroke=0, fill=1)
            c.restoreState()
            cursor = band_y + band_h - pad
        else:
            # Centre the two blocks together in the text area.
            cursor = text_top - max((text_h - block_h) / 2, 0)

        if en_lines:
            draw_lines(c, en_lines, fonts["en"], en_size, en_leading, en_cfg["color"],
                       (text_x, cursor - en_h, text_w, en_h), en_cfg.get("align", "center"))
            cursor -= en_h + gap
        if zh_lines:
            draw_ruby_lines(c, zh_lines, fonts, zh_size, zh_pitch, zh_cfg["color"],
                            (text_x, cursor - zh_h, text_w, zh_h), zh_cfg.get("align", "center"))

    if layout.get("show_page_numbers", True) and not overlay:
        c.setFont(fonts["en"], 9)
        c.setFillColor(HexColor("#9a958a"))
        c.drawCentredString(page_w / 2, margin - 0.04 * inch, str(page.get("n", "")))

    if draft:
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#b9b3a6"))
        c.drawString(margin, page_h - margin + 0.12 * inch, f"DRAFT · {image_name}")

    c.showPage()


def cast_sheet(project: Path) -> list[dict]:
    """The book's entry in cast-sheets.json, or [] if it has none."""
    path = shared_file(project, CAST_SHEETS)
    if not path:
        return []
    return json.loads(path.read_text(encoding="utf-8")).get(project.name) or []


def cast_entries(project: Path, data: dict) -> list[dict]:
    """Return the cast page entries for a book, each with its name filled in."""
    entries = cast_sheet(project)
    if not entries:
        sys.exit(f"error: no {CAST_SHEETS} entry for {project.name}")
    names = {ch["id"]: ch["name"]
             for ch in (data.get(CHARACTERS_KEY) or {}).get("characters", [])}
    seen = set()
    out = []
    for entry in entries:
        # Several drawings of one character share a single label.
        name = None if entry["id"] in seen else entry.get("name") or names.get(entry["id"])
        seen.add(entry["id"])
        out.append({**entry, "name": name})
    return out


def cast_source(project: Path, name: str) -> Path:
    """The image a cast crop is cut from: line art if the page has it, else colour."""
    line = images_dir(project) / name
    return line if line.exists() else images_dir(project, color=True) / name


def draw_cast_page(c, data, fonts, project, page_w, page_h, margin) -> None:
    """Draw the characters in a grid, each above its name in both languages.

    The drawings come from the line art, whatever the edition, because the
    page is there to be copied from. A page with no line art uses its colour
    art.
    """
    layout = data["layout"]
    en_cfg, zh_cfg = layout["en"], layout["zh"]
    c.setFillColor(HexColor(layout.get("background", "#ffffff")))
    c.rect(0, 0, page_w, page_h, stroke=0, fill=1)

    top = page_h - margin
    content_w = page_w - 2 * margin
    overrides = data.get("pinyin_overrides")
    size = en_cfg["size"] * 1.3
    top -= size
    c.setFont(fonts["en"], size)
    c.setFillColor(HexColor(en_cfg["color"]))
    c.drawCentredString(page_w / 2, top, "Who is in this book?")
    top -= size * 0.5
    top -= draw_ruby_line(c, "这本书里有谁？", fonts, overrides, zh_cfg["size"] * 1.2,
                          zh_cfg["color"], page_w / 2, top, content_w)
    top -= 0.15 * inch

    entries = cast_entries(project, data)
    cols = 1 if len(entries) == 1 else 2 if len(entries) <= 4 else 3
    rows = -(-len(entries) // cols)
    name_size = zh_cfg["size"] * 0.8
    label_h = (en_cfg["size"] * 0.8 + ruby_pitch(name_size, name_size * 1.2) + 0.2 * inch)
    cell_w = content_w / cols
    cell_h = (top - margin) / rows
    pad = 0.12 * inch

    for i, entry in enumerate(entries):
        row, col = divmod(i, cols)
        # Centre a short last row.
        in_row = min(cols, len(entries) - row * cols)
        x = margin + (cols - in_row) * cell_w / 2 + col * cell_w
        y = top - (row + 1) * cell_h
        img_box = (x + pad, y + label_h, cell_w - 2 * pad, cell_h - label_h - pad)

        with Image.open(cast_source(project, entry["src"])) as img:
            crop = img.convert("RGB").crop(tuple(entry["box"]))
        buf = io.BytesIO()
        crop.save(buf, "PNG")
        reader = ImageReader(buf)
        scale = min(img_box[2] / crop.width, img_box[3] / crop.height)
        w, h = crop.width * scale, crop.height * scale
        c.drawImage(reader, img_box[0] + (img_box[2] - w) / 2, img_box[1] + (img_box[3] - h) / 2,
                    width=w, height=h)

        name = entry["name"]
        if name:
            cx = x + cell_w / 2
            c.setFillColor(HexColor(en_cfg["color"]))
            c.setFont(fonts["en"], en_cfg["size"] * 0.8)
            c.drawCentredString(cx, y + label_h - en_cfg["size"] * 0.8, name["en"])
            draw_ruby_line(c, name["zh"], fonts, overrides, name_size, zh_cfg["color"],
                           cx, y + 0.1 * inch + ruby_pitch(name_size, name_size * 1.2), cell_w)
    c.showPage()


def booklet_sheets(count: int) -> list[tuple[int | None, int | None]]:
    """The page pairs for each printed side of a folded booklet, in print order.

    Pages are numbered from 0. None is a blank that pads the count to a
    multiple of four. Each sheet has a front and then a back, and each side
    is (left, right). For 8 pages the front of the outer sheet is (7, 0).
    """
    n = count + (-count % 4)
    pages = [i if i < count else None for i in range(n)]
    sides = []
    for sheet in range(n // 4):
        sides.append((pages[n - 1 - 2 * sheet], pages[2 * sheet]))       # front
        sides.append((pages[2 * sheet + 1], pages[n - 2 - 2 * sheet]))   # back
    return sides


class BookletCanvas(pdfcanvas.Canvas):
    """A canvas that lays its pages out as a folded booklet when it is saved.

    Each page is drawn into a form instead of onto a sheet. save() then places
    the forms two to a landscape sheet, so that the printed stack folds into
    pages 1, 2, 3 and on. Blank pages pad the count to a multiple of four.
    """

    def __init__(self, path: str, pagesize: tuple[float, float]):
        self._half = pagesize
        super().__init__(path, pagesize=(pagesize[0] * 2, pagesize[1]))
        self._forms: list[str] = []
        self._begin()

    def _begin(self) -> None:
        name = f"page{len(self._forms)}"
        self._forms.append(name)
        self.beginForm(name, 0, 0, *self._half)

    def showPage(self) -> None:
        self.endForm()
        self._begin()

    def save(self) -> None:
        self.endForm()
        self._forms.pop()  # opened by the last showPage, never drawn on
        for left, right in booklet_sheets(len(self._forms)):
            for index, dx in ((left, 0), (right, self._half[0])):
                if index is not None:
                    self.saveState()
                    self.translate(dx, 0)
                    self.doForm(self._forms[index])
                    self.restoreState()
            pdfcanvas.Canvas.showPage(self)
        super().save()


# --------------------------------------------------------------------------

def apply_size(data: dict, name: str) -> None:
    """Set the trim and every layout field that depends on it, together."""
    spec = SIZES[name]
    data["page"]["width_in"] = spec["w"]
    data["page"]["height_in"] = spec["h"]
    layout = data["layout"]
    layout["margin_in"] = spec["margin"]
    layout.setdefault("overlay", {})
    layout["overlay"]["padding_in"] = spec["padding"]
    layout["overlay"]["band_height_frac"] = spec["band"]
    layout["en"]["size"] = spec["en"]
    layout["en"]["leading"] = round(spec["en"] * 1.34, 1)
    layout["zh"]["size"] = spec["zh"]
    layout["zh"]["leading"] = round(spec["zh"] * 1.6, 1)


def apply_profile(data: dict, name: str) -> None:
    data["layout"].update(PROFILES[name])


def build(project: Path, out: Path | None, cover: bool, draft: bool,
          placement: str | None = None, fit: str | None = None,
          size: str | None = None, profile: str | None = None,
          variant: str = "full", color: bool = False, web: bool = False,
          cast_page: bool = False, booklet: bool = False) -> Path:
    data = with_defaults(load_book(project))
    require_valid(data, project)
    if booklet:
        if size and size != "half-letter":
            sys.exit("error: --booklet folds letter sheets, so it needs --size half-letter")
        size = "half-letter"
    # Every override below edits the parsed copy only. book-data.json is never
    # written back, so one book renders at any size in any variant.
    if size:
        apply_size(data, size)
    if profile:
        apply_profile(data, profile)
    if placement:
        data["layout"]["text_placement"] = placement
    if fit:
        data["layout"]["image_fit"] = fit
    if web:
        data["layout"]["jpeg_quality"] = WEB_JPEG_QUALITY
    spec = VARIANTS[variant]

    art = images_dir(project, color)
    build_dir = project / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    if not out:
        parts = [data.get("slug", project.name)]
        if size:
            parts.append(size)
        if variant != "full":
            parts.append(variant)
        if color:
            parts.append("color")
        if web:
            parts.append("web")
        if booklet:
            parts.append("booklet")
        out = build_dir / ("-".join(parts) + ".pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w = data["page"]["width_in"] * inch
    page_h = data["page"]["height_in"] * inch
    margin = data["layout"].get("margin_in", 0.55) * inch

    fonts = {
        "en": resolve_font("BookEN", data["fonts"]["en"]),
        "zh": resolve_font("BookZH", data["fonts"]["zh"], fallback="STSong-Light"),
        "py": resolve_font("BookPY", data["fonts"].get("pinyin", DEFAULT_PINYIN_FONTS)),
    }
    if fonts["py"] in BUILTIN_FONTS:
        print(f"  warning: the pinyin font is {fonts['py']}, which cannot print tone marks"
              " such as ǎ.\n           Set fonts.pinyin in book-data.json to a .ttf that has"
              " them, such as DejaVu Sans.", file=sys.stderr)

    if booklet:
        c = BookletCanvas(str(out), (page_w, page_h))
    else:
        c = pdfcanvas.Canvas(str(out), pagesize=(page_w, page_h))
    c.setTitle(data.get("title", {}).get("en", project.name))
    if data.get("author"):
        c.setAuthor(data["author"])

    if cover:
        draw_cover(c, data, fonts, art, page_w, page_h, margin, spec)
    if cast_page:
        draw_cast_page(c, data, fonts, project, page_w, page_h, margin)
    for page in data.get("pages", []):
        draw_page(c, page, data, fonts, art, page_w, page_h, margin, draft, spec)
    c.save()

    # A variant that draws the art as an empty box does not care that the art
    # is missing, so do not warn about it.
    if spec.get("art") != "box":
        entries = ([data["cover"]] if cover and data.get("cover") else []) + data.get("pages", [])
        missing = [e["image"] for e in entries
                   if e.get("image") and not (art / e["image"]).exists()]
        if missing:
            print(f"  {len(missing)} image(s) missing, drawn as placeholders: {', '.join(missing)}")
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build a portrait PDF from book-data.json.")
    ap.add_argument("project", nargs="?", default=".", type=Path, help="project directory (default: cwd)")
    ap.add_argument("--out", type=Path, help="output PDF path (default: <project>/build/<slug>.pdf)")
    ap.add_argument("--no-cover", action="store_true", help="skip the cover page")
    ap.add_argument("--draft", action="store_true", help="stamp each page with its image filename")
    ap.add_argument("--placement", choices=["below", "overlay"],
                    help="override layout.text_placement for this build")
    ap.add_argument("--fit", choices=["contain", "cover"],
                    help="override layout.image_fit for this build")
    ap.add_argument("--size", choices=sorted(SIZES),
                    help="override the trim and the layout fields that depend on it")
    ap.add_argument("--profile", choices=sorted(PROFILES),
                    help="picturebook = full-bleed art; activity = square art on white")
    ap.add_argument("--variant", default="full", choices=sorted(VARIANTS) + ["all"],
                    help="which half of the page the child fills in (default: full)")
    ap.add_argument("--color", action="store_true",
                    help="use the colour art in images/color/ instead of the line art")
    ap.add_argument("--web", action="store_true",
                    help="embed the art as JPEG, for a smaller file to put online")
    ap.add_argument("--cast-page", action="store_true",
                    help="add a page of the characters after the cover")
    ap.add_argument("--booklet", action="store_true",
                    help="lay half-letter pages out to fold into a booklet")
    args = ap.parse_args(argv)

    if args.variant == "all" and args.out:
        ap.error("--out names one file, so it cannot be used with --variant all")

    project = args.project.expanduser().resolve()
    wanted = sorted(VARIANTS) if args.variant == "all" else [args.variant]
    for variant in wanted:
        out = build(project, args.out, not args.no_cover, args.draft,
                    args.placement, args.fit, args.size, args.profile, variant,
                    args.color, args.web, args.cast_page, args.booklet)
        print(f"  wrote {out}")

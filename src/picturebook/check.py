"""Check the verse in a book: Chinese syllable counts, rhymes, English lines.

Usage:
    picturebook check [project-dir ...]

Every book declares its Chinese line shape in `background.meter_zh`, for
example "5+5 per line". This script measures what the pages actually do and
reports anything that disagrees.

It checks four things:

1. Each Chinese line has the number of characters the book declares.
2. The two lines rhyme, in 十三辙 terms, and do not rhyme on the same
   character as each other.
3. No two pages in a row use the same rhyme category.
4. Each English page is exactly two lines.

A book with `background.form` set to "prose" skips all four. Its pages are
checked only for 2-5 English sentences and some Chinese text.

Rhymes are read through the same pinyin path as the HTML reader, with the
一 and 不 tone changes and the book's own `pinyin_overrides` applied, so a
heteronym like 行 is measured the way a reader will say it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .bookdata import is_han, load_book
from .pinyin import ruby_html

RUBY = re.compile(r"<ruby>(.)<rt>(.*?)</rt></ruby>")

TONE = str.maketrans("āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ", "aaaaeeeeiiiioooouuuuvvvv")

RHYME_GROUPS = {
    "发花": ["a", "ia", "ua"],
    "梭波": ["o", "e", "uo"],
    "乜斜": ["ie", "ve"],
    "一七": ["i", "v", "er"],
    "姑苏": ["u"],
    "怀来": ["ai", "uai"],
    "灰堆": ["ei", "ui", "uei"],
    "遥条": ["ao", "iao"],
    "由求": ["ou", "iu", "iou"],
    "言前": ["an", "ian", "uan", "van"],
    "人辰": ["en", "in", "un", "uen", "vn"],
    "江阳": ["ang", "iang", "uang"],
    "中东": ["eng", "ing", "ong", "iong", "ueng"],
}
# ü after j q x y is written u, so 去 qu is really qü and belongs to 一七.
PALATAL = set("jqxy")


def han_only(text: str) -> str:
    """The Han characters of a text. Nothing else counts toward the syllables."""
    return "".join(ch for ch in text if is_han(ch))


def final_of(syllable: str) -> str:
    """Strip the initial and the tone mark, leaving the rhyming final."""
    s = syllable.translate(TONE).strip()
    if not s:
        return ""
    if s[0] in PALATAL and len(s) > 1 and s[1] == "u":
        s = s[0] + "v" + s[2:]
    # y and w are spelling, not initials: 也 ye is the final ie, 我 wo is uo.
    # They stand in for i, u or ü, or are written in front of one.
    if s[0] == "y":
        return s[1:] if s[1:2] in ("i", "v") else "i" + s[1:]
    if s[0] == "w":
        return s[1:] if s[1:2] == "u" else "u" + s[1:]
    for initial in ("zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
                    "g", "k", "h", "j", "q", "x", "r", "z", "c", "s"):
        if s.startswith(initial):
            return s[len(initial):] or s
    return s


def rhyme_group(syllable: str) -> str:
    final = final_of(syllable)
    for name, finals in RHYME_GROUPS.items():
        if final in finals:
            return name
    return f"?{final}"


def expected_shape(data: dict) -> list[int]:
    """The half-line lengths a book declares, e.g. "5+5 per line" -> [5, 5]."""
    meter = data.get("background", {}).get("meter_zh", "")
    match = re.search(r"(\d+(?:\+\d+)+)", meter)
    if not match:
        sys.exit("error: background.meter_zh must declare a shape like \"5+5 per line\"")
    return [int(n) for n in match.group(1).split("+")]


def read_page(zh: str, overrides: dict) -> tuple[list[str], list[str]]:
    """Return each printed line's Han characters and its rhyming syllable.

    The rhyme always falls on the last character of a printed line, whatever
    punctuation sits inside the line. Counting characters per line, rather
    than trying to split half-lines on punctuation, avoids guessing about
    quotes, dashes and pause marks.
    """
    lines = [han_only(line) for line in zh.split("\n")]
    finals = []
    for han in lines:
        pairs = RUBY.findall(ruby_html(han, overrides, True))
        finals.append(pairs[-1][1] if pairs else "")
    return lines, finals


# A sentence ends at . ! or ?, optionally followed by a closing quote. A
# lowercase word after it is a speech tag ("Hi!" says Dad.), so it does not count.
SENTENCE_END = re.compile(r"[.!?]+[\"”’']?(?=\s+(?![a-z])|$)")


def check_prose(project: Path, pages: list[dict]) -> int:
    """A prose book: 2-5 English sentences a page, and Chinese present."""
    print(f"\n=== {project.name} — prose, expect 2-5 sentences a page ===")
    problems = 0
    for page in pages:
        sentences = len(SENTENCE_END.findall(page["en"]))
        notes = []
        if not 2 <= sentences <= 5:
            notes.append(f"{sentences} English sentences, expected 2-5")
        if not han_only(page.get("zh", "")):
            notes.append("no Chinese text")
        status = "  <-- " + "; ".join(notes) if notes else ""
        problems += bool(notes)
        print(f"  p{page['n']:>2} {sentences} sentences{status}")
    return problems


def check(project: Path) -> int:
    data = load_book(project)
    if data.get("background", {}).get("form") == "prose":
        return check_prose(project, data.get("pages", []))
    overrides = data.get("pinyin_overrides", {})
    pages = data.get("pages", [])
    problems = 0

    shape = expected_shape(data)
    per_line = sum(shape)
    shown = "+".join(str(n) for n in shape)

    print(f"\n=== {project.name} — expect {shown} = {per_line} characters a line ===")
    groups: list[str] = []
    for page in pages:
        lines, finals = read_page(page["zh"], overrides)
        lens = [len(line) for line in lines]
        chars = [line[-1] if line else "?" for line in lines]
        gs = [rhyme_group(f) for f in finals]

        notes = []
        if len(lines) != 2:
            notes.append(f"{len(lines)} Chinese lines, expected 2")
        for i, n in enumerate(lens):
            if n != per_line:
                notes.append(f"line {i + 1} is {n} characters, expected {per_line}")
        if len(gs) == 2:
            if gs[0] != gs[1]:
                notes.append(f"{chars[0]}/{chars[1]} do not rhyme")
            elif chars[0] == chars[1]:
                notes.append(f"rhymes {chars[0]} on itself")
        if len(page["en"].split("\n")) != 2:
            notes.append("English is not two lines")

        groups.append(gs[0] if gs else "?")
        status = "  <-- " + "; ".join(notes) if notes else ""
        problems += bool(notes)
        print(f"  p{page['n']:>2} {'/'.join(str(n) for n in lens):<7}"
              f" {''.join(chars):<3} {gs[0] if gs else '?':<4}{status}")

    for i in range(len(groups) - 1):
        if groups[i] == groups[i + 1] and not groups[i].startswith("?"):
            print(f"  <-- pages {i + 1} and {i + 2} both rhyme on {groups[i]}")
            problems += 1
    return problems


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projects", nargs="*", default=["."], type=Path)
    args = ap.parse_args(argv)
    total = sum(check(Path(p).expanduser().resolve()) for p in args.projects)
    print(f"\n{total} page(s) to look at")
    sys.exit(1 if total else 0)

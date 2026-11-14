"""Generate page art for a book project, one image per page.

Usage:
    picturebook generate [project-dir ...] [options]

Options:
    --backend NAME    manual (default) or replicate.
    --style NAME      color (default), line or paint. Picks the master style
                      block. paint colours the filed line art; see below.
    --aspect RATIO    Override the art shape, e.g. "1:1".
    --pages LIST      Only these pages, e.g. "cover,1,4". Default is all.
    --model NAME      Replicate model, e.g. flux-1.1-pro. paint defaults to
                      kontext-pro.
    --extra TEXT      Extra text to append to every prompt.
    --seeds LIST      Several seeds in one run, e.g. "1234,1235". Each seed
                      makes --variants images per page.
    --delay SECONDS   Pause between requests. Replicate allows 6 a minute
                      while the account holds under $5, so 11 avoids throttling.
    --force           Send every prompt again, even the cached ones.
    --dry-run         Print what would be sent. Call nothing, write nothing.

The prompt is assembled the same way `picturebook prompts` assembles it:
the master style block, then the page's own prompt.

The art shape comes from `--aspect`, then `page.art_aspect`, then the page
size. An activity book sets `art_aspect` to `1:1`, because a square prints the
same on letter, A4 or half-letter. A picture book leaves it unset, so the art
and the trim cannot disagree.

`--style line` also drops the trailing "Keep ... for text" sentence from each
prompt. That sentence reserves empty space for a text overlay, and an activity
book puts its text below the art instead. See docs/prompt-sheet.md.

`--style paint` starts from the line drawing already filed as
`images/page-NN.png` and asks an image-to-image model to colour it, so the
colour book keeps the composition picked for the activity book. It needs a
model that takes a drawing, such as `--model kontext-pro`. A page with no
filed drawing is skipped. See `paint_prompt` for what the instruction says.

Generated files land in `images/_incoming/`, named after the page they belong
to. Colour art, from `--style color` or `paint`, lands in
`images/color/_incoming/` instead, so it never overwrites the line art. Nothing
overwrites a filed image directly. Run `picturebook import` (with `--color` for
colour) to review what arrived and file it.

The cache lives in `images/.generate-cache.json` and is keyed on everything
that changes the picture. A prompt that has not changed is not sent again, so
an interrupted run costs nothing to resume. `--force` sends again but keeps
the other pages' entries, so it never makes a later run pay for them twice.

The exit status is 1 if any page failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from .backends import BACKENDS, Job, PredictionFailed, Result
from .bookdata import CHARACTERS_KEY, images_dir, load_book

CACHE_NAME = ".generate-cache.json"
STYLES = ("color", "line", "paint")

# The sentence every prompt ends with, naming the part of the frame to leave
# quiet for the text. `picturebook text-positions` reads the same sentence.
KEEP_SENTENCE = re.compile(r"\s*Keep\b[^.]*\.\s*$", re.IGNORECASE)
# The palette sentence. It is pure colour instruction and carries no shape, so
# line art drops it rather than argue with its own "no color fill".
PALETTE_SENTENCE = re.compile(r"\s*Palette of [^.]*\.", re.IGNORECASE)
RATIO = re.compile(r"^\d+:\d+$")

# Colour adjectives, stripped from a page prompt when generating line art.
#
# Telling the model to ignore the colours it is about to read does not work.
# It was tried on 20 September 2026 with a pinned seed and changed nothing: a
# blue headband, a green t-shirt and red sneakers still came back filled in.
# A concrete noun beats a meta-instruction, so the words have to go.
#
# Material and pattern words stay. "denim", "canvas" and "striped" say what a
# thing is made of and how it is shaped, which is what the drawing needs.
_COLOURS = (
    "black|white|grey|gray|blue|red|green|yellow|orange|purple|pink|brown|"
    "tan|khaki|gold|golden|silver|bronze|copper|crimson|scarlet|violet|"
    "indigo|teal|turquoise|beige|cream|ivory|amber|ochre|russet|maroon|"
    "navy|olive|lavender|magenta|cyan|rust|sepia|charcoal|blond|blonde|"
    "auburn|iridescent|colou?red pencil"
)
# Matches a colour, and hyphenated runs of them such as "gray-brown". One
# leading qualifier goes with it, so "burnt-orange" does not leave "burnt-".
COLOUR_WORD = re.compile(
    rf"\b(?:[a-z]+-)?(?:{_COLOURS})(?:-(?:{_COLOURS}))*\b", re.IGNORECASE)

# Light and shade, which line art also drops. "coins of dappled light on the
# floor" came back on 25 September 2026 as grey hatching over a tenth of the
# page, despite "no shading" in the style block. The same lesson as colour: the
# noun wins. "lit" alone is left out because "his face lit with triumph" is an
# expression, not a light source, and "delight" is not light either. Nor are
# the objects named for light: "a boy holds a flashlight" must keep its torch.
LIGHT_OBJECTS = r"delight|flashlight|headlight|streetlight|nightlight|stoplight|skylight"
LIGHT_WORD = re.compile(
    rf"\b(?:(?!(?:{LIGHT_OBJECTS})\b)\w*light|lights|shade|shadows?|dappled|glow|glowing"
    r"|backlit|sunlit)\b",
    re.IGNORECASE)
# Where a light phrase starts inside a longer fragment: "a tunnel with coins
# of dappled light" is cut back to "a tunnel".
LIGHT_LEAD = re.compile(r"\s+(?:with|in|under|through|catching)\s+[^,.;]*$",
                        re.IGNORECASE)
# A fragment with no such lead-in is dropped whole only when it is this short.
# Longer ones, such as "the shoe is up against the ceiling light", are mostly
# about something else and stay.
LIGHT_FRAGMENT_WORDS = 8
# A fragment that names its light in the first few words is about the light,
# however long it runs: "Low late-afternoon light raking in sideways under the
# oak canopy" goes whole.
LIGHT_LEAD_WORDS = 3
# Words a colour removal would leave hanging: "going red on the bank" would
# become "going on the bank", "soft pink and" would become "soft and". Removed
# together with the colour, so "faces bright with effort" is left alone.
DANGLING = re.compile(
    r"\b(?:going|turning|soft|pale|bright|deep|warm|cold|cool|hot)\s+"
    rf"(?={COLOUR_WORD.pattern}(?:\s+(?:on|at|in|along|and|with)\b|\s*[,.;]))",
    re.IGNORECASE)


def art_dir(project: Path, style: str) -> Path:
    """Where a style's art is filed: images/ for line, images/color/ for colour."""
    return images_dir(project, color=style != "line")


def shared_data(data: dict) -> dict:
    """The book's characters.json, or an empty dict if it has none."""
    return data.get(CHARACTERS_KEY) or {}


def aspect_ratio(page: dict, override: str = "") -> str:
    """The art's shape as a ratio, such as "2:3" or "1:1".

    `--aspect` wins, then `page.art_aspect`, then the page size. An activity
    book pins a square so that one image serves every paper size.
    """
    for candidate in (override, str(page.get("art_aspect", "")).strip()):
        if candidate:
            if not RATIO.match(candidate):
                sys.exit(f"error: aspect {candidate!r} is not in the form W:H")
            return candidate
    width = float(page.get("width_in", 8.0))
    height = float(page.get("height_in", 10.6667))
    if height <= 0:
        sys.exit("error: page.height_in must be greater than zero")
    ratio = Fraction(width / height).limit_denominator(32)
    return f"{ratio.numerator}:{ratio.denominator}"


def style_block(data: dict, style: str) -> str:
    """The master style block to put on the front of every prompt.

    A book may override a style in its own `style_blocks`. Otherwise the shared
    one in the book's `characters.json` wins. `style_block`, the older single-style
    field, is the colour block.
    """
    for source in (data.get("style_blocks") or {}, shared_data(data).get("style_blocks") or {}):
        if source.get(style):
            return str(source[style]).strip()
    if style == "color":
        return (data.get("style_block") or "").strip()
    sys.exit(
        f"error: no {style!r} style block. Add style_blocks.{style} to the book,\n"
        f"       or to characters.json."
    )


def for_style(prompt: str, style: str) -> str:
    """Adjust a page prompt for the style being generated.

    Line art drops four things. The `Keep ...` sentence reserves negative
    space for a text overlay, and an activity book puts its text below the art
    instead. The `Palette of ...` sentence asks for colours a black and white
    drawing cannot have. Every remaining colour adjective goes too, because a
    model that reads "a green t-shirt" fills the t-shirt in whatever else the
    style block says. Light and shade go last, for the same reason: "dappled
    light" comes back as grey hatching. See `drop_light`.

    The character descriptions therefore differ between the two styles. That
    is the point: `characters.json` holds one bible, and this strips it
    down for line art rather than making anyone maintain two.
    """
    if style != "line":
        return prompt
    prompt = PALETTE_SENTENCE.sub("", prompt)
    prompt = KEEP_SENTENCE.sub("", prompt)
    prompt = DANGLING.sub("", prompt)
    prompt = COLOUR_WORD.sub("", prompt)
    prompt = re.sub(r"\s+(?:in|of)\s+(?:and\s+)?(?=[,.;])", "", prompt)  # "in and."
    prompt = drop_light(prompt)
    prompt = re.sub(r"\s+([,.])", r"\1", prompt)   # " ," left by a removal
    prompt = re.sub(r"\b(?:a|an)\s+(?=[,.])", "", prompt)  # dangling article
    prompt = re.sub(r",\s*([,.])", r"\1", prompt)   # ", ." left by a dropped clause
    prompt = re.sub(r"\.\s*[.,]", ".", prompt)      # ". ," and ".." likewise
    prompt = re.sub(r"^\s*[,.]\s*", "", prompt)
    prompt = re.sub(r"(\.\s+)([a-z])", lambda m: m[1] + m[2].upper(), prompt)
    return re.sub(r"\s{2,}", " ", prompt).strip()


def drop_light(prompt: str) -> str:
    """Remove the light and shade from a line-art prompt.

    Works one comma- or sentence-delimited fragment at a time. A fragment that
    leads into its light with "with", "in" and so on is cut back to before it.
    A short fragment that is only about light goes whole. A long one stays.
    """
    out = []
    for fragment in re.split(r"(?<=[,.;])", prompt):
        body = fragment.rstrip(",.;")
        if LIGHT_WORD.search(body):
            cut = LIGHT_LEAD.sub("", body)
            words = body.split()
            if cut != body and not LIGHT_WORD.search(cut) and cut.strip():
                fragment = cut + fragment[len(body):]
            elif (not cut.strip() or len(words) <= LIGHT_FRAGMENT_WORDS
                  or LIGHT_WORD.search(" ".join(words[:LIGHT_LEAD_WORDS]))):
                fragment = fragment[len(body):]
        out.append(fragment)
    return "".join(out)


# A character's `match` in characters.json is a regular expression for how a
# page's line prompt refers to them, such as "\\bsquirrel\\b". Paint sends a
# character's colours only to the pages that match, because Kontext draws in
# anyone it is told about: it once added a dad, two children and a squirrel to
# pages that had none of them.


def cast_colours(data: dict, entry: dict) -> str:
    """The colour description of the cast members this page shows.

    Who is on the page comes from its line prompt, because that describes the
    drawing being coloured. A character with no `match` is sent to every page.

    A page's `paint_cast` list of ids overrides that guess. Use it when the
    picked drawing leaves out someone the prompt names, or adds someone it
    does not. Kontext draws in anyone it is told about, even a character the
    picked drawing left out.
    """
    shown = entry.get("line_prompt") or entry.get("prompt") or ""
    listed = entry.get("paint_cast")
    people = {c.get("id"): c for c in shared_data(data).get("characters", [])}
    parts = []
    for cid in data.get("cast", []):
        words = (people.get(cid) or {}).get("match")
        if listed is not None:
            if cid not in listed:
                continue
        elif words and not re.search(words, shown, re.IGNORECASE):
            continue
        person = people.get(cid) or {}
        name = (person.get("name") or {}).get("en", cid)
        if person.get("description"):
            parts.append(f"{name}: {person['description'].rstrip('.')}.")
    return "Colour the characters like this. " + " ".join(parts) if parts else ""


def paint_prompt(entry: dict, cast: str) -> str:
    """The colouring instruction for one page, after the paint style block.

    The drawing already fixes what is in the picture, so the scene is not
    described again. A description that disagrees with the drawing, such as
    a squirrel drawn five times in one scene, could make the model redraw it.
    Only the sentences of the colour prompt that name a colour or a light go,
    and the palette sentence is one of them. The `Keep ...` sentence goes too.

    A page's `paint_prompt` replaces those sentences. Use it when Replicate
    flags the colour prompt as sensitive (E005).
    """
    if entry.get("paint_prompt"):
        return " ".join([cast, entry["paint_prompt"].strip()]).strip()
    prompt = KEEP_SENTENCE.sub("", (entry.get("prompt") or "").strip())
    kept = [sentence for sentence in re.split(r"(?<=\.)\s+", prompt)
            if COLOUR_WORD.search(sentence) or LIGHT_WORD.search(sentence)]
    return " ".join([cast] + kept).strip()


def negative_prompt(data: dict, style: str) -> str:
    """What to keep out of the picture, for a model that takes a negative.

    None of the models in use takes one; FLUX ignores a negative. It is still
    read, because it is part of every cache key made so far.
    """
    for source in (data.get("negative_prompts") or {},
                   shared_data(data).get("negative_prompts") or {}):
        if source.get(style):
            return str(source[style]).strip()
    return ""


def jobs_for(data: dict, only: set[str], style: str = "color",
             aspect_override: str = "", line_dir: Path | None = None) -> list[Job]:
    """One Job per page that has a prompt, plus the cover.

    Line art uses a page's `line_prompt` when it has one. flux-schnell draws one
    plain action well and loses panels, counts and camera tricks, so the short
    version says only what is in the picture. The colour prompt is untouched.

    Paint sends the drawing filed in `line_dir`, and keeps its shape unless
    `--aspect` says otherwise. A page with no drawing filed yet is left out.
    """
    master = style_block(data, style)
    if style == "paint":
        aspect = aspect_override or "match_input_image"
    else:
        aspect = aspect_ratio(data.get("page", {}), aspect_override)
    negative = negative_prompt(data, style)
    jobs: list[Job] = []

    def pick(entry: dict) -> str:
        if style == "line" and entry.get("line_prompt"):
            return entry["line_prompt"].strip()
        if style == "paint":
            return paint_prompt(entry, cast_colours(data, entry))
        return (entry.get("prompt") or "").strip()

    def source(image: str) -> Path | None:
        return line_dir / image if style == "paint" and line_dir else None

    cover = data.get("cover") or {}
    if pick(cover):
        jobs.append(Job(
            page="cover",
            image=cover.get("image", "cover.png"),
            text=f"{master} {for_style(pick(cover), style)}".strip(),
            aspect=aspect,
            negative=negative,
            source=source(cover.get("image", "cover.png")),
        ))
    for page in data.get("pages", []):
        prompt = pick(page)
        if not prompt:
            continue
        n = page.get("n", 0)
        image = page.get("image", f"page-{n:02d}.png")
        jobs.append(Job(
            page=f"{n:02d}",
            image=image,
            text=f"{master} {for_style(prompt, style)}".strip(),
            aspect=aspect,
            negative=negative,
            source=source(image),
        ))

    if only:
        jobs = [job for job in jobs if job.page in only or job.page.lstrip("0") in only]
    if style == "paint":
        missing = [job.image for job in jobs if not job.source.exists()]
        if missing:
            print(f"  skipping, no line art filed: {', '.join(missing)}")
        jobs = [job for job in jobs if job.source.exists()]
    return jobs


def parse_pages(value: str) -> set[str]:
    """Turn "cover,1,04" into {"cover", "1", "04"}."""
    return {part.strip() for part in value.split(",") if part.strip()}


# Fields of the cache key that no longer exist: the Midjourney style reference,
# and the local backend's step count and size. They keep their old empty
# values, so a cache made by an older version still matches and an
# interrupted run is not charged again.
RETIRED_SREF, RETIRED_STEPS, RETIRED_PX = "", "0", "0"


def cache_key(job: Job, args: argparse.Namespace) -> str:
    """Everything that changes the picture goes into the key.

    For paint that includes the drawing itself, so re-picking a page's line
    art sends it to be coloured again.
    """
    parts = [
        job.text, job.aspect, RETIRED_SREF, job.negative, args.backend, args.extra,
        args.model, str(args.variants), str(args.seed), args.style,
        RETIRED_STEPS, RETIRED_PX,
    ]
    # Added only when there is a drawing, so line and colour keys made before
    # paint existed still match.
    if job.source:
        parts.append(hashlib.sha256(job.source.read_bytes()).hexdigest())
    blob = "␟".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def run(project: Path, args: argparse.Namespace) -> int:
    data = load_book(project)
    backend = BACKENDS[args.backend](
        extra_flags=args.extra, model=args.model,
        variants=args.variants, seed=args.seed,
    )
    jobs = jobs_for(data, parse_pages(args.pages) if args.pages else set(),
                    args.style, args.aspect, art_dir(project, "line"))
    if not jobs:
        print(f"  {project.name}: nothing to generate")
        return 0

    out_dir = art_dir(project, args.style) / "_incoming"
    cache_file = art_dir(project, args.style) / CACHE_NAME
    # Loaded even with --force. Starting from an empty cache and saving it
    # would forget every page this run does not send.
    cache = {}
    if cache_file.exists():
        cache = json.loads(cache_file.read_text(encoding="utf-8"))

    print(f"\n=== {project.name} — {len(jobs)} page(s), {jobs[0].aspect}, "
          f"{args.style} art, backend {args.backend} ===")

    if args.dry_run:
        for job in jobs:
            print(f"\n  {job.image}")
            print(f"    {backend.line(job)}")
        print("\n  dry run — nothing sent, nothing written")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []
    sent = 0
    failed = []
    for job in jobs:
        key = cache_key(job, args)
        if key in cache and not args.force:
            print(f"  {job.image:<16} cached")
            continue
        if sent or failed:
            time.sleep(args.delay)
        try:
            result = backend.submit(job, out_dir)
        except PredictionFailed as err:
            # A failed prediction, such as a false NSFW flag, costs only this
            # page. Anything else, such as a missing token, stops the run.
            print(f"  {job.image:<16} FAILED: {err}")
            failed.append(job.page)
            continue
        results.append(result)
        if not result.files and backend.name != "manual":
            # Nothing came back, so nothing is cached: a rerun tries again.
            print(f"  {job.image:<16} FAILED: {result.note}")
            failed.append(job.page)
            continue
        cache[key] = {
            "page": job.page,
            "image": job.image,
            "job_id": result.job_id,
            "model": args.model,
            "seed": args.seed,
            "files": [str(p.relative_to(project)) for p in result.files],
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        sent += 1
        note = result.note or f"{len(result.files)} file(s)"
        print(f"  {job.image:<16} {note}")
        # Saved after every page, so a crash does not forget paid-for work.
        cache_file.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    backend.finish(results, jobs, out_dir)
    print(f"  {sent} sent, {len(failed)} failed, "
          f"{len(jobs) - sent - len(failed)} cached")
    if failed:
        print(f"  retry with another --seed: --pages {','.join(failed)}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projects", nargs="*", default=["."], type=Path)
    ap.add_argument("--backend", default="manual", choices=sorted(BACKENDS))
    ap.add_argument("--style", default="color", choices=STYLES,
                    help="which master style block to use (default: color)")
    ap.add_argument("--aspect", default="",
                    help='override the art shape, e.g. "1:1"')
    ap.add_argument("--model", default="", help="Replicate model, e.g. flux-1.1-pro")
    ap.add_argument("--variants", type=int, default=1, help="images per page")
    ap.add_argument("--seed", type=int, default=None, help="pin the seed")
    ap.add_argument("--seeds", default="", help='several seeds, e.g. "1234,1235"')
    ap.add_argument("--delay", type=float, default=0,
                    help="seconds between requests (11 avoids Replicate's low-credit limit)")
    ap.add_argument("--pages", default="", help='e.g. "cover,1,4"')
    ap.add_argument("--extra", default="", help="extra text to append to every prompt")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    # kontext-pro kept the drawing better than kontext-dev in a side-by-side test.
    if args.style == "paint" and not args.model:
        args.model = "kontext-pro"
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()] or [args.seed]
    status = 0
    for seed in seeds:
        args.seed = seed
        for project in args.projects:
            status |= run(Path(project).expanduser().resolve(), args)
    if not args.dry_run and args.backend != "manual":
        from .pick import write_pick_page
        print(f"\n  pick your favourites: open {write_pick_page([Path(p) for p in args.projects])}")
    sys.exit(status)

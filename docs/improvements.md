# picturebook — improvements

## At a glance

1. No `picturebook new` command — S · open
2. `print --cast-page` crashes when the art is missing — S · open
3. A `pinyin_overrides` entry of the wrong length is skipped silently — S · open
4. `check` rejects a non-prose `form` that has no `meter_zh` — S · decision owed

## 1. No `picturebook new` command

A new user copies `examples/pip-forgets` by hand. A `new` command could write a
minimal `book-data.json` and `characters.json`, or read a Markdown story.

## 2. `print --cast-page` crashes when the art is missing

`print BOOK --only draw-in --cast-page` ends in a `FileNotFoundError`
traceback when the book has no art, though `draw-in` needs none.
`cast_source` in `pdf.py` falls through to a missing `images/color/<file>`.
Give a clean error that names the file, or skip the cast page with a message.
Found 2026-11-18 while the docs were written; reproduced then.

## 3. A `pinyin_overrides` entry of the wrong length is skipped silently

`_apply_overrides` skips an override whose syllable count does not match its
character count. The author gets the default pinyin and no hint. Warn instead,
or fail `check`. From a code read on 2026-11-18; not reproduced.

## 4. `check` rejects a non-prose `form` that has no `meter_zh`

Only an unset `background.form` falls back to prose. `"form": "verse"` with no
`meter_zh` exits with an error about `meter_zh`. That may be intended: verse
needs a meter. Decide, then document it in `docs/book-file.md`. From a code
read on 2026-11-18; not reproduced.

## Settled

- 2026-11-18: Fixed: `import --resize` crops from the centre, applies EXIF rotation, and flattens transparency onto white.
- 2026-11-18: Fixed: clean errors for a missing import folder, bad --seeds, an out-of-range --pages and an unknown --model (any backend); generate skips a page with no image key, as import does.
- 2026-11-18: Fixed: the manual backend writes no cache entries and reports "queued, none sent".
- 2026-11-18: Fixed: text-positions keeps a text_position the Keep sentence does not contradict, and writes book-data.json.bak first. A Keep sentence that names the bottom still clears a top.
- 2026-11-18: Fixed: the print README computes the sheet count from each book's page count (cover, optional cast page, pages).
- 2026-11-18: Fixed: the placeholder note sits just below the caption, in the middle of the image, clear of a top or bottom text band.
- 2026-11-18: Fixed: page, layout and fonts have code defaults (from examples/pip-forgets) for pdf; pdf and check list each problem with its field and page; check treats a book with no form and no meter as prose. The reader does not apply or validate them.
- 2026-11-18: Fixed in styles: the default pages leave out pages the book lacks, a named page the book lacks is an error, and the book's own style_blocks.color is used. The default style and the prediction count are still the owner's decision.
- 2026-11-18: Docs only: the README installs with [dev], runs pre-commit install and says the hooks need ./.venv. The hooks are unchanged.
- 2026-11-18: Added end-to-end tests for generate (stand-in backend, no network), pick and import. The Linux job without fonts is still open.
- 2026-11-18: Defaults: `generate` keeps `--style color`. `import` and `pdf` now use `images/color/` when it exists, and `--line` takes the line art. `styles` keeps 60 predictions to `flux-1.1-pro`.
- 2026-11-18: Kept: the local hooks call `.venv/bin/ruff` and `.venv/bin/python`. The README says so.
- 2026-11-18: Declined: a CI job without fonts. CI stays simple.
- 2026-11-18: Kept: an unknown `--model` is an error with every backend, the manual one too.
- 2026-11-18: Kept: a Keep sentence that names the bottom clears a hand-set top in `text-positions`.
- 2026-11-18: Character drift in text-only colour runs moved to `ideas.md`.
- 2026-11-18: Docs: the README is split into docs/book-file.md, docs/art.md and docs/print.md, written from the code.

# picturebook — improvements

## At a glance

1. No `picturebook new` command — S · open
2. Docs are one README — M · open
3. Costly or surprising defaults in `generate` and `styles` — S · open
4. Pre-commit hooks assume `./.venv` — S · open
5. CI does not run `generate`, `pick` or `import` — S · open
6. Characters drift between pages in text-only colour runs — M · open

## 1. No `picturebook new` command

A new user copies `examples/pip-forgets` by hand. A `new` command could write a
minimal `book-data.json` and `characters.json`, or read a Markdown story.

## 2. Docs are one README

Split out: the book file reference, the three art paths, generating art (cost,
rate limits, E005 flags), print options, languages and pinyin, the cast page
(`cast-sheets.json`), and the `shared/` folder lookup.

## 3. Costly or surprising defaults in `generate` and `styles`

`generate` defaults to `--style color`, so its output goes to `images/color/`,
which a plain `import` and `pdf` do not read. `styles` with no flags sends 60
predictions to `flux-1.1-pro`, and asks for page 9 even in a shorter book.
`styles` also ignores a style block set in `book-data.json`.

## 4. Pre-commit hooks assume `./.venv`

The local hooks call `.venv/bin/ruff` and `.venv/bin/python`. The README
installs without `[dev]` and never mentions `pre-commit install`.

## 5. CI does not run `generate`, `pick` or `import`

The end-to-end tests build PDFs and the reader only. There is also no Linux
job without fonts, which is where the font fallbacks matter.

## 6. Characters drift between pages in text-only colour runs

`generate --style color` sends text only, so FLUX redraws each character from
the words on every page. Faces, facial hair, heights and the head count
drift, and attributes bleed between characters (a boy gets the girl's
headband). Option: a reference-image backend that sends one picked portrait
per character with the page prompt, through a multi-image editing model.
Check the model names and prices on Replicate before building it.

## Settled

- 2026-11-18: Fixed: `import --resize` crops from the centre, applies EXIF rotation, and flattens transparency onto white.
- 2026-11-18: Fixed: clean errors for a missing import folder, bad --seeds, an out-of-range --pages and an unknown --model (any backend); generate skips a page with no image key, as import does.
- 2026-11-18: Fixed: the manual backend writes no cache entries and reports "queued, none sent".
- 2026-11-18: Fixed: text-positions keeps a text_position the Keep sentence does not contradict, and writes book-data.json.bak first. A Keep sentence that names the bottom still clears a top.
- 2026-11-18: Fixed: the print README computes the sheet count from each book's page count (cover, optional cast page, pages).
- 2026-11-18: Fixed: the placeholder note sits just below the caption, in the middle of the image, clear of a top or bottom text band.
- 2026-11-18: Fixed: page, layout and fonts have code defaults (from examples/pip-forgets) for pdf; pdf and check list each problem with its field and page; check treats a book with no form and no meter as prose. The reader does not apply or validate them.

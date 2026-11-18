# picturebook — improvements

## At a glance

1. Book files need every layout and font field — M · open
2. No `picturebook new` command — S · open
3. Docs are one README — M · open
4. Costly or surprising defaults in `generate` and `styles` — S · open
5. The manual backend writes cache entries — S · open
6. `text-positions` clears values set by hand — S · open
7. The print README text assumes a 10-page book — S · open
8. Pre-commit hooks assume `./.venv` — S · open
9. CI does not run `generate`, `pick` or `import` — S · open
10. Placeholder footer text hides under the text band — S · open
11. Characters drift between pages in text-only colour runs — M · open

## 1. Book files need every layout and font field

`pdf` reads `page`, `layout` and `fonts` straight from `book-data.json`, so a
book with only a title and pages fails with `KeyError: 'page'`. `check` fails
on a prose book unless it sets `background.form: "prose"`. Put the defaults in
code, validate the file, and name the field and the page in each error.

## 2. No `picturebook new` command

A new user copies `examples/pip-forgets` by hand. A `new` command could write a
minimal `book-data.json` and `characters.json`, or read a Markdown story.

## 3. Docs are one README

Split out: the book file reference, the three art paths, generating art (cost,
rate limits, E005 flags), print options, languages and pinyin, the cast page
(`cast-sheets.json`), and the `shared/` folder lookup.

## 4. Costly or surprising defaults in `generate` and `styles`

`generate` defaults to `--style color`, so its output goes to `images/color/`,
which a plain `import` and `pdf` do not read. `styles` with no flags sends 60
predictions to `flux-1.1-pro`, and asks for page 9 even in a shorter book.
`styles` also ignores a style block set in `book-data.json`.

## 5. The manual backend writes cache entries

A manual run reports "11 sent", and a rerun "11 cached", though nothing was
made.

## 6. `text-positions` clears values set by hand

It removes `text_position` from every page whose `Keep` sentence does not ask
for the top, and rewrites the file with no backup.

## 7. The print README text assumes a 10-page book

"Each book is 3 sheets" is fixed text in `editions.py`.

## 8. Pre-commit hooks assume `./.venv`

The local hooks call `.venv/bin/ruff` and `.venv/bin/python`. The README
installs without `[dev]` and never mentions `pre-commit install`.

## 9. CI does not run `generate`, `pick` or `import`

The end-to-end tests build PDFs and the reader only. There is also no Linux
job without fonts, which is where the font fallbacks matter.

## 10. Placeholder footer text hides under the text band

"PLACEHOLDER — replace with final art" sits near the bottom of the image, where
the overlay band covers it.

## 11. Characters drift between pages in text-only colour runs

`generate --style color` sends text only, so FLUX redraws each character from
the words on every page. Faces, facial hair, heights and the head count
drift, and attributes bleed between characters (a boy gets the girl's
headband). Option: a reference-image backend that sends one picked portrait
per character with the page prompt, through a multi-image editing model.
Check the model names and prices on Replicate before building it.

## Settled

- 2026-11-18: Fixed: `import --resize` crops from the centre, applies EXIF rotation, and flattens transparency onto white.
- 2026-11-18: Fixed: clean errors for a missing import folder, bad --seeds, an out-of-range --pages and an unknown --model (any backend); generate skips a page with no image key, as import does.

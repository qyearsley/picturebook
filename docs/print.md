# Print

Use this page to build the print editions of a book, and to print them.

```
picturebook print examples/pip-forgets
```

## Editions

`print` builds PDFs for each book into `print/<book>/`. The files are rebuilt on every run, so a later art fix is one command.

| File ends with | What it is | Art it needs | Built |
| --- | --- | --- | --- |
| `color-booklet.pdf` | The finished book in colour, as a half-letter booklet. | Colour on every page. | by default |
| `color-letter.pdf` | The same, one page per letter sheet. | Colour on every page. | by default |
| `coloring-booklet.pdf` | Line art and words, to colour in. Half-letter booklet. | Line art on every page. | with `--activity` |
| `coloring-letter.pdf` | The same, one page per letter sheet. | Line art on every page. | with `--activity` |
| `write-in-letter.pdf` | Line art with writing lines and 田字格 squares for the words. | Line art on every page. | with `--activity` |
| `draw-in-booklet.pdf` | The words with an empty box for each picture. Half-letter booklet. | None. | with `--activity` |
| `draw-in-letter.pdf` | The same, one page per letter sheet, with bigger boxes. | None. | with `--activity` |

A book does not need line art. The colour editions need colour art on every page, from `images/color/`. The colouring and write-in editions need line art on every page, from `images/`.

If the art is not ready, `print` skips those editions and says so, for example `colour art is not finished, so no colour editions`. It also deletes an older PDF of the same name, so a stale file never reaches the printer.

If a page has line art, its colour art must not be older than the line art. If it is older, the colour editions are skipped. Import the colour again.

## Options

| Option | What it does |
| --- | --- |
| `--activity` | Adds the black-and-white editions: draw-in, colouring and write-in. |
| `--only VARIANT` | Builds only one variant: `draw-in`, `write-in` or `full`. It replaces the default choice and ignores `--activity`. |
| `--cast-page` | Adds a page of the characters after the cover. See [Cast page](#cast-page). |
| `--out DIR` | The output folder. Default: `print/` in the current folder. |

`--only full` builds both the colouring editions and the colour editions, because both use the full variant. To build only the colour editions, run `print` with no options.

A book that has no art can print before it has any. Build the draw-in editions:

```
picturebook print examples/pip-forgets --only draw-in
```

You can give several books to one run. They share one `README.txt`.

## Cast page

`--cast-page` adds a page titled "Who is in this book?" after the cover. It shows each character above the name, in English and Chinese. It gives a child something to copy from in the draw-in edition. Every edition in the run gets the page.

The drawings are cropped from art the book already has: the line art, or the colour art for a page with no line art. A file `cast-sheets.json` says which crops.

```json
{
  "pip-forgets": [
    {"id": "pip", "src": "page-01.png", "box": [120, 340, 620, 900]},
    {"id": "pip", "src": "page-05.png", "box": [80, 200, 560, 760]}
  ]
}
```

| Field | Required | What it does |
| --- | --- | --- |
| Top-level key | yes | The name of the book folder. One file can hold several books. |
| `id` | yes | The character id from `characters.json`. |
| `src` | yes | The art file to crop, such as `page-01.png`. |
| `box` | yes | The crop in pixels of `src`: left, top, right, bottom. |
| `name` | no | Object with `en` and `zh`. If it is missing, the name comes from `characters.json`. |

- Several entries can show one character. Only the first one of each `id` has a label.
- The page has 1 column for one entry, 2 columns for up to 4, and 3 for more.
- The tool looks for `cast-sheets.json` in the book folder, then in a `shared/` folder. See [book-file.md](book-file.md#shared-files). A file in the folder that holds the books, outside `shared/`, is not found.
- If the book has no entry, `print` stops with `no cast-sheets.json entry for <book>`.
- The crops need the art files. If a file is missing, the build stops with a Python error.

## print/README.txt

Each run writes `README.txt` in the output folder. It lists every edition and says how to print them. It lists all seven, built or not.

It also says how many sheets a booklet has: the cover, the cast page if there is one, and the pages, four pages to a sheet, rounded up. If the books of the run differ, it gives the count for each one.

A later run writes the file again. If you run `print` for one book and then for another with the same `--out`, the sheet counts are those of the last run.

## Booklet printing

A `*-booklet.pdf` is already laid out as a booklet. Two half-letter pages sit on each landscape letter sheet, in the order that folds into pages 1, 2, 3 and on. The tool adds blank pages to make the count a multiple of four.

1. Print double-sided on letter paper, flipped on the short edge.
2. Fold the stack in half.
3. Staple twice along the fold.

Do not choose "booklet" or "2 pages per sheet" in the print dialog. The file already is one.

A `*-letter.pdf` prints double-sided, flipped on the long edge, which is the usual setting. Staple it at the left edge, or bind it.

Markers show through ordinary copy paper. Use heavier paper, about 28 to 32 lb, or use crayons and pencils.

To make one booklet outside `print`, run `picturebook pdf BOOK --booklet`. It sets `--size half-letter`.

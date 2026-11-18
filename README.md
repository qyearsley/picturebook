# picturebook

Make bilingual picture books. You write the text and the image prompts in one
JSON file. The tool makes print PDFs and an HTML reader, with pinyin above
each Chinese character.

You can make a book with no pictures, with your own pictures, or with
pictures that an image service generates.

## Quick start

You need Python 3.10 or later.

```
git clone https://github.com/qyearsley/picturebook
cd picturebook
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The commands below assume the venv is active. In a new terminal, run
`source .venv/bin/activate` again.

Build the example book with placeholder art:

```
picturebook placeholders examples/pip-forgets
picturebook pdf examples/pip-forgets
picturebook reader examples/pip-forgets
```

The PDF and the reader are in `examples/pip-forgets/build/`. Open
`build/reader/index.html` in a browser.

## Commands

| Command | What it does |
| --- | --- |
| `prompts` | Writes `text-and-prompts.md`, the text and prompts for review. |
| `check` | Checks the verse form or the sentence count of each page. |
| `placeholders` | Writes labelled stand-in images for missing art. |
| `styles` | Tries a few pages in several art styles, through Replicate. |
| `generate` | Generates art candidates, or a prompt queue to paste into any service. |
| `pick` | Rebuilds `pick.html`, the page where you choose candidates. |
| `import` | Files picked or provided images under their page names. |
| `text-positions` | Sets each page's text band from its prompt. |
| `pdf` | Builds one PDF of a book. |
| `reader` | Builds the HTML reader of a book. |
| `print` | Builds the print editions of one or more books: colour by default, `--activity` for the black-and-white ones. |

Run `picturebook <command> --help` for the options of a command.

## Print editions

`picturebook print BOOK...` builds the colour editions, a half-letter booklet
and a letter-size book. A book needs colour art on every page; it does not
need line art. `--activity` adds the black-and-white editions: draw-in,
colouring and write-in. The colouring and write-in editions need line art on
every page, and `print` skips them when it is missing. `--cast-page` adds a
page of the characters after the cover, cropped as `cast-sheets.json` says.

## Make a book with no pictures

The draw-in editions print the words with an empty box where each picture
goes. A child draws the pictures.

```
picturebook print examples/pip-forgets --only draw-in
```

The PDFs are in `print/pip-forgets/`, and `print/README.txt` says how to print
each one.

## Use your own pictures

Put one image per page in the book's `images/` folder. Name them `cover.png`,
`page-01.png`, `page-02.png`, and so on.

Or let `import` name them for you. First run it with no mapping. It copies the
files into `images/_incoming/`, writes a contact sheet, and proposes a mapping.
It files nothing yet:

```
picturebook import examples/pip-forgets ~/my-pictures
```

Then file them with the mapping it printed, edited as you like:

```
picturebook import examples/pip-forgets --map "cover=IMG_0001.png,1=IMG_0002.png"
```

Or file the files in order, oldest file first, with `--by-order`. A file that
the book already has is moved to `images/_replaced/`, never deleted.

## Generate pictures

The art comes in two steps. Line art comes first. Colour is then painted onto
the picked line art, so both keep the same composition. Each step generates
candidates, you pick one per page, and `import` files the picks.

The `manual` backend calls no service. It writes one prompt per page to
`images/_incoming/_queue.md`, for you to paste into any image service. Save
the results into `images/_incoming/`, then file them with `import` as above:

```
picturebook generate examples/pip-forgets --style line
```

The `replicate` backend calls [Replicate](https://replicate.com). It costs
money. Set `REPLICATE_API_TOKEN` first. Try a few pages before you send a whole
book:

```
picturebook generate examples/pip-forgets --backend replicate \
  --model flux-schnell --style line --pages 1,2 --seeds 1234,1235 --delay 11
```

At the end, the run writes `pick.html` in the current folder. Open it, choose
one candidate per page, and copy the commands from the box at the bottom. Run
them from the same folder.

To paint the picked line art, generate with `--style paint`, then pick, and
file the picks with `import --color`. Build with `pdf --color` to use the
colour art.

`--delay 11` keeps under Replicate's limit of 6 predictions a minute, which
applies while an account has less than $5 of credit. An interrupted run can
start again: the cache in `images/.generate-cache.json` skips pages that are
already done.

See `docs/prompt-sheet.md` for how to write a prompt.

## No images in this repo

The repo holds no images and no PDFs. `.gitignore` excludes them, and CI fails
if one is committed. Each person generates or provides their own art.

## License

MIT. See [LICENSE](LICENSE).

Personal educational project by Quinten Yearsley.

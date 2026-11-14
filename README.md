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
.venv/bin/pip install -e .
```

Build the example book with placeholder art:

```
.venv/bin/picturebook placeholders examples/pip-forgets
.venv/bin/picturebook pdf examples/pip-forgets
.venv/bin/picturebook reader examples/pip-forgets
```

The PDF and the reader are in `examples/pip-forgets/build/`. Open
`build/index.html` in a browser.

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
| `print` | Builds every print edition of one or more books. |

Run `picturebook <command> --help` for the options of a command.

## Use your own pictures

Put one image per page in the book's `images/` folder. Name them `cover.png`,
`page-01.png`, `page-02.png`, and so on. Or let `import` file them for you:

```
.venv/bin/picturebook import examples/pip-forgets ~/my-pictures
```

## Generate pictures

The `manual` backend calls no service. It writes one prompt per page to
`images/_incoming/_queue.md`, for you to paste into any image service:

```
.venv/bin/picturebook generate examples/pip-forgets --style line
```

The `replicate` backend calls [Replicate](https://replicate.com). It costs
money. Set `REPLICATE_API_TOKEN` first. Try a few pages before you send a whole
book:

```
.venv/bin/picturebook generate examples/pip-forgets --backend replicate \
  --model flux-schnell --style line --pages 1,2 --seeds 1234,1235 --delay 11
```

Then open `pick.html`, choose one candidate per page, and run the `import`
command that the page gives you. See `docs/prompt-sheet.md` for how to write a
prompt.

## No images in this repo

The repo holds no images and no PDFs. `.gitignore` excludes them, and CI fails
if one is committed. Each person generates or provides their own art.

## License

MIT. See [LICENSE](LICENSE).

Personal educational project by Quinten Yearsley.

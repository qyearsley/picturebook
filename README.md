# picturebook

Make bilingual picture books. You write the text and the image prompts in one JSON file, and the tool makes print PDFs and an HTML reader, with pinyin above each Chinese character.

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

## Docs

| Page | What it covers |
| --- | --- |
| [Book file](docs/book-file.md) | The fields of `book-data.json` and `characters.json`, verse and prose, pinyin, shared files. |
| [Art](docs/art.md) | Books with no pictures, your own pictures, or generated ones: Replicate, cost, the cache, `pick`, `styles`. |
| [Print](docs/print.md) | The print editions, `--activity`, the cast page, booklet printing. |
| [Prompt sheet](docs/prompt-sheet.md) | How to write an image prompt. |

## Develop

Install the dev tools in the repo's `.venv`, and set up the git hooks:

```
pip install -e '.[dev]'
pre-commit install
```

The hooks call `.venv/bin/ruff` and `.venv/bin/python`, so the venv must be
`.venv` in the repo root. To run the checks by hand:

```
ruff check src tests
python -m unittest discover -s tests
```

## No images in this repo

The repo holds no images and no PDFs. `.gitignore` excludes them, and CI fails
if one is committed. Each person generates or provides their own art.

## License

MIT. See [LICENSE](LICENSE).

Personal educational project by Quinten Yearsley.

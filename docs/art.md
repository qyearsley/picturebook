# Art

Use this page to get pictures into a book: with none, with your own, or with pictures an image service generates.

| Path | Cost | Steps |
| --- | --- | --- |
| [No pictures](#no-pictures) | none | A child draws them. |
| [Your own pictures](#your-own-pictures) | none | Put the files in `images/`, or file them with `import`. |
| [Generated pictures](#generate-pictures) | free by hand, paid with Replicate | `generate`, `pick`, `import`. |

For a layout check before any art exists, run `picturebook placeholders BOOK`. It writes labelled stand-in images, and it never overwrites a file that is there. `--force` replaces them and keeps the old ones in `images/_replaced/`.

## No pictures

The draw-in editions print the words with an empty box where each picture goes. A child draws the pictures.

```
picturebook print examples/pip-forgets --only draw-in
```

The PDFs are in `print/pip-forgets/`. See [print.md](print.md) for the other editions.

## Your own pictures

Put one image per page in the book's `images/` folder. Name them `cover.png`, `page-01.png`, `page-02.png`, and so on. The names come from `image` in `book-data.json`.

Or let `import` name them for you. First run it with no mapping. It copies the files into `images/_incoming/`, writes a contact sheet, and proposes a mapping. It files nothing yet:

```
picturebook import examples/pip-forgets ~/my-pictures
```

Then file them with the mapping it printed, edited as you like:

```
picturebook import examples/pip-forgets --map "cover=IMG_0001.png,1=IMG_0002.png"
```

Or file the files in order, oldest file first, with `--by-order`.

- A file that the book already has moves to `images/_replaced/`. `import` never deletes it.
- `import` warns when a file has the wrong shape or is smaller than the print size. It keeps the original unless you pass `--resize`.
- `--resize` crops from the centre to the print shape, applies the EXIF rotation, and flattens transparency onto white.
- `--dry-run` shows what would happen.

## Generate pictures

The art comes in two steps. Line art comes first. Colour is then painted onto the picked line art, so both keep the same composition. Each step generates candidates, you pick one per page, and `import` files the picks.

`generate --style` chooses the step:

| Style | What it makes | Files go to |
| --- | --- | --- |
| `line` | Line art from `line_prompt`. | `images/` |
| `paint` | Colour, painted onto the line art already filed in `images/`. | `images/color/` |
| `color` (default) | Colour from the text prompt alone. | `images/color/` |

Candidates arrive in an `_incoming/` folder inside the folder they will be filed to: `images/_incoming/` for line art, `images/color/_incoming/` for colour. A new run never overwrites an old candidate. Candidates are named `page-04.1.png`, `page-04.2.png`, and so on.

### Choose a backend

The `manual` backend (the default) calls no service. It writes one prompt per page to `_incoming/_queue.md`, for you to paste into any image service. Save the results into `_incoming/`, then file them with `import`:

```
picturebook generate examples/pip-forgets --style line
```

The `replicate` backend calls [Replicate](https://replicate.com). It costs money. Replicate charges for each prediction, so check its current prices. Try a few pages before you send a whole book:

```
picturebook generate examples/pip-forgets --backend replicate \
  --model flux-schnell --style line --pages 1,2 --seeds 1234,1235 --delay 11
```

`--dry-run` prints each prompt as it would be sent. It sends nothing and writes nothing.

### Token

Set `REPLICATE_API_TOKEN` first. If it is not set, the tool reads the macOS Keychain, from a generic password named `replicate-api`. Without a token, the run stops on the first page it would send.

### Models

| Model | Use for | Images per prediction |
| --- | --- | --- |
| `flux-schnell` (default) | `line`, `color` | up to 4 |
| `flux-dev` | `line`, `color` | up to 4 |
| `flux-1.1-pro` | `line`, `color` | 1 |
| `kontext-pro` (default for `paint`) | `paint` | 1 |
| `kontext-max`, `kontext-dev` | `paint` | 1 |

A `kontext` model takes a drawing, so it works only with `--style paint`. The other models work only with `line` and `color`. The tool stops with an error if you mix them.

`--variants N` asks for N images per prediction. A model that returns 1 image ignores it. To get more candidates from such a model, give `--seeds` several numbers. Each seed makes `--variants` images per page.

### Rate limit and --delay

Replicate allows 6 predictions a minute while an account has less than $5 of credit. `--delay 11` keeps under that limit.

The wait happens between predictions that are sent. A cached page does not wait. If Replicate answers with a rate limit (429) anyway, the tool waits at least 10 seconds and tries again, up to 6 times.

### The cache

Each run saves a cache beside the filed art: `images/.generate-cache.json` for line art, and `images/color/.generate-cache.json` for colour and paint. A page that is in the cache is not sent again, so an interrupted run costs nothing to resume.

The cache key covers everything that changes the picture: the prompt text, the aspect, the backend, the model, `--extra`, `--variants`, the seed and the style. For paint it also covers the line drawing, so if you pick a new drawing, the page is painted again.

- If you change a prompt, that page is sent again, and costs money again.
- `--force` sends every page again. It keeps the entries of the other pages.
- The `manual` backend writes no cache entries.
- A page that fails is not cached. The run prints `retry with another --seed: --pages ...` and exits with status 1.

### E005

Replicate flags some prompts as sensitive and reports the code E005. Per the comments in `generate.py`, the flag is often false. The code does not handle E005 on its own: the page fails like any other failed prediction. It costs only that page, and the run goes on.

- In `paint`, set `paint_prompt` on the page. It replaces the colour sentences of `prompt`, which are what paint sends.
- In `line` and `color`, change the wording of the prompt, or run the page again with another `--seed`.

### Line, then paint, then colour

1. Generate line art with `--style line`. `generate` drops the `Keep ...` sentence, the `Palette of ...` sentence, every colour word and the light and shade words from the prompt, because a model that reads "a green t-shirt" fills it in. Write a short `line_prompt` for each page. See [prompt-sheet.md](prompt-sheet.md).
2. Pick and import the line art. It goes to `images/`.
3. Generate colour with `--style paint`. A page with no filed drawing is skipped.
4. Pick and import the colour. It goes to `images/color/`.

`paint` sends the drawing, the colour description of each character on the page (from `description` in `characters.json`), and the colour sentences of the page's `prompt`. Paint sends a character only to the pages that match its `match` expression, because the model draws in anyone it is told about. If it guesses wrong, set `paint_cast` on the page.

### Line art or colour art

Colour art goes in `images/color/`, so it never overwrites the line art. When `images/color/` exists, `import` and `pdf` use it. Pass `--line` to use the line art in `images/` instead. Pass `--color` to use colour art whether or not the folder exists.

The reader does not follow this rule. It uses the line art unless you pass `--color`.

`print` chooses the art for each edition itself. See [print.md](print.md).

## Pick

At the end of a `replicate` run, `generate` writes `pick.html` in the current folder. If a book is outside the current folder, it goes in the folder that holds the books. To rebuild it, run `picturebook pick BOOK...`.

Open it, choose one candidate per page, and copy the commands from the box at the bottom. The commands start with `cd` to the right folder, so you can run them from anywhere. Colour rows have `--color` in their commands.

- A page shows up only while it has a candidate newer than the filed image.
- A colour candidate older than the line drawing was painted from an earlier drawing. It stays hidden until you tick "show variants from older drawings".
- "none good" lists the page as a to-do. It makes no command.
- The page keeps your picks in the browser. If you rebuild it, the picks start again.

## Try art styles

`picturebook styles BOOK` tries the colour prompts of a few pages in several art styles, to help you choose a style block. It needs Replicate and a token, and it costs money.

```
picturebook styles examples/pip-forgets --dry-run
```

| Default | Value |
| --- | --- |
| Pages | 1, 3 and 9. It leaves out a page the book does not have. |
| Seeds | 1234 and 1235 |
| Model | `flux-1.1-pro` |
| Delay | 11 seconds |
| Styles | All ten of them |

With the defaults, a book with those pages sends 60 predictions: 10 styles, 3 pages, 2 seeds. Use `--styles`, `--pages` and `--seeds` to send fewer.

The images go to `images/_styles/`, and `images/_styles/index.html` shows one row per style. A file that is already there is not sent again. The `house` style is your own `style_blocks.color`.

To use a winner, copy its style text into the book's `style_blocks.color`.

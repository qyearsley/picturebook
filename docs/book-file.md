# Book file reference

Use this page to look up a field of `book-data.json` or `characters.json`: what it does, whether it is required, and what the default is.

A book is a folder. It holds `book-data.json`, and usually `characters.json` and an `images/` folder. See `examples/pip-forgets/` for a complete book.

## What a book needs

If a field is not in the table, the tool does not need it. The tool stops with a list of problems if one of these is wrong:

- `book-data.json` is valid JSON.
- `pages` is a list with at least one page.
- Each page has a whole number in `n` and text in `en`.
- Each number the PDF uses (see [Layout](#layout)) is a number.

`check` also needs text in `zh` on each page of a verse book.

## book-data.json

| Field | Required | What it does |
| --- | --- | --- |
| `slug` | no | Names the PDF: `build/<slug>.pdf`. Default: the folder name. |
| `title` | no | Object with `en` and `zh`. Printed on the cover. |
| `author` | no | One line on the cover. |
| `background` | no | Notes about the book. See [Background](#background). |
| `cast` | no | List of character ids from `characters.json`. `generate --style paint` uses it to colour the characters. |
| `page` | no | Trim size and art shape. See [Page](#page). |
| `layout` | no | How the PDF sets the page. See [Layout](#layout). |
| `fonts` | no | Font lists for the PDF. See [Fonts](#fonts). |
| `cover` | no | The cover art. Same fields as a page: `image`, `prompt`, `line_prompt`, `paint_prompt`. |
| `pinyin_overrides` | no | Your own pinyin for a word. See [pinyin_overrides](#pinyin_overrides). |
| `style_blocks` | no | Art style text. See [Style blocks](#style-blocks). |
| `pages` | yes | List of pages. |

The tool does not read `version`, `notes` or `background.meter_en` and `background.no_lesson`. Use them as notes to yourself.

### Pages

| Field | Required | What it does |
| --- | --- | --- |
| `n` | yes | The page number, as a whole number. |
| `en` | yes | The English text. Put a line break (`\n`) between verse lines. |
| `zh` | for verse | The Chinese text. Pinyin goes above each character. |
| `image` | no | The art file name, such as `page-01.png`. Without it, the page has no art file, and `generate`, `import`, `pdf`, `reader` and `placeholders` skip its art. |
| `prompt` | for art | The colour prompt. See [Art](art.md). |
| `line_prompt` | no | The prompt for line art. If it is missing, `generate --style line` uses `prompt`. |
| `paint_prompt` | no | Replaces the colour sentences of `prompt` when `generate --style paint` colours the drawing. |
| `paint_cast` | no | List of character ids to colour on this page. It overrides each character's `match`. |
| `text_position` | no | `top` puts the text band at the top. Any other value, or none, uses `layout.overlay.position`. |
| `notes` | no | Not read. Your notes for the artist. |

`text_position` only matters when the text sits over the art (`layout.text_placement` is `overlay`). The reader ignores it.

`picturebook text-positions` sets `text_position` from the `Keep ...` sentence at the end of each prompt. See [prompt-sheet.md](prompt-sheet.md).

### Background

| Field | Used by |
| --- | --- |
| `synopsis`, `setting`, `cast`, `shape` | `prompts`, which writes them at the top of `text-and-prompts.md`. |
| `form` | `check`. `prose` marks a prose book. See [Prose or verse](#prose-or-verse). |
| `meter_zh` | `check`. The Chinese line shape, such as `5+5 per line`. |

### Page

The defaults are in `DEFAULTS` in `src/picturebook/bookdata.py`. A field you set wins. The PDF fills in a missing `page`, `layout` or `fonts` from them. The reader does not.

| Field | Default | What it does |
| --- | --- | --- |
| `width_in`, `height_in` | 8.0, 10.6667 | The trim size in inches. |
| `art_aspect` | none | The art shape, such as `1:1`. If it is not set, the art takes the shape of the page. |
| `art_px` | 2048 | The long side of the art in pixels. `import --resize` uses it, and only when `art_aspect` is set. |

An activity book sets `art_aspect` to `1:1`. A square prints the same on letter, A4 and half-letter paper.

### Layout

All sizes are in inches, except the type sizes, which are in points.

| Field | Default | What it does |
| --- | --- | --- |
| `margin_in` | 0.55 | The margin on all four sides. |
| `image_height_frac` | 0.6 | The share of the page the art takes, when the text sits below the art. |
| `image_fit` | `cover` | `cover` fills the box and crops. `contain` shows the whole image. |
| `text_placement` | `overlay` | `overlay` puts the text in a band over the art. `below` puts it under the art. |
| `gutter_in` | 0.3 | The gap between the art and the text. |
| `background` | `#fdfcf8` | The page colour. |
| `overlay.color` | `#fdfcf8` | The band colour. |
| `overlay.alpha` | 0.92 | The band opacity. |
| `overlay.padding_in` | 0.34 | The space inside the band. |
| `overlay.band_height_frac` | 0.3 | The band height, as a share of the page. |
| `overlay.position` | `bottom` | `top` or `bottom`. A page's `text_position` wins. |
| `en`, `zh` | see below | Type settings: `size`, `leading`, `color`, `align`. |
| `show_page_numbers` | `true` | Prints the page number. |

| Type setting | `en` | `zh` |
| --- | --- | --- |
| `size` | 18 | 20 |
| `leading` | 24 | 32 |
| `color` | `#20242b` | `#3c4450` |
| `align` | `center` | `center` |

If a text block is too tall for its space, the PDF shrinks the type until it fits.

`pdf --size`, `--profile` and `--variant` change the layout for one build. They never write to `book-data.json`.

### Fonts

`fonts.en` and `fonts.zh` are lists. The PDF uses the first entry that loads. An entry is a built-in font name, a `.ttf` path, or `path.ttc:index` for a font collection. The last entry of each default list is a built-in font, so a build works on any machine. Chinese then falls back to `STSong-Light`, which looks plainer.

`fonts.pinyin` is optional. The font must have the tone marks. If you leave it out, the PDF tries Arial, Georgia and DejaVu Sans.

## Style blocks

A style block is the text that goes in front of every prompt. A book has three: `color`, `line` and `paint`.

`generate` looks for a block in this order, and uses the first it finds:

1. `style_blocks.<style>` in `book-data.json`.
2. `style_blocks.<style>` in `characters.json`.
3. For `color` only, the older `style_block` field of `book-data.json`.

If none exists, `generate` stops with an error that names the style.

## characters.json

The character bible. It sits in the book folder, or in a shared folder (see [Shared files](#shared-files)).

| Field | What it does |
| --- | --- |
| `style_blocks` | The `color`, `line` and `paint` blocks. A book's own `style_blocks` win. |
| `negative_prompts` | Text to keep out of a picture, by style. No current model uses it. |
| `characters` | List of characters. |
| `_comment` | Not read. |

Each entry of `characters`:

| Field | What it does |
| --- | --- |
| `id` | The id that `cast`, `paint_cast` and `cast-sheets.json` use. |
| `name` | Object with `en` and `zh`. The cast page prints it under the drawing. |
| `description` | `generate --style paint` sends it to colour the character. |
| `match` | A regular expression. Paint sends the character only to pages whose `line_prompt` matches. If it is missing, the character goes to every page. |
| `keep_consistent`, `role` | Not read. Your notes. `prompt-sheet.md` says how to use them. |

The tool does not paste a `description` into your prompts for you, except in paint. Copy it into each `prompt` that shows the character.

## Prose or verse

`check` treats a book as one of two forms:

| Form | When | What `check` tests |
| --- | --- | --- |
| Prose | `background.form` is `prose`, or `form` is not set and `meter_zh` is empty. | 2 to 5 English sentences a page, and some Chinese text. |
| Verse | Anything else. | The four tests below. |

For verse, `background.meter_zh` must hold a shape with a plus sign, such as `5+5 per line`. The tool adds the numbers to get the characters per line. If it finds no shape, `check` stops with an error.

1. Each Chinese line has the declared number of characters. Only Han characters count.
2. A page has two Chinese lines, and they rhyme in the 十三辙 groups. The rhyme is on the last character of each line, and the two lines do not rhyme on the same character.
3. Two pages in a row do not use the same rhyme group.
4. The English of each page is two lines.

`check` reads the pinyin the same way as the reader, with your `pinyin_overrides`. A word like 行 is measured as a reader says it. The exit status is 1 if any page needs a look.

## Languages and pinyin

A book has English text (`en`) and Chinese text (`zh`). `pdf` needs `en` only. A page with no `zh` prints no Chinese.

`pinyin.py` puts pinyin above each Han character, in the PDF and in the reader. Other characters, such as punctuation, get none. It follows textbook rules:

- It reads a whole run of Han characters at once, so a character gets the reading that fits its word.
- It uses base tones. Third-tone sandhi is off, so 只好 is zhǐ hǎo.
- 一 and 不 change tone before another syllable, as textbooks print them. `reader --no-sandhi` turns this off. `pdf` and `check` always apply it.
- A short list of words has a neutral second syllable: 爸爸 is bà ba. The list is `DEFAULT_WORDS` in `pinyin.py`.
- 得 after a verb is read as de, except in a few words that keep dé, such as 得意 and 取得.

### pinyin_overrides

If a reading is wrong, add the word to `pinyin_overrides`. The value has one syllable for each character, separated by spaces:

```json
"pinyin_overrides": {
  "一颗": "yì kē",
  "埋得": "mái de"
}
```

- An override wins over every automatic rule, including the list of words and the 一 and 不 changes.
- If two overrides overlap, the longer word wins. 十一颗 beats the 一颗 inside it.
- If the number of syllables does not match the number of characters, the tool skips the override and says nothing.
- A word cannot span punctuation, because the tool reads each run of Han characters on its own.

## Shared files

Several books can share one `characters.json` and one `cast-sheets.json`. The tool looks for the file in this order:

1. The book folder.
2. A `shared/` folder in each parent folder, nearest first.

```
books/
  shared/
    characters.json
    cast-sheets.json
  pip-forgets/
    book-data.json
```

A `characters.json` in the book folder hides the shared one. The tool does not merge them.

A file next to the books, outside `shared/`, is not found.

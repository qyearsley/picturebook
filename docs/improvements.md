# picturebook — improvements

## At a glance

1. Book files need every layout and font field — M · open
2. No `picturebook new` command — S · open
3. Docs are one README — M · open
4. Placeholder footer text hides under the text band — S · open
5. The private books repo still has its own copy of the scripts — M · open

## 1. Book files need every layout and font field

`pdf` reads `layout`, `fonts` and `page` straight from `book-data.json`, so a
new book has to copy all of them from the example. Put the defaults in code,
validate the file, and name the field and the page in each error.

## 2. No `picturebook new` command

A new user copies `examples/pip-forgets` by hand. A `new` command could write a
minimal `book-data.json` and `characters.json`, or read a Markdown story.

## 3. Docs are one README

Split out: the book file reference, the three art paths, generating art (cost,
rate limits, E005 flags), print options, languages and pinyin.

## 4. Placeholder footer text hides under the text band

"PLACEHOLDER — replace with final art" sits near the bottom of the image, where
the overlay band covers it.

## 5. The private books repo still has its own copy of the scripts

Point it at this package and delete its `scripts/`. Its `shared/characters.json`
needs a `match` field per character, which replaced the old hard-coded
`CAST_WORDS`, or paint sends every character to every page.

# Prompt sheet

How to write an image prompt that gives you a picture instead of a stage
direction.

## The shape of a prompt

The tool puts the master style block on the front of every prompt for you.
What you write in the page's `prompt` field is everything after it, in this
order:

```
<camera and composition>  <the subject, doing something>  <light>  <palette>  <character description>  <one background detail>  <where the negative space goes>
```

Every one of those seven parts earns its place. A prompt that names only the
subject gives you a generic picture, because the service chooses the camera,
the light and the colour for you, and it chooses differently every time.

Weak:

```
A squirrel burying an acorn in the woods.
```

Strong:

```
Low ground-level view across the autumn woodland floor. A fluffy-tailed light
gray squirrel with a tiny tan canvas satchel digs a small hole with both paws,
an acorn held in its mouth, tail curled high. Low golden afternoon light, long
shadows through the oak trunks. Palette of russet leaf litter, bark brown, gold
light. One fern stands beside the hole. Keep the top of the frame open for
text.
```

## Camera and composition

Name one. Do not let the service pick.

- Low worm's-eye angle, high overhead, straight down, flat side-on, extreme
  close macro, wide with the subject small.
- Say where the subject sits in the frame.
- Vary the camera between pages. A book where every page is a mid-shot of a
  child at eye level reads as flat, however good each picture is.
- Eye level is the child's, not an adult's, unless you are choosing otherwise
  on purpose.

## Light

Name the time of day and the direction. Hard midday, low gold late afternoon,
cold blue morning through a window, backlit against a blazing sky, one slice
of moonlight. Light does more for mood than expression does.

## Palette

Give three or four colours and one accent. Naming the palette is what makes
ten pages look like one book. It is also how you make a page land: on Pip
Forgets page 9 the whole effect is that green arrives after four cold pages.

## Character description

Each character's description is in the book's `characters.json`. Copy it exactly,
and do not reword it between pages. If a character drifts between pages, add
the drifting detail to `keep_consistent` there and regenerate the page.

## One background detail

Put one thing in the frame that the text never mentions. The other squirrel's
footprints on Pip Forgets page 6 are one. This is what makes a book worth a
second reading, and a 5-year-old will find all of them.

## Where the negative space goes

End every prompt with a sentence that starts `Keep`. Say which part of the
frame to leave quiet, because the text sits over it.

`picturebook text-positions` reads that sentence. If it says `Keep the top...` or
`Keep the upper...` or names the sky, the page's `text_position` is set to
`top`. If it names the bottom, the page goes back to the default band, at the
bottom. If it names neither, the page keeps the `text_position` it has. So the
sentence is not a note to yourself, it drives the layout. Before it rewrites
`book-data.json`, the command copies the file to `book-data.json.bak`.

## Line prompts

Line art uses the page's `line_prompt`, not `prompt`. Write two to four plain
sentences about one action. flux-schnell loses camera jargon, panels, head
counts and explanations.

To generate and file the art, see "Generate pictures" in `README.md`.

## What to avoid

- Frightening faces, sharp teeth, deep shadows.
- Extra fingers and warped hands. Check every hand before you accept an image.
- Modern logos, brand marks, and readable signage.
- Text of any kind in the image. The book puts the words on top.

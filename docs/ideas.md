# picturebook — ideas

Feature ideas. Not committed to. Defects and debt are in
[`improvements.md`](improvements.md).

## Reference images to stop character drift

`generate --style color` sends text only, so FLUX redraws each character from
the words on every page. Faces, facial hair, heights and the head count
drift, and attributes bleed between characters (a boy gets the girl's
headband).

Option: a reference-image backend that sends one picked portrait per
character with the page prompt, through a multi-image editing model. Check
the model names and prices on Replicate before building it. Deferred
2026-11-18.

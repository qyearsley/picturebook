"""Write pick.html: every unpicked variant, one row per page, click to choose.

Usage:
    picturebook pick BOOK [BOOK ...]

Scans `images/_incoming` and `images/color/_incoming` in each book, and writes
pick.html in the folder that holds the books. A page shows up when it has a variant newer than the image filed
for it, so a page drops off the list once a pick is imported. Colour rows are
labelled as such, and their commands carry `--color`.

Click a variant to pick it, "keep current" to keep the filed image, or "none
good" to mark the page for another try.
The box at the bottom turns the picks into `picturebook import --map` commands,
one per book. The rejects are listed below the box as a to-do, not as
commands. Copy takes both. Each row shows the page's verse and its prompt.

Variants are newest first, and the ones from the latest run are marked "new".
A colour row also shows the drawing filed for the page. A colour variant older
than that drawing was painted from an earlier one, so it is hidden unless
"show variants from older drawings" is ticked.

Picks are kept in the browser's local storage, so reloading the page loses
nothing. Rebuilding the page starts the picks afresh.

`picturebook generate` runs this at the end of every run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from .bookdata import images_dir

OUT_NAME = "pick.html"
VARIANT = re.compile(r"^(cover|page-(\d+))\.(\d+)\.png$")
# Variants this close to the newest one anywhere count as the latest run.
LATEST_RUN_S = 30 * 60


def page_entries(project: Path) -> dict[str, dict]:
    """The cover and pages of a book's book-data.json, keyed by image stem."""
    try:
        data = json.loads((project / "book-data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = {"cover": data.get("cover") or {}}
    for page in data.get("pages", []):
        entries[f"page-{int(page.get('n', 0)):02d}"] = page
    return entries


def root_of(projects: list[Path]) -> Path:
    """The folder that holds all the books. pick.html goes here."""
    return Path(os.path.commonpath([p.parent for p in projects]))


def pages_to_pick(projects: list[Path]) -> list[dict]:
    """One entry per page that has variants newer than its filed image."""
    rows = []
    root = root_of(projects)
    books = sorted(projects)
    for project, color in [(p, c) for p in books for c in (False, True)]:
        images = images_dir(project, color)
        incoming = images / "_incoming"
        if not incoming.is_dir():
            continue
        entries = page_entries(project)
        by_page: dict[str, list[Path]] = {}
        for path in incoming.glob("*.png"):
            match = VARIANT.match(path.name)
            if match:
                by_page.setdefault(match[1], []).append(path)
        for stem in sorted(by_page, key=lambda s: (s != "cover", s)):
            filed = images / f"{stem}.png"
            since = filed.stat().st_mtime if filed.exists() else 0
            fresh = [p for p in by_page[stem] if p.stat().st_mtime > since]
            if not fresh:
                continue
            fresh.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            # A colour variant older than the filed drawing was painted from
            # an earlier one.
            drawing = project / "images" / f"{stem}.png" if color else None
            drawn = drawing.stat().st_mtime if drawing and drawing.exists() else 0
            entry = entries.get(stem, {})
            prompt = entry.get("prompt", "") if color else (
                entry.get("line_prompt") or entry.get("prompt", ""))
            rows.append({
                "text": entry.get("en", ""),
                "prompt": prompt,
                "book": project.relative_to(root).as_posix(),
                "color": color,
                "page": "cover" if stem == "cover" else str(int(stem[5:])),
                "filed": filed.relative_to(root).as_posix() if filed.exists() else "",
                "drawing": drawing.relative_to(root).as_posix() if drawn else "",
                "variants": [{"path": p.relative_to(root).as_posix(),
                              "mtime": p.stat().st_mtime,
                              "old": p.stat().st_mtime < drawn} for p in fresh],
            })
    newest = max((v["mtime"] for r in rows for v in r["variants"]), default=0)
    for r in rows:
        for v in r["variants"]:
            v["new"] = v["mtime"] > newest - LATEST_RUN_S
    return rows


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Pick images</title>
<style>
  body { font: 14px/1.4 -apple-system, sans-serif; margin: 1.5rem; background: #fbfaf7; }
  h2 { margin: 2rem 0 0.5rem; }
  .row { display: flex; gap: 0.6rem; align-items: flex-start; margin: 0.4rem 0 1rem; flex-wrap: wrap; }
  .label { width: 7rem; font-weight: 600; }
  figure { margin: 0; cursor: pointer; border: 4px solid transparent; }
  figure img { width: 220px; display: block; background: white; }
  figure figcaption { font-size: 11px; color: #777; text-align: center; }
  figure.current { cursor: default; opacity: 0.55; }
  figure.drawing { cursor: default; }
  figure.old { opacity: 0.7; }
  figure .tag { color: #2a9d4b; font-weight: 600; }
  figure.old .tag { color: #c0392b; }
  .hidden-note { align-self: center; color: #999; font-size: 12px; }
  body:not(.show-old) figure.old { display: none; }
  body.show-old .hidden-note { display: none; }
  figure.picked { border-color: #2a9d4b; }
  button.none { height: 2.2rem; align-self: center; }
  button.none.on { background: #c0392b; color: white; }
  button.keep.on { background: #2a9d4b; color: white; }
  #out { position: sticky; bottom: 0; background: #fff; border-top: 2px solid #ccc; padding: 0.8rem; }
  textarea { width: 100%; height: 9rem; font: 12px monospace; }
  .words { flex-basis: 100%; }
  .words > div { max-width: 60rem; }
  figure.drawing img { outline: 1px dashed #bbb; }
  .words .verse { white-space: pre-line; font-size: 15px; }
  .words .prompt { font-size: 12px; color: #666; margin-top: 0.2rem; }
  #redo { font: 12px monospace; white-space: pre-line; margin-top: 0.4rem; }
</style>
<h1>Pick images</h1>
<p>Click the best variant for each page. Click it again to unpick. The faded
image "now" is what the book has now. In a colour row, "drawing" is the line
art the paint should start from. Newest variants come first. "Keep current"
keeps the filed image and drops the page from this list. "None good" marks the
page to regenerate.</p>
<label><input type="checkbox" id="showold"> show variants from older drawings</label>
<div id="rows"></div>
<div id="out">
  <b>Commands</b> (run from __ROOT__)
  <button onclick="navigator.clipboard.writeText([document.getElementById('cmd').value, document.getElementById('redo').textContent].filter(Boolean).join('\\n\\n'))">Copy</button>
  <button onclick="localStorage.removeItem(KEY); location.reload()">Clear picks</button>
  <textarea id="cmd" readonly></textarea>
  <div id="redo"></div>
</div>
<script>
const ROWS = __ROWS__;
const BUILD = __BUILD__;
const KEY = "pick-state";
// Picks from an earlier build of this page name files that may be gone.
const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
const state = saved.__build === BUILD ? saved : {__build: BUILD};
const showOld = document.getElementById("showold");
showOld.onchange = () => document.body.classList.toggle("show-old", showOld.checked);
const id = r => r.book + ":" + r.page + (r.color ? ":color" : "");
const group = r => r.book + (r.color ? " --color" : "");
const base = p => p.split("/").pop();
const esc = s => s.replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const rowsEl = document.getElementById("rows");
let book = "";
for (const r of ROWS) {
  if (group(r) !== book) {
    book = group(r);
    rowsEl.insertAdjacentHTML("beforeend", `<h2>${r.book}${r.color ? " (colour)" : ""}</h2>`);
  }
  const row = document.createElement("div");
  row.className = "row";
  row.innerHTML = `<div class="label">${r.page === "cover" ? "cover" : "page " + r.page}</div>`;
  if (r.text || r.prompt) {
    row.insertAdjacentHTML("beforeend", `<div class="words">` +
      (r.text ? `<div class="verse">${esc(r.text)}</div>` : "") +
      (r.prompt ? `<div class="prompt">${esc(r.prompt)}</div>` : "") + `</div>`);
  }
  if (r.drawing) {
    row.insertAdjacentHTML("beforeend",
      `<figure class="drawing"><img src="${r.drawing}?${Date.now()}"><figcaption>drawing</figcaption></figure>`);
  }
  if (r.filed) {
    row.insertAdjacentHTML("beforeend",
      `<figure class="current"><img src="${r.filed}?${Date.now()}"><figcaption>now</figcaption></figure>`);
  }
  for (const v of r.variants) {
    const name = base(v.path);
    const f = document.createElement("figure");
    if (v.old) f.className = "old";
    const tag = v.old ? " <span class=tag>old drawing</span>" : v.new ? " <span class=tag>new</span>" : "";
    f.innerHTML = `<img loading="lazy" src="${v.path}"><figcaption>${name}${tag}</figcaption>`;
    f.onclick = () => { state[id(r)] = state[id(r)] === name ? undefined : name; render(); };
    f.dataset.key = id(r); f.dataset.file = name;
    row.appendChild(f);
  }
  const old = r.variants.filter(v => v.old).length;
  if (old) {
    row.insertAdjacentHTML("beforeend", `<div class="hidden-note">${old} from an older drawing hidden` +
      (old === r.variants.length ? " (nothing new: paint again)" : "") + `</div>`);
  }
  if (r.filed) {
    const keep = document.createElement("button");
    keep.className = "none keep"; keep.textContent = "keep current"; keep.dataset.key = id(r);
    keep.onclick = () => { state[id(r)] = state[id(r)] === "KEEP" ? undefined : "KEEP"; render(); };
    row.appendChild(keep);
  }
  const none = document.createElement("button");
  none.className = "none"; none.textContent = "none good"; none.dataset.key = id(r);
  none.onclick = () => { state[id(r)] = state[id(r)] === "NONE" ? undefined : "NONE"; render(); };
  row.appendChild(none);
  rowsEl.appendChild(row);
}
function render() {
  localStorage.setItem(KEY, JSON.stringify(state));
  document.querySelectorAll("figure[data-key]").forEach(f =>
    f.classList.toggle("picked", state[f.dataset.key] === f.dataset.file));
  document.querySelectorAll("button.none").forEach(b =>
    b.classList.toggle("on", state[b.dataset.key] === (b.classList.contains("keep") ? "KEEP" : "NONE")));
  const picks = {}, redo = {}, keeps = [];
  for (const r of ROWS) {
    const s = state[id(r)];
    if (s === "NONE") (redo[group(r)] ||= []).push(r.page);
    else if (s === "KEEP") keeps.push(r.filed);
    else if (s) (picks[group(r)] ||= []).push(`${r.page}=${s}`);
  }
  const lines = [];
  for (const [g, m] of Object.entries(picks)) {
    const [b, flag] = g.split(" ");
    lines.push(`picturebook import ${b} --map "${m.join(",")}"${flag ? " " + flag : ""}`);
  }
  // A filed image newer than its variants drops the page off this list.
  if (keeps.length) lines.push(`touch ${keeps.join(" ")}`);
  document.getElementById("cmd").value = lines.join("\\n");
  // Rejects are a to-do list, not commands, so they stay out of the Copy box.
  const todo = Object.entries(redo).map(([b, p]) => `${b}: pages ${p.join(",")}`);
  document.getElementById("redo").textContent =
    todo.length ? "To regenerate (not commands):\\n" + todo.join("\\n") : "";
}
render();
</script>
"""


def write_pick_page(projects: list[Path]) -> Path:
    projects = [p.expanduser().resolve() for p in projects]
    root = root_of(projects)
    rows = pages_to_pick(projects)
    # Inside <script> nothing is entity-decoded, so only "</" needs guarding.
    data = json.dumps(rows).replace("</", "<\\/")
    page = (PAGE.replace("__ROWS__", data)
            .replace("__BUILD__", json.dumps(str(time.time())))
            .replace("__ROOT__", str(root)))
    out = root / OUT_NAME
    out.write_text(page, encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("projects", nargs="+", type=Path, help="book folders")
    args = ap.parse_args(argv)
    print(f"  open {write_pick_page(args.projects)}")

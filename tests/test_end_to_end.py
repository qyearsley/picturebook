"""Build the example book from a clean copy, the way the README tells a new user to."""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from picturebook import cli
from picturebook.bookdata import CHARACTERS_KEY, load_book, shared_file

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "pip-forgets"


def run(*argv: str) -> str:
    """Run one command and return what it printed. A non-zero exit raises."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            cli.main(list(argv))
        except SystemExit as exit_:
            if exit_.code not in (0, None):
                raise
    return out.getvalue()


class ExampleBookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.book = self.tmp / "pip-forgets"
        shutil.copytree(EXAMPLE, self.book, ignore=shutil.ignore_patterns("images", "build"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_pdf_with_no_art(self):
        run("pdf", str(self.book))
        pdf = self.book / "build" / "pip-forgets.pdf"
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))

    def test_placeholders_then_pdf_and_reader(self):
        run("placeholders", str(self.book))
        with Image.open(self.book / "images" / "page-01.png") as img:
            self.assertEqual(img.width, img.height, "the example book wants square art")
        run("pdf", str(self.book), "--variant", "all")
        run("reader", str(self.book))
        html = (self.book / "build" / "reader" / "index.html").read_text(encoding="utf-8")
        self.assertIn("<ruby>", html)
        self.assertIn("Pip Forgets", html)

    def test_print_draw_in_editions(self):
        out = self.tmp / "print"
        run("print", str(self.book), "--out", str(out), "--only", "draw-in")
        self.assertTrue((out / "pip-forgets" / "pip-forgets-draw-in-letter.pdf").exists())
        self.assertTrue((out / "README.txt").exists())

    def test_manual_backend_writes_a_queue(self):
        run("generate", str(self.book), "--style", "line")
        queue = self.book / "images" / "_incoming" / "_queue.md"
        self.assertIn("squirrel", queue.read_text(encoding="utf-8"))

    def test_manual_backend_writes_no_cache_and_claims_nothing_sent(self):
        out = run("generate", str(self.book), "--style", "line")
        again = run("generate", str(self.book), "--style", "line")
        self.assertFalse((self.book / "images" / ".generate-cache.json").exists())
        for text in (out, again):
            self.assertIn("queued, none sent", text)
            self.assertNotIn("cached", text)
            self.assertNotIn(" sent,", text)

    def test_dry_run_names_each_seed(self):
        out = run("generate", str(self.book), "--style", "line", "--backend", "replicate",
                  "--seeds", "1234,1235", "--pages", "1", "--dry-run")
        self.assertIn("seed 1234", out)
        self.assertIn("seed 1235", out)

    def fails_with(self, *argv: str) -> str:
        """The message of a clean exit. A traceback would be another exception."""
        with self.assertRaises(SystemExit) as caught:
            run(*argv)
        self.assertIsInstance(caught.exception.code, str)
        return caught.exception.code

    def test_import_from_a_missing_folder_is_a_clean_error(self):
        message = self.fails_with("import", str(self.book), str(self.tmp / "missing-folder"))
        self.assertIn("missing-folder", message)

    def test_bad_seeds_are_a_clean_error(self):
        self.assertIn("--seeds", self.fails_with(
            "generate", str(self.book), "--seeds", "a,b", "--dry-run"))

    def test_a_page_the_book_lacks_is_a_clean_error(self):
        self.assertIn("no page 99", self.fails_with(
            "generate", str(self.book), "--pages", "99", "--dry-run"))

    def test_an_unknown_model_is_a_clean_error_even_in_a_dry_run(self):
        self.assertIn("unknown model 'nope'", self.fails_with(
            "generate", str(self.book), "--model", "nope", "--dry-run"))

    def test_a_page_with_no_image_key_is_skipped_by_generate(self):
        data = json.loads((self.book / "book-data.json").read_text(encoding="utf-8"))
        del data["pages"][0]["image"]
        (self.book / "book-data.json").write_text(json.dumps(data), encoding="utf-8")
        out = run("generate", str(self.book), "--style", "line", "--dry-run")
        self.assertIn("skipping, no image name in book-data.json: page 1", out)
        self.assertNotIn("page-01.png", out)
        self.assertIn("page-02.png", out)

    def test_text_positions_keeps_hand_set_values_and_writes_a_backup(self):
        path = self.book / "book-data.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        pages = data["pages"]
        pages[0]["prompt"] = "A squirrel. Keep the lower third clear."
        pages[0]["text_position"] = "top"          # the sentence says bottom: cleared
        pages[1]["prompt"] = "A squirrel on a log."  # no Keep sentence
        pages[1]["text_position"] = "top"          # set by hand: kept
        pages[2]["prompt"] = "A squirrel. Keep the top clear."
        pages[2].pop("text_position", None)         # the sentence says top: added
        pages[3]["prompt"] = "A squirrel. Keep the middle quiet."
        pages[3]["text_position"] = "top"          # neither: kept
        path.write_text(json.dumps(data), encoding="utf-8")
        before = path.read_text(encoding="utf-8")
        run("text-positions", str(self.book))
        after = json.loads(path.read_text(encoding="utf-8"))["pages"]
        self.assertNotIn("text_position", after[0])
        self.assertEqual(after[1]["text_position"], "top")
        self.assertEqual(after[2]["text_position"], "top")
        self.assertEqual(after[3]["text_position"], "top")
        self.assertEqual(
            (self.book / "book-data.json.bak").read_text(encoding="utf-8"), before)

    def test_prompts_and_check(self):
        run("prompts", str(self.book))
        self.assertTrue((self.book / "text-and-prompts.md").exists())
        self.assertIn("0 page(s) to look at", run("check", str(self.book)))


class SharedFileTest(unittest.TestCase):
    def test_book_folder_wins_then_a_parent_shared_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            book = root / "projects" / "a"
            book.mkdir(parents=True)
            (book / "book-data.json").write_text('{"pages": []}', encoding="utf-8")
            self.assertIsNone(shared_file(book, "characters.json"))
            (root / "shared").mkdir()
            (root / "shared" / "characters.json").write_text(
                json.dumps({"characters": [{"id": "x"}]}), encoding="utf-8")
            self.assertEqual(shared_file(book, "characters.json"),
                             root / "shared" / "characters.json")
            self.assertEqual(load_book(book)[CHARACTERS_KEY]["characters"][0]["id"], "x")
            (book / "characters.json").write_text("{}", encoding="utf-8")
            self.assertEqual(shared_file(book, "characters.json"), book / "characters.json")


class CliTest(unittest.TestCase):
    def test_help_lists_every_command(self):
        text = run("--help")
        for name in cli.COMMANDS:
            self.assertIn(name, text)

    def test_unknown_command_exits(self):
        with self.assertRaises(SystemExit):
            run("nope")


class ReplicateFailureTest(unittest.TestCase):
    """Paid-for work is never lost or wrongly cached. No network is used."""

    def test_download_failure_names_the_url(self):
        import urllib.error
        from unittest import mock

        from picturebook import backends

        err = urllib.error.URLError("connection reset")
        with mock.patch("urllib.request.urlopen", side_effect=err), \
                mock.patch("time.sleep"):
            with self.assertRaises(backends.PredictionFailed) as caught:
                backends.download("https://replicate.delivery/x.png")
        self.assertIn("https://replicate.delivery/x.png", str(caught.exception))

    def test_a_reply_with_no_image_is_not_cached(self):
        from unittest import mock

        from picturebook import backends

        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "pip-forgets"
            shutil.copytree(EXAMPLE, book, ignore=shutil.ignore_patterns("images", "build"))

            def empty(self, job, out_dir):
                return backends.Result(job=job, note="no image returned (failed)")

            with mock.patch.object(backends.ReplicateBackend, "submit", empty):
                with self.assertRaises(SystemExit) as caught:
                    run("generate", str(book), "--backend", "replicate", "--style", "line",
                        "--pages", "1")
            self.assertEqual(caught.exception.code, 1)
            cache = book / "images" / ".generate-cache.json"
            entries = json.loads(cache.read_text()) if cache.exists() else {}
            self.assertEqual(entries, {})


class ReaderEditionTest(unittest.TestCase):
    def test_each_edition_has_its_own_folder_and_no_stale_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "pip-forgets"
            shutil.copytree(EXAMPLE, book, ignore=shutil.ignore_patterns("images", "build"))
            run("placeholders", str(book))
            color = book / "images" / "color"
            color.mkdir()
            for png in (book / "images").glob("*.png"):
                shutil.copy2(png, color / png.name)
            run("reader", str(book))
            run("reader", str(book), "--color", "--web")
            line = {p.name for p in (book / "build" / "reader" / "images").iterdir()}
            web = {p.name for p in (book / "build" / "reader-color-web" / "images").iterdir()}
            self.assertIn("page-01.png", line)
            self.assertIn("page-01.jpg", web)
            self.assertFalse(any(n.endswith(".png") for n in web))
            # A page that loses its art also loses its stale copy.
            (book / "images" / "page-02.png").unlink()
            run("reader", str(book))
            self.assertNotIn("page-02.png",
                             {p.name for p in (book / "build" / "reader" / "images").iterdir()})


class PickPageTest(unittest.TestCase):
    def test_pick_html_goes_in_the_current_folder_with_relative_paths(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            book = root / "My Books" / "Pip Forgets"
            shutil.copytree(EXAMPLE, book, ignore=shutil.ignore_patterns("images", "build"))
            incoming = book / "images" / "_incoming"
            incoming.mkdir(parents=True)
            (incoming / "page-01.1.png").write_bytes(b"x")
            old = os.getcwd()
            os.chdir(root)
            try:
                run("pick", "My Books/Pip Forgets")
            finally:
                os.chdir(old)
            html = (root / "pick.html").read_text(encoding="utf-8")
            self.assertIn('"book": "My Books/Pip Forgets"', html)
            self.assertIn("My Books/Pip Forgets/images/_incoming/page-01.1.png", html)
            # The import commands must run in a shell without the venv active.
            from picturebook.pick import command_path
            self.assertIn(f"const CMD = {json.dumps(command_path())};", html)
            # The commands cd to the root first, so they run from any folder.
            self.assertIn(f"const ROOT = {json.dumps(str(root))};", html)
            self.assertIn("`cd ${q(ROOT)}`", html)
            # Commands and the redo list copy separately.
            self.assertIn('id="copy-cmd"', html)
            self.assertIn('id="copy-redo"', html)

    def test_command_path_is_the_script_beside_the_interpreter(self):
        import sys
        from unittest import mock

        from picturebook.pick import command_path

        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp).resolve()
            (bin_dir / "python").write_text("")
            with mock.patch.object(sys, "executable", str(bin_dir / "python")):
                self.assertEqual(command_path(), "picturebook")
                (bin_dir / "picturebook").write_text("")
                self.assertEqual(command_path(), str(bin_dir / "picturebook"))


class PrintEditionsTest(unittest.TestCase):
    """`print` builds colour by default and does not need line art."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.book = self.tmp / "pip-forgets"
        shutil.copytree(EXAMPLE, self.book, ignore=shutil.ignore_patterns("images", "build"))
        self.out = self.tmp / "print"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def names(self) -> list[str]:
        data = load_book(self.book)
        return [e["image"] for e in [data["cover"], *data["pages"]] if e.get("image")]

    def paint(self, color: bool) -> None:
        folder = self.book / "images" / ("color" if color else "")
        folder.mkdir(parents=True, exist_ok=True)
        for name in self.names():
            Image.new("RGB", (64, 64), "orange" if color else "white").save(folder / name)

    def built(self) -> set[str]:
        return {p.name.removeprefix("pip-forgets-") for p in (self.out / "pip-forgets").glob("*.pdf")}

    def test_colour_only_book_gets_colour_editions_by_default(self):
        self.paint(color=True)
        run("print", str(self.book), "--out", str(self.out))
        self.assertEqual(self.built(), {"color-booklet.pdf", "color-letter.pdf"})

    def test_activity_skips_line_art_editions_without_line_art(self):
        self.paint(color=True)
        printed = run("print", str(self.book), "--out", str(self.out), "--activity")
        self.assertEqual(self.built(), {"color-booklet.pdf", "color-letter.pdf",
                                        "draw-in-booklet.pdf", "draw-in-letter.pdf"})
        self.assertIn("line art is not finished", printed)

    def test_activity_with_line_art_builds_everything(self):
        self.paint(color=False)
        self.paint(color=True)
        run("print", str(self.book), "--out", str(self.out), "--activity")
        self.assertEqual(len(self.built()), 7)

    def test_no_colour_art_means_no_colour_editions(self):
        self.paint(color=False)
        printed = run("print", str(self.book), "--out", str(self.out))
        self.assertEqual(self.built(), set())
        self.assertIn("colour art is not finished", printed)

    def test_colour_older_than_line_art_is_stale(self):
        from picturebook.editions import color_is_current
        self.paint(color=True)
        self.assertTrue(color_is_current(self.book))
        self.paint(color=False)
        line = self.book / "images" / self.names()[0]
        stamp = line.stat().st_mtime + 10
        os.utime(line, (stamp, stamp))
        self.assertFalse(color_is_current(self.book))

    def test_cast_crop_falls_back_to_colour_art(self):
        from picturebook.pdf import cast_source
        self.paint(color=True)
        name = self.names()[0]
        self.assertEqual(cast_source(self.book, name), self.book / "images" / "color" / name)
        self.paint(color=False)
        self.assertEqual(cast_source(self.book, name), self.book / "images" / name)

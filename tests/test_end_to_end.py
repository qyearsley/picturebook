"""Build the example book from a clean copy, the way the README tells a new user to."""

from __future__ import annotations

import contextlib
import io
import json
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

    def test_dry_run_names_each_seed(self):
        out = run("generate", str(self.book), "--style", "line", "--backend", "replicate",
                  "--seeds", "1234,1235", "--pages", "1", "--dry-run")
        self.assertIn("seed 1234", out)
        self.assertIn("seed 1235", out)

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

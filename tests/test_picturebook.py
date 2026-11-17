"""Unit tests for the pure parts of the book scripts.

Run from the repo root:

    .venv/bin/python -m unittest discover -s tests

Most examples here come from the comments in the scripts, which record real
prompts and real verse that once went wrong.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from picturebook import check as check_verse
from picturebook import generate as generate_images
from picturebook import importer as import_images
from picturebook.bookdata import CHARACTERS_KEY, parse_ratio
from picturebook.pdf import booklet_sheets, wrap_cjk, wrap_latin, zh_rows
from picturebook.pinyin import cells, ruby_html

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class ForStyleTest(unittest.TestCase):
    """Line art drops colour and light, and nothing else."""

    def line(self, prompt: str) -> str:
        return generate_images.for_style(prompt, "line")

    def test_colour_and_light_go_in_line_art(self):
        self.assertEqual(
            self.line("A boy in a green t-shirt and red sneakers."),
            "A boy in a t-shirt and sneakers.")
        self.assertEqual(self.line("A creek bed, a tunnel with coins of dappled light."),
                         "A creek bed, a tunnel.")

    def test_hyphenated_colour_goes_whole(self):
        self.assertEqual(self.line("A burnt-orange scarf."), "A scarf.")

    def test_palette_and_keep_sentences_go(self):
        self.assertEqual(
            self.line("A crow on a stump. Palette of dusk orange and violet. "
                      "Keep the top of the frame quiet for text."),
            "A crow on a stump.")

    def test_a_flashlight_is_an_object_not_a_light(self):
        self.assertEqual(self.line("A boy holds a flashlight under the bed."),
                         "A boy holds a flashlight under the bed.")

    def test_delight_is_not_light(self):
        self.assertEqual(self.line("Her face full of delight."), "Her face full of delight.")

    def test_colour_style_is_untouched(self):
        prompt = "A green t-shirt in dappled light."
        self.assertEqual(generate_images.for_style(prompt, "color"), prompt)


class AspectTest(unittest.TestCase):
    def test_from_page_size(self):
        self.assertEqual(generate_images.aspect_ratio({"width_in": 6, "height_in": 9}), "2:3")

    def test_art_aspect_and_override_win(self):
        self.assertEqual(generate_images.aspect_ratio({"art_aspect": "1:1"}), "1:1")
        self.assertEqual(generate_images.aspect_ratio({"art_aspect": "1:1"}, "3:4"), "3:4")

    def test_parse_ratio(self):
        self.assertEqual(parse_ratio("2:3"), (2.0, 3.0))
        self.assertIsNone(parse_ratio("square"))
        self.assertIsNone(parse_ratio("0:3"))

    def test_import_target_size(self):
        self.assertEqual(import_images.target_size({"width_in": 6, "height_in": 9}), (1800, 2700))
        self.assertEqual(import_images.target_size({"art_aspect": "1:1", "art_px": 1024}),
                         (1024, 1024))


class RhymeTest(unittest.TestCase):
    def test_finals(self):
        cases = {
            "yě": "ie",    # 也: y is spelling, not an initial
            "xiè": "ie",
            "yuè": "ve",
            "yǒu": "iou",
            "yī": "i",
            "yún": "vn",
            "wǒ": "uo",
            "wǔ": "u",
            "wèi": "uei",
            "qù": "v",     # 去 is qü
            "zhāng": "ang",
        }
        for syllable, final in cases.items():
            with self.subTest(syllable=syllable):
                self.assertEqual(check_verse.final_of(syllable), final)

    def test_ye_rhymes_with_xie(self):
        self.assertEqual(check_verse.rhyme_group("yě"), check_verse.rhyme_group("xiè"))
        self.assertEqual(check_verse.rhyme_group("yě"), "乜斜")


class RubyTest(unittest.TestCase):
    def test_longer_override_wins(self):
        # 十一颗 must beat 一颗 sitting inside it.
        overrides = {"一颗": "yì kē", "十一颗": "shí yī kē"}
        html = ruby_html("十一颗", overrides)
        self.assertIn("<ruby>一<rt>yī</rt></ruby>", html)

    def test_punctuation_passes_through(self):
        self.assertEqual(ruby_html("，"), "，")


def readings(text, overrides=None):
    return " ".join(py for _, py in cells(text, overrides) if py)


class PinyinTest(unittest.TestCase):
    def test_third_tone_keeps_its_base_tone(self):
        # Textbooks print zhǐ hǎo and xiǎo shǒu, not the spoken sandhi.
        self.assertEqual(readings("只好"), "zhǐ hǎo")
        self.assertEqual(readings("小手指"), "xiǎo shǒu zhǐ")

    def test_yi_follows_the_next_tone(self):
        self.assertEqual(readings("一块"), "yí kuài")
        self.assertEqual(readings("一根"), "yì gēn")
        self.assertEqual(readings("星期一。"), "xīng qī yī")
        self.assertEqual(readings("十一"), "shí yī")

    def test_yi_between_a_doubled_verb_is_neutral(self):
        self.assertEqual(readings("找一找"), "zhǎo yi zhǎo")
        self.assertEqual(readings("看一看"), "kàn yi kàn")

    def test_bu_changes_only_before_a_fourth_tone(self):
        self.assertEqual(readings("不见"), "bú jiàn")
        self.assertEqual(readings("不停"), "bù tíng")

    def test_kin_words_end_in_a_neutral_tone(self):
        self.assertEqual(readings("弟弟"), "dì di")
        self.assertEqual(readings("姐姐"), "jiě jie")

    def test_de_particle_is_neutral_but_deyi_is_not(self):
        self.assertEqual(readings("看得到"), "kàn de dào")
        self.assertEqual(readings("睡得香"), "shuì de xiāng")
        self.assertEqual(readings("真得意"), "zhēn dé yì")

    def test_book_override_beats_a_default(self):
        self.assertEqual(readings("弟弟", {"弟弟": "dì dì"}), "dì dì")


class BookTextTest(unittest.TestCase):
    """Catches text bugs that once reached the books."""

    def test_no_broken_characters_or_straight_quotes_in_chinese(self):
        paths = sorted(EXAMPLES.glob("*/book-data.json"))
        self.assertTrue(paths, f"no example books found in {EXAMPLES}")
        for path in paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            texts = [data["title"]["zh"]] + [p.get("zh", "") for p in data["pages"]]
            for text in texts:
                self.assertNotIn("\ufffd", text, path.parent.name)
                self.assertNotIn('"', text, path.parent.name)


class WrapTest(unittest.TestCase):
    def test_wrapped_paragraph_is_balanced(self):
        # Helvetica 10 pt: a width that fits all but the last word greedily.
        text = "Then the snow melted off and the ground turned to mud,"
        full = wrap_latin(text, "Helvetica", 10, 10000)
        self.assertEqual(len(full), 1)
        greedy_width = 215  # greedy leaves "mud," alone at this width
        lines = wrap_latin(text, "Helvetica", 10, greedy_width)
        self.assertEqual(len(lines), 2)
        self.assertGreater(len(lines[1].split()), 2)

    def test_closing_mark_never_starts_a_line(self):
        # Helvetica has no CJK widths, so every character measures the same.
        lines = wrap_cjk("一二三四。", "Helvetica", 10, 22)
        for line in lines:
            self.assertNotEqual(line[:1], "。")

    def test_zh_rows_split_evenly(self):
        # 16 characters too long for one row read as 8 and 8, not 15 and 1.
        rows, _ = zh_rows("一" * 16, width=72 * 5, cell_in=0.6, min_cell_in=0.6)
        self.assertEqual(rows, [8, 8])


class BookletTest(unittest.TestCase):
    def test_eight_pages_fold_in_order(self):
        self.assertEqual(booklet_sheets(8),
                         [(7, 0), (1, 6), (5, 2), (3, 4)])

    def test_pads_to_four_with_blanks(self):
        self.assertEqual(booklet_sheets(3), [(None, 0), (1, 2)])

    def test_every_page_appears_once(self):
        for count in range(1, 15):
            pages = [p for side in booklet_sheets(count) for p in side if p is not None]
            self.assertEqual(sorted(pages), list(range(count)))


CAST = {"characters": [
    {"id": "corvus", "name": {"en": "Corvus"}, "description": "A black crow.",
     "match": r"\bcrow\b"},
    {"id": "pip", "name": {"en": "Pip"}, "description": "A gray squirrel.",
     "match": r"\bsquirrel\b"},
]}


class CastColoursTest(unittest.TestCase):
    def test_only_the_cast_the_page_shows(self):
        data = {"cast": ["corvus", "pip"], CHARACTERS_KEY: CAST}
        entry = {"line_prompt": "A crow on a stump."}
        text = generate_images.cast_colours(data, entry)
        self.assertIn("Corvus", text)
        self.assertNotIn("Pip", text)

    def test_a_character_with_no_match_goes_to_every_page(self):
        cast = {"characters": [{"id": "pip", "name": {"en": "Pip"},
                                "description": "A gray squirrel."}]}
        data = {"cast": ["pip"], CHARACTERS_KEY: cast}
        entry = {"line_prompt": "A crow on a stump."}
        self.assertIn("Pip", generate_images.cast_colours(data, entry))

    def test_paint_cast_overrides_the_guess(self):
        data = {"cast": ["corvus", "pip"], CHARACTERS_KEY: CAST}
        entry = {"line_prompt": "A crow on a stump.", "paint_cast": []}
        self.assertEqual(generate_images.cast_colours(data, entry), "")


class ImportTest(unittest.TestCase):
    """A plain scan proposes. It never files."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.targets = {"cover": "cover.png", "1": "page-01.png", "2": "page-02.png"}

    def tearDown(self):
        self.dir.cleanup()

    def files(self, *names: str) -> list[Path]:
        """Make the files, oldest first, as sources() returns them."""
        out = []
        now = time.time()
        for i, name in enumerate(names):
            path = self.root / name
            path.write_bytes(b"")
            os.utime(path, (now + i, now + i))
            out.append(path)
        return out

    def test_named_files_propose_the_newest_variant(self):
        files = self.files("page-01.1.png", "page-01.2.png")
        guess = import_images.propose(self.targets, files)
        self.assertEqual(guess["1"].name, "page-01.2.png")

    def test_loose_files_fill_the_pages_left_over(self):
        files = self.files("page-01.1.png", "IMG_1.png", "IMG_2.png")
        guess = import_images.propose(self.targets, files)
        self.assertEqual({page: path.name for page, path in guess.items()},
                         {"cover": "IMG_1.png", "1": "page-01.1.png", "2": "IMG_2.png"})

    def test_by_order_without_a_cover(self):
        targets = {"1": "page-01.png", "2": "page-02.png"}
        files = self.files("IMG_1.png", "IMG_2.png")
        self.assertEqual(list(import_images.by_order(targets, files)), ["1", "2"])

    def test_dry_run_with_no_map_files_nothing(self):
        project = self.root / "book"
        incoming = project / "images" / "_incoming"
        incoming.mkdir(parents=True)
        (project / "book-data.json").write_text(
            '{"page": {}, "pages": [{"n": 1, "image": "page-01.png"}]}')
        from PIL import Image
        Image.new("RGB", (4, 4)).save(project / "images" / "page-01.png")
        Image.new("RGB", (4, 4)).save(incoming / "page-01.1.png")
        before = (project / "images" / "page-01.png").read_bytes()
        args = type("Args", (), {"map": "", "by_order": False, "resize": False,
                                 "color": False, "dry_run": False})()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            import_images.run(project, args)
        self.assertEqual((project / "images" / "page-01.png").read_bytes(), before)
        self.assertFalse((project / "images" / "_replaced").exists())


if __name__ == "__main__":
    unittest.main()

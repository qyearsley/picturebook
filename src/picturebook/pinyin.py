"""Pinyin for the Chinese text, shared by the HTML reader and the PDF builder.

The readings are textbook pinyin: base tones, with no third-tone sandhi (so
只好 stays zhǐ hǎo). Only 一 and 不 change tone, as textbooks print them.
Each book's `pinyin_overrides` win over every automatic reading.
"""

from __future__ import annotations

import html

from pypinyin import Style, pinyin

from .bookdata import is_han

TONE_MARKS = {
    1: "āēīōūǖ",
    2: "áéíóúǘ",
    3: "ǎěǐǒǔǚ",
    4: "àèìòùǜ",
}

# Words pypinyin reads with the wrong tone, or with a full tone where
# textbooks print a neutral one. A book's own `pinyin_overrides` win over these.
DEFAULT_WORDS = {
    "爸爸": "bà ba", "妈妈": "mā ma", "哥哥": "gē ge", "姐姐": "jiě jie",
    "弟弟": "dì di", "妹妹": "mèi mei", "爷爷": "yé ye", "奶奶": "nǎi nai",
    "看看": "kàn kan", "说说": "shuō shuo", "抖抖": "dǒu dou",
    "东西": "dōng xi", "时候": "shí hou", "衣服": "yī fu", "力气": "lì qi",
    "事情": "shì qing", "糊涂": "hú tu", "招呼": "zhāo hu", "糊糊": "hū hu",
    "上面": "shàng mian", "里面": "lǐ mian", "重来": "chóng lái",
    "头发": "tóu fa", "耳朵": "ěr duo", "点点头": "diǎn dian tóu", "玩玩": "wán wan",
}

# 得 after a verb is the particle de. It keeps its full tone dé only in these
# words. A bare 得到 at the start of a run is "to get"; 看得到 is "can see".
DE_FULL_TONE = ("得意", "得分", "得罪", "取得", "获得", "难得")

# 一 keeps its own tone after these, as in 十一 and 第一.
YI_STAYS = set("零〇十百千万第")


def tone_of(syllable: str) -> int:
    """Return the tone number 1-4 of a syllable, or 0 for a neutral tone."""
    for tone, marks in TONE_MARKS.items():
        if any(m in syllable for m in marks):
            return tone
    return 0


def _read_run(run: str) -> list[str]:
    readings = pinyin(run, style=Style.TONE, heteronym=False)
    return [r[0] if r else "" for r in readings]


def _apply_overrides(run: str, syllables: list[str], overrides: dict[str, str]) -> list[bool]:
    """Overlay manual corrections. Return which positions they claimed."""
    claimed = [False] * len(run)
    # Longest word first, so 十一颗 beats the 一颗 sitting inside it.
    for word in sorted(overrides, key=len, reverse=True):
        fixed = overrides[word].split()
        if len(fixed) != len(word):
            continue
        start = run.find(word)
        while start != -1:
            end = start + len(word)
            if not any(claimed[start:end]):
                syllables[start:end] = fixed
                claimed[start:end] = [True] * len(word)
            start = run.find(word, start + 1)
    return claimed


def _apply_de(run: str, syllables: list[str], claimed: list[bool]) -> None:
    """Read 得 as the particle de, unless it sits in a word that keeps dé."""
    for i, ch in enumerate(run):
        if claimed[i] or ch != "得":
            continue
        if any(w in run[max(i - 1, 0):i + 2] for w in DE_FULL_TONE):
            continue
        if run[i:i + 2] == "得到" and i == 0:
            continue
        syllables[i] = "de"


def _apply_yi_bu(run: str, syllables: list[str], claimed: list[bool]) -> None:
    """一 and 不 change tone before another syllable: yí/yì and bú."""
    for i, ch in enumerate(run):
        if claimed[i] or ch not in "一不" or i + 1 >= len(run):
            continue
        next_tone = tone_of(syllables[i + 1])
        if ch == "不":
            syllables[i] = "bú" if next_tone == 4 else "bù"
        elif i > 0 and run[i - 1] in YI_STAYS:
            syllables[i] = "yī"
        elif i > 0 and run[i - 1] == run[i + 1]:
            syllables[i] = "yi"  # 看一看: a doubled verb takes a neutral yi.
        elif next_tone == 4:
            syllables[i] = "yí"
        elif next_tone:
            syllables[i] = "yì"
        else:
            syllables[i] = "yī"


def cells(text: str, overrides: dict[str, str] | None = None,
          tone_change: bool = True) -> list[tuple[str, str]]:
    """Return (character, pinyin) for every character in `text`.

    Pinyin is "" for anything that is not a Han character. It is read a whole
    run at a time, so pypinyin can pick the right reading in context.
    """
    overrides = {**DEFAULT_WORDS, **(overrides or {})}
    out: list[tuple[str, str]] = []
    i, n = 0, len(text)
    while i < n:
        if not is_han(text[i]):
            out.append((text[i], ""))
            i += 1
            continue
        j = i
        while j < n and is_han(text[j]):
            j += 1
        run = text[i:j]
        syllables = _read_run(run)
        claimed = _apply_overrides(run, syllables, overrides)
        _apply_de(run, syllables, claimed)
        if tone_change:
            _apply_yi_bu(run, syllables, claimed)
        out.extend(zip(run, syllables))
        i = j
    return out


def ruby_html(text: str, overrides: dict[str, str] | None = None,
              tone_change: bool = True) -> str:
    """Wrap every Han character in <ruby> with its pinyin in <rt>."""
    parts = []
    for ch, syllable in cells(text, overrides, tone_change):
        if syllable:
            parts.append(f"<ruby>{html.escape(ch)}<rt>{html.escape(syllable)}</rt></ruby>")
        else:
            parts.append(html.escape(ch))
    return "".join(parts)

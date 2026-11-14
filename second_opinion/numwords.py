"""Numbers written as words: "ninety-seven", "eleven hundred", "a hundred and thirty-nine", "five dozen".

One reader for the rules (extract.py) and the AI quote check (ai/executor.py), so a number the rules read
from a sentence is the same number the AI is allowed to quote from it. Shares written as fractions
("one in fifteen", "nine in every hundred", "one tumour in eight") are read here too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
TEENS = {
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
SCALES = {"hundred": 100, "thousand": 1000, "dozen": 12}
WORDS = {"zero": 0, **UNITS, **TEENS, **TENS}

_KIND = {**{w: "unit" for w in UNITS}, **{w: "teen" for w in TEENS}, **{w: "tens" for w in TENS},
         **{w: w for w in SCALES}, "zero": "zero", "a": "a", "an": "a"}
# What may follow each kind of word inside one number ("forty" "seven", "eleven" "hundred", ...).
_NEXT = {
    "start": {"unit", "teen", "tens", "zero", "a"},
    "a": {"hundred", "thousand", "dozen"},
    "unit": {"hundred", "thousand", "dozen"},
    "teen": {"hundred", "thousand", "dozen"},
    "tens": {"unit", "thousand"},
    "hundred": {"unit", "teen", "tens", "thousand"},
    "thousand": {"unit", "teen", "tens"},
    "dozen": set(),
    "zero": set(),
}
_TOKENS = "|".join(sorted([*WORDS, *SCALES, "a", "an"], key=len, reverse=True))
_TOKEN = re.compile(rf"\b(?:{_TOKENS}|and)\b", re.IGNORECASE)
_JOIN = re.compile(r"[\s-]+")
_COUNT_NOUNS = r"tumou?rs?|patients?|samples?|cases?|wom[ae]n|m[ae]n|people|persons?"
_PHRASE = rf"(?:{_TOKENS})(?:(?:[\s-]+|\s+and\s+)(?:{_TOKENS}))*"
_FRACTION = re.compile(
    rf"\b(?P<num>{_PHRASE}|\d+)(?:\s+(?:{_COUNT_NOUNS}))?\s+(?:in|out\s+of)\s+(?:every\s+)?"
    rf"(?P<den>{_PHRASE}|\d{{1,3}}(?:,\d{{3}})+|\d+)\b(?!\s*(?:%|per\s*cent))",
    re.IGNORECASE,
)


@dataclass
class WordNumber:
    start: int
    end: int
    value: float


def _value(words: list[str], bare_scale: bool = False) -> float | None:
    """The number these words spell, or None when they are not one number."""
    if not words:
        return None
    kinds = [_KIND.get(w.lower()) for w in words]
    if None in kinds or kinds[-1] == "a":
        return None
    if bare_scale and kinds[0] in SCALES:
        kinds = ["a", *kinds]
        words = ["a", *words]
    total, current, last = 0, 0, "start"
    for word, kind in zip(words, kinds):
        if kind not in _NEXT[last]:
            return None
        w = word.lower()
        if kind == "a":
            current = 1
        elif kind in ("unit", "teen", "tens", "zero"):
            current += WORDS[w]
        elif kind == "thousand":
            total += (current or 1) * 1000
            current = 0
        else:  # hundred, dozen
            current = (current or 1) * SCALES[w]
        last = kind
    return float(total + current)


def number_value(text: str, bare_scale: bool = False) -> float | None:
    """'ninety-seven' -> 97, 'a hundred and thirty-nine' -> 139; None unless the whole text is one number.

    bare_scale lets 'hundred' alone mean 100, as in 'nine in every hundred'.
    """
    words = [w for w in _JOIN.split(text.strip()) if w]
    if not words or words[-1].lower() == "and":
        return None
    joined: list[str] = []
    for i, w in enumerate(words):
        if w.lower() == "and":  # only inside a number, after hundred or thousand: "a hundred and nine"
            if not joined or _KIND.get(joined[-1].lower()) not in ("hundred", "thousand"):
                return None
            continue
        joined.append(w)
    return _value(joined, bare_scale)


def word_numbers(text: str) -> list[WordNumber]:
    """Every number written as words, longest phrase first: 'one thousand two hundred and forty-seven' is one."""
    tokens = list(_TOKEN.finditer(text))
    found: list[WordNumber] = []
    i = 0
    while i < len(tokens):
        if tokens[i].group().lower() == "and":
            i += 1
            continue
        best: tuple[int, float] | None = None  # (index of the last token, value)
        j = i
        while j < len(tokens):
            if j > i and not _JOIN.fullmatch(text[tokens[j - 1].end():tokens[j].start()]):
                break
            phrase = text[tokens[i].start():tokens[j].end()]
            value = number_value(phrase)
            if value is not None:
                best = (j, value)
            elif tokens[j].group().lower() != "and" and best is not None and j > best[0] + 1:
                break
            j += 1
        if best is None:
            i += 1
            continue
        found.append(WordNumber(tokens[i].start(), tokens[best[0]].end(), best[1]))
        i = best[0] + 1
    return found


def _amount(raw: str) -> float | None:
    raw = raw.strip()
    if raw.replace(",", "").isdigit():
        return float(raw.replace(",", ""))
    return number_value(raw, bare_scale=True)


def fraction_amounts(text: str) -> list[WordNumber]:
    """Shares written as fractions, as a percent: 'one in fifteen' 6.67, 'nine in every hundred' 9."""
    found: list[WordNumber] = []
    for m in _FRACTION.finditer(text):
        num, den = _amount(m.group("num")), _amount(m.group("den"))
        if num is None or not den or num > den:
            continue
        if m.group("num").strip().isdigit() and m.group("den").replace(",", "").isdigit() and den > 20:
            continue  # "5 in 1,000" style numbers are counts, read elsewhere
        found.append(WordNumber(m.start(), m.end(), 100.0 * num / den))
    return found

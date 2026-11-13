"""Read a Markdown report: cut it into sentences (B1), then pick out the claims (B2)."""

from __future__ import annotations

import re

from second_opinion.model import SentenceInfo

# Words that end with a period but don't end a sentence ("e.g. Luminal A", "et al. Reported").
# Compared lower-case, without the final period. Single letters are left out on purpose:
# "Luminal A." and "Luminal B." end sentences in these reports.
ABBREVIATIONS = {
    "e.g", "i.e", "al", "vs", "cf", "fig", "figs", "approx", "ca", "c", "no", "nos",
    "dr", "mr", "mrs", "ms", "prof", "st", "u.s", "resp", "eq", "ref", "refs", "vol",
}

_FENCE = re.compile(r"^\s*(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}#{1,6}(\s|$)")
_RULE = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+")
_BLOCKQUOTE = re.compile(r"^\s*(>\s?)+")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_EMPHASIS_UNDERSCORE = re.compile(r"(?<!\w)_+|_+(?!\w)")  # keeps snake_case like protein_rppa

# Candidate end of sentence: . ! or ? (plus closing quotes/brackets), whitespace, then a capital,
# a digit, or an opening quote/bracket.
_BOUNDARY = re.compile(r"[.!?]+[\"'”’)\]]*(\s+)(?=[A-Z0-9\"'“‘(\[])")


def split_sentences(report_text: str) -> list[SentenceInfo]:
    """Cut a Markdown report into sentences, in order, with `index` counting from 0."""
    sentences: list[str] = []
    for block in _blocks(report_text):
        sentences.extend(_split_block(_clean_inline(block)))
    return [SentenceInfo(index=i, text=text, claim_id=None) for i, text in enumerate(sentences)]


def _blocks(report_text: str) -> list[str]:
    """Group lines into paragraphs, bullets and table rows; drop headings, rules and code."""
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    in_bullet = False

    def flush() -> None:
        nonlocal in_bullet
        if current:
            blocks.append(" ".join(current))
            current.clear()
        in_bullet = False

    for raw in _HTML_COMMENT.sub("", report_text).splitlines():
        if _FENCE.match(raw):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        line = _BLOCKQUOTE.sub("", raw)
        stripped = line.strip()
        if not stripped or _HEADING.match(line) or _RULE.match(line) or _TABLE_SEPARATOR.match(line):
            flush()
            continue

        if stripped.startswith("|"):
            flush()
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            blocks.append(" | ".join(cell for cell in cells if cell))
            continue

        bullet = _BULLET.match(line)
        if bullet:
            flush()
            current.append(line[bullet.end():].strip())
            in_bullet = True
            continue

        # A continuation line: joins the open paragraph or bullet.
        current.append(stripped)

    flush()
    return blocks


def _clean_inline(text: str) -> str:
    """Strip Markdown emphasis, code ticks and link syntax, keeping the words."""
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    text = text.replace("`", "").replace("*", "")
    text = _EMPHASIS_UNDERSCORE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _split_block(text: str) -> list[str]:
    if not text:
        return []
    pieces: list[str] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        before = text[start:match.start()]
        last_word = before.rsplit(None, 1)[-1] if before.strip() else ""
        if last_word.lstrip("(\"'“‘[").lower() in ABBREVIATIONS:
            continue
        pieces.append(text[start:match.start(1)].strip())
        start = match.end()
    pieces.append(text[start:].strip())
    return [piece for piece in pieces if piece]

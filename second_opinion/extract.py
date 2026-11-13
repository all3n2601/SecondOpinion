"""Read a Markdown report: cut it into sentences (B1), then pick out the claims (B2).

Claim typing is a fixed list of rules, first match wins (see `classify_sentence`). Every keyword
list and pattern is a module-level constant so a new trap can be handled by adding a word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from second_opinion.model import Claim, ClaimParams, ClaimType, ExtractResult, SentenceInfo
from second_opinion.unanswerable import detect_unanswerable
from second_opinion.variants import normalise_subtype

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


# ---------------------------------------------------------------------------------------------
# B2: claim typing and number parsing
# ---------------------------------------------------------------------------------------------

APPROXIMATE_WORDS = (
    "about", "roughly", "nearly", "around", "approximately", "almost", "circa", "c.", "ca.",
    "close to", "some", "~", "≈",
)
# Words a count can be about, and which kind of thing they count.
COUNT_NOUNS = {
    "primary tumors": "primary_tumors", "primary tumours": "primary_tumors",
    "primary tumor": "primary_tumors", "primary tumour": "primary_tumors",
    "tumors": "primary_tumors", "tumours": "primary_tumors", "tumor": "primary_tumors", "tumour": "primary_tumors",
    "samples": "samples", "sample": "samples", "specimens": "samples", "aliquots": "samples",
    "patients": "patients", "patient": "patients", "women": "patients", "men": "patients",
    "cases": "patients", "case": "patients", "individuals": "patients", "participants": "patients",
    "donors": "patients", "people": "patients",
}
# Sub-groups a count can be restricted to. The subject becomes "<filter>_<noun>", e.g.
# "male_samples"; checks that don't know a subject say so instead of counting everyone.
COUNT_FILTERS = {
    "male": r"\bmales?\b|\bmen\b",
    "female": r"\bfemales?\b|\bwomen\b",
    "normal_tissue": r"\bnormal[\s-]+(?:tissue|adjacent|breast|solid)|\bsolid tissue normal|\badjacent normal|\bnormal samples?\b",
    "metastatic": r"\bmetasta\w*",
}
# Data layers, as they may be written. The key is the `has_<layer>` subject name.
LAYERS = {
    "survival": r"\bsurvival\b",
    "mutation": r"\b(?:somatic\s+)?mutations?\b|\bmutation\s+calls?\b",
    "copy_number": r"\bcopy[\s-]+number\b|\bCNVs?\b|\bGISTIC\b",
    "rna": r"\bRNA(?:[\s-]?seq)?\b(?![\s-]+subtype)|\bgene expression\b|\bmRNA\b",
    "protein": r"\bprotein\b|\bRPPA\b",
}
ALL_LAYERS = re.compile(
    r"\ball\s+(?:of\s+the\s+)?(?:five|5|four|4)?\s*(?:available\s+)?(?:data\s+)?(?:layers|data\s+types)"
    r"|\bevery\s+(?:data\s+)?layer|\b(?:five|5)\s+(?:data\s+)?layers",
    re.IGNORECASE,
)
HAVE_WORDS = re.compile(r"\b(?:have|has|had|having|with|include|includes|included|carry|carries|contain|contains)\b", re.IGNORECASE)
EVERY_WORDS = re.compile(
    r"\b(?:every|each|all)\b(?:\s+[\d,]+)?\s+(?:of\s+the\s+)?(?:[\d,]+\s+)?(?:primary\s+)?"
    r"(?:tumou?rs?|samples?|patients?|cases?)\b",
    re.IGNORECASE,
)
# Subtypes. "HER2" counts as the subtype only when it is not a receptor status ("HER2-positive").
SUBTYPE_PATTERN = re.compile(
    r"\bLum(?:inal)?[\s-]*[AB]\b"
    r"|\bHER-?2(?:[\s-]*enriched)?\b(?![\s-]*(?:positive|negative|pos\b|neg\b|status|amplif|protein|levels?|\+|/neu))"
    r"|\bBasal(?:[\s-]*like)?\b"
    r"|\bNormal[\s-]*like\b",
    re.IGNORECASE,
)
# Receptor-status groups for comparisons: "ER-positive", "HER2 negative", "PR+".
GROUP_PATTERN = re.compile(
    r"\b(?:ER|PR|HER-?2(?:/neu)?|estrogen[\s-]+receptor|progesterone[\s-]+receptor)"
    r"(?:[\s-]?(?:positive|negative|pos|neg)\b|[+−-](?![\w]))",
    re.IGNORECASE,
)
MEASURES = (  # (pattern, measure name the comparison check knows)
    (r"\bER[\s-]?(?:alpha|α)\b|\bERα|\bestrogen[\s-]+receptor[\s-]+alpha\b|\bERALPHA\b|\bESR1\b", "ER-alpha protein"),
    (r"\bHER-?2(?:/neu)?\s+(?:protein|levels?|expression|abundance)\b", "HER2 protein"),
)
# Any other "<GENE-LIKE NAME> protein/levels": passed on so the check can say the release lacks it.
OTHER_MEASURE = re.compile(r"\b([A-Z][A-Za-z0-9]*[A-Z0-9][A-Za-z0-9-]*)\s+(?:protein|levels?|abundance)\b")
DIRECTIONS = {
    "higher": ("higher", "greater", "more", "elevated", "increased", "larger", "stronger"),
    "lower": ("lower", "less", "reduced", "decreased", "smaller", "weaker"),
}
# Numbers after these words are references, not data: "Figure 2", "version 3".
REFERENCE_WORDS = re.compile(r"(?:figure|fig\.|table|section|version|v|step|chapter|appendix|ref\.?|page)\s*$", re.IGNORECASE)
WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}

_NUM = r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?!\w|,\d|\.\d)"
_NUMBER = re.compile(_NUM)
_PERCENT_AFTER = re.compile(r"\s*(?:%|percent\b|per\s+cent\b)", re.IGNORECASE)
_RANGE = re.compile(
    r"(?P<between>between\s+)?"
    r"(?<![\w.,])(?P<lo>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<lodec>\d+))?\s*(?:%|percent\b|per\s+cent\b)?\s*"
    r"(?P<sep>–|—|-|to|and)\s*"
    r"(?P<hi>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<hidec>\d+))?(?!\w|,\d|\.\d)",
    re.IGNORECASE,
)
_WORD_NUMBER = re.compile(
    r"\b(" + "|".join(WORD_NUMBERS) + r")\b(?=(?:\s+[\w-]+){0,2}?\s+(?:" + "|".join(sorted(COUNT_NOUNS, key=len, reverse=True)) + r")\b)",
    re.IGNORECASE,
)
_TOTAL_BEFORE = re.compile(r"\b(?:of|out\s+of|among)\s+(?:the\s+|all\s+|these\s+)?$", re.IGNORECASE)
_APPROX_BEFORE = re.compile(
    r"(?:^|[\s(])(?:" + "|".join(re.escape(w) for w in APPROXIMATE_WORDS) + r")\s*$", re.IGNORECASE
)
_BOUND_BEFORE = re.compile(
    r"\b(?:more|fewer|less|greater|higher|lower)\s+than\s+$|\b(?:at\s+least|at\s+most|over|under|above|below|up\s+to|exceeds?|exceeding)\s+$",
    re.IGNORECASE,
)
_YEAR = re.compile(r"^(?:19|20)\d\d$")


@dataclass
class StatedNumber:
    start: int
    end: int
    value: float
    decimals: int
    percent: bool
    approximate: bool
    bound: bool  # "more than 500": we don't check one-sided bounds yet
    high: float | None = None  # upper end of a range
    is_total: bool = False  # the "1,101" in "535 of 1,101"


def _to_float(whole: str, frac: str | None) -> float:
    return float(whole.replace(",", "") + (f".{frac}" if frac else ""))


def find_numbers(text: str) -> list[StatedNumber]:
    """Every number in the sentence that states data (not years or figure references)."""
    found: list[StatedNumber] = []
    taken: list[tuple[int, int]] = []

    def context(start: int) -> tuple[bool, bool, bool]:
        before = text[:start]
        return (
            bool(_APPROX_BEFORE.search(before)),
            bool(_BOUND_BEFORE.search(before)),
            bool(_TOTAL_BEFORE.search(before)),
        )

    for m in _RANGE.finditer(text):
        sep = m.group("sep").lower()
        if sep == "and" and not m.group("between"):
            continue
        low = _to_float(m.group("lo"), m.group("lodec"))
        high = _to_float(m.group("hi"), m.group("hidec"))
        if high <= low:
            continue
        approx, bound, total = context(m.start())
        end = m.end()
        tail = _PERCENT_AFTER.match(text, end)
        if tail:
            end = tail.end()
        percent = bool(tail) or "%" in m.group(0) or "percent" in m.group(0).lower()
        found.append(StatedNumber(m.start(), end, low, len(m.group("lodec") or ""), percent, approx, bound, high, total))
        taken.append((m.start(), end))

    for m in _NUMBER.finditer(text):
        if any(a <= m.start() < b for a, b in taken):
            continue
        whole, frac = m.group(1), m.group(2)
        before = text[: m.start()]
        if REFERENCE_WORDS.search(before):
            continue
        tail = _PERCENT_AFTER.match(text, m.end())
        if _YEAR.match(whole) and not frac and not tail and not _counted_noun_follows(text, m.end()):
            continue
        approx, bound, total = context(m.start())
        found.append(StatedNumber(
            m.start(), tail.end() if tail else m.end(), _to_float(whole, frac), len(frac or ""),
            bool(tail), approx, bound, None, total,
        ))

    for m in _WORD_NUMBER.finditer(text):
        approx, bound, total = context(m.start())
        found.append(StatedNumber(m.start(), m.end(), float(WORD_NUMBERS[m.group(1).lower()]), 0, False, approx, bound, None, total))

    return sorted(found, key=lambda n: n.start)


def _counted_noun_follows(text: str, end: int) -> bool:
    nouns = "|".join(sorted(COUNT_NOUNS, key=len, reverse=True))
    return bool(re.match(rf"(?:\s+[\w-]+){{0,2}}?\s+(?:{nouns})\b", text[end:], re.IGNORECASE))


def _stated(params: ClaimParams, number: StatedNumber, total: StatedNumber | None = None) -> None:
    params.stated_value = number.value
    params.stated_high = number.high
    params.decimals = number.decimals
    params.approximate = number.approximate
    if total is not None:
        params.stated_total = total.value


def _value_and_total(numbers: list[StatedNumber]) -> tuple[StatedNumber | None, StatedNumber | None]:
    """The stated count and, for "535 of 1,101" / "Of the 1,101 ..., 535", the total."""
    totals = [n for n in numbers if n.is_total and not n.percent]
    values = [n for n in numbers if not n.is_total and not n.percent]
    value = values[0] if values else None
    total = totals[0] if totals and value is not None else None
    return value, total


_COUNT_NOUN = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in sorted(COUNT_NOUNS, key=len, reverse=True)) + r")\b", re.IGNORECASE
)


def _count_subject(text: str, after: int = 0) -> str | None:
    """"male_samples", "primary_tumors", ...; None when no count noun is named.

    The noun counted is the first one after the stated number ("12 samples are from male
    patients" counts samples), else the first one in the sentence ("Of the 1,101 primary
    tumors, 12 are male").
    """
    noun = _COUNT_NOUN.search(text, after) or _COUNT_NOUN.search(text)
    if noun is None:
        return None
    kind = COUNT_NOUNS[noun.group(1).lower()]
    filters = [name for name, pattern in COUNT_FILTERS.items() if re.search(pattern, text, re.IGNORECASE)]
    if len(filters) > 1:
        return "+".join(filters) + f"_{kind}"
    return f"{filters[0]}_{kind}" if filters else kind


def _layers(text: str) -> list[str]:
    have = HAVE_WORDS.search(text)
    if not have:
        return []
    after = text[have.start():]
    return [layer for layer, pattern in LAYERS.items() if re.search(pattern, after, re.IGNORECASE)]


def _subtypes(text: str) -> list[str]:
    names: list[str] = []
    for m in SUBTYPE_PATTERN.finditer(text):
        name = normalise_subtype(re.sub(r"[\s-]+", "", m.group(0)))
        if name not in names:
            names.append(name)
    return names


def _direction(text: str) -> str | None:
    for direction, words in DIRECTIONS.items():
        for word in words:
            for m in re.finditer(rf"\b{word}\b", text, re.IGNORECASE):
                if re.match(r"\s+than\s+(?:about\s+|around\s+|roughly\s+)?\d", text[m.end():], re.IGNORECASE):
                    continue  # "more than 500 tumors" is a bound on a count, not a comparison
                return direction
    return None


def _measure(text: str) -> str | None:
    for pattern, name in MEASURES:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    other = OTHER_MEASURE.search(text)
    if other and not GROUP_PATTERN.fullmatch(other.group(1)):
        return f"{other.group(1)} protein"
    return None


# --- the rules, in order; each returns a Claim or None -------------------------------------


def _rule_not_answerable(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    found = detect_unanswerable(info.text)
    if found is None:
        return None
    return Claim(
        id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.NOT_ANSWERABLE,
        needed_data=found.needed_data, clinical_terms=found.terms,
    )


def _rule_share(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    subtypes = _subtypes(info.text)
    if len(subtypes) != 1:
        return None  # none, or several subtypes in one sentence: not one share we can check
    usable = [n for n in numbers if not n.bound]
    percents = [n for n in usable if n.percent]
    params = ClaimParams(subtype=subtypes[0], subject="primary_tumors")
    if percents:
        params.unit = "percent"
        _stated(params, percents[0])
    else:
        value, total = _value_and_total(usable)
        if value is None or total is None:
            return None
        params.unit = "count"
        _stated(params, value, total)
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.SHARE, params=params)


def _rule_comparison(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    direction = _direction(info.text)
    measure = _measure(info.text)
    groups = [m.group(0) for m in GROUP_PATTERN.finditer(info.text)]
    if not (direction and measure and groups):
        return None
    params = ClaimParams(
        direction=direction, measure=measure,
        group_a=groups[0], group_b=groups[1] if len(groups) > 1 else None,
    )
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COMPARISON, params=params)


def _rule_coverage(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    if ALL_LAYERS.search(info.text):
        return None  # "all five layers" is a count of tumors, handled by the count rule
    layers = _layers(info.text)
    if len(layers) != 1:
        return None
    params = ClaimParams(subject=f"has_{layers[0]}")
    usable = [n for n in numbers if not n.bound]
    percents = [n for n in usable if n.percent]
    if EVERY_WORDS.search(info.text) and not percents:
        params.unit = "all"  # "All 1,101 primary tumors have ...": any number there is the total
    elif percents:
        params.unit = "percent"
        _stated(params, percents[0])
    else:
        value, total = _value_and_total(usable)
        if value is None or _count_subject(info.text) not in ("primary_tumors", None):
            return None
        params.unit = "count"
        _stated(params, value, total)
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COVERAGE, params=params)


def _rule_count(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    usable = [n for n in numbers if not n.bound and not n.percent]
    value, total = _value_and_total(usable)
    if value is None:
        return None
    if ALL_LAYERS.search(info.text) or len(_layers(info.text)) == len(LAYERS):
        subject = "all_five_layers"
    elif _layers(info.text):
        return None  # some but not all layers: no check for that combination yet
    else:
        subject = _count_subject(info.text, value.end)
        if subject is None or GROUP_PATTERN.search(info.text):
            return None  # nothing countable named, or a receptor-status subgroup we can't count yet
    params = ClaimParams(unit="count", subject=subject)
    _stated(params, value, total)
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COUNT, params=params)


def _rule_unmapped(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    if not numbers:
        return None
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.UNMAPPED)


RULES = (_rule_not_answerable, _rule_share, _rule_comparison, _rule_coverage, _rule_count, _rule_unmapped)


def classify_sentence(info: SentenceInfo, claim_id: str) -> Claim | None:
    """Type one sentence as a claim (first rule that matches wins), or None if it states nothing checkable."""
    numbers = find_numbers(info.text)
    for rule in RULES:
        claim = rule(info, claim_id, numbers)
        if claim is not None:
            return claim
    return None


def extract_claims(report_text: str) -> ExtractResult:
    """Split the report and type every sentence. Claim ids run C1, C2, ... over claims only."""
    sentences = split_sentences(report_text)
    claims: list[Claim] = []
    for info in sentences:
        claim = classify_sentence(info, f"C{len(claims) + 1}")
        if claim is not None:
            claims.append(claim)
            info.claim_id = claim.id
    return ExtractResult(sentences=sentences, claims=claims)

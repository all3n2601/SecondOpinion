"""Read a Markdown report: cut it into sentences (B1), then pick out the claims (B2).

Claim typing is a fixed list of rules, first match wins (see `classify_sentence`). Every keyword
list and pattern is a module-level constant so a new trap can be handled by adding a word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from second_opinion.model import Claim, ClaimParams, ClaimType, ExtractResult, SentenceInfo
from second_opinion.numwords import WORDS, fraction_amounts, number_value, word_numbers
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
    """Cut a Markdown report into sentences, in order, with `index` counting from 0.

    `text` has the Markdown stripped; `original_text` is the same sentence as written in the report.
    A sentence that repeats an earlier one (same words, any Markdown) is dropped, so the report
    never yields two findings for one sentence.
    """
    sentences: list[SentenceInfo] = []
    seen: set[str] = set()
    for block in _blocks(report_text):
        text, where = _clean_inline_tracked(block)
        for piece, original in _split_block(block, text, where):
            key = piece.casefold()
            if key in seen:
                continue
            seen.add(key)
            sentences.append(SentenceInfo(index=len(sentences), text=piece, claim_id=None, original_text=original))
    return sentences


_PERCENT_HEADER = re.compile(r"%|\bpercent|\bper\s+cent|\bshare\b|\bproportion\b", re.IGNORECASE)


def _blocks(report_text: str) -> list[str]:
    """Group lines into paragraphs, bullets and table rows; drop headings, rules and code."""
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    in_bullet = False
    header: list[str] | None = None  # the open table's header cells, to give bare numbers their unit
    last_cells: list[str] | None = None

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
        if _TABLE_SEPARATOR.match(line) and stripped.startswith("|"):
            flush()
            header = last_cells  # the row above "|---|---|" names the columns
            continue
        if not stripped or _HEADING.match(line) or _RULE.match(line) or _TABLE_SEPARATOR.match(line):
            flush()
            header = None
            continue

        if stripped.startswith("|"):
            flush()
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            last_cells = cells
            if header and len(header) == len(cells):  # "| Basal-like | 141 | 12.8 |" under "| Group | n | % |"
                cells = [c + "%" if _PERCENT_HEADER.search(h) and re.fullmatch(r"\d+(?:\.\d+)?", c) else c
                         for h, c in zip(header, cells)]
            blocks.append(" | ".join(cell for cell in cells if cell))
            continue
        header = None

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
    return _clean_inline_tracked(text)[0]


def _clean_inline_tracked(raw: str) -> tuple[str, list[int]]:
    """`_clean_inline` plus, for every kept character, its position in `raw`."""
    chars = list(raw)
    where = list(range(len(raw)))

    def sub(pattern: re.Pattern[str], keep_group: int | None) -> None:
        nonlocal chars, where
        out_chars: list[str] = []
        out_where: list[int] = []
        last = 0
        for m in pattern.finditer("".join(chars)):
            out_chars += chars[last:m.start()]
            out_where += where[last:m.start()]
            if keep_group is not None and m.group(keep_group):
                out_chars += chars[m.start(keep_group):m.end(keep_group)]
                out_where += where[m.start(keep_group):m.end(keep_group)]
            last = m.end()
        chars, where = out_chars + chars[last:], out_where + where[last:]

    sub(_IMAGE, 1)
    sub(_LINK, 1)
    sub(re.compile(r"[`*]"), None)
    sub(_EMPHASIS_UNDERSCORE, None)

    # Collapse whitespace runs to one space (keeping the first one's position), then trim the ends.
    out_chars: list[str] = []
    out_where: list[int] = []
    for c, w in zip(chars, where):
        if c.isspace():
            if out_chars and out_chars[-1] == " ":
                continue
            c = " "
        out_chars.append(c)
        out_where.append(w)
    while out_chars and out_chars[-1] == " ":
        out_chars.pop(), out_where.pop()
    while out_chars and out_chars[0] == " ":
        out_chars.pop(0), out_where.pop(0)
    return "".join(out_chars), out_where


def _split_block(raw: str, text: str, where: list[int]) -> list[tuple[str, str]]:
    """Cut one cleaned block into (sentence, the same sentence as written in `raw`) pairs."""
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        before = text[start:match.start()]
        last_word = before.rsplit(None, 1)[-1] if before.strip() else ""
        if last_word.lstrip("(\"'“‘[").lower() in ABBREVIATIONS:
            continue
        spans.append((start, match.start(1)))
        start = match.end()
    spans.append((start, len(text)))
    pairs: list[tuple[str, str]] = []
    for a, b in spans:
        piece = text[a:b].strip()
        if not piece:
            continue
        first = a + len(text[a:b]) - len(text[a:b].lstrip())
        pairs.append((piece, _original_span(raw, where[first], where[first + len(piece) - 1])))
    return pairs


_LINK_TAIL = re.compile(r"\]\([^)]*\)")


def _original_span(raw: str, first: int, last: int) -> str:
    """`raw[first..last]` as written, whitespace runs collapsed.

    Markup that touches the sentence's first or last kept character is part of it: the `**` in
    "**Luminal A** is the largest.", the `**` closing "**Luminal A is the largest.**", the
    `](url)` ending "see [the table](url)."
    """
    start, end = first, last + 1
    while start > 0 and raw[start - 1] in "*_`[":
        start -= 1
    while True:
        if end < len(raw) and raw[end] in "*_`" and raw[end] in raw[start:end]:
            end += 1
            continue
        tail = _LINK_TAIL.match(raw, end)
        if tail is None:
            break
        end = tail.end()
    return re.sub(r"\s+", " ", raw[start:end]).strip()


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
    "metastases": "samples", "metastasis": "samples",
    "slides": "slides", "slide": "slides", "sections": "slides", "section": "slides", "slide images": "slides",
}
# Sub-groups a count can be restricted to. The subject becomes "<filter>_<noun>", e.g.
# "male_samples"; checks that don't know a subject say so instead of counting everyone.
COUNT_FILTERS = {
    "male": r"\bmales?\b|\bmen\b",
    "female": r"\bfemales?\b|\bwomen\b",
    "normal_tissue": r"\bnormal[\s-]+(?:tissue|adjacent|breast|solid)|\bsolid tissue normal|\badjacent normal|\bnormal samples?\b",
    "metastatic": r"\bmetasta\w*",
    "diagnostic": r"\bdiagnostic\b|\bFFPE\b",
    "frozen": r"\bfrozen\b",
    "unknown_age": r"\b(?:lacks?|lacking|without|missing|has\s+no|have\s+no)\s+(?:an?\s+)?(?:recorded\s+)?age\b",
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
AVAILABLE_WORDS = re.compile(
    r"\b(?:available|availability|exists?|present|profiled|measured|covered|covers?|assayed|sequenced|overlap\w*|shared|joined|joinable)\b",
    re.IGNORECASE,
)
EVERY_WORDS = re.compile(
    r"\b(?:every|each|all)\b(?:\s+[\d,]+)?\s+(?:of\s+the\s+)?(?:[\d,]+\s+)?(?:primary\s+)?"
    r"(?:tumou?rs?|samples?|patients?|cases?)\b",
    re.IGNORECASE,
)
# Subtypes. "HER2" counts as the subtype only when it is not a receptor status ("HER2-positive").
SUBTYPE_PATTERN = re.compile(
    r"\bLum(?:inal)?[\s-]*[AB]\b"
    r"|(?<!PR and )(?<!PR, )(?<!PR or )(?<!ER and )(?<!ER or )"  # "ER, PR and HER2 were all negative": receptors
    r"\bHER-?2(?:[\s-]*enriched)?\b(?![\s-]*(?:(?:status\s+)?(?:was|were|is|are)\s+(?:all\s+|also\s+)?(?:positive|negative)"
    r"|positiv|negativ|pos\b|neg\b|status|amplif|gene|protein|levels?|\+|/neu|mutat|copy|by\s+imm|IHC|testing|test\b|result))"
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
# A gene symbol: capitals with a digit (TP53, PIK3CA, BRCA1). These look alike but are not genes.
GENE_SYMBOL = re.compile(r"\b[A-Z][A-Z0-9]*\d[A-Z0-9]*\b|\b(?:PIK3CA|TP53|CDH1|GATA3|MAP3K1|PTEN|ESR1|ERBB2)\b")
NOT_GENES = {"HER2", "PAM50", "H2", "COVID19"}
# Capitalised words that are never genes, even next to "mutation" or "amplification".
NOT_GENE_WORDS = {
    "ER", "PR", "PGR", "HR", "IHC", "RNA", "DNA", "MRNA", "TCGA", "BRCA", "TCGA-BRCA", "PAM50", "RPPA", "FFPE",
    "GISTIC", "OS", "DSS", "PFI", "DFI", "CNV", "CNA", "SNV", "WES", "WGS", "NGS", "FISH", "TNBC", "IDC", "ILC",
    "NOS", "US", "NCI", "IDC", "MAF", "VAF", "AND", "OR", "THE", "A", "AN", "IN", "OF", "HER", "II", "III", "IV",
    "UCSC", "PFS", "DFS", "HR+", "LUMA", "LUMB", "BASAL", "AJCC", "TNM",
}
_GENE_CANDIDATE = re.compile(r"\b[A-Z][A-Z0-9]{1,9}(?:-[A-Z0-9]{1,4})?\b")
_GENE_CONTEXT = re.compile(
    r"\b(?:mutat\w*|amplif\w*|delet\w*|alter\w*|gene|genes|harbou?r\w*|carr(?:y|ies|ied|ying)|variants?|copy[\s-]number|loss|gains?)\b",
    re.IGNORECASE,
)
# Numbers after these words are references, not data: "Figure 2", "version 3".
REFERENCE_WORDS = re.compile(
    r"(?:figure|fig\.|table|section|version|v|step|chapter|appendix|ref\.?|page|grade|GISTIC"
    r"|(?:value|score|threshold|cut-?off|level|code)(?:\s+of)?)\s*$",
    re.IGNORECASE,
)
# A parenthesis that defines a call, not data: "(GISTIC value of 2)", "(GISTIC 1 or 2)", "(GISTIC -1 or -2)".
_DEFINITION = re.compile(r"\((?:[^()]*?\b(?:GISTIC|value|values|score|code|threshold|cut-?off)\b[^()]*)\)", re.IGNORECASE)
# An age threshold: "patients over 60", "older than 65", "diagnosed under 40", "aged 70 or older", "65+",
# with the age in digits or words ("aged seventy or more", "diagnosed before forty").
_AGE_WORD = r"(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)(?:[\s-](?:one|two|three|four|five|six|seven|eight|nine))?"
AGE_THRESHOLD = re.compile(
    r"\b(?:aged?\s+)?(?P<op>over|older\s+than|above|at\s+least|under|younger\s+than|below|diagnosed\s+before)\s+(?:(?:the\s+)?age\s+(?:of\s+)?)?"
    r"(?P<age>\d{2}|" + _AGE_WORD + r"\b)"
    r"(?!\d|[,.]\d|\s*%|\s*per\s*cent|\s+(?:primary\s+)?(?:tumou?rs?|samples?|patients?|cases?|women|men|deaths?)\b)"
    r"(?:\s*(?:years?|yrs?)(?:\s+(?:old|of\s+age))?)?"
    r"|\b(?:aged?|(?:diagnosed\s+)?at(?:\s+age)?)\s+(?P<age2>\d{2}|" + _AGE_WORD + r")\s*(?:years?\s+)?(?:or|and)\s+(?P<op2>older|over|above|more|younger|under|below)\b"
    r"|\b(?P<age3>\d{2})\s*\+",
    re.IGNORECASE,
)


def age_of(match: re.Match[str]) -> int:
    """The age in an AGE_THRESHOLD match, written as digits or words."""
    raw = match.group("age") or match.group("age2") or match.group("age3")
    return int(raw) if raw.isdigit() else int(number_value(raw))


_AGE_CONTEXT = re.compile(r"\b(?:age[sd]?|older|younger|years?|diagnos\w*|patients?|women|men)\b", re.IGNORECASE)


def age_thresholds(text: str) -> list[re.Match[str]]:
    """Age cut-offs in the sentence; their numbers are part of a group's name, never a stated figure."""
    if not _AGE_CONTEXT.search(text):
        return []
    return [m for m in AGE_THRESHOLD.finditer(text) if 10 <= age_of(m) <= 100]
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
# After a number written as words: a counted noun ("ninety-seven tumours", "a dozen of the primary tumours")
# or a total ("Fifteen of the 20 stage IV patients").
_WORD_NUMBER_AFTER = re.compile(
    r"(?:\s+of(?:\s+the)?)?(?:\s+[\w-]+){0,2}?\s+(?:" + "|".join(sorted(COUNT_NOUNS, key=len, reverse=True)) + r")\b"
    r"|\s+of\s+(?:the\s+)?[\d,]+\b",
    re.IGNORECASE,
)
_TOTAL_BEFORE = re.compile(r"(?:\b(?:of|out\s+of|among)\s+(?:the\s+|all\s+|these\s+)?|\d\s*/\s*)$", re.IGNORECASE)
_APPROX_BEFORE = re.compile(
    r"(?:^|[\s(])(?:" + "|".join(re.escape(w) for w in APPROXIMATE_WORDS) + r")\s*$", re.IGNORECASE
)
_BOUND_BEFORE = re.compile(
    r"\b(?:more|fewer|less|greater|higher|lower)\s+than\s+$|\b(?:at\s+least|at\s+most|over|under|above|below|up\s+to|exceeds?|exceeding)\s+$",
    re.IGNORECASE,
)
_YEAR = re.compile(r"^(?:19|20)\d\d$")
# "58 years", "6-month": an age or a duration, not a count of tumors, samples or patients.
_TIME_UNIT_AFTER = re.compile(r"[\s-]*(?:years?|yrs?|months?|weeks?|days?)\b(?:[\s-]*old)?", re.IGNORECASE)


_RATIO_NUMBERS = re.compile(r"(?<![\w.,])\d+(?:\.\d+)?\s*(?:to|:)\s*(?:1|one)\b(?!\s*%|\.\d|,\d)", re.IGNORECASE)


_AGE_NUMBER_AFTER = re.compile(r"\s*(?:years?\s+old\s+)?(?:at|when)\s+(?:first\s+)?diagnos", re.IGNORECASE)
_AGE_NUMBER_BEFORE = re.compile(r"\bdiagnosed\s+at\s+(?:the\s+age\s+of\s+)?$|\bat\s+the\s+age\s+of\s+$", re.IGNORECASE)


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
    # numbers inside a definition "(GISTIC 1 or 2)" or an age cut-off "over 60" are not stated figures
    taken: list[tuple[int, int]] = [m.span() for m in _DEFINITION.finditer(text)]
    taken += [m.span() for m in age_thresholds(text)]
    taken += [m.span() for m in AGE_RANGE.finditer(text)]  # "between the ages of 26 and 89": read by _rule_statistic
    taken += [m.span() for m in _RATIO_NUMBERS.finditer(text)]  # "3:1", "2.5 to 1": a ratio, read by _rule_ratio

    def context(start: int) -> tuple[bool, bool, bool]:
        before = text[:start]
        return (
            bool(_APPROX_BEFORE.search(before)),
            bool(_BOUND_BEFORE.search(before)),
            bool(_TOTAL_BEFORE.search(before)),
        )

    for m in _RANGE.finditer(text):
        if any(a <= m.start() < b for a, b in taken):
            continue
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
        if not tail and (_AGE_NUMBER_AFTER.match(text, m.end()) or _AGE_NUMBER_BEFORE.search(before)):
            continue  # "was 90 at diagnosis", "diagnosed at 26": an age, read by _rule_statistic
        approx, bound, total = context(m.start())
        found.append(StatedNumber(
            m.start(), tail.end() if tail else m.end(), _to_float(whole, frac), len(frac or ""),
            bool(tail), approx, bound, None, total,
        ))

    taken += [(f.start, f.end) for f in fraction_amounts(text)]  # "one tumour in eight" is a share, read by find_amounts
    for w in word_numbers(text):
        if any(a <= w.start < b for a, b in taken) or not _WORD_NUMBER_AFTER.match(text, w.end):
            continue
        if w.value == 1 and re.search(r"\b(?:at\s+least|only|a\s+single|just|every|each|any)\s+$", text[: w.start], re.IGNORECASE):
            continue  # "at least one diagnostic slide", "every one of the 742": a condition, not a stated count
        approx, bound, total = context(w.start)
        found.append(StatedNumber(w.start, w.end, w.value, 0, False, approx, bound, None, total))

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
    if {"male", "female"} <= set(filters):
        return None  # "1,085 female patients and 12 male patients" is two counts, not one group
    if len(filters) > 1:
        return "+".join(filters) + f"_{kind}"
    return f"{filters[0]}_{kind}" if filters else kind


def _layers(text: str) -> list[str]:
    have = HAVE_WORDS.search(text)
    if have:
        after = text[have.start():]
        found = [layer for layer, pattern in LAYERS.items() if re.search(pattern, after, re.IGNORECASE)]
        if found or not AVAILABLE_WORDS.search(text):
            return found
    if AVAILABLE_WORDS.search(text):  # "Survival, mutation, ... data are all available for 553 tumors"
        return [layer for layer, pattern in LAYERS.items() if re.search(pattern, text, re.IGNORECASE)]
    return []


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
    by = _BY_DIFFERENCE.search(info.text)
    if by:  # "higher ... by about 3 units": the size of the difference is part of the claim
        raw = by.group("n")
        params.unit, params.stated_value = "difference", float(raw) if raw[0].isdigit() else number_value(raw)
        params.stated_high = float(by.group("hi")) if by.group("hi") else None
        params.decimals = len(raw.split(".")[1]) if "." in raw else 0
        params.bound = bound_op(info.text[: by.start("n")])
        params.approximate = not params.bound and bool(_APPROX_BEFORE.search(info.text[: by.start("n")]))
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COMPARISON, params=params)


_BY_DIFFERENCE = re.compile(
    r"\b(?:by|(?:difference|gap)\s+of)\s+(?:(?:about|roughly|nearly|around|approximately|almost|some|more\s+than|less\s+than|over|under"
    r"|at\s+least|at\s+most)\s+)?(?P<n>\d+(?:\.\d+)?|" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")"
    r"(?:\s*(?:–|—|-|to)\s*(?P<hi>\d+(?:\.\d+)?))?\s*(?:units?|points?)\b",
    re.IGNORECASE,
)


_KNOWN_STATUS = re.compile(
    r"\b(?:and|with)\s+(?:an?\s+)?(?:definitive|known|recorded|conclusive|valid|positive\s+or\s+negative)\s+"
    r"(?P<rec>ER|PR|HER2)\s+(?:results?|status(?:es)?|calls?)\b",
    re.IGNORECASE,
)
_KNOWN_STATUS_ATTRIBUTE = {"ER": "er_status", "PR": "pr_status", "HER2": "her2_status"}


def _rule_coverage(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    if ALL_LAYERS.search(info.text):
        return None  # "all five layers" is a count of tumors, handled by the count rule
    if any(g.upper() not in NOT_GENES for g in GENE_SYMBOL.findall(info.text)):
        return None  # "have a TP53 or PIK3CA mutation" is about those genes, not "has a mutation call"
    layers = _layers(info.text)
    if len(layers) != 1:
        return None
    params = ClaimParams(subject=f"has_{layers[0]}")
    known = _KNOWN_STATUS.search(info.text)
    if known:  # "... with both RPPA data and a definitive ER result": among tumours with a known status
        params.within_attribute, params.within_category = _KNOWN_STATUS_ATTRIBUTE[known.group("rec").upper()], "any"
    usable = [n for n in numbers if not n.bound]
    percents = [n for n in usable if n.percent]
    words = [a for a in find_amounts(info.text) if a.words]
    bounded = [n for n in numbers if n.bound and not n.is_total]
    if words and not percents:  # "nearly all", "the majority of", "about half": a share, not every one
        _stated_amount(params, words[0])
    elif EVERY_WORDS.search(info.text) and not percents:
        params.unit = "all"  # "All 1,101 primary tumors have ...": any number there is the total
    elif percents:
        params.unit = "percent"
        _stated(params, percents[0])
    elif bounded and not [n for n in usable if not n.is_total]:  # "At least 1,000 primary tumors have ..."
        if _count_subject(info.text) not in ("primary_tumors", None):
            return None
        params.unit = "percent" if bounded[0].percent else "count"
        _stated(params, bounded[0], next((n for n in numbers if n.is_total), None))
        params.bound = bound_op(info.text[: bounded[0].start])
    else:
        value, total = _value_and_total(usable)
        if value is None or _count_subject(info.text) not in ("primary_tumors", None):
            return None
        params.unit = "count"
        _stated(params, value, total)
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COVERAGE, params=params)


def _stated_amount(params: ClaimParams, amount: "Amount") -> None:
    params.unit = "percent" if amount.percent else "count"
    params.stated_value, params.stated_high = amount.value, amount.high
    params.approximate, params.bound = amount.approximate, amount.bound
    params.decimals = None if amount.words else amount.decimals


LAYER_NEGATION = re.compile(r"\bbut\s+(?:no|not)\b|\bwithout\b|\black(?:s|ing)?\b|\bmissing\b|\bonly\s+one\b", re.IGNORECASE)
# Words that narrow "tumours" / "patients" to a group. A plain count never applies when one is present.
UNREAD_QUALIFIER = re.compile(
    r"\b(?:both|without|lack\w*|carr(?:y|ies|ied|ying)|harbou?r\w*|diagnosed\s+(?:under|over|before|after|at)|aged?|older|younger"
    r"|node|nodal|lymph\w*|co-?occur\w*|equivocal|indeterminate|status|positive|negative|mutat\w*|amplif\w*|gains?|loss"
    r"|lost|died|death|deaths|deceased|alive|living|stage[ds]?|grade|receiv\w*|treated|subtyp\w*|called|recorded|known"
    r"|measured|profiled|sequenced|tested|over\s+\d|under\s+\d|above\s+\d|below\s+\d)\b",
    re.IGNORECASE,
)


# "131 proteins", "more than 40,000 genes": what a file measures, not how many tumours it covers.
_FEATURE_AFTER = re.compile(r"\s+(?:[a-z-]+\s+)?(?P<noun>genes|proteins|antibodies)\b", re.IGNORECASE)


def feature_layer(text: str, end: int) -> str | None:
    """The file a feature count right after `end` is about: proteins -> protein; genes -> the layer the sentence names."""
    m = _FEATURE_AFTER.match(text, end)
    if m is None:
        return None
    if m.group("noun").lower() in ("proteins", "antibodies"):
        return "protein"
    named = [layer for layer in ("mutation", "copy_number", "rna") if re.search(LAYERS[layer], text, re.IGNORECASE)]
    return named[0] if len(named) == 1 else None


_AGE_COMPARE = re.compile(
    r"\b(?:were|was|are|is)\s+(?:diagnosed\s+)?(?:(?P<approx>about|roughly|nearly|around|some|approximately|almost)\s+)?"
    r"(?:(?P<n>\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+years?\s+)?"
    r"(?P<dir>younger|older|later|earlier)\b(?P<avg>\s+on\s+average)?(?:\s+(?:at|when)\s+(?:first\s+)?diagnos\w*)?"
    r"(?P<avg2>\s+on\s+average)?\s+than\b",
    re.IGNORECASE,
)
_AGE_SUPERLATIVE = re.compile(r"\b(?:were|was|are|is)\s+(?:the\s+)?(?P<sup>youngest|oldest)\b", re.IGNORECASE)


def _rule_age_groups(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"Basal-like patients were diagnosed younger than Luminal A patients" (median ages compared) and
    "Basal-like patients were the youngest at diagnosis of any subtype" (median ages ranked). No numbers stated."""
    text = info.text
    if [n for n in numbers if not n.is_total and not _AGE_COMPARE.search(text, max(0, n.start - 40))]:
        return None  # with the ages written, _rule_statistic checks each one
    groups = [e for e in find_entities(text) if e.attribute in GROUP_ATTRIBUTES]
    compare = _AGE_COMPARE.search(text)
    if compare:
        before = [e for e in groups if e.end <= compare.start()]
        after = [e for e in groups if e.start >= compare.end()]
        if not before or not after or before[-1].attribute != after[0].attribute or before[-1].category == after[0].category:
            return None
        a, b = before[-1], after[0]
        mean = bool(compare.group("avg") or compare.group("avg2") or re.search(r"\b(?:mean|average)\b", text, re.IGNORECASE))
        params = ClaimParams(measure="mean_age" if mean else "median_age",
                             direction="lower" if compare.group("dir").lower() in ("younger", "earlier") else "higher",
                             within_attribute=a.attribute, within_category=a.category, category_b=b.category,
                             group_a=a.category, group_b=b.category)
        if compare.group("n"):  # "about six years later": the size of the gap is part of the claim
            raw = compare.group("n")
            params.unit, params.stated_value = "difference", float(raw) if raw[0].isdigit() else number_value(raw)
            params.approximate = bool(compare.group("approx"))
        return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COMPARISON, params=params)
    sup = _AGE_SUPERLATIVE.search(text)
    if sup and re.search(r"\bdiagnos|\bage\b", text, re.IGNORECASE):
        before = [e for e in groups if e.end <= sup.start()]
        if not before:
            return None
        params = ClaimParams(measure="median_age", unit="rank", stated_value=1.0, subject="primary_tumors",
                             direction="lower" if sup.group("sup").lower() == "youngest" else None,
                             within_attribute=before[-1].attribute, within_category=before[-1].category)
        return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RANK, params=params)
    return None


_AGREE = re.compile(r"\b(?:agree\w*|concordan\w*|disagree\w*|discordan\w*|match(?:es|ed)?|same\s+subtype)\b", re.IGNORECASE)
_STUDY_LABEL = re.compile(r"\b2012\b|\bconsortium\b|\bstudy\s+labels?\b|\bnature\s*2012\b", re.IGNORECASE)


def _rule_agreement(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"The RNA-seq call and the 2012 label agree for 90% of tumours": the two subtype sources compared."""
    text = info.text
    if not (_AGREE.search(text) and _STUDY_LABEL.search(text) and re.search(r"\bRNA|\bPAM50|\bcall", text, re.IGNORECASE)):
        return None
    amounts = [a for a in find_amounts(text) if a.percent and not a.is_total]
    if len(amounts) != 1:
        return None
    params = ClaimParams(subject="subtype_sources")
    _stated_amount(params, amounts[0])
    if re.search(r"\bdisagree\w*|\bdiscordan\w*", text, re.IGNORECASE):
        params.stated_value = 100 - params.stated_value  # "disagree for 10%": agree for 90%
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.AGREEMENT, params=params)


_RNA_SOURCE = re.compile(r"\bRNA[\s-]?seq\b|\bRNA\s+calls?\b|\bPAM50Call", re.IGNORECASE)
_LARGEST_DISAGREEMENT = re.compile(r"\b(?:largest|biggest|commonest|most\s+common)\s+(?:single\s+)?(?:disagreement|discordance|mismatch)", re.IGNORECASE)


def _rule_label_pair(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"31 tumors that the 2012 study placed in LumB and that RNA-seq calls LumA": one cell of the two labels' table,
    and with "the largest single disagreement", its place among the cells where the labels differ."""
    text = info.text
    study, rna = _STUDY_LABEL.search(text), _RNA_SOURCE.search(text)
    stated = [n for n in numbers if not n.percent]  # "a group of 31 tumors": one number, read as a total
    subtypes = [e for e in find_entities(text) if e.attribute == "subtype"]
    if not (study and rna and len(stated) == 1 and len(subtypes) == 2) or subtypes[0].category == subtypes[1].category:
        return None

    def source(e: Entity) -> str:  # the label source named closest before the subtype
        last_study = max((m.start() for m in _STUDY_LABEL.finditer(text, 0, e.start)), default=-1)
        last_rna = max((m.start() for m in _RNA_SOURCE.finditer(text, 0, e.start)), default=-1)
        return "study" if last_study > last_rna else "rna"

    by = {source(e): e.category for e in subtypes}
    if set(by) != {"study", "rna"}:
        return None
    params = ClaimParams(unit="count", subject=f"label_pair:{by['study']}:{by['rna']}", stated_value=stated[0].value, decimals=0)
    count = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COUNT, params=params)
    if not _LARGEST_DISAGREEMENT.search(text):
        return count
    rank = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RANK,
                 params=ClaimParams(unit="rank", stated_value=1.0, subject=params.subject, measure="label_pair"))
    return _compound(info, claim_id, [_part(count, text[stated[0].start:stated[0].end], 1),
                                      _part(rank, "the largest disagreement", 2)])


def _rule_features(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"The mutation file lists more than 40,000 genes": a count of the file's rows."""
    stated = [n for n in numbers if not n.is_total]
    if len(stated) != 1 or stated[0].percent:
        return None
    layer = feature_layer(info.text, stated[0].end)
    if layer is None:
        return None
    params = ClaimParams(unit="count", subject=f"features:{layer}")
    _stated(params, stated[0])
    params.bound = bound_op(info.text[: stated[0].start]) if stated[0].bound else None
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COUNT, params=params)


def _rule_count(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    usable = [
        n for n in numbers
        if not n.bound and not n.percent and not _TIME_UNIT_AFTER.match(info.text, n.end)
    ]
    bound = None
    if not [n for n in usable if not n.is_total]:  # "More than 1,000 samples ...": a one-sided count
        bounded = [n for n in numbers if n.bound and not n.percent and not n.is_total
                   and not _TIME_UNIT_AFTER.match(info.text, n.end)]
        if bounded:
            usable = [bounded[0]] + [n for n in usable if n.is_total]
            bound = bound_op(info.text[: bounded[0].start])
    value, total = _value_and_total(usable)
    which = _OF_WHICH.search(info.text)
    if which:  # "the 1,101 primary tumors ..., of which 535 (48.6%) carry all five layers": 535 of 1,101
        after = [n for n in usable if n.start >= which.end()]
        before = [n for n in usable if n.end <= which.start() and not _in_parentheses(info.text, n.start)]
        if after and before:
            value, total = after[0], before[0]
    zero = ZERO_AMOUNT.search(info.text) if value is None else None
    if zero:  # "Not a single primary tumour lacks an age": a count of 0
        value = StatedNumber(zero.start(), zero.end(), 0.0, 0, False, False, False)
    if value is None:
        return None
    layers = _layers(info.text)
    if ALL_LAYERS.search(info.text) or len(layers) == len(LAYERS):
        subject = "all_five_layers"
    elif len(layers) >= 2:  # "742 tumours have both RNA and protein data"
        if LAYER_NEGATION.search(info.text):
            return None  # "RNA but no protein data": a difference of layers, not an overlap
        subject = "layers:" + "+".join(layers)
    elif layers:
        return None  # one layer is coverage, owned by _rule_coverage
    else:
        subject = _count_subject(info.text, value.end)
        if subject is None or GROUP_PATTERN.search(info.text):
            return None  # nothing countable named, or a receptor-status subgroup we can't count yet
        if "+" in subject and len([n for n in usable if not n.is_total]) > 1:
            return None  # "7 metastatic and 139 normal samples" is two groups, never one group that is both
        if subject in ("primary_tumors", "samples", "patients"):
            rest = info.text[: value.start] + " " + info.text[value.end:]
            if UNREAD_QUALIFIER.search(rest):
                return None  # "Patients over 60: 493", "HER2 was equivocal for 197 tumours": a group we can't read
                # is never counted as everyone; the claim stays insufficient_evidence for a person or the AI
    params = ClaimParams(unit="count", subject=subject, bound=bound)
    _stated(params, value, total)
    claim = Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COUNT, params=params)
    pct = _PAREN_PERCENT.match(info.text, value.end)
    if pct and total is not None:  # "535 (48.6%)": the percent of the same total is a second figure to check
        share = ClaimParams(unit="percent", subject=subject, stated_value=float(pct.group(1)),
                            decimals=len(pct.group(1).split(".")[1]) if "." in pct.group(1) else 0)
        return _compound(info, claim_id, [
            _part(claim, info.text[value.start:value.end], 1),
            _part(Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COUNT, params=share),
                  pct.group(0).strip(" ()"), 2)])
    return claim


_OF_WHICH = re.compile(r"\b(?:of|among)\s+(?:which|whom|these|them)\b", re.IGNORECASE)
_PAREN_PERCENT = re.compile(r"\s*\(\s*(\d+(?:\.\d+)?)\s*%\s*\)")


def _in_parentheses(text: str, at: int) -> bool:
    return text.rfind("(", 0, at) > text.rfind(")", 0, at)


def _rule_unmapped(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    if not numbers and not _states_a_fact(info.text):
        return None
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.UNMAPPED)


# ---------------------------------------------------------------------------------------------
# B3: claims without a plain number, attributes beyond subtype, and sentences with several claims
# ---------------------------------------------------------------------------------------------

# Measures a TCGA-BRCA release does not hold. A claim about one gets "the data can't answer this".
# (pattern, what is missing). The clinical file has no grade, Ki-67, size, BMI, race or lifestyle data.
UNAVAILABLE_MEASURES: tuple[tuple[str, str], ...] = (
    (r"\bKi[\s-]?67\b|\bMIB[\s-]?1\b", "Ki-67 (proliferation) measurements"),
    (r"\btumou?r\s+(?:size|diameter|volume)\b|\btumou?rs?\s+(?:larger|smaller|bigger)\s+than\b|\b\d+(?:\.\d+)?\s*(?:cm|mm)\b",
     "tumor size measurements"),
    (r"\b(?:histologic(?:al)?|nuclear|tumou?r|Nottingham|Elston(?:-Ellis)?)\s+grade\b|\bgrade\s+(?:[1-3]|I{1,3})\b|\b(?:high|low|intermediate)[\s-]grade\b",
     "tumor grade"),
    (r"\bBMI\b|\bbody[\s-]mass\b|\bobes(?:e|ity)\b|\boverweight\b", "body-mass index"),
    (r"\bsmok(?:e|ed|er|ers|ing)\b|\btobacco\b|\balcohol\b|\bdiet(?:ary)?\b|\bphysical\s+activity\b", "lifestyle data"),
    (r"\bfamily\s+history\b|\bgermline\b|\binherited\b|\bhereditary\b", "family-history or germline data"),
    (r"\bOncotype\b|\bMammaPrint\b|\brecurrence\s+score\b|\bProsigna\b", "commercial genomic test results"),
    (r"\bmammographic\b|\bbreast\s+density\b|\bMRI\b|\bultrasound\b|\bimaging\b", "imaging data"),
    (r"\btumou?r[\s-]infiltrating\s+lymphocytes\b|\bTILs\b", "tumor-infiltrating lymphocyte scores"),
    (r"\brac(?:e|ial)\b|\bethnic(?:ity|ities)?\b|\bAfrican[\s-]Americans?\b|\bHispanic\b|\bLatina\b|\bAsian\b|\bCaucasian\b"
     r"|\b(?:Black|White)\s+(?:women|patients|individuals|people|participants|cases)\b",
     "race or ethnicity data"),
    (r"\bincome\b|\binsurance\b|\bsocioeconomic\b|\beducation(?:al)?\s+level\b", "socioeconomic data"),
    (r"\b(?:DNA[\s-]binding|kinase|helical|binding)\s+domains?\b|\bhot[\s-]?spots?\b|\bcodons?\b|\bamino[\s-]acids?\b"
     r"|\bmissense\b|\bnonsense\b|\btruncating\b|\bframe[\s-]?shift\b|\bsplice[\s-]site\b|\bin[\s-]frame\b",
     "mutation-level data showing where in the gene each mutation falls and what kind it is (such as a MAF file; "
     "the release has one mutated / not-mutated call per gene)"),
)
_UNAVAILABLE = [(re.compile(p, re.IGNORECASE), need) for p, need in UNAVAILABLE_MEASURES]

# Comparing survival between groups needs a survival analysis, not a count: never judged here.
SURVIVAL_COMPARISON = re.compile(
    r"\b(?:live[sd]?|lived|survive[sd]?|surviving)\s+(?:significantly\s+|much\s+)?(?:longer|shorter)\b"
    r"|\b(?:better|worse|poorer|longer|shorter|improved|reduced|inferior|superior|favou?rable|unfavou?rable)\s+"
    r"(?:overall\s+|disease[\s-]free\s+|progression[\s-]free\s+|disease[\s-]specific\s+|long[\s-]term\s+)?(?:survival|prognosis|outcomes?)\b"
    r"|\b(?:survival|prognosis|outcomes?)\s+(?:is|was|were|are)\s+(?:significantly\s+)?(?:better|worse|poorer|longer|shorter|improved|reduced|inferior|superior)\b"
    r"|\bprognos\w*|\bhazard\s+ratios?\b|\bKaplan[\s-]Meier\b|\blog[\s-]rank\b|\bCox\s+(?:model|regression)\b"
    r"|\b(?:higher|lower|greater|increased|reduced|elevated)\s+(?:risk\s+of\s+(?:death|dying|relapse|recurrence)|mortality)\b"
    r"|\b(?:more|less)\s+likely\s+to\s+(?:die|survive|relapse|recur)\b",
    re.IGNORECASE,
)
SURVIVAL_NEED = (
    "a survival analysis that uses follow-up time (for example Kaplan-Meier curves with a log-rank test, or a Cox "
    "model), done and reviewed by a statistician; the release has survival times and events, but counting deaths "
    "per group cannot show that one group lives longer"
)

# Receptor status, written many ways: "ER-positive", "ER+", "estrogen receptor negative", "HER2 status positive".
STATUS_ENTITY = re.compile(
    r"\b(?P<rec>ER|PR|PgR|HER-?2(?:/neu)?|ERBB2|(?:o?estrogen|progesterone|hormone)[\s-]+receptors?|HR)"
    r"(?:\s+(?:IHC|immunohistochemistry|immunohistochemical))?(?:\s+(?:status|results?|scores?))?(?:\s+(?:was|were|is|are)(?:\s+also)?)?"
    r"(?:[\s-]*(?P<word>positive|negative|positivity|negativity|pos|neg|equivocal|indeterminate)\b|(?P<sym>\+|−|-)(?![\w-]))",
    re.IGNORECASE,
)
_RECEPTOR = {"er": "er_status", "estrogen": "er_status", "oestrogen": "er_status", "pr": "pr_status",
             "pgr": "pr_status", "progesterone": "pr_status", "her2": "her2_status", "her-2": "her2_status",
             "erbb2": "her2_status", "hormone": "hr_status", "hr": "hr_status"}
TRIPLE_NEGATIVE = re.compile(r"\btriple[\s-]+negative\b|\bTNBCs?\b", re.IGNORECASE)
STAGE_ENTITY = re.compile(r"\bstage[\s-]+(IV|III|II|I|[1-4])([ABC])?(?![\w])", re.IGNORECASE)
_ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV"}
_STAGES = ("I", "II", "III", "IV")
# "stage III or IV", "stage III or higher", "stages I to III": one group made of every stage it spans.
STAGE_UNION = re.compile(
    r"\bstages?[\s-]+(?P<lo>IV|III|II|I|[1-4])\s*(?:(?:or|and|to|through|–|-)\s*(?:stage\s+)?(?P<hi>IV|III|II|I|[1-4])(?![\w])"
    r"|(?:or|and)\s+(?P<dir>higher|above|later|greater|more\s+advanced|lower|below|earlier|less\s+advanced)\b)",
    re.IGNORECASE,
)


YEAR_GROUP = re.compile(
    r"\bdiagnosed\s+(?:in\s+)?(?P<y>(?:19|20)\d\d)\s+or\s+(?P<op>later|after|earlier|before)\b"
    r"|\bdiagnosed\s+(?P<op2>before|after|since|from|prior\s+to)\s+(?P<y2>(?:19|20)\d\d)\b",
    re.IGNORECASE,
)
# "Diagnoses span the years 1988 to 2013": the first and last year of diagnosis
YEAR_SPAN = re.compile(r"\bdiagnos\w*\b[^.;]*?\b((?:19|20)\d\d)\s*(?:to|-|–|through|and)\s*((?:19|20)\d\d)\b", re.IGNORECASE)
_BUSIEST_YEAR = re.compile(
    r"\b(?P<y>(?:19|20)\d\d)\s+(?:is|was)\s+the\s+(?:busiest|most\s+common|peak|commonest)\s+(?:single\s+)?year"
    r"(?:\s+(?:with|at)\s+(?P<n>[\d,]+)\s+(?:diagnoses|tumou?rs|patients|cases))?",
    re.IGNORECASE,
)
_NODES = re.compile(r"\b(?:positive\s+)?lymph\s+nodes?\b", re.IGNORECASE)


def stage_union(lo: str, hi: str | None, direction: str | None) -> str | None:
    """"III", "IV" -> "Stage III or IV"; "III" and "higher" -> "Stage III or IV"; "I", "III" -> "Stage I, II or III"."""
    a = _STAGES.index(_ROMAN.get(lo, lo.upper()))
    if hi is not None:
        b = _STAGES.index(_ROMAN.get(hi, hi.upper()))
    else:
        b = len(_STAGES) - 1 if re.match(r"higher|above|later|greater|more", direction, re.IGNORECASE) else 0
    a, b = min(a, b), max(a, b)
    if a == b:
        return None
    names = _STAGES[a:b + 1]
    return "Stage " + (", ".join(names[:-1]) + " or " + names[-1])
HISTOLOGY_ENTITY = re.compile(r"\b(ductal|lobular|mucinous|metaplastic|medullary)\b", re.IGNORECASE)
MENOPAUSE_ENTITY = re.compile(r"\b(pre|peri|post)[\s-]?menopausal\b", re.IGNORECASE)
DEATH_ENTITY = re.compile(r"\b(?:deaths?|died|deceased|dead|death\s+events?)\b", re.IGNORECASE)
# Deaths from the disease itself (survival.tsv DSS) and progression / recurrence events (PFI).
DSS_WORDS = re.compile(
    r"\b(?:disease|cancer|tumou?r|breast[\s-]cancer)[\s-]+(?:specific|related)\s+(?:deaths?|mortality)\b"
    r"|\bdied\s+(?:of|from)\s+(?:their\s+|the\s+)?(?:breast\s+)?(?:cancer|disease)\b|\bbreast[\s-]cancer\s+deaths?\b",
    re.IGNORECASE,
)
PFI_WORDS = re.compile(
    r"\b(?:progression|progressed|recurrence|recurred|relapsed?|relapses)\b(?:\s+(?:events?|or\s+(?:recurrence|relapse|death)))?",
    re.IGNORECASE,
)
SLIDE_KIND_ENTITY = re.compile(r"\b(diagnostic|FFPE|frozen)\b", re.IGNORECASE)
ALIVE_ENTITY = re.compile(r"\b(?:alive|still\s+living|living\s+patients|survivors)\b", re.IGNORECASE)
SEX_ENTITY = re.compile(r"\b(?:are|were|is|was)\s+(?:female|women|male|men)\b", re.IGNORECASE)
SEX_GROUP = re.compile(
    r"\b(?:of|among|in|no|none\s+of\s+the)\s+(?:the\s+|all\s+)?(?:[\d,]+\s+)?(?P<w>male|female)\s+(?:patients?|tumou?rs?|samples?|cases?)\b"
    r"|\b(?:of|among)\s+(?:the\s+)?(?P<w2>men|women)\b",
    re.IGNORECASE,
)
MUTATION_WORDS = re.compile(
    r"\b(?:mutat\w*|harbou?r(?:s|ed|ing)?|carr(?:y|ies|ied|ying)|altered|alterations?|variants?|mutants?)\b", re.IGNORECASE
)
AMPLIFICATION_WORDS = re.compile(r"\bamplif\w*|\bhigh[\s-]level\s+gains?\b", re.IGNORECASE)
DELETION_WORDS = re.compile(r"\b(?:deep|homozygous)\s+(?:deletions?|loss(?:es)?)\b|\bdeleted\b|\bdeletions?\b", re.IGNORECASE)
GAIN_WORDS = re.compile(r"\b(?:copy[\s-]number\s+)?gains?\b|\bgained\b", re.IGNORECASE)
LOSS_WORDS = re.compile(r"\b(?:copy[\s-]number\s+)?loss(?:es)?\b|\blost\b", re.IGNORECASE)
CO_OCCUR = re.compile(r"\bco-?occur\w*|\bboth\b|\btogether\b|\bconcurrent\w*|\bin\s+combination\b", re.IGNORECASE)
LUMINAL_UNION = re.compile(
    r"\bluminal\b(?![\s-]*(?:A|B)\b)|\bluminal\s+A\s*(?:\+|and|/)\s*(?:luminal\s+)?B\s+(?:together|combined)\b",
    re.IGNORECASE,
)
# Words that make "most" a superlative ("most common") rather than an amount ("most tumors").
_SUPERLATIVE_NEXT = r"common(?:ly)?|frequent(?:ly)?|prevalent|often|widely|likely|abundant|studied|used|important|striking|notable|recent|aggressive"
RANK_PHRASE = re.compile(
    r"\b(?:the\s+)?(?:(?P<ord>second|third|fourth|fifth|2nd|3rd|4th|5th)[\s-]+)?"
    r"(?P<sup>most\s+(?:common(?:ly)?|frequent(?:ly)?|prevalent|often)|largest|biggest|commonest|dominant|predominant"
    r"|least\s+(?:common(?:ly)?|frequent(?:ly)?|prevalent|often)|smallest|rarest)\b",
    re.IGNORECASE,
)
# "TTN ranks third", "Luminal B comes in second": a place among the groups, most common first
RANK_PLACE = re.compile(
    r"\b(?:ranks?|ranked|comes?|came|places?|placed|sits?|stands?)\s+(?:in\s+|at\s+)?(?:the\s+)?"
    r"(?P<ord>first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\b(?P<sup>)",
    re.IGNORECASE,
)
TOP_N_PHRASE = re.compile(
    r"\b(?:the\s+)?(?P<n>two|three|four|five|2|3|4|5)\s+(?:most\s+(?:common(?:ly)?|frequent(?:ly)?|prevalent)|largest)\b",
    re.IGNORECASE,
)
_ORDINAL_WORDS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5}
_SMALL_NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
RATIO_PHRASE = re.compile(
    r"(?P<n>\d+(?:\.\d+)?|two|three|four|five|six|seven|eight|nine|ten)\s*(?:-|\s)?(?:to|:)(?:-|\s)?\s*(?:1|one)\b"
    r"|(?P<times>twice|double|(?:\d+(?:\.\d+)?|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty)"
    r"[\s-]*(?:times|-?fold))\s+(?:as\s+)?(?:many|more|common|frequent|numerous|often|likely)"
    r"|(?P<outnumber>outnumber(?:s|ed|ing)?)",
    re.IGNORECASE,
)
# The ratio stated after "outnumber": "about three to one", "by more than 2:1", "ten to one".
_OUTNUMBER_RATIO = re.compile(
    r"(?P<n>\d+(?:\.\d+)?|(?:" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")(?:[\s-]+(?:"
    + "|".join(sorted(WORDS, key=len, reverse=True)) + r"))?)\s*(?:to|:)\s*(?:1|one)\b",
    re.IGNORECASE,
)
# Amount words that are not digits. Value is a percent; "bound" makes it one-sided.
WORD_AMOUNTS: tuple[tuple[str, float, str | None], ...] = (
    (r"\b(?:the\s+)?vast\s+majority\b", 80.0, "gte"),
    (r"\b(?:nearly|almost|virtually|practically|essentially)\s+(?:all|every)\b", 90.0, "gte"),
    (r"\b(?:the\s+)?majority\b|\bmost\b(?!\s+(?:" + _SUPERLATIVE_NEXT + r")\b)", 50.0, "gt"),
    (r"\b(?:a\s+)?minority\b", 50.0, "lt"),
    (r"\btwo[\s-]thirds\b", 200 / 3, None),
    (r"\bthree[\s-]quarters\b|\bthree[\s-]fourths\b", 75.0, None),
    (r"\b(?:a|one)[\s-]third\b", 100 / 3, None),
    (r"\b(?:a|one)[\s-](?:quarter|fourth)\b", 25.0, None),
    (r"\b(?:a|one)[\s-]fifth\b", 20.0, None),
    (r"\b(?:a|one)[\s-]tenth\b", 10.0, None),
    (r"\b(?:one[\s-])?half\b", 50.0, None),
)
_WORD_AMOUNTS = [(re.compile(p, re.IGNORECASE), v, b) for p, v, b in WORD_AMOUNTS]
ZERO_AMOUNT = re.compile(
    r"\bnot\s+(?:a\s+)?single\b|\bno\s+(?:[\w-]+\s+){0,2}?(?:tumou?rs?|samples?|patients?|cases?|women|men)\b"
    r"|\bnone\s+of\s+the\b|\bzero\b|\bnobody\b",
    re.IGNORECASE,
)
_BOUND_OPS = (  # checked in order, each anchored at the end of the text before the number
    (re.compile(r"\b(?:no\s+more\s+than|at\s+most|up\s+to|not\s+more\s+than)\s*$", re.IGNORECASE), "lte"),
    (re.compile(r"\b(?:no\s+(?:fewer|less)\s+than|at\s+least|not\s+(?:fewer|less)\s+than)\s*$", re.IGNORECASE), "gte"),
    (re.compile(r"\b(?:more|greater|higher)\s+than\s*$|\b(?:over|above|exceeds?|exceeding|in\s+excess\s+of)\s*$", re.IGNORECASE), "gt"),
    (re.compile(r"\b(?:fewer|less|lower)\s+than\s*$|\b(?:under|below)\s*$", re.IGNORECASE), "lt"),
)
# Sentences that only look like claims: plans, advice, questions, methods.
NOT_A_FINDING = re.compile(
    r"^\s*(?:we|this\s+(?:summary|report|study|analysis|brief))\s+(?:recommend|suggest|propose|plan|will|aim|hope|looks?|describes?)\b"
    r"|\b(?:should|could|might|would)\b|\bfuture\s+work\b|\?\s*$",
    re.IGNORECASE,
)
_FACT_WORDS = re.compile(
    r"\b(?:most|majority|minority|half|third|quarter|fifth|tenth|all|every|none|few|rare(?:ly)?|common(?:ly)?|frequent(?:ly)?"
    r"|predominant(?:ly)?|largest|smallest|more|fewer|less|higher|lower|highest|lowest|greatest|twice|outnumber\w*"
    r"|dominate[sd]?|absent|none|no)\b",
    re.IGNORECASE,
)


@dataclass
class Entity:
    start: int
    end: int
    attribute: str
    category: str


def bound_op(before: str) -> str | None:
    for pattern, op in _BOUND_OPS:
        if pattern.search(before):
            return op
    return None


def _genes(text: str) -> list[tuple[int, int, str]]:
    """Gene symbols: TP53-style names anywhere, other capitalised symbols (MYC, PTEN) only next to a
    mutation or copy-number word, so "ER" or "TCGA" never count."""
    out: list[tuple[int, int, str]] = []
    for m in GENE_SYMBOL.finditer(text):
        name = m.group(0)
        if name.upper() in NOT_GENES or re.fullmatch(r"(?:19|20)\d\d|\d+", name):
            continue
        out.append((m.start(), m.end(), name.upper()))
    if _GENE_CONTEXT.search(text):
        for m in _GENE_CANDIDATE.finditer(text):
            name = m.group(0)
            if name.upper() in NOT_GENE_WORDS or name.upper() in NOT_GENES or any(a <= m.start() < b for a, b, _ in out):
                continue
            if m.start() > 0 and text[m.start() - 1] == "-":
                continue  # "TCGA-BRCA"
            near = text[max(0, m.start() - 40): m.end() + 40]
            if _GENE_CONTEXT.search(near) and not re.fullmatch(r"[A-Z]", name):
                out.append((m.start(), m.end(), name.upper()))
    return sorted(out)


def _gene_kind(words: str) -> str | None:
    """Which gene-level call a stretch of words names, if any."""
    if GAIN_WORDS.search(words) and not re.search(r"\bhigh[\s-]level\s+gains?\b", words, re.IGNORECASE):
        return "gain"
    if AMPLIFICATION_WORDS.search(words):
        return "amplification"
    if DELETION_WORDS.search(words) or re.search(r"\bhomozygous(?:ly)?\b", words, re.IGNORECASE):
        return "deletion"
    if LOSS_WORDS.search(words):
        return "loss"
    if MUTATION_WORDS.search(words):
        return "mutation"
    return None


def find_entities(text: str) -> list[Entity]:
    """Every attribute value the sentence names, in order: statuses, stage, histology, genes, deaths..."""
    found: list[Entity] = []
    taken: list[tuple[int, int]] = []

    def add(start: int, end: int, attribute: str, category: str) -> None:
        if any(a < end and start < b for a, b in taken):
            return
        taken.append((start, end))
        found.append(Entity(start, end, attribute, category))

    for m in TRIPLE_NEGATIVE.finditer(text):
        add(m.start(), m.end(), "triple_negative", "triple-negative")
    her2_amp = re.search(r"\bHER-?2\s+(?:gene\s+)?amplif\w*|\bamplif\w*\s+(?:of\s+)?HER-?2\b", text, re.IGNORECASE)
    if her2_amp:
        add(her2_amp.start(), her2_amp.end(), "amplification", "ERBB2")
    her2_over = re.search(r"\bHER-?2(?:/neu)?\s+(?:protein\s+)?over-?expressi\w*|\bover-?expressi\w*\s+(?:of\s+)?HER-?2\b", text, re.IGNORECASE)
    if her2_over:  # "HER2 overexpression by immunohistochemistry": HER2-positive status, not the HER2-enriched subtype
        add(her2_over.start(), her2_over.end(), "her2_status", "positive")
    for m in STATUS_ENTITY.finditer(text):
        rec = m.group("rec").lower().replace("-", "")
        key = "her2" if rec.startswith("her2") else rec.split()[0].replace("receptors", "").replace("receptor", "")
        attribute = _RECEPTOR.get(key) or _RECEPTOR.get(rec.split()[0])
        if attribute is None:
            continue
        word = (m.group("word") or "").lower()
        if word in ("equivocal", "indeterminate"):
            sign = word
        else:
            sign = "positive" if word.startswith("pos") or m.group("sym") == "+" else "negative"
        add(m.start(), m.end(), attribute, sign)
    for m in age_thresholds(text):
        op = (m.group("op") or m.group("op2") or "over").lower().split()[0]
        age = age_of(m)
        if m.group("age3"):  # "65+"
            code = "gte"
        elif m.group("op2"):  # "aged 70 or older", "aged seventy or more"
            code = "gte" if op in ("older", "over", "above", "more") else "lte"
        else:
            code = {"over": "gt", "older": "gt", "above": "gt", "at": "gte", "under": "lt", "younger": "lt", "below": "lt",
                    "diagnosed": "lt"}[op]
        add(m.start(), m.end(), "age_group", f"{code}{age}")
    union = LUMINAL_UNION.search(text)
    if union:  # "Luminal tumours (Luminal A and Luminal B together)": one group, A and B
        add(union.start(), union.end(), "subtype", "Luminal")
    for m in YEAR_GROUP.finditer(text):  # "diagnosed in 2010 or later", "diagnosed before 1990"
        if m.group("op"):  # "in 2010 or later": the year itself is in the group
            code = "gte" if m.group("op").lower() in ("later", "after") else "lte"
        else:
            code = {"before": "lt", "prior": "lt", "after": "gt", "since": "gte", "from": "gte"}[m.group("op2").lower().split()[0]]
        add(m.start(), m.end(), "diagnosis_year", f"{code}{m.group('y') or m.group('y2')}")
    for m in STAGE_UNION.finditer(text):
        union_name = stage_union(m.group("lo"), m.group("hi"), m.group("dir"))
        if union_name:
            add(m.start(), m.end(), "stage", union_name)
    for m in STAGE_ENTITY.finditer(text):
        roman = _ROMAN.get(m.group(1), m.group(1).upper())
        add(m.start(), m.end(), "stage", f"Stage {roman}{(m.group(2) or '').upper()}")
    for m in HISTOLOGY_ENTITY.finditer(text):
        add(m.start(), m.end(), "histology", m.group(1).lower())
    for m in MENOPAUSE_ENTITY.finditer(text):
        add(m.start(), m.end(), "menopause", m.group(1).lower())
    for m in DSS_WORDS.finditer(text):
        add(m.start(), m.end(), "dss_status", "deceased")
    for m in DEATH_ENTITY.finditer(text):
        add(m.start(), m.end(), "vital_status", "deceased")
    if not SURVIVAL_COMPARISON.search(text):
        for m in PFI_WORDS.finditer(text):
            add(m.start(), m.end(), "pfi_status", "event")
    if re.search(r"\bslides?\b|\bsections?\b", text, re.IGNORECASE):
        for m in SLIDE_KIND_ENTITY.finditer(text):
            add(m.start(), m.end(), "slide_kind", "frozen" if m.group(1).lower() == "frozen" else "diagnostic")
    for m in ALIVE_ENTITY.finditer(text):
        add(m.start(), m.end(), "vital_status", "living")
    for m in SUBTYPE_PATTERN.finditer(text):
        name = normalise_subtype(re.sub(r"[\s-]+", "", m.group(0)))
        if union and name in ("Luminal A", "Luminal B") and re.search(r"together|combined|\+|A\s*/\s*B", text, re.IGNORECASE):
            continue  # already counted as the Luminal group
        add(m.start(), m.end(), "subtype", name)
    genes = _genes(text)
    if genes:
        kind = (
            "gain" if GAIN_WORDS.search(text) and not re.search(r"\bhigh[\s-]level\s+gains?\b", text, re.IGNORECASE)
            else "amplification" if AMPLIFICATION_WORDS.search(text)
            else "deletion" if DELETION_WORDS.search(text)
            else "loss" if LOSS_WORDS.search(text)
            else "mutation" if MUTATION_WORDS.search(text)
            else None
        )
        if kind == "mutation" and len(genes) >= 2 and CO_OCCUR.search(text) and not re.search(r"\beach\b", text, re.IGNORECASE):
            # "TP53 and PIK3CA mutations co-occurred in 57 tumours": tumours with all of them
            add(genes[0][0], genes[-1][1], "mutation", "+".join(name for _, _, name in genes))
        if kind:
            # "CCND1 was amplified in 177 tumors and PTEN homozygously deleted in 56": each gene takes the
            # copy-number or mutation word nearest to it, the sentence's word only when its own words name none
            for k, (start, end, name) in enumerate(genes):
                after = text[end: genes[k + 1][0] if k + 1 < len(genes) else len(text)]
                before = text[genes[k - 1][1] if k > 0 else 0: start]
                add(start, end, _gene_kind(after) or _gene_kind(before) or kind, name)
    sex = SEX_ENTITY.search(text)
    if sex:
        word = sex.group(0).split()[-1].lower()
        add(sex.start(), sex.end(), "sex", "female" if word in ("female", "women") else "male")
    group = SEX_GROUP.search(text)
    if group and not sex:  # "None of the male patients had ...": a group named by sex
        word = (group.group("w") or group.group("w2")).lower()
        add(group.start("w") if group.group("w") else group.start("w2"),
            group.end("w") if group.group("w") else group.end("w2"), "sex", "female" if word in ("female", "women") else "male")
    found.sort(key=lambda e: e.start)
    # "Triple-negative tumours (ER-, PR-, HER2-)": a parenthesis right after an entity defines it.
    defined: list[tuple[int, int]] = []
    for e in found:
        m = re.match(r"\s*(?:tumou?rs?|cases?|disease|cancers?|carcinomas?)?\s*\(([^()]*)\)", text[e.end:], re.IGNORECASE)
        if m and not re.search(r"(?<![A-Za-z])\d", m.group(1)):  # "(ER-, PR-, HER2-)" names, "(n = 116)" counts
            defined.append((e.end + m.start(1), e.end + m.end(1)))
    return [e for e in found if not any(a <= e.start < b for a, b in defined)]


@dataclass
class Amount:
    start: int
    end: int
    value: float
    percent: bool
    approximate: bool
    bound: str | None
    high: float | None = None
    decimals: int = 0
    is_total: bool = False
    words: bool = False  # "a third", "most": not written as digits


def find_amounts(text: str) -> list[Amount]:
    """Digits (with their bounds) plus amount words ("a third", "most", "one in ten")."""
    amounts: list[Amount] = []
    taken: list[tuple[int, int]] = []
    # Fractions first, "one in ten" before the rest: its "ten" must not be read as a count of ten tumors.
    words = [(f.start, f.end, f.value, None) for f in fraction_amounts(text)]
    words += [(m.start(), m.end(), value, bound) for pattern, value, bound in _WORD_AMOUNTS for m in pattern.finditer(text)]
    for start, end, value_here, bound in words:
        if any(a < end and start < b for a, b in taken):
            continue
        before = text[:start]
        op = bound or bound_op(before)
        approx = bool(_APPROX_BEFORE.search(before)) or bound is None
        if bound is None and op is not None:
            approx = False
        taken.append((start, end))
        amounts.append(Amount(start, end, value_here, True, approx, op, None, 1, False, True))
    for m in ZERO_AMOUNT.finditer(text):  # "Not a single tumour carried a BRCA1 mutation": a count of 0
        if not any(a < m.end() and m.start() < b for a, b in taken):
            taken.append(m.span())
            amounts.append(Amount(m.start(), m.end(), 0.0, False, False, None, None, 0, False, False))
    for n in find_numbers(text):
        if any(a < n.end and n.start < b for a, b in taken):
            continue
        if _TIME_UNIT_AFTER.match(text, n.end) and not n.percent:
            continue
        before = text[: n.start]
        op = bound_op(before) if n.bound or re.search(r"\b(?:no|not)\s+(?:more|fewer|less)\s+than\s*$", before, re.IGNORECASE) else None
        amounts.append(Amount(n.start, n.end, n.value, n.percent, n.approximate, op, n.high, n.decimals, n.is_total))
    return sorted(amounts, key=lambda a: a.start)


def _not_a_finding(text: str) -> bool:
    return bool(NOT_A_FINDING.search(text))


def _states_a_fact(text: str) -> bool:
    """A sentence with no number that still asserts something checkable about named groups or genes."""
    if _not_a_finding(text):
        return False
    return bool(find_entities(text)) and bool(_FACT_WORDS.search(text) or RANK_PHRASE.search(text))


def _rule_unavailable(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    needs = []
    terms = []
    for pattern, need in _UNAVAILABLE:
        m = pattern.search(info.text)
        if m and need not in needs:
            needs.append(need)
            terms.append(m.group(0))
    if not needs:
        return None
    return Claim(
        id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.NOT_ANSWERABLE,
        needed_data=" and ".join(needs) + ", which this release does not contain", clinical_terms=terms,
    )


def _rule_survival_comparison(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    m = SURVIVAL_COMPARISON.search(info.text)
    if m is None:
        return None
    return Claim(
        id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.NOT_ANSWERABLE,
        needed_data=SURVIVAL_NEED, clinical_terms=[m.group(0)],
    )


_POPULATION_AFTER = re.compile(
    r"^\s*(?:\)\s*)?(?:breast\s+)?(?:cancers?\s+)?(?:primary\s+)?(?:invasive\s+)?"
    r"(?:tumou?rs?|samples?|patients?|cases?|women|cancers?|carcinomas?|specimens?|subgroup|group|disease)\b",
    re.IGNORECASE,
)
# "of the tumors scored HER2-positive": the group's noun comes before its status
_SCORED_BEFORE = re.compile(
    r"\b(?:of|among|in|within)\s+(?:the\s+|all\s+|these\s+)?(?:primary\s+)?(?:tumou?rs|patients|samples|cases|women)\s+"
    r"(?:scored|classed|classified|called|recorded|labell?ed|deemed|that\s+(?:are|were)|which\s+(?:are|were)|who\s+(?:are|were))\s+(?:as\s+)?$",
    re.IGNORECASE,
)
_SUBGROUP_BEFORE = re.compile(
    r"\b(?:of|among|in|within|across|for)\s+(?:the\s+|all\s+|these\s+|those\s+)?(?:[\d,]+\s+)?(?:primary\s+)?"
    r"(?:infiltrating\s+|invasive\s+)?$", re.IGNORECASE
)


def _split_subgroup(text: str, entities: list[Entity]) -> tuple[list[Entity], Entity | None]:
    """(entities the claim is about, the subgroup entity).

    The subgroup is the entity that names a population ("... of Basal-like tumours", "Among lobular
    carcinomas, 59% carried a CDH1 mutation", "one in ten Basal-like tumours was ER-positive"); the claim is
    about the other one. With two population-like entities, the one after of / among / in wins.
    """
    if len(entities) < 2:
        return entities, None
    lead = re.match(r"^\s*(?:among|in|of|within|for)\b([^,]*),", text, re.IGNORECASE)
    if lead:  # "Among tumors scored HER2-positive by immunohistochemistry, 87 show ERBB2 amplification"
        inside = [e for e in entities if e.end <= lead.end()]
        outside = [e for e in entities if e.start >= lead.end()]
        if len(inside) == 1 and outside and all((e.attribute, e.category) != (inside[0].attribute, inside[0].category) for e in outside):
            return outside, inside[0]
    cells = text.split(" | ")
    if len(cells) >= 3:  # a table row "Measure | Group | Value": the middle cell names the group
        group_start = len(cells[0]) + 3
        group_end = group_start + len(cells[1])
        in_group = [e for e in entities if group_start <= e.start < group_end]
        rest = [e for e in entities if not group_start <= e.start < group_end]
        if len(in_group) == 1 and rest:
            return rest, in_group[0]
    scored = [e for e in entities if e.attribute in GROUP_ATTRIBUTES and _SCORED_BEFORE.search(text[: e.start])]
    if len(scored) == 1 and len(entities) == 2:  # "of the tumors scored HER2-positive by IHC, ... ERBB2 amplification"
        return [e for e in entities if e is not scored[0]], scored[0]
    sexes = [e for e in entities if e.attribute == "sex"]
    if len(sexes) == 1 and len(entities) == 2 and SEX_GROUP.search(text):  # "No male patient had a Basal-like tumour"
        return [e for e in entities if e is not sexes[0]], sexes[0]
    groups = [e for e in entities if _POPULATION_AFTER.match(text[e.end:])]
    introduced = [e for e in groups if _SUBGROUP_BEFORE.search(text[: e.start])]
    pick = introduced[0] if introduced else (groups[0] if len(groups) == 1 else None)
    if pick is None:
        pick = next((e for e in entities if _SUBGROUP_BEFORE.search(text[: e.start])
                     and e.attribute in ("subtype", "triple_negative", "histology", "stage")), None)
    if pick is not None and any(e.attribute == pick.attribute and e.category != pick.category for e in entities):
        pick = None  # "Stage II ... while only 20 were Stage IV": two values of one attribute, not a subgroup
    if pick is not None:
        rest = [x for x in entities if x is not pick and (x.attribute, x.category) != (pick.attribute, pick.category)]
        if rest:
            return rest, pick
    return entities, None


def _params_for(entity: Entity, amount: Amount | None, subgroup: Entity | None, text: str) -> ClaimParams:
    params = ClaimParams(attribute=entity.attribute, category=entity.category, subject="primary_tumors")
    if subgroup is not None:
        params.within_attribute, params.within_category = subgroup.attribute, subgroup.category
    if amount is not None:
        params.stated_value = amount.value
        params.stated_high = amount.high
        params.approximate = amount.approximate
        params.bound = amount.bound
        params.decimals = amount.decimals if not amount.words else None
        params.unit = "percent" if amount.percent else "count"
    if re.search(r"\bpatients?\b|\bwomen\b|\bcases?\b|\bindividuals?\b", text, re.IGNORECASE):
        params.subject = "patients" if params.unit == "count" else params.subject
    return params


def _amount_for_claim(text: str, amounts: list[Amount]) -> tuple[Amount | None, Amount | None]:
    """(the stated amount, the stated total) among the sentence's amounts."""
    totals = [a for a in amounts if a.is_total and not a.percent]
    values = [a for a in amounts if not a.is_total]
    if not values:
        return None, None
    # a figure written in digits beats an amount word ("the majority (62%)" states 62%)
    value = next((a for a in values if a.percent and not a.words), None) or next(
        (a for a in values if a.percent), values[0])
    total = totals[0] if totals and not value.percent else None
    return value, total


def _rule_rank(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    text = info.text
    top = TOP_N_PHRASE.search(text)
    m = RANK_PHRASE.search(text) or RANK_PLACE.search(text)
    if not (m or top):
        return None
    entities = [e for e in find_entities(text) if e.attribute not in ("vital_status", "sex")]
    if not entities:
        return None
    if top:
        n = top.group("n").lower()
        top_n = int(_SMALL_NUMBERS.get(n, n))
        named = [e for e in entities if e.attribute == entities[0].attribute][:top_n]
        params = ClaimParams(attribute=named[0].attribute, category=named[0].category, unit="rank", top_n=top_n,
                             category_b=named[1].category if len(named) > 1 else None, subject="primary_tumors")
        params.stated_value = float(top_n)
    else:
        sup = m.group("sup").lower()
        least = sup.startswith(("least", "smallest", "rarest"))
        position = _ORDINAL_WORDS.get((m.group("ord") or "").lower(), 1)
        about, subgroup = _split_subgroup(text, entities)
        entity = min(about, key=lambda e: abs(e.start - m.start()))
        params = ClaimParams(attribute=entity.attribute, category=entity.category, unit="rank",
                             stated_value=float(position), direction="lower" if least else None, subject="primary_tumors")
        if subgroup is not None:
            params.within_attribute, params.within_category = subgroup.attribute, subgroup.category
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RANK, params=params)


_COUNT_AGAINST = re.compile(
    r"\b(?P<more>outnumber(?:s|ed|ing)?)\b|\b(?:are|were)\s+(?P<word>fewer|more)\s+than\b|^\s*(?P<lead>more|fewer)\s+(?:primary\s+)?(?:tumou?rs|patients|samples|cases)\s+(?:are|were)\b",
    re.IGNORECASE,
)


def _rule_count_against(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"HER2-positive tumours are fewer than ERBB2-amplified tumours": two different attributes, counted."""
    text = info.text
    m = _COUNT_AGAINST.search(text)
    if m is None or [n for n in numbers if not n.is_total]:
        return None
    entities = [e for e in find_entities(text) if e.attribute != "sex"]
    if len(entities) != 2 or entities[0].attribute == entities[1].attribute:
        return None  # two values of one attribute is _rule_ratio's
    a, b = entities
    more = bool(m.group("more")) or (m.group("word") or m.group("lead") or "").lower() == "more"
    params = ClaimParams(attribute=a.attribute, category=a.category, attribute_b=b.attribute, category_b=b.category,
                         unit="ratio", stated_value=1.0, bound="gt" if more else "lt", subject="primary_tumors")
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RATIO, params=params)


def _rule_ratio(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    text = info.text
    m = RATIO_PHRASE.search(text)
    if m is None:
        return None
    entities = find_entities(text)
    groups: dict[str, list[Entity]] = {}
    for e in entities:
        groups.setdefault(e.attribute, []).append(e)
    pair = next((g for g in groups.values() if len({x.category for x in g}) >= 2), None)
    if pair is None:
        return None
    a, b = pair[0], next(x for x in pair if x.category != pair[0].category)
    params = ClaimParams(attribute=a.attribute, category=a.category, category_b=b.category, unit="ratio",
                         subject="primary_tumors")
    target = next((e for e in entities if e.attribute != a.attribute), None)
    if m.group("times") and target is not None:  # "TP53 mutations are eight times as common in Basal-like as in Luminal A"
        params = ClaimParams(attribute=target.attribute, category=target.category, within_attribute=a.attribute,
                             within_category=a.category, category_b=b.category, measure="rate", unit="ratio",
                             subject="primary_tumors")
    before = text[: m.start()]
    params.approximate = bool(_APPROX_BEFORE.search(before)) or bool(re.search(r"\b(?:about|roughly|nearly|around|approximately|almost)\b", text[max(0, m.start() - 25): m.start()], re.IGNORECASE))
    if m.group("n"):
        raw = m.group("n").lower()
        params.stated_value = float(_SMALL_NUMBERS.get(raw, raw))
        params.bound = bound_op(before)  # "by more than two to one"
        if params.bound:
            params.approximate = False
    elif m.group("times"):
        raw = m.group("times").lower()
        if raw in ("twice", "double"):
            params.stated_value = 2.0
        else:
            first = re.match(r"(\d+(?:\.\d+)?|\w+)", raw).group(1)
            params.stated_value = float(first) if first.replace(".", "").isdigit() else number_value(first)
        if re.search(r"\b(?:more|over)\s+than\s*$", before, re.IGNORECASE):
            params.bound = "gt"
    else:  # "A outnumber B", alone (more A than B) or with the ratio after it ("about three to one")
        stated = _OUTNUMBER_RATIO.search(text, m.end())
        value = stated and (float(stated.group("n")) if stated.group("n")[0].isdigit() else number_value(stated.group("n")))
        if value:
            near = text[m.end(): stated.start("n")]
            params.stated_value = value
            params.bound = bound_op(near)
            params.approximate = not params.bound and bool(re.search(
                r"\b(?:about|roughly|nearly|around|approximately|almost|some)\s*$", near, re.IGNORECASE))
        else:
            params.stated_value, params.bound = 1.0, "gt"
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RATIO, params=params)


_COMPARE_SHARE = re.compile(
    r"\b(?:more|less|fewer)\s+(?:common(?:ly)?|frequent(?:ly)?|often|likely|prevalent)\b|\b(?:higher|lower|greater|smaller)\s+"
    r"(?:death\s+|mutation\s+|event\s+|amplification\s+)?(?:share|proportion|percentage|fraction|rate|frequency|prevalence)\b|\b(?:enriched|depleted|rarer|commoner)\s+(?:in|among)\b"
    r"|\bconcentrated\s+(?:in|among)\b",
    re.IGNORECASE,
)


def _rule_share_comparison(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"TP53 mutations are more common in Basal-like than in Luminal A tumors"."""
    text = info.text
    m = _COMPARE_SHARE.search(text)
    if m is None or not re.search(r"\bthan\b|\bversus\b|\bvs\.?(?!\w)|\bcompared\s+with\b", text, re.IGNORECASE):
        return None
    entities = find_entities(text)
    groups: dict[str, list[Entity]] = {}
    for e in entities:
        groups.setdefault(e.attribute, []).append(e)
    pair_attr = next((k for k, g in groups.items() if len({x.category for x in g}) >= 2), None)
    if pair_attr is None:
        return None
    pair = groups[pair_attr]
    others = [e for e in entities if e.attribute != pair_attr]
    word = m.group(0).lower()
    lower = word.startswith(("less", "fewer", "lower", "smaller", "depleted", "rarer"))
    if not others:  # "CCND1 amplification was more frequent than ERBB2 amplification": a ratio above 1
        a = pair[0]
        b = next(x for x in pair if x.category != a.category)
        params = ClaimParams(attribute=pair_attr, category=a.category, category_b=b.category, unit="ratio",
                             stated_value=1.0, bound="lt" if lower else "gt", subject="primary_tumors")
        return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RATIO, params=params)
    # "ER-negative tumors are more likely to carry TP53 mutations than ER-positive tumors": the group named
    # first is the subject; "more common in A than in B" also names A first.
    a = pair[0]
    b = next(x for x in pair if x.category != a.category)
    target = others[0]
    params = ClaimParams(attribute=target.attribute, category=target.category, within_attribute=pair_attr,
                         within_category=a.category, category_b=b.category, direction="lower" if lower else "higher",
                         subject="primary_tumors")
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COMPARISON, params=params)


def _rule_group_shares(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """One thing in two groups, a figure for each: "TP53 mutations are concentrated in basal-like tumors, where 85% carry
    one, against roughly one in ten Luminal A tumors". Each figure belongs to the group nearest it."""
    text = info.text
    entities = find_entities(text)
    groups = [e for e in entities if e.attribute in GROUP_ATTRIBUTES]
    targets = [e for e in entities if e not in groups or e.attribute == "vital_status"]
    groups = [e for e in groups if e not in targets]
    if len(targets) != 1 or len(groups) != 2 or groups[0].attribute != groups[1].attribute \
            or groups[0].category == groups[1].category:
        return None
    amounts = [a for a in find_amounts(text) if a.percent and not a.is_total]
    if len(amounts) != 2 or re.search(r"\b(?:each|both|together|combined)\b", text, re.IGNORECASE):
        return None

    def gap(a: "Amount", g: Entity) -> int:
        return g.start - a.end if a.end <= g.start else a.start - g.end

    first = min(groups, key=lambda g: gap(amounts[0], g))
    second = next(g for g in groups if g is not first)
    if gap(amounts[1], second) > gap(amounts[1], first):
        return None  # both figures sit by the same group: not one figure per group
    parts = []
    for k, (amount, group) in enumerate(((amounts[0], first), (amounts[1], second)), start=1):
        part = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.SHARE,
                     params=_params_for(targets[0], amount, group, text))
        parts.append(_part(part, f"{group.category}: {text[amount.start:amount.end]}", k))
    return _compound(info, claim_id, parts)


def _rule_attribute(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """A share or count of samples with an attribute: "77% are ER-positive", "TP53 is mutated in a third"."""
    text = info.text
    entities = find_entities(text)
    if not entities:
        return None
    amounts = find_amounts(text)
    value, total = _amount_for_claim(text, amounts)
    if value is None:
        return None
    if len(entities) == 1 and entities[0].attribute == "subtype" and entities[0].category != "Luminal" and value.percent:
        return None  # a subtype's share on its own is _rule_share's; its count ("421 Luminal A tumours") is ours
    about, subgroup = _split_subgroup(text, entities)
    if not about:
        return None
    entity = about[0]
    same = [e for e in about if e.attribute == entity.attribute]
    if len({e.category for e in same}) > 1:
        each = re.search(r"\b(?:each|both|every\s+one)\b", text, re.IGNORECASE)
        if each and not re.search(r"\btogether|\bcombined|\bbetween\s+them", text, re.IGNORECASE):
            # "GATA3 and MAP3K1 were each mutated in more than 10% of tumors": one check per gene
            parts = []
            for k, e in enumerate(dict((x.category, x) for x in same).values(), start=1):
                part = Claim(id=claim_id, text=text, sentence_index=info.index,
                             type=ClaimType.SHARE if value.percent else ClaimType.COUNT,
                             params=_params_for(e, value, subgroup, text))
                parts.append(_part(part, f"{e.category}: {text[value.start:value.end]}", k))
            return _compound(info, claim_id, parts)
        return None  # "Luminal A and Luminal B together", "a TP53 or PIK3CA mutation": not one value to check
    if entity.attribute == "sex" and not value.percent:
        return None  # "Twelve samples are male" is a count of samples; _rule_count owns it
    params = _params_for(entity, value, subgroup, text)
    if total is not None:
        params.stated_total = total.value
    claim_type = ClaimType.SHARE if value.percent else ClaimType.COUNT
    if claim_type == ClaimType.COUNT and entity.attribute == "vital_status":
        params.subject = "patients"
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=claim_type, params=params)


def _rule_subgroup_coverage(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"Protein data covers most triple-negative tumors", "RNA is available for 90% of Basal-like tumors"."""
    text = info.text
    layers = [layer for layer, pattern in LAYERS.items() if re.search(pattern, text, re.IGNORECASE)]
    if len(layers) != 1 or ALL_LAYERS.search(text):
        return None
    entities = find_entities(text)
    if len(entities) != 1 or entities[0].attribute in ("mutation", "amplification", "deletion", "gain", "loss"):
        return None
    if not _POPULATION_AFTER.match(text[entities[0].end:]):
        return None  # "151 patients died ... of those with survival data": the entity is the claim, not a group
    if not re.search(r"\b(?:cover\w*|available|have|has|had|with|include\w*|measured|profiled|present)\b", text, re.IGNORECASE):
        return None
    value, total = _amount_for_claim(text, find_amounts(text))
    params = ClaimParams(subject=f"has_{layers[0]}", within_attribute=entities[0].attribute,
                         within_category=entities[0].category)
    if value is None:
        if not EVERY_WORDS.search(text) and not re.search(r"\b(?:all|every|each)\b", text, re.IGNORECASE):
            return None
        params.unit = "all"
    else:
        params.unit = "percent" if value.percent else "count"
        params.stated_value, params.stated_high = value.value, value.high
        params.approximate, params.bound = value.approximate, value.bound
        params.decimals = value.decimals if not value.words else None
        if total is not None:
            params.stated_total = total.value
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COVERAGE, params=params)


STAT_PHRASE = re.compile(
    r"\b(?P<stat>median|mean|average|youngest|oldest)\s+(?:patient\s+)?(?:age|aged?)?\b|\bages?\s+ranged?\s+from\b",
    re.IGNORECASE,
)


_STAT_WORD = re.compile(
    r"\b(?P<w>median|mean|average|youngest|oldest|range[ds]?|ranging)\b", re.IGNORECASE
)
AGE_RANGE = re.compile(
    r"\b(?:between\s+the\s+ages\s+of\s+|aged\s+(?:between\s+)?|ages?\s+(?:ranged?\s+)?(?:from\s+)?)(\d{1,3})\s*(?:and|to|-|–)\s*(\d{1,3})\b",
    re.IGNORECASE,
)
_OS_TIME = re.compile(r"\b(?:overall\s+)?survival\s+time|\bfollow[\s-]?up(?:\s+time)?|\bOS\s+time|\btime\s+to\s+death", re.IGNORECASE)
_YEARS_VALUE = re.compile(
    r"(?<![\w.])(?P<n>\d+(?:\.\d+)?|" + _AGE_WORD + r"|one|two|three|four|five|six|seven|eight|nine|ten)\b\s*(?:-\s*(?P<hi>\d+(?:\.\d+)?)\s*)?"
    r"(?P<unit>years?|yrs?|months?|days?)?",
    re.IGNORECASE,
)


def _rule_statistic(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"The median age at diagnosis was 58 years (range 26-90); mean age, 59.5 years." One part per statistic.

    Ages are years at diagnosis; "median survival time / follow-up" reads survival.tsv OS.time in years.
    """
    text = info.text
    years = YEAR_SPAN.search(text)
    if years and not find_entities(text):
        parts = []
        for stat, raw in (("year_min", years.group(1)), ("year_max", years.group(2))):
            params = ClaimParams(unit="years", measure=stat, stated_value=float(raw), decimals=0, subject="primary_tumors")
            parts.append(_part(Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.STATISTIC,
                                     params=params), f"{'first' if stat == 'year_min' else 'last'} year {raw}", len(parts) + 1))
        busiest = _BUSIEST_YEAR.search(text)
        if busiest:  # "2010 is the busiest single year with 225 diagnoses"
            year = busiest.group("y")
            params = ClaimParams(unit="years", measure="year_mode", stated_value=float(year), decimals=0, subject="primary_tumors")
            parts.append(_part(Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.STATISTIC,
                                     params=params), f"busiest year {year}", len(parts) + 1))
            if busiest.group("n"):
                params = ClaimParams(unit="count", subject="primary_tumors", attribute="diagnosis_year", category=f"eq{year}",
                                     stated_value=float(busiest.group("n").replace(",", "")), decimals=0)
                parts.append(_part(Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COUNT,
                                         params=params), f"{busiest.group('n')} diagnosed in {year}", len(parts) + 1))
        return _compound(info, claim_id, parts)
    nodes = _NODES.search(text)
    stat_word = _STAT_WORD.search(text)
    if nodes and stat_word and stat_word.group("w").lower() in ("median", "mean", "average"):
        value = next((v for v in _YEARS_VALUE.finditer(text, stat_word.end()) if not (v.group("unit") or "")), None)
        if value is not None:  # "The median number of positive lymph nodes was one."
            raw = value.group("n")
            stat = {"average": "mean"}.get(stat_word.group("w").lower(), stat_word.group("w").lower())
            params = ClaimParams(unit="years", measure=f"nodes_{stat}", subject="primary_tumors",
                                 stated_value=float(raw) if raw[0].isdigit() else number_value(raw),
                                 decimals=len(raw.split(".")[1]) if "." in raw else 0)
            return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.STATISTIC, params=params)
    span = AGE_RANGE.search(text)
    if span is not None and not _STAT_WORD.search(text) and not find_entities(text):
        # "Patients were diagnosed between the ages of 26 and 89": the youngest and the oldest
        parts = []
        for stat, raw in (("min", span.group(1)), ("max", span.group(2))):
            params = ClaimParams(unit="years", measure=stat, stated_value=float(raw), decimals=0, subject="primary_tumors")
            label = f"{'youngest' if stat == 'min' else 'oldest'} {raw}"
            parts.append(_part(Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.STATISTIC,
                                     params=params), label, len(parts) + 1))
        return _compound(info, claim_id, parts)
    if not _STAT_WORD.search(text):
        return None
    os_time = bool(_OS_TIME.search(text))
    if not os_time and not re.search(r"\bage|\baged|\byears?\s+old\b|\byears\b|\bdiagnos", text, re.IGNORECASE):
        return None
    entities = [e for e in find_entities(text) if e.attribute != "vital_status"]
    pair = [e for e in entities if e.attribute == (entities[0].attribute if entities else None)]
    values = [m for m in re.finditer(r"(?<![\w.])(\d{2}(?:\.\d+)?)(?![\w.])", text)
              if not any(a <= m.start() < b for a, b in [x.span() for x in _DEFINITION.finditer(text)])]
    if len(entities) == 2 and len(pair) == 2 and pair[0].category != pair[1].category and len(values) == 2:
        # "Basal-like patients were diagnosed younger than Luminal A patients, with median ages of 54 and 61 years"
        stat = {"average": "mean"}.get(_STAT_WORD.search(text).group("w").lower(), _STAT_WORD.search(text).group("w").lower())
        if stat in ("median", "mean"):
            parts = []
            for entity, value in zip(pair, values):
                raw = value.group(1)
                params = ClaimParams(unit="years", measure=("os_" if os_time else "") + stat, stated_value=float(raw),
                                     decimals=len(raw.split(".")[1]) if "." in raw else 0, subject="primary_tumors",
                                     within_attribute=entity.attribute, within_category=entity.category)
                parts.append(_part(Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.STATISTIC,
                                         params=params), f"{entity.category}: {stat} {raw}", len(parts) + 1))
            return _compound(info, claim_id, parts)
    group = None
    if " | " in text and len(entities) == 1:  # a table row: "Median age at diagnosis | Basal tumours | 54 years"
        group = entities[0]
    elif len(entities) > 1 or entities and not _SUBGROUP_BEFORE.search(text[: entities[0].start]):
        return None  # "HER2-enriched tumors are more aggressive, and the median age was 58": not only an age
    elif entities:
        group = entities[0]  # "Among triple-negative tumors, the median age was 55 years"
    marks = list(_STAT_WORD.finditer(text))
    parts: list[Claim] = []
    for k, mark in enumerate(marks):
        stop = marks[k + 1].start() if k + 1 < len(marks) else len(text)
        segment_start = mark.end()
        value = None
        for v in _YEARS_VALUE.finditer(text, segment_start, stop):
            raw = v.group("n").lower()
            if not raw[0].isdigit() and not v.group("unit") and (number_value(raw) or 0) < 18:
                continue  # a small word number only counts with its unit: "under three years"; "ninety" is an age
            if any(a <= v.start() < b for a, b in [m.span() for m in _DEFINITION.finditer(text)]):
                continue
            value = v
            break
        if value is None and len(marks) == 1:  # "diagnosed at fifty-eight, going by the median": the age comes first
            value = next((v for v in _YEARS_VALUE.finditer(text, 0, mark.start())
                          if not v.group("n")[0].isdigit() or _AGE_NUMBER_BEFORE.search(text[: v.start()])), None)
            if value is not None and not value.group("n")[0].isdigit() and (number_value(value.group("n")) or 0) < 18:
                value = None
        if value is None:
            continue
        word = mark.group("w").lower()
        raw_n = value.group("n")
        number = float(raw_n) if raw_n[0].isdigit() else number_value(raw_n)
        decimals = len(value.group("n").split(".")[1]) if "." in value.group("n") else 0
        unit = (value.group("unit") or "years").lower()
        if unit.startswith("month") or unit.startswith("day"):
            # "843 days" holds when our time is 843 days: keep the precision written, in years (4 more places ~ 0.04 day)
            decimals += 4 if unit.startswith("day") else 3
            number = round(number / (365.25 if unit.startswith("day") else 12), decimals)
        before = text[segment_start:value.start()]
        approx = bool(re.search(r"\b(?:about|roughly|around|approximately|nearly|almost|~)\s*$", before, re.IGNORECASE))
        bound = bound_op(text[: value.start()])
        if word.startswith("rang"):
            if not value.group("hi"):
                continue
            stats = [("min", number, f"{text[value.start():value.end()]} (youngest)"),
                     ("max", float(value.group("hi")), f"{text[value.start():value.end()]} (oldest)")]
        else:
            stat = {"average": "mean", "youngest": "min", "oldest": "max"}.get(word, word)
            stats = [(stat, number, text[mark.start():value.end()])]
        for stat, val, label in stats:
            params = ClaimParams(unit="years", measure=("os_" if os_time else "") + stat, stated_value=val,
                                 decimals=decimals, approximate=approx, bound=bound if stat not in ("min", "max") else None,
                                 subject="primary_tumors")
            if group is not None:
                params.within_attribute, params.within_category = group.attribute, group.category
            part = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.STATISTIC, params=params)
            parts.append(_part(part, label, len(parts) + 1))
    if not parts:
        return None
    if len(parts) == 1:
        single = parts[0]
        single.id, single.part_label = claim_id, ""
        return single
    return _compound(info, claim_id, parts)


_TRAILING_JOINERS = re.compile(
    r"(?:[\s,;:.]+|\s+(?:and|or|from|of|with|in|for|while|whereas|but|plus|to|compared|versus|vs\.?|than|only))+$", re.IGNORECASE
)


def _part(claim: Claim, label: str, index: int) -> Claim:
    claim.id = f"{claim.id}.{index}"
    claim.part_label = _TRAILING_JOINERS.sub("", label.strip()).strip(" ,;")
    return claim


UNKNOWN_SEX_BEFORE = re.compile(
    r"\b(?:sex|gender)\s+(?:was\s+|is\s+|were\s+)?(?:missing|unknown|not\s+recorded|unrecorded|absent|not\s+known)\s+(?:for|in)\s*$",
    re.IGNORECASE,
)
UNKNOWN_SEX_AFTER = re.compile(
    r"^\s*(?:\w+\s+){0,2}?(?:with|have|had|has)\s+(?:no|an?\s+unknown|unknown|missing|unrecorded)\s+(?:recorded\s+)?(?:sex|gender)\b",
    re.IGNORECASE,
)


def _count_window_subject(text: str, start: int, end: int, number_start: int | None = None) -> str | None:
    """Count subject for a number: filters from the words right after it (or, in a "label, number" list such as
    "(normal tissue, 139; metastatic, 7)", right before it) and the count noun after it, else before it."""
    window = re.split(r"[(;]", text[start:end], maxsplit=1)[0]
    filters = [name for name, pattern in COUNT_FILTERS.items() if re.search(pattern, window, re.IGNORECASE)]
    if number_start is not None and (UNKNOWN_SEX_BEFORE.search(text[:number_start]) or UNKNOWN_SEX_AFTER.match(window)):
        filters = ["unknown_sex"]  # "with sex missing for 4", "4 with no recorded sex": neither women nor men
    if not filters and number_start is not None:
        before = re.split(r"[(;]", text[:number_start])[-1]
        if re.search(r"[,:]\s*$", before):
            filters = [name for name, pattern in COUNT_FILTERS.items() if re.search(pattern, before, re.IGNORECASE)]
    noun = _COUNT_NOUN.search(text, start)
    if noun is None:
        earlier = list(_COUNT_NOUN.finditer(text, 0, start))
        if not earlier:
            return None
        noun = earlier[-1]
    kind = COUNT_NOUNS[noun.group(1).lower()]
    if len(filters) > 1 or {"male", "female"} <= set(filters):
        return None
    if filters and filters[0] in ("normal_tissue", "metastatic") and kind == "primary_tumors":
        kind = "samples"  # "Primary tumours numbered 1,101 (normal tissue, 139; ...)": normal tissue is not a tumour
    return f"{filters[0]}_{kind}" if filters else kind


def _rule_compound(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """A sentence that makes several checks: one part per stated number, plus a rank stated with a share."""
    text = info.text
    rank_claim = _rule_rank(info, claim_id, numbers) if (RANK_PHRASE.search(text) or TOP_N_PHRASE.search(text)) else None
    all_amounts = find_amounts(text)
    amounts = [a for a in all_amounts if not a.is_total and not a.words]

    if rank_claim is not None and not rank_claim.params.top_n:
        rank_entity = Entity(0, 0, rank_claim.params.attribute, rank_claim.params.category)
        sup = RANK_PHRASE.search(text)
        rank_label = text[: sup.end()] if sup else text
        followers = _followed_by(text, rank_claim)
        if not amounts and followers:  # "Luminal A was the most common, followed by Luminal B and then Basal-like"
            return _compound(info, claim_id, [_part(rank_claim, rank_label, 1)] + [
                _part(f, f.part_label, k) for k, f in enumerate(followers, start=2)])
        if len(amounts) == 1 or (not amounts and [a for a in all_amounts if a.words and not a.is_total]):
            amount = amounts[0] if amounts else next(a for a in all_amounts if a.words and not a.is_total)
            if rank_entity.attribute == "subtype" and amount.percent and not find_entities_except(text, "subtype"):
                share = _rule_share(info, claim_id, numbers)  # keeps the subtype share's own wording and limitation
            else:
                share = None
            if share is None:
                params = _params_for(rank_entity, amount, None, text)
                if rank_claim.params.within_attribute:
                    params.within_attribute = rank_claim.params.within_attribute
                    params.within_category = rank_claim.params.within_category
                share = Claim(id=claim_id, text=text, sentence_index=info.index,
                              type=ClaimType.SHARE if amount.percent else ClaimType.COUNT, params=params)
            return _compound(info, claim_id, [_part(share, text[amount.start:], 1), _part(rank_claim, rank_label, 2)])

    if len(amounts) < 2:
        return None
    comparison = _rule_share_comparison(info, claim_id, numbers)
    percents = [a for a in amounts if a.percent]
    if comparison is not None and comparison.type == ClaimType.COMPARISON and len(percents) == 2:
        # "TP53 mutations were more common in Basal-like tumors (85%) than in Luminal A tumors (10%)",
        # "CDH1 mutations were concentrated in lobular tumours (85/144; 59.0%) versus ductal tumours (9/560; 1.6%)"
        cp = comparison.params
        parts = []
        for k, (amount, group) in enumerate(zip(percents, (cp.within_category, cp.category_b)), start=1):
            params = ClaimParams(attribute=cp.attribute, category=cp.category, within_attribute=cp.within_attribute,
                                 within_category=group, subject="primary_tumors", unit="percent",
                                 stated_value=amount.value, stated_high=amount.high, approximate=amount.approximate,
                                 bound=amount.bound, decimals=amount.decimals)
            share = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.SHARE, params=params)
            parts.append(_part(share, f"{group}: {text[amount.start:amount.end]}", k))
        parts.append(_part(comparison, f"more common in {cp.within_category} than {cp.category_b}"
                           if cp.direction == "higher" else f"less common in {cp.within_category} than {cp.category_b}", 3))
        return _compound(info, claim_id, parts)
    entities_all = find_entities(text)
    by_group = _group_shares(info, claim_id, amounts, entities_all)
    if by_group is not None:
        return by_group
    if amounts[0].approximate:  # "About 77% are ER-positive and 66% are PR-positive": "about" covers both
        for later in amounts[1:]:
            if later.bound is None and later.high is None:
                later.approximate = True
    totals = [a for a in all_amounts if a.is_total and not a.percent]

    # "264 (33%)": a count and its percent state one thing; they share one entity.
    same_as_previous = [
        k > 0 and (
            amounts[k].percent and not amounts[k - 1].percent
            # "264 (33%)", "124 of 136 with a known ER status (91.2%)": the percent of that count, in brackets
            and re.fullmatch(r"(?:\s+of\s+[\d,]+)?[^\d;()]{0,60}\(\s*", text[amounts[k - 1].end:amounts[k].start]) is not None
            # "16.1% of the 722 tumours with all three receptors known (n = 116)": the count of the same group
            or not amounts[k].percent and amounts[k - 1].percent
            and re.search(r"\(\s*n\s*=\s*$", text[amounts[k - 1].end:amounts[k].start], re.IGNORECASE) is not None
        )
        for k in range(len(amounts))
    ]
    statements = sum(1 for flag in same_as_previous if not flag)
    entities = [e for e in find_entities(text) if e.attribute != "sex"]
    _, subgroup = _split_subgroup(text, entities)
    pairing = [e for e in entities if e is not subgroup]
    paired: list[Entity | None] = []
    if pairing and len(pairing) == statements:  # entities and figures named in the same order
        it = iter(pairing)
        for flag in same_as_previous:
            paired.append(paired[-1] if flag else next(it))
    else:
        paired = [None] * len(amounts)

    # "Copy number profiles are available for 1,080 primary tumors and protein profiles for 724": layers and
    # figures named in the same order pair up in that order.
    layer_marks = sorted((m.start(), layer) for layer, pattern in LAYERS.items() for m in re.finditer(pattern, text, re.IGNORECASE))
    ordered_layers = [layer for _, layer in layer_marks] if (not pairing and len(layer_marks) == len(amounts)
                                                             and not ALL_LAYERS.search(text)) else []
    parts: list[Claim] = []
    for k, amount in enumerate(amounts):
        nxt = amounts[k + 1].start if k + 1 < len(amounts) else len(text)
        prev = amounts[k - 1].end if k > 0 else 0
        window = text[amount.end:nxt]
        entity = paired[k]
        if entity is None:
            window_entities = [_shifted(e, amount.end) for e in find_entities(window) if e.attribute != "sex"]
            if not window_entities:
                window_entities = [_shifted(e, prev) for e in find_entities(text[prev:amount.start]) if e.attribute != "sex"]
            if same_as_previous[k] and parts:
                window_entities = []  # use the count's own reading below
            entity = window_entities[0] if window_entities else None
            if entity is None and len(pairing) == 1 and not same_as_previous[k]:
                entity = pairing[0]  # "Stage II predominated (622 of 1,075 staged tumours; 58%)": one thing named
            if entity is not None and _out_of_group(text, amount, entity, entities):
                # "59% of lobular carcinomas" names the group the share is out of, not what was counted; with
                # something else named too, we cannot tell what was counted, so we do not guess
                return _unsure(info, claim_id)
        window_layers = [layer for layer, pattern in LAYERS.items() if re.search(pattern, window, re.IGNORECASE)]
        if not window_layers:
            window_layers = [layer for layer, pattern in LAYERS.items() if re.search(pattern, text[prev:amount.start], re.IGNORECASE)]
        if ordered_layers:
            window_layers = [ordered_layers[k]]
        stated = dict(stated_value=amount.value, stated_high=amount.high, approximate=amount.approximate,
                      bound=amount.bound, decimals=amount.decimals)
        if same_as_previous[k] and parts and parts[-1].params.attribute is None and entity is None:
            prior = parts[-1].params
            params = ClaimParams(subject=prior.subject, subtype=prior.subtype, unit="percent", **stated)
            kind = ClaimType.COVERAGE if (prior.subject or "").startswith("has_") else ClaimType.SHARE
            if kind == ClaimType.SHARE and prior.subtype is None:
                return None  # the percent of a plain count has no denominator we can name
            part = Claim(id=claim_id, text=text, sentence_index=info.index, type=kind, params=params)
        elif entity is not None and entity.attribute != "subtype":
            params = _params_for(entity, amount, subgroup if subgroup is not entity else None, text[amount.start:nxt])
            if not amount.percent and entity.attribute in ("vital_status", "dss_status"):
                params.subject = "patients"
            if totals and not amount.percent:
                params.stated_total = totals[0].value
            part = Claim(id=claim_id, text=text, sentence_index=info.index,
                         type=ClaimType.SHARE if amount.percent else ClaimType.COUNT, params=params)
        elif entity is not None and amount.percent:  # "Luminal A is 50% and Basal-like 17% of ..."
            params = ClaimParams(subtype=entity.category, subject="primary_tumors", unit="percent", **stated)
            part = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.SHARE, params=params)
        elif entity is not None:  # "421 Luminal A and 141 Basal-like tumours"
            params = _params_for(entity, amount, None, text[amount.start:nxt])
            part = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COUNT, params=params)
        elif len(window_layers) == 1 and not ALL_LAYERS.search(window):  # "821 have RNA and 742 have protein data"
            params = ClaimParams(subject=f"has_{window_layers[0]}", unit="percent" if amount.percent else "count", **stated)
            if totals and not amount.percent:
                params.stated_total = totals[0].value
            part = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COVERAGE, params=params)
        elif not amount.percent and feature_layer(text, amount.end):  # "... measured across 131 proteins"
            params = ClaimParams(unit="count", subject=f"features:{feature_layer(text, amount.end)}", **stated)
            part = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COUNT, params=params)
        elif not amount.percent:
            subject = _count_window_subject(text, amount.end, nxt, amount.start)
            if subject is None:
                return None
            params = ClaimParams(unit="count", subject=subject, **stated)
            part = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COUNT, params=params)
        else:
            return None
        parts.append(_part(part, text[amount.start:nxt], k + 1))
    keys = {(p.params.subject, p.params.attribute, p.params.category, p.params.subtype, p.params.unit) for p in parts}
    if len(keys) < len(parts):
        return None  # the same thing stated twice: not separate statements we can tell apart
    if rank_claim is not None:  # "Stage II was the most common stage (622 tumors), while only 20 were Stage IV"
        sup = RANK_PHRASE.search(text)
        parts.append(_part(rank_claim, text[: sup.end()] if sup else text, len(parts) + 1))
    ratio = _rule_ratio(info, claim_id, numbers) if RATIO_PHRASE.search(text) else None
    if ratio is not None:  # "outnumbered HER2-enriched tumours by more than two to one (141 versus 67)"
        m = RATIO_PHRASE.search(text)
        parts.append(_part(ratio, text[max(0, m.start() - 40): m.end()].split(",")[-1], len(parts) + 1))
    return _compound(info, claim_id, parts)


def _followed_by(text: str, rank_claim: Claim) -> list[Claim]:
    """"X was the most common, followed by Y and then Z": rank claims for Y (2nd) and Z (3rd)."""
    m = re.search(r"\bfollowed\s+by\b", text, re.IGNORECASE)
    if m is None:
        return []
    later = [e for e in find_entities(text[m.end():]) if e.attribute == rank_claim.params.attribute]
    claims = []
    for k, e in enumerate(later, start=2):
        params = replace(rank_claim.params, category=e.category, stated_value=float(k))
        c = Claim(id=rank_claim.id, text=text, sentence_index=rank_claim.sentence_index, type=ClaimType.RANK, params=params)
        c.part_label = f"{e.category} {_ordinal_word(k)}"
        claims.append(c)
    return claims


def _ordinal_word(n: int) -> str:
    return {2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(n, f"#{n}")


def _compound(info: SentenceInfo, claim_id: str, parts: list[Claim]) -> Claim:
    first = parts[0]
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=first.type, params=first.params,
                 parts=parts)


_CLAUSE_SPLIT = re.compile(r";\s+|,\s+(?:and|while|whereas|but)\s+|\)\s+(?:and|while|whereas|but)\s+")
_SUBJECT_END = re.compile(
    r"\b(?:was|were|is|are|had|has|have|showed|accounted|comprised|numbered|made|makes?|predominated|occurred|"
    r"affects?|affected|present|represent\w*|appeared|occur)\b",
    re.IGNORECASE,
)


def _clause_spans(text: str) -> list[tuple[int, int]]:
    """Split at ";" / ", and" / ", while" outside parentheses: "ER+ (808/1,046; 77.3%); PR+ (699 of 1,043)"."""
    spans, start = [], 0
    for m in _CLAUSE_SPLIT.finditer(text):
        depth = text[: m.start()].count("(") - text[: m.start()].count(")")
        cut = m.start() + (1 if m.group(0).startswith(")") else 0)
        if depth > (1 if m.group(0).startswith(")") else 0):
            continue
        spans.append((start, cut))
        start = m.end()
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip(" ,;.")]


def _rule_clauses(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """A sentence of several clauses that each state a figure: each clause is read as its own sentence.

    "GATA3 mutations were absent in basal tumours (0/106) and present in 12.3% of all sequenced tumours":
    a clause that names nothing ("present in 12.3% ...") borrows the first clause's subject.
    """
    text = info.text
    spans = _clause_spans(text)
    if len(spans) < 2:
        return None
    clauses = [text[a:b].strip(" ,;.") for a, b in spans]
    if not all([a for a in find_amounts(c) if not a.is_total] for c in clauses):
        return None  # only when every clause states its own figure
    first = clauses[0]
    verb = _SUBJECT_END.search(first)
    subject = first[: verb.start()].strip() if verb else ""
    parts: list[Claim] = []
    named = [e for e in find_entities(first) if e.attribute in GROUP_ATTRIBUTES]
    for clause in clauses:
        reading = clause
        if subject and find_entities(subject) and not find_entities(clause) and not _layers(clause):
            reading = f"{subject} {clause}"
        them = OF_THEM.search(reading)
        if them and clause is not first:
            if len({(e.attribute, e.category) for e in named}) != 1:
                return None  # no single group for "them" to mean; _rule_of_them marks the sentence unsure
            group = first[named[0].start:named[0].end]
            noun = "" if _POPULATION_AFTER.match(first[named[0].end:]) is None else _POPULATION_AFTER.match(first[named[0].end:]).group(0)
            reading = f"{reading[:them.start()]}of {group}{noun or ' tumors'}{reading[them.end():]}"
        sub = classify_sentence(SentenceInfo(index=info.index, text=reading + ".", claim_id=None), claim_id)
        if sub is None or sub.type in (ClaimType.UNMAPPED, ClaimType.NOT_ANSWERABLE):
            return None
        for piece in sub.parts or [sub]:
            parts.append(_part(piece, piece.part_label or clause, len(parts) + 1))
    return _compound(info, claim_id, parts)


_PROTEIN_WORDS = re.compile(r"\bprotein\b|\bRPPA\b|\blevels?\b|\babundance\b|\bexpression\b", re.IGNORECASE)
# Two means: "2.18 vs -0.87", "2.18 in ER-positive tumors against -0.87 in ER-negative tumors".
_SIGNED_PAIR = re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*(?:(?:in|among|for)\s+[\w+-]+(?:\s+[\w+,-]+){0,8}?\s+)?"
    r"(?:vs\.?|versus|compared\s+with|against|and)\s*(-?\d+(?:\.\d+)?)(?![\w.])",
    re.IGNORECASE,
)


def protein_key(name: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", name.upper()).replace("ALFA", "ALPHA")


def _rule_protein_comparison(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """A protein compared between two groups of any attribute: "E-cadherin protein was lower in lobular than in
    ductal tumours", "Mean ER-alpha protein (RPPA) | ER-positive vs ER-negative | 2.18 vs -0.87"."""
    text = info.text
    if not _PROTEIN_WORDS.search(text):
        return None
    name = re.search(r"\b([A-Z][A-Za-z0-9-]*[A-Za-z0-9](?:[\s-]?(?:alpha|α))?)\s+(?:\(RPPA\)\s+)?(?:protein|levels?|abundance|expression)\b"
                     r"|\b(?:mean|average|median)\s+([A-Za-z0-9-]+(?:[\s-]?(?:alpha|α))?)\s+(?:protein|levels?)", text)
    if name is None:
        return None
    measure = (name.group(1) or name.group(2)).replace("α", "alpha")
    rppa = re.search(r"\(RPPA\s+([A-Z][A-Z0-9]{2,})\)", text)  # "cyclin B1 protein (RPPA CYCLINB1)": the file's own name
    two_words = re.search(r"\b([a-z]+[\s-][A-Z0-9]+)\s+(?:\(RPPA[^)]*\)\s+)?protein\b", text)  # "cyclin B1 protein"
    if rppa:
        measure = rppa.group(1)
    elif two_words and len(measure) <= 3:
        measure = two_words.group(1)
    entities = [e for e in find_entities(text) if e.attribute not in ("mutation", "amplification", "deletion", "gain", "loss")]
    groups: dict[str, list[Entity]] = {}
    for e in entities:
        groups.setdefault(e.attribute, []).append(e)
    pair = next((g for g in groups.values() if len({x.category for x in g}) >= 2), None)
    if pair is None:
        return None
    a = pair[0]
    b = next(x for x in pair if x.category != a.category)
    means = _SIGNED_PAIR.search(text)
    direction = _direction(text)
    if direction is None and means is None:
        return None
    params = ClaimParams(measure=measure, within_attribute=a.attribute, within_category=a.category, category_b=b.category,
                         direction=direction, subject="primary_tumors")
    if means is not None:
        first, second = means.group(1), means.group(2)
        params.stated_value, params.stated_high = float(first), float(second)
        params.decimals = max(len(first.split(".")[1]) if "." in first else 0, len(second.split(".")[1]) if "." in second else 0)
        if direction is None:
            params.direction = "higher" if float(first) > float(second) else "lower"
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COMPARISON, params=params)


def find_entities_except(text: str, attribute: str) -> list[Entity]:
    return [e for e in find_entities(text) if e.attribute != attribute]


READINESS = re.compile(
    r"\b(?:large|big)\s+enough\b|\b(?:enough|sufficient|adequate)\s+(?:samples|tumou?rs|patients|cases|power|data|numbers?)\b"
    r"|\b(?:adequately|well|under)[\s-]?powered\b|\bsample\s+sizes?\s+(?:is|are|was|were)\s+(?:sufficient|adequate|enough|large)\b"
    r"|\bsufficient(?:ly)?\s+(?:large|sized|powered)\b",
    re.IGNORECASE,
)
READINESS_NEED = (
    "a pre-specified sample-size requirement (for example from a power calculation); whether a cohort is "
    "large enough is a judgment the counts alone cannot make"
)


def _rule_readiness(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"The cohort is large enough for a subtype comparison": no threshold to test, so a person decides."""
    m = READINESS.search(info.text)
    if m is None or _not_a_finding(info.text):
        return None
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.NOT_ANSWERABLE,
                 needed_data=READINESS_NEED, clinical_terms=[])


def _rule_not_answerable_first(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    return _rule_not_answerable(info, claim_id, numbers) or _rule_unavailable(info, claim_id, numbers) \
        or _rule_survival_comparison(info, claim_id, numbers)


def _rule_share_alone(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """A subtype share, unless the sentence also names another attribute (then the subtype is a subgroup)."""
    if find_entities_except(info.text, "subtype"):
        return None
    share = _rule_share(info, claim_id, numbers)
    if share is not None or len(_subtypes(info.text)) != 1:
        return share
    words = [a for a in find_amounts(info.text) if a.words and not a.is_total]
    if not words:
        return None
    # "Nearly half of primary tumours with an RNA subtype call were Luminal A"
    params = ClaimParams(subtype=_subtypes(info.text)[0], subject="primary_tumors")
    _stated_amount(params, words[0])
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.SHARE, params=params)


# Plans and calls for more work: they name treatments or data, but assert nothing about this release.
FORWARD_LOOKING = re.compile(
    r"\bwill\s+be\s+(?:needed|required|necessary)\b|\b(?:are|is)\s+(?:still\s+)?(?:needed|required)\b|\bwill\s+need\b"
    r"|\bfuture\s+(?:work|studies|research|analyses)\b|\bwe\s+(?:recommend|encourage|suggest|propose|plan|hope|intend)\b"
    r"|\bremains?\s+to\s+be\s+(?:seen|tested|shown)\b",
    re.IGNORECASE,
)


RATE_RANK = re.compile(
    r"\b(?P<sup>highest|lowest|greatest|largest|smallest)\s+(?:\w+[\s-]+){0,2}?(?:rate|share|proportion|percentage|frequency|prevalence)\b"
    r"|\b(?:rate|share|proportion|percentage|frequency|prevalence)\s+(?:\w+\s+){0,3}?(?:was|is)\s+(?P<sup2>highest|lowest)\b",
    re.IGNORECASE,
)


def _rule_rate_rank(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"Basal-like tumours showed the highest death rate of any PAM50 subtype": the group whose rate ranks first."""
    text = info.text
    m = RATE_RANK.search(text)
    if m is None:
        return None
    entities = find_entities(text)
    groups = [e for e in entities if e.attribute in ("subtype", "stage", "histology", "triple_negative", "er_status",
                                                     "pr_status", "her2_status", "menopause", "age_group")]
    targets = [e for e in entities if e not in groups]
    if len(groups) != 1 or len(targets) != 1:
        return None
    sup = (m.group("sup") or m.group("sup2")).lower()
    params = ClaimParams(attribute=targets[0].attribute, category=targets[0].category, within_attribute=groups[0].attribute,
                         within_category=groups[0].category, measure="rate", unit="rank", stated_value=1.0,
                         direction="lower" if sup in ("lowest", "smallest") else None, subject="primary_tumors")
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RANK, params=params)


EVERY_SLIDE = re.compile(r"\b(?:every|each|all(?:\s+of\s+the)?)\s+(?:\w+\s+){0,2}?slides?\b", re.IGNORECASE)


def _rule_every_slide(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"Every slide in the archive is a diagnostic FFPE slide": a share of slides, stated as 100%."""
    if not EVERY_SLIDE.search(info.text):
        return None
    kinds = [e for e in find_entities(info.text) if e.attribute == "slide_kind"]
    if len({e.category for e in kinds}) != 1:
        return None
    params = ClaimParams(attribute="slide_kind", category=kinds[0].category, subject="slides", unit="percent",
                         stated_value=100.0, decimals=0)
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.SHARE, params=params)


LAYER_SUBSET = re.compile(
    r"\b(?:every|each|all(?:\s+of\s+the)?|any)(?:\s+one\s+of\s+the|\s+of\s+the)?\s+(?P<n>[\d,]+\s+)?(?:primary\s+)?(?:tumou?rs?|samples?|patients?|cases?)\s+(?:that\s+(?:has|have)|with)\s+(?P<a>.+?)"
    r"\s+(?:data\s+|profiles?\s+|measurements?\s+)?(?:also\s+)?(?:has|have|had|is\s+in|are\s+in)\s+(?P<b>.+?)\s*(?:data|profiles?|measurements?)?\s*[.!]?$",
    re.IGNORECASE,
)


def _rule_layer_subset(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"Every primary tumor with protein data also has RNA data": coverage of one layer among samples with another."""
    m = LAYER_SUBSET.search(info.text)
    if m is None or [x for x in numbers if not (m.group("n") and m.start("n") <= x.start < m.end("n"))]:
        return None
    a = [layer for layer, pattern in LAYERS.items() if re.search(pattern, m.group("a"), re.IGNORECASE)]
    b = [layer for layer, pattern in LAYERS.items() if re.search(pattern, m.group("b"), re.IGNORECASE)]
    if len(a) != 1 or len(b) != 1 or a == b:
        return None
    params = ClaimParams(subject=f"has_{b[0]}", unit="all", within_attribute="layer", within_category=a[0])
    subset = Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COVERAGE, params=params)
    if not m.group("n"):
        return subset
    size = float(m.group("n").replace(",", ""))  # "Every one of the 742 primary tumors with protein data ...": 742 too
    count = Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.COVERAGE,
                  params=ClaimParams(subject=f"has_{a[0]}", unit="count", stated_value=size, decimals=0))
    return _compound(info, claim_id, [_part(count, m.group("n").strip(), 1), _part(subset, f"all have {b[0]} data", 2)])


def _rule_protein_first(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """Protein comparisons before the multi-figure rules: "2.18 vs -0.87" are two means, not two counts."""
    if _rule_comparison(info, claim_id, numbers) is not None:
        return None  # the receptor comparison (reference analysis A1) keeps its own rule, later
    return _rule_protein_comparison(info, claim_id, numbers)


# ---------------------------------------------------------------------------------------------
# Sentences that say several things about named groups
# ---------------------------------------------------------------------------------------------

# Attributes that name a group of samples a share can be taken within ("of lobular carcinomas").
GROUP_ATTRIBUTES = ("subtype", "stage", "histology", "triple_negative", "er_status", "pr_status", "her2_status",
                    "hr_status", "menopause", "age_group", "sex")
UNSURE_PAIRING = (
    "We could not tell which group each figure in this sentence is out of, so it was not checked automatically; "
    "a person should check it"
)


def _shifted(entity: Entity, offset: int) -> Entity:
    """An entity found in a slice of the sentence, placed back at its position in the whole sentence."""
    return Entity(entity.start + offset, entity.end + offset, entity.attribute, entity.category)


# "59% of them", "half of whom": the group is named earlier in the sentence
OF_THEM = re.compile(r"\b(?:of|among)\s+(?:them|whom)\b|\b(?:of|among)\s+(?:these|those)\b(?=\s*(?:[,.;:)]|$))", re.IGNORECASE)


def _rule_of_them(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """A share "of them" that no earlier rule tied to its group: never read as a share of every tumor."""
    if OF_THEM.search(info.text) and [a for a in find_amounts(info.text) if a.percent and not a.is_total]:
        return _unsure(info, claim_id)
    return None


def _unsure(info: SentenceInfo, claim_id: str) -> Claim:
    """Insufficient evidence instead of a guess: the sentence is shown to a person (and the AI helper, if on)."""
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.UNMAPPED,
                 needed_data=UNSURE_PAIRING)


def _is_group(text: str, entity: Entity) -> bool:
    """"... of lobular carcinomas", "Among HER2-positive tumors, ...": the entity names a population."""
    return (entity.attribute in GROUP_ATTRIBUTES and bool(_POPULATION_AFTER.match(text[entity.end:]))
            and bool(_SUBGROUP_BEFORE.search(text[: entity.start])))


_OF_RIGHT_AFTER = re.compile(r"\s*(?:of|among|in)\s+(?:the\s+|all\s+|these\s+|those\s+)?(?:primary\s+)?", re.IGNORECASE)


def _out_of_group(text: str, amount: "Amount", entity: Entity, entities: list[Entity]) -> bool:
    """True when a percent is "N% of <group>" and the sentence also names something else that may be what was counted."""
    if not amount.percent or not _is_group(text, entity) or entity.start < amount.end:
        return False
    if not _OF_RIGHT_AFTER.fullmatch(text[amount.end:entity.start]):
        return False
    return any(e.attribute != entity.attribute for e in entities)


def _group_shares(info: SentenceInfo, claim_id: str, amounts: list["Amount"], entities: list[Entity]) -> Claim | None:
    """One share per group: "CDH1 was mutated in 59% of lobular carcinomas but only 1.6% of ductal carcinomas",
    "Among HER2-positive tumors, about 54% carry an ERBB2 amplification, compared with under 2% of HER2-negative tumors".

    Each percent is the share of the one other thing named (the gene, status, ...) within its group; groups and
    figures pair in the order they are written.
    """
    text = info.text
    if len(amounts) < 2 or not all(a.percent for a in amounts):
        return None
    groups = [e for e in entities if _is_group(text, e)]
    if len(groups) != len(amounts) or len({e.attribute for e in groups}) != 1 or len({e.category for e in groups}) != len(groups):
        return None
    targets = {(e.attribute, e.category): e for e in entities if e.attribute != groups[0].attribute}
    if len(targets) != 1:
        return None
    for k, group in enumerate(groups):  # group k sits between figure k-1 and figure k+1
        if k + 1 < len(amounts) and group.start > amounts[k + 1].start:
            return None
        if k > 0 and group.end < amounts[k - 1].end:
            return None
    target = next(iter(targets.values()))
    parts = []
    for k, (amount, group) in enumerate(zip(amounts, groups), start=1):
        share = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.SHARE,
                      params=_params_for(target, amount, group, ""))
        parts.append(_part(share, f"{text[amount.start:amount.end]} of {text[group.start:group.end]}", k))
    return _compound(info, claim_id, parts)


def _named_group(text: str) -> Entity | None:
    """The group a phrase like "12 male patients" or "the 116 triple-negative tumours" names."""
    groups = [e for e in find_entities(text) if e.attribute in GROUP_ATTRIBUTES]
    if groups:
        return groups[-1]
    sexes = [name for name in ("male", "female") if re.search(COUNT_FILTERS[name], text, re.IGNORECASE)]
    if len(sexes) == 1:
        return Entity(0, 0, "sex", sexes[0])
    return None


ALL_OF_THEM = re.compile(
    r",?\s*(?:and\s+)?(?P<q>all|none|every\s+one|each)\s+of\s+(?:them|whom|these|those)\s+(?:(?:was|were|is|are|being)\s+)?",
    re.IGNORECASE,
)


def _rule_all_of_them(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"The cohort includes 12 male patients, all of them ER-positive": the count, then 100% (or 0%) within that group."""
    text = info.text
    m = ALL_OF_THEM.search(text)
    if m is None:
        return None
    head, tail = text[: m.start()], text[m.end():]
    targets = [e for e in find_entities(tail) if e.attribute != "sex"]
    if len({(e.attribute, e.category) for e in targets}) != 1:
        return None
    group = _named_group(head)
    if group is None:
        return _unsure(info, claim_id)
    parts: list[Claim] = []
    if find_amounts(head):
        counted = classify_sentence(SentenceInfo(index=info.index, text=head.strip(" ,;") + ".", claim_id=None), claim_id)
        if counted is None or counted.type in (ClaimType.UNMAPPED, ClaimType.NOT_ANSWERABLE):
            return _unsure(info, claim_id)
        for piece in counted.parts or [counted]:
            parts.append(_part(piece, piece.part_label or head.strip(" ,;"), len(parts) + 1))
    none = m.group("q").lower() == "none"
    target = targets[0]
    params = ClaimParams(attribute=target.attribute, category=target.category, within_attribute=group.attribute,
                         within_category=group.category, subject="primary_tumors", unit="percent",
                         stated_value=0.0 if none else 100.0, bound="lte" if none else "gte")
    share = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.SHARE, params=params)
    parts.append(_part(share, text[m.start():].strip(" ,;."), len(parts) + 1))
    if len(parts) == 1:
        single = parts[0]
        single.id, single.part_label = claim_id, ""
        return single
    return _compound(info, claim_id, parts)


MOST_IN = re.compile(
    r"\b(?:was|were|is|are)\s+(?:the\s+)?(?:(?P<sup>most|least)\s+(?:common(?:ly)?|frequent(?:ly)?|prevalent|often)|(?P<rare>rarest)|commonest)\s+"
    r"(?:seen\s+|found\s+|observed\s+|recorded\s+)?(?:in|among)\s+",
    re.IGNORECASE,
)


def _rule_most_in(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"Death was most frequent in stage IV disease, where 15 of 20 patients died": the death rate is highest in
    Stage IV (not "Stage IV is the most common stage"), plus the figure stated for that group."""
    text = info.text
    m = MOST_IN.search(text)
    if m is None:
        return None
    entities = find_entities(text)
    before = [e for e in entities if e.end <= m.start()]
    after = [e for e in entities if e.start >= m.end() and e.attribute in GROUP_ATTRIBUTES]
    if not before or not after:
        return None
    target, group = before[-1], after[0]
    if target.attribute == group.attribute:
        return None
    rank = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RANK,
                 params=ClaimParams(attribute=target.attribute, category=target.category, within_attribute=group.attribute,
                                    within_category=group.category, measure="rate", unit="rank", stated_value=1.0,
                                    direction="lower" if m.group("rare") or (m.group("sup") or "").lower() == "least" else None,
                                    subject="primary_tumors"))
    rest = text[group.end:]
    rest_amounts = [a for a in find_amounts(rest) if not a.words]
    values = [a for a in rest_amounts if not a.is_total]
    if not values:
        return rank
    if len(values) > 1 or len([a for a in rest_amounts if a.is_total]) > 1:
        return _unsure(info, claim_id)
    value, total = _amount_for_claim(rest, rest_amounts)
    params = _params_for(target, value, group, "")
    if not value.percent:
        params.subject = "patients" if target.attribute in ("vital_status", "dss_status") else "primary_tumors"
        if total is not None:
            params.stated_total = total.value
    figure = Claim(id=claim_id, text=text, sentence_index=info.index,
                   type=ClaimType.SHARE if value.percent else ClaimType.COUNT, params=params)
    return _compound(info, claim_id, [_part(rank, text[: group.end], 1),
                                      _part(figure, rest[value.start:].strip(" ,;."), 2)])


SUBTYPE_CALLS = re.compile(
    r"\b(?:PAM50|(?:intrinsic|molecular|RNA(?:[\s-]?seq)?)[\s-]+subtype)\b(?:[\s-]+(?:RNA[\s-]?seq|mRNA))?(?:\s+subtype)?\s+"
    r"(?:calls?|labels?|assignments?|classifications?)\b",
    re.IGNORECASE,
)


def _rule_subtype_calls(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"PAM50 RNA-seq calls are available for 844 of the 1,097 primary tumors with RNA data": 844 tumors have a
    subtype call, and 1,097 have RNA data. The total is its own claim, never the denominator of the call count."""
    text = info.text
    if SUBTYPE_CALLS.search(text) is None:
        return None
    amounts = [a for a in find_amounts(text) if not a.words]
    if not amounts or any(a.percent for a in amounts):
        return None
    values = [a for a in amounts if not a.is_total]
    totals = [a for a in amounts if a.is_total]
    if len(values) != 1 or len(totals) > 1:
        return None
    value = values[0]
    params = ClaimParams(attribute="subtype", category="any", subject="primary_tumors", unit="count",
                         stated_value=value.value, bound=value.bound, approximate=value.approximate)
    calls = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COUNT, params=params)
    if not totals:
        return calls
    total = totals[0]
    after = text[total.end:]
    layers = [layer for layer, pattern in LAYERS.items() if re.search(pattern, after, re.IGNORECASE)]
    if len(layers) > 1:
        return _unsure(info, claim_id)
    if layers:
        whole = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COVERAGE,
                      params=ClaimParams(subject=f"has_{layers[0]}", unit="count", stated_value=total.value))
    else:
        whole = Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.COUNT,
                      params=ClaimParams(subject=_count_subject(text, total.end) or "primary_tumors", unit="count",
                                         stated_value=total.value))
    return _compound(info, claim_id, [_part(calls, f"{text[value.start:value.end]} with a PAM50 subtype call", 1),
                                      _part(whole, text[total.start:].strip(" ,;."), 2)])


PROTEIN_RANK = re.compile(r"\b(?:was|were|is|are)\s+(?:the\s+)?(?P<sup>highest|lowest)\s+(?:in|among)\s+", re.IGNORECASE)


def _rule_protein_rank(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"Mean HER2 protein was highest in the HER2-enriched subtype": that group ranks first by mean protein level."""
    text = info.text
    if not _PROTEIN_WORDS.search(text):
        return None
    m = PROTEIN_RANK.search(text)
    if m is None:
        return None
    name = re.search(r"\b([A-Z][A-Za-z0-9-]*[A-Za-z0-9](?:[\s-]?(?:alpha|α))?)\s+(?:\(RPPA\)\s+)?(?:protein|levels?|abundance|expression)\b",
                     text[: m.start()])
    if name is None or name.group(1).lower() in ("mean", "median", "average"):
        return None
    groups = [e for e in find_entities(text[m.end():]) if e.attribute in GROUP_ATTRIBUTES]
    if len({(e.attribute, e.category) for e in groups}) != 1:
        return None
    g = groups[0]
    params = ClaimParams(measure=name.group(1).replace("α", "alpha"), within_attribute=g.attribute, within_category=g.category,
                         unit="rank", stated_value=1.0, direction="lower" if m.group("sup").lower() == "lowest" else None,
                         subject="primary_tumors")
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.RANK, params=params)


ONLY_IN = re.compile(r"\b(?:only|exclusively|solely)\s+(?:in|among)\s+|\b(?:restricted|confined|limited)\s+to\s+", re.IGNORECASE)
_OPPOSITE = {"positive": "negative", "negative": "positive"}


def _rule_only_in(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"GATA3 mutations were found only in ER-positive tumors": none of the ER-negative tumors has one."""
    text = info.text
    m = ONLY_IN.search(text)
    if m is None or numbers:
        return None
    groups = [e for e in find_entities(text[m.end():]) if e.attribute in ("er_status", "pr_status", "her2_status", "hr_status")]
    targets = [e for e in find_entities(text[: m.start()]) if e.attribute not in GROUP_ATTRIBUTES]
    if len(groups) != 1 or len({(e.attribute, e.category) for e in targets}) != 1:
        return None
    other = _OPPOSITE.get(groups[0].category)
    if other is None:
        return None
    t = targets[0]
    params = ClaimParams(attribute=t.attribute, category=t.category, within_attribute=groups[0].attribute,
                         within_category=other, subject="primary_tumors", unit="percent", stated_value=0.0, bound="lte")
    return Claim(id=claim_id, text=text, sentence_index=info.index, type=ClaimType.SHARE, params=params)


SPECULATION = re.compile(
    r"\b(?:likely|probably|possibly|presumably|may|might|could)\s+(?:also\s+)?(?:reflects?|indicates?|arises?|stems?"
    r"|results?\s+from|be\s+(?:due|explained|driven|caused|related|attributable|a\s+(?:result|consequence)))\b"
    r"|\b(?:is|are|was|were)\s+(?:likely|probably|presumably)\s+(?:due|explained|driven|caused|related|attributable)\b",
    re.IGNORECASE,
)
SPECULATION_NEED = (
    "a study designed to test this explanation; the release records what was measured, not why, so an "
    "explanation is an interpretation for a person to weigh"
)


def _rule_speculation(info: SentenceInfo, claim_id: str, numbers: list[StatedNumber]) -> Claim | None:
    """"These differences likely reflect screening practice": an explanation the release cannot test."""
    if numbers or not SPECULATION.search(info.text):
        return None
    return Claim(id=claim_id, text=info.text, sentence_index=info.index, type=ClaimType.NOT_ANSWERABLE,
                 needed_data=SPECULATION_NEED, clinical_terms=[])


RULES = (
    _rule_not_answerable_first, _rule_speculation, _rule_agreement, _rule_label_pair, _rule_features, _rule_protein_first, _rule_protein_rank, _rule_rate_rank,
    _rule_most_in, _rule_every_slide, _rule_layer_subset, _rule_subtype_calls, _rule_all_of_them, _rule_only_in, _rule_clauses,
    _rule_of_them, _rule_compound,
    _rule_share_alone, _rule_rank,
    _rule_count_against, _rule_ratio, _rule_comparison, _rule_share_comparison, _rule_subgroup_coverage, _rule_group_shares, _rule_attribute,
    _rule_coverage, _rule_count, _rule_statistic, _rule_age_groups, _rule_readiness, _rule_unmapped,
)


def classify_sentence(info: SentenceInfo, claim_id: str) -> Claim | None:
    """Type one sentence as a claim (first rule that matches wins), or None if it states nothing checkable."""
    numbers = find_numbers(info.text)
    if info.text.rstrip().rstrip(")\"'”’").endswith("?"):
        return None  # a question asserts nothing: "Could the 355 tumours with RNA but no protein data differ?"
    if not numbers and FORWARD_LOOKING.search(info.text):
        return None  # "Larger, treatment-annotated cohorts will be needed to translate these findings."
    for rule in RULES:
        try:
            claim = rule(info, claim_id, numbers)
        except Exception:  # noqa: BLE001 - an odd sentence skips one rule; it never stops the report
            continue
        if claim is not None:
            if _STUDY_SOURCE.search(info.text):  # "Under the 2012 consortium labels, ...": read the second source
                for c in (claim, *(claim.parts or [])):
                    if "subtype" in (c.params.attribute, c.params.within_attribute) or c.params.subtype:
                        c.params.subtype_source = "study_2012_label"
            return claim
    return None


_STUDY_SOURCE = re.compile(
    r"\b(?:under|by|using|with|per|according\s+to|in)\s+(?:the\s+)?(?:2012\s+(?:TCGA\s+|consortium\s+|study\s+)?(?:labels?|calls?|"
    r"classification|assignments?)|consortium(?:'s)?\s+(?:2012\s+)?labels?|PAM50_mRNA_nature2012)\b",
    re.IGNORECASE,
)


GATED = "this sentence also states {words}, which the rules could not check; a person should check it"


def _quoted_list(words: list[str]) -> str:
    """'"N0", "15" and "N3"'."""
    quoted = [f'"{w}"' for w in words]
    return quoted[0] if len(quoted) == 1 else ", ".join(quoted[:-1]) + " and " + quoted[-1]


def gate(claim: Claim) -> Claim:
    """The coverage gate: a rules reading that leaves part of the sentence unused gives no verdict.

    A complete reading, a `NOT_ANSWERABLE` claim or an `UNMAPPED` one comes back unchanged. Otherwise the claim
    becomes `UNMAPPED` (same id, text, sentence and original text; no params or parts), with the unused words in
    `coverage_gaps` and a `needed_data` reason naming them, so the audit says "can't check".
    """
    if claim.type in (ClaimType.NOT_ANSWERABLE, ClaimType.UNMAPPED):
        return claim
    from second_opinion.coverage import missing, reading_uses  # coverage imports this module

    gaps = missing(claim.text, reading_uses(claim))
    if not gaps:
        return claim
    return Claim(
        id=claim.id, text=claim.text, sentence_index=claim.sentence_index, type=ClaimType.UNMAPPED,
        needed_data=GATED.format(words=_quoted_list(gaps)), source=claim.source, original_text=claim.original_text,
        coverage_gaps=gaps,
    )


def extract_claims(report_text: str) -> ExtractResult:
    """Split the report and type every sentence, gating each reading (`gate`). Claim ids run C1, C2, ... over
    claims only."""
    sentences = split_sentences(report_text)
    claims: list[Claim] = []
    for info in sentences:
        claim = classify_sentence(info, f"C{len(claims) + 1}")
        if claim is not None:
            claim.original_text = info.original_text
            claim = gate(claim)
            claims.append(claim)
            info.claim_id = claim.id
    return ExtractResult(sentences=sentences, claims=claims)

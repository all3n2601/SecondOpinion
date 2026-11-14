"""Coverage: did a reading of a sentence use everything the sentence states?

`sentence_demands` lists what a complete reading must use: the figures, the named groups, the thing a figure
counts, a reference back to the previous sentence, and qualifiers the rules cannot read (N0, 40x, ...).
`reading_uses` lists what one reading used: a rules claim with its parts, or an AI query plan.
`missing` names the sentence's words the reading left unused, in sentence order; `[]` means complete.

Pure functions over text and params: no release data, no AI calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from second_opinion.extract import (
    _DEFINITION,
    _NUMBER,
    _OPPOSITE,
    AGE_RANGE,
    STAGE_ENTITY,
    _STUDY_SOURCE,
    age_of,
    age_thresholds,
    find_amounts,
    find_entities,
    find_numbers,
)
from second_opinion.model import Claim, ClaimParams, ClaimType
from second_opinion.verdict import PERCENT_TOLERANCE_POINTS

if TYPE_CHECKING:
    from second_opinion.ai.plan import QueryPlan

# Numbers that are part of a name, not a stated figure. find_numbers already skips gene and protein names
# (TP53, PAM50), years, references ("Figure 2", "a value of 2"), definitions "(GISTIC -1 or -2)", age cut-offs
# and ratios; these are the rest: "Stage 2", "HER2 3+", "chromosome 17".
NAME_LIKE_NUMBERS = (
    STAGE_ENTITY,
    re.compile(r"\b(?:HER-?2|IHC)\s+(?:score\s+(?:of\s+)?)?[0-3](?![\d,.])\s*\+?|(?<![\w.,])[0-3]\+", re.IGNORECASE),
    re.compile(r"\bchromosomes?\s+\d+", re.IGNORECASE),
    re.compile(r"^[\s|]*\d{1,3}\s*\|"),  # a table row's number: "6 | Luminal A tumors had higher HER3 protein ..."
)
# Entities that find_entities reports but that name a method, not a group: "GISTIC2 calls".
NOT_GROUPS = re.compile(r"^GISTIC\d*$", re.IGNORECASE)
# The things a figure counts (plural forms only: "the most frequently mutated gene" counts nothing), with the
# lemma a reading must count. Patients and primary tumors are one per patient in this release, so a reading of
# either uses both (see _SUBJECT_COUNTS).
COUNTED_NOUNS = {
    "tumors": "tumors", "tumours": "tumors",
    "samples": "samples", "specimens": "samples",
    "patients": "patients", "cases": "patients", "women": "patients", "men": "patients",
    "slides": "slides", "sections": "slides",
    "deaths": "deaths",
    "genes": "genes",
    "proteins": "proteins",
}
_COUNTED = re.compile(r"\b(?P<tumor>tumou?r\s+)?(?P<noun>" + "|".join(COUNTED_NOUNS) + r")\b", re.IGNORECASE)
# Words that look like a group label but that find_entities does not know, so the rules cannot have used them.
QUALIFIERS = (
    re.compile(r"\b[pcy]?(?:T[0-4X][a-d]?|N[0-3X][a-c]?|M[01X])\b"),  # TNM codes: N0, T2, pT2, M1, NX
    re.compile(r"(?<![\w.,])\d+(?:\.\d+)?\s?[x×](?!\w)", re.IGNORECASE),  # magnifications: 40x, 20 ×
    re.compile(r"\b(?:frozen|diagnostic|FFPE)\b", re.IGNORECASE),  # slide kinds, when no slide is named
    re.compile(r"\bequivocal\b", re.IGNORECASE),
    # the 2012 consortium subtype labels ("Under the 2012 labels, ..."): a source the subtype group is read from
    _STUDY_SOURCE,
)
# The group key a qualifier demands, when it is not "qualifier:<its words>".
SUBTYPE_SOURCE_KEY = "subtype_source:study_2012_label"
# A sentence that opens by pointing at the previous sentence's group: "Their ages ...", "Of these, 12 ...".
# "It is notable that ..." is not a reference.
BACK_REFERENCE = re.compile(
    r"^[\s\"'“‘(*_]*(?P<w>Their|These|Those|This\s+group|Of\s+(?:these|those|them)|Among\s+(?:them|these|those)"
    r"|In\s+(?:these|this\s+group)|A\s+further|The\s+remaining|They|It)\b(?!\s+(?:is|was)\s+\w+\s+(?:that|to)\b)",
)
# Subjects of a rules claim and the things they count.
_SUBJECT_COUNTS = (
    (re.compile(r"(?:^|_)(?:primary_)?tumors$|(?:^|_)patients$"), {"tumors", "patients"}),
    (re.compile(r"(?:^|_)samples$"), {"samples"}),
    (re.compile(r"(?:^|_)slides$"), {"slides"}),
    # a feature count counts the file's rows: genes (mutation, copy number, RNA) or proteins
    (re.compile(r"^features:(?:genes|mutation|copy_number|rna)$"), {"genes"}),
    (re.compile(r"^features:(?:proteins?|antibodies)$"), {"proteins"}),
    # data-layer coverage ("has_rna", "layers:rna+protein"): tumors or samples with the layer
    (re.compile(r"^(?:has_|layers:|all_five_layers|subtype_sources|label_pair)"), {"tumors", "patients", "samples"}),
)
# Sub-group filters in a rules subject ("male_patients", "diagnostic_slides") and the groups they name.
_SUBJECT_GROUPS = {
    "male": {"sex:male"},
    "female": {"sex:female"},
    "diagnostic": {"slide_kind:diagnostic", "qualifier:diagnostic", "qualifier:ffpe"},
    "frozen": {"slide_kind:frozen", "qualifier:frozen"},
}
# A slide-kind group is also named by the qualifier words ("Diagnostic (FFPE) slides").
_SLIDE_KIND_WORDS = {"diagnostic": {"qualifier:diagnostic", "qualifier:ffpe"}, "frozen": {"qualifier:frozen"}}
_THRESHOLD_ATTRIBUTES = ("age_group", "diagnosis_year")  # categories like "gt60", "gte2010" carry a figure
_DEATH_ATTRIBUTES = ("vital_status", "dss_status")


@dataclass
class Piece:
    start: int
    end: int
    words: str
    value: float | None = None
    key: str | None = None  # "attribute:category" for groups, the noun lemma for counted things
    amount_word: bool = False  # "a third", "majority": an amount written in words
    bound: str | None = None  # an amount word's bound: "majority" is "gt" 50


@dataclass
class Demands:
    figures: list[Piece]
    groups: list[Piece]
    counted: list[Piece]
    back_reference: Piece | None
    qualifiers: list[Piece]


@dataclass
class Uses:
    figures: set[float] = field(default_factory=set)
    groups: set[str] = field(default_factory=set)
    counted: set[str] = field(default_factory=set)
    spans: list[tuple[int, int]] = field(default_factory=list)  # quoted by an AI plan: figures inside are used
    resolves_back_reference: bool = False
    # Where each part of a compound reading sits in the sentence: for the join (Task 6) only; never marks a
    # figure as used.
    part_spans: list[tuple[int, int]] = field(default_factory=list)


def _inside(start: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= start < b for a, b in spans)


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(a < end and start < b for a, b in spans)


def _piece(text: str, start: int, end: int, value: float | None = None, key: str | None = None) -> Piece:
    return Piece(start, end, text[start:end], value, key)


def _figures(text: str, entities: list) -> list[Piece]:
    names = [m.span() for pattern in NAME_LIKE_NUMBERS for m in pattern.finditer(text)]
    names += [(e.start, e.end) for e in entities if e.attribute not in _THRESHOLD_ATTRIBUTES]
    out: list[Piece] = []
    for n in find_numbers(text):
        if _inside(n.start, names):
            continue
        if n.high is None:
            out.append(_piece(text, n.start, n.end, n.value))
        else:  # "55-65%": the low and the high end are two figures
            for m in _NUMBER.finditer(text, n.start, n.end):
                out.append(_piece(text, m.start(), m.end(), float(m.group(0).replace(",", ""))))
    amounts = [a for a in find_amounts(text) if a.words]  # amount words: "a third", "most", "one in ten"
    # a number word inside a fraction is part of it: "two thirds" is one figure, not "two"
    out = [p for p in out if not any(a.start <= p.start and p.end <= a.end and (a.start, a.end) != (p.start, p.end)
                                     for a in amounts)]
    taken = [(p.start, p.end) for p in out]
    for a in amounts:
        if not _overlaps(a.start, a.end, taken):
            piece = _piece(text, a.start, a.end, a.value)
            piece.amount_word, piece.bound = True, a.bound
            out.append(piece)
    for m in age_thresholds(text):  # "over 60": the age is a figure (and the group a group)
        g = next(g for g in ("age", "age2", "age3") if m.group(g))
        out.append(_piece(text, m.start(g), m.end(g), float(age_of(m))))
    for m in AGE_RANGE.finditer(text):  # "ages ranged from 44 to 84"
        out += [_piece(text, m.start(g), m.end(g), float(m.group(g))) for g in (1, 2)]
    for e in entities:  # "diagnosed in 2010 or later": the year is a figure
        if e.attribute == "diagnosis_year":
            for m in re.finditer(r"(?:19|20)\d\d", text[e.start:e.end]):
                out.append(_piece(text, e.start + m.start(), e.start + m.end(), float(m.group(0))))
    return sorted(out, key=lambda p: p.start)


def sentence_demands(text: str) -> Demands:
    """The pieces of the sentence a complete reading must use."""
    definitions = [m.span() for m in _DEFINITION.finditer(text)]
    entities = find_entities(text)
    figures = _figures(text, entities)

    groups: list[Piece] = []
    for e in entities:
        key = f"{e.attribute}:{e.category}"
        if NOT_GROUPS.match(e.category) or _inside(e.start, definitions) or any(g.key == key for g in groups):
            continue
        groups.append(_piece(text, e.start, e.end, key=key))

    counted: list[Piece] = []
    if figures:  # a noun is a counted thing only in a sentence that states a figure
        for m in _COUNTED.finditer(text):
            noun = m.group("noun")
            key = "tumors" if m.group("tumor") else COUNTED_NOUNS[noun.lower()]  # "tumor samples" are tumors
            if not any(c.words.lower() == noun.lower() for c in counted):
                counted.append(_piece(text, m.start("noun"), m.end("noun"), key=key))

    taken = [(e.start, e.end) for e in entities] + definitions
    qualifiers: list[Piece] = []
    for pattern in QUALIFIERS:
        for m in pattern.finditer(text):
            if not _overlaps(m.start(), m.end(), taken):
                taken.append(m.span())
                key = SUBTYPE_SOURCE_KEY if pattern is _STUDY_SOURCE else f"qualifier:{m.group(0).lower()}"
                qualifiers.append(_piece(text, m.start(), m.end(), key=key))
    qualifiers.sort(key=lambda p: p.start)
    figures = [f for f in figures if not any(q.start <= f.start < q.end for q in qualifiers)]  # "40 x"

    ref = BACK_REFERENCE.match(text)
    back = _piece(text, ref.start("w"), ref.end("w")) if ref else None
    return Demands(figures, groups, counted, back, qualifiers)


# ---------------------------------------------------------------------------------------------------------
# What a reading used
# ---------------------------------------------------------------------------------------------------------


def _add_group(uses: Uses, attribute: str | None, category: str | None) -> None:
    if not attribute or not category:
        return
    uses.groups.add(f"{attribute}:{category}")
    if "+" in category:  # "TP53+PIK3CA": tumors with both, named gene by gene in the sentence
        uses.groups.update(f"{attribute}:{part}" for part in category.split("+"))
    if attribute in _THRESHOLD_ATTRIBUTES:
        uses.figures.update(float(n) for n in re.findall(r"\d+", category))
    if attribute in _DEATH_ATTRIBUTES:
        uses.counted.add("deaths")
    if attribute == "slide_kind":
        uses.groups.update(_SLIDE_KIND_WORDS.get(category, set()))


def _add_words(uses: Uses, words: str | None) -> None:
    """A group written as words in the params ("ER-positive", "Basal-like")."""
    if words:
        for e in find_entities(words):
            _add_group(uses, e.attribute, e.category)


def _span(text: str, words: str | None) -> tuple[int, int] | None:
    if words and words in text:
        start = text.index(words)
        return start, start + len(words)
    return None


def _recorded(p: ClaimParams) -> list[float]:
    """The figures a reading records: its stated value, the upper end of a range, its total, a top-N."""
    return [float(v) for v in (p.stated_value, p.stated_high, p.stated_total, p.top_n) if v is not None]


def _part_span(text: str, part: Claim, figures: list[Piece]) -> tuple[int, int] | None:
    """Where a part sits in the sentence: its label's words, or, for a generated label ("youngest 44"), the stretch
    from the first to the last of the sentence's figures the part records."""
    span = _span(text, part.part_label)
    if span is not None:
        return span
    own = [f for f in figures if any(_same_figure(f, v) for v in _recorded(part.params))]
    return (min(f.start for f in own), max(f.end for f in own)) if own else None


DAYS_PER_YEAR = 365.25


def _add_params(uses: Uses, claim: Claim) -> None:
    p: ClaimParams = claim.params
    uses.figures.update(_recorded(p))
    if p.unit == "years":  # "843 days" is read as 2.308 years
        uses.figures.update(v * DAYS_PER_YEAR for v in (p.stated_value, p.stated_high) if v is not None)
    if p.subtype_source:  # "Under the 2012 consortium labels": the subtype group is read from that source
        uses.groups.add(f"subtype_source:{p.subtype_source}")
    if (p.subject or "").startswith(("label_pair", "subtype_sources")):  # compares the two label sources
        uses.groups.add(SUBTYPE_SOURCE_KEY)
    if (p.subject or "").startswith("label_pair:"):  # "label_pair:Luminal B:Luminal A": the two labels
        uses.groups.update(f"subtype:{label}" for label in p.subject.split(":")[1:] if label)
    if p.subtype:
        uses.groups.add(f"subtype:{p.subtype}")
    _add_group(uses, p.attribute, p.category)
    # the second group is of the claim's attribute, or of the subgroup's ("lower in lobular than in ductal")
    for attribute in {p.attribute_b or p.attribute, p.within_attribute}:
        _add_group(uses, attribute, p.category_b)
    _add_group(uses, p.within_attribute, p.within_category)
    if p.stated_value == 0 and p.bound == "lte" and p.within_category in _OPPOSITE:
        # "found only in ER-positive tumors" is read as "in none of the ER-negative tumors"
        _add_group(uses, p.within_attribute, _OPPOSITE[p.within_category])
    _add_words(uses, p.group_a)
    _add_words(uses, p.group_b)
    if p.attribute == "mutation" and claim.type == ClaimType.RANK:  # ranked among all genes
        uses.counted.add("genes")
    subject = p.subject
    if subject is None and claim.type not in (ClaimType.UNMAPPED, ClaimType.NOT_ANSWERABLE):
        subject = "primary_tumors"  # the checks count primary tumors unless told otherwise
    if subject:
        for pattern, nouns in _SUBJECT_COUNTS:
            if pattern.search(subject):
                uses.counted.update(nouns)
        names = re.split(r"[_+]", subject)
        for name in names:
            uses.groups.update(_SUBJECT_GROUPS.get(name, set()))
        if "samples" in names and {"male", "female"} & set(names):  # "samples from male patients"
            uses.counted.add("patients")


def _filter_value(value: Any) -> list:
    return value if isinstance(value, list) else [value]


def _add_filters(uses: Uses, filters: list) -> None:
    for f in filters:
        for value in _filter_value(f.value):
            if value is None:
                continue
            if f.field in ("subtype_rna", "subtype_2012"):
                uses.groups.add(f"subtype:{value}")
                if f.field == "subtype_2012":
                    uses.groups.add(SUBTYPE_SOURCE_KEY)
            elif f.field in ("sex", "er_status", "her2_status"):
                uses.groups.add(f"{f.field}:{value}")
            elif f.field == "attribute":
                _add_group(uses, f.attribute, str(value))
            elif f.field in ("age_years", "diagnosis_year"):
                number = float(value)
                uses.figures.add(number)
                attribute = "age_group" if f.field == "age_years" else "diagnosis_year"
                uses.groups.add(f"{attribute}:{f.op}{number:g}")
            elif f.field == "positive_lymph_nodes":
                uses.figures.add(float(value))
            elif f.field == "sample_type" and value != "primary":
                uses.counted.add("samples")


def _add_plan(uses: Uses, text: str, query: QueryPlan) -> None:
    plan = query.plan
    uses.counted.update({"tumors", "patients"})
    if plan is not None:
        for name in ("where", "numerator", "group_a", "group_b"):
            value = getattr(plan, name, None)
            if isinstance(value, list):
                _add_filters(uses, value)
        if plan.op == "count" and plan.of == "samples":
            uses.counted.add("samples")
        if plan.op == "compare_means":
            uses.groups.update({f"{plan.group_field}:{plan.group_a}", f"{plan.group_field}:{plan.group_b}"})
        field_name = getattr(plan, "category_field", None)
        for category in (getattr(plan, n, None) for n in ("category", "category_a", "category_b")):
            if not category or not field_name:
                continue
            if field_name == "subtype_2012":
                uses.groups.add(SUBTYPE_SOURCE_KEY)
            if field_name == "mutated_gene":
                uses.groups.add(f"mutation:{category}")
                uses.counted.add("genes")
            else:
                uses.groups.add(f"subtype:{category}")
    stated = query.stated
    if stated is not None:
        uses.figures.update(float(v) for v in (stated.value, stated.high, stated.total) if v is not None)
        span = _span(text, stated.span)
        if span is not None:
            uses.spans.append(span)


def reading_uses(claim: Claim, plan: QueryPlan | None = None) -> Uses:
    """What a reading used: the AI plan when one is given, else the claim's params and its parts' params.

    A figure counts as used only when the reading records it (a stated value, range end, total or threshold) or an
    AI plan quotes it. Each part also adds where it sits in the sentence to `part_spans`, for the join.
    """
    uses = Uses()
    if plan is not None:
        _add_plan(uses, claim.text, plan)
        return uses
    _add_params(uses, claim)
    figures = _figures(claim.text, find_entities(claim.text)) if claim.parts else []
    for part in claim.parts:
        _add_params(uses, part)
        span = _part_span(claim.text, part, figures)
        if span is not None:
            uses.part_spans.append(span)
    return uses


# ---------------------------------------------------------------------------------------------------------
# What it left unused
# ---------------------------------------------------------------------------------------------------------


def _decimals(words: str) -> int:
    """Digits after the point as written: "49.9%" -> 1; amount words ("a third") are matched to one decimal."""
    point = re.search(r"\d\.(\d+)", words)
    if point:
        return len(point.group(1))
    return 0 if re.search(r"\d", words) else 1


def _same_figure(piece: Piece, value: float) -> bool:
    """The written figure and a recorded value agree to the precision written; the sign is not a figure of its own
    ("-0.87" is found as 0.87)."""
    if piece.value is None:
        return False
    d = _decimals(piece.words)
    return round(abs(value), d) == round(abs(piece.value), d)


def _figure_used(piece: Piece, uses: Uses) -> bool:
    return _inside(piece.start, uses.spans) or any(_same_figure(piece, used) for used in uses.figures)


# Words between an amount word and the percent that restates it that start a different statement.
_NOT_A_RESTATEMENT = re.compile(r";|\b(?:and|but|while|whereas|versus|vs|against|compared|than|or)\b", re.IGNORECASE)


def _agrees(amount: Piece, percent: float) -> bool:
    """The percent satisfies the amount word: "a majority" (gt 50) and 59%, "a quarter" and 27%."""
    v = amount.value or 0.0
    return {
        "gt": percent > v, "gte": percent >= v, "lt": percent < v, "lte": percent <= v,
    }.get(amount.bound or "", abs(percent - v) <= float(PERCENT_TOLERANCE_POINTS) * 2)


_PERCENT_AFTER = re.compile(r"\s*(?:%|percent\b|per\s+cent\b)", re.IGNORECASE)


def _is_percent(figure: Piece, text: str) -> bool:
    """The figure itself is a percent ("46%", "46 per cent"), not a count with a percent after it ("512 (46%)")."""
    return bool(re.search(r"(?:%|percent|per\s+cent)\s*$", figure.words, re.IGNORECASE)) or bool(
        _PERCENT_AFTER.match(text, figure.end))


def _restated(amount: Piece, figures: list[Piece], text: str, uses: Uses) -> bool:
    """An amount word followed, in the same statement, by a used percent that agrees with it is used through that
    percent: "a majority (59%)", "Just over a quarter of patients, 27%", "almost all ER-negative: 124 of 136 (91.2%)".
    """
    for f in figures:
        if f.start < amount.end or not _is_percent(f, text):
            continue
        between = text[amount.end:f.start]
        if _NOT_A_RESTATEMENT.search(between):
            return False
        return _figure_used(f, uses) and f.value is not None and _agrees(amount, f.value)
    return False


def missing(text: str, uses: Uses) -> list[str]:
    """The sentence's words the reading left unused, in sentence order; [] when the reading is complete.

    A back reference is used only when the reading says it resolved one (a rules reading never does); a
    qualifier only when a reading names it as a group, which the rules cannot.
    """
    d = sentence_demands(text)
    unused: list[Piece] = [
        f for f in d.figures
        if not _figure_used(f, uses) and not (f.amount_word and _restated(f, d.figures, text, uses))
    ]
    unused += [g for g in d.groups if g.key not in uses.groups]
    unused += [c for c in d.counted if c.key not in uses.counted]
    unused += [q for q in d.qualifiers if q.key not in uses.groups]
    if d.back_reference is not None and not uses.resolves_back_reference:
        unused.append(d.back_reference)
    return [p.words for p in sorted(unused, key=lambda p: p.start)]

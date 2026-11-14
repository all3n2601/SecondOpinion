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
    AGE_RANGE,
    STAGE_ENTITY,
    age_of,
    age_thresholds,
    find_amounts,
    find_entities,
    find_numbers,
)
from second_opinion.model import Claim, ClaimParams, ClaimType

if TYPE_CHECKING:
    from second_opinion.ai.plan import QueryPlan

# Numbers that are part of a name, not a stated figure. find_numbers already skips gene and protein names
# (TP53, PAM50), years, references ("Figure 2", "a value of 2"), definitions "(GISTIC -1 or -2)", age cut-offs
# and ratios; these are the rest: "Stage 2", "HER2 3+", "chromosome 17".
NAME_LIKE_NUMBERS = (
    STAGE_ENTITY,
    re.compile(r"\b(?:HER-?2|IHC)\s+(?:score\s+(?:of\s+)?)?[0-3]\s*\+?|(?<![\w.,])[0-3]\+", re.IGNORECASE),
    re.compile(r"\bchromosomes?\s+\d+", re.IGNORECASE),
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
)
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
    (re.compile(r"^features:genes$"), {"genes"}),
    (re.compile(r"^features:(?:proteins|antibodies)$"), {"proteins"}),
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
_THRESHOLD_ATTRIBUTES = ("age_group", "diagnosis_year")  # categories like "gt60", "gte2010" carry a figure
_DEATH_ATTRIBUTES = ("vital_status", "dss_status")


@dataclass
class Piece:
    start: int
    end: int
    words: str
    value: float | None = None
    key: str | None = None  # "attribute:category" for groups, the noun lemma for counted things


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
    spans: list[tuple[int, int]] = field(default_factory=list)
    resolves_back_reference: bool = False


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
    taken = [(p.start, p.end) for p in out]
    for a in find_amounts(text):  # amount words: "a third", "most", "one in ten"
        if a.words and not _overlaps(a.start, a.end, taken):
            out.append(_piece(text, a.start, a.end, a.value))
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
                qualifiers.append(_piece(text, m.start(), m.end(), key=f"qualifier:{m.group(0).lower()}"))
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


def _add_words(uses: Uses, words: str | None) -> None:
    """A group written as words in the params ("ER-positive", "Basal-like")."""
    if words:
        for e in find_entities(words):
            _add_group(uses, e.attribute, e.category)


def _add_span(uses: Uses, text: str, words: str | None) -> None:
    if words and words in text:
        start = text.index(words)
        uses.spans.append((start, start + len(words)))


def _add_params(uses: Uses, claim: Claim) -> None:
    p: ClaimParams = claim.params
    uses.figures.update(float(v) for v in (p.stated_value, p.stated_high, p.stated_total, p.top_n) if v is not None)
    if p.subtype:
        uses.groups.add(f"subtype:{p.subtype}")
    _add_group(uses, p.attribute, p.category)
    # the second group is of the claim's attribute, or of the subgroup's ("lower in lobular than in ductal")
    for attribute in {p.attribute_b or p.attribute, p.within_attribute}:
        _add_group(uses, attribute, p.category_b)
    _add_group(uses, p.within_attribute, p.within_category)
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
        for name in re.split(r"[_+]", subject):
            uses.groups.update(_SUBJECT_GROUPS.get(name, set()))


def _filter_value(value: Any) -> list:
    return value if isinstance(value, list) else [value]


def _add_filters(uses: Uses, filters: list) -> None:
    for f in filters:
        for value in _filter_value(f.value):
            if value is None:
                continue
            if f.field in ("subtype_rna", "subtype_2012"):
                uses.groups.add(f"subtype:{value}")
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
            if field_name == "mutated_gene":
                uses.groups.add(f"mutation:{category}")
                uses.counted.add("genes")
            else:
                uses.groups.add(f"subtype:{category}")
    stated = query.stated
    if stated is not None:
        uses.figures.update(float(v) for v in (stated.value, stated.high, stated.total) if v is not None)
        _add_span(uses, text, stated.span)


def reading_uses(claim: Claim, plan: QueryPlan | None = None) -> Uses:
    """What a reading used: the AI plan when one is given, else the claim's params and its parts' params.

    Each part also adds the span of the sentence its label quotes, when the label is the sentence's own words.
    """
    uses = Uses()
    if plan is not None:
        _add_plan(uses, claim.text, plan)
        return uses
    _add_params(uses, claim)
    for part in claim.parts:
        _add_params(uses, part)
        _add_span(uses, claim.text, part.part_label)
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


def _figure_used(piece: Piece, uses: Uses) -> bool:
    if _inside(piece.start, uses.spans):
        return True
    if piece.value is None:
        return False
    d = _decimals(piece.words)
    return any(round(used, d) == round(piece.value, d) for used in uses.figures)


def missing(text: str, uses: Uses) -> list[str]:
    """The sentence's words the reading left unused, in sentence order; [] when the reading is complete.

    A back reference is used only when the reading says it resolved one (a rules reading never does); a
    qualifier only when a reading names it as a group, which the rules cannot.
    """
    d = sentence_demands(text)
    unused: list[Piece] = [f for f in d.figures if not _figure_used(f, uses)]
    unused += [g for g in d.groups if g.key not in uses.groups]
    unused += [c for c in d.counted if c.key not in uses.counted]
    unused += [q for q in d.qualifiers if q.key not in uses.groups]
    if d.back_reference is not None and not uses.resolves_back_reference:
        unused.append(d.back_reference)
    return [p.words for p in sorted(unused, key=lambda p: p.start)]

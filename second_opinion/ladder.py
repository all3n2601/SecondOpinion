"""The Claim Ladder: the claim as written, with over-strong words struck and the honest words inserted.

Rules only, no AI: the same claim and result always give the same ladder. Every original
character appears exactly once, in order, in a struck or unstruck segment; inserted segments
carry the new words. Rules, in order:

1. Contradicted number: strike the stated number (and any "about" before it); insert the correct value.
2. Vague amount: strike "about 50%" / "most" / "the majority of"; insert the exact "N of M".
3. Clinical or treatment words: strike them; after the first struck run insert
   "— not answerable from this data; would need: <needed data>".
4. Cause or prediction words: strike; insert "was associated with".
5. Over-generalising ("breast cancer patients", "in general"): add the scope
   "in this TCGA-BRCA release, among N primary tumors" before the final full stop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from second_opinion.extract import APPROXIMATE_WORDS, DIRECTIONS, find_numbers
from second_opinion.model import Claim, ClaimResult, ClaimType, Fact, LadderSegment, Verdict
from second_opinion.unanswerable import KEYWORD_GROUPS
from second_opinion.verdict import format_fact

NOT_ANSWERABLE_NOTE = "— not answerable from this data; would need: {needed}"
ASSOCIATION = "was associated with"
SCOPE = " in this TCGA-BRCA release"
SCOPE_WITH_N = " in this TCGA-BRCA release, among {n:,} primary tumors"

CAUSE_TERMS = set(KEYWORD_GROUPS["cause"][1])
VAGUE_AMOUNT = re.compile(
    r"\b(?:the\s+)?(?:vast\s+)?majority\s+of\b|\b(?:nearly|almost|virtually)\s+all\b|\bmost\b",
    re.IGNORECASE,
)
OVER_GENERAL = re.compile(
    r"\b(?:breast\s+cancer\s+patients|patients\s+with\s+breast\s+cancer|women\s+with\s+breast\s+cancer"
    r"|all\s+women|all\s+patients|in\s+general|generally|always)\b",
    re.IGNORECASE,
)
# Short words that may sit between two struck terms and get struck with them:
# "responded best to hormone therapy" reads as one struck phrase.
_JOINER = re.compile(r"^\s*(?:(?:to|the|a|an|of|and|with|on|in|for|by)\s+)?$", re.IGNORECASE)
_APPROX_BEFORE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(w) for w in sorted(APPROXIMATE_WORDS, key=len, reverse=True)) + r")\s*$",
    re.IGNORECASE,
)
_TOTAL_JOIN = re.compile(r"^\s+(?:of|out\s+of)\s+(?:the\s+)?$", re.IGNORECASE)
_FINAL_STOP = re.compile(r"[.!?]+[\"'”’)\]]*\s*$")


@dataclass
class _Edit:
    start: int
    end: int  # start == end: a pure insertion
    inserts: list[str] = field(default_factory=list)


def build_ladder(claim: Claim, result: ClaimResult) -> list[LadderSegment]:
    text = claim.text
    edits: list[_Edit] = []
    edits += _contradicted_number(claim, result)
    if not edits:
        edits += _vague_amount(claim, result)
    edits += _clinical_and_cause(claim, result)
    edits += _over_general(claim, result)
    return _segments(text, edits)


# --- rule 1 ----------------------------------------------------------------------------------


def _number_span(claim: Claim) -> tuple[int, int, bool] | None:
    """(start, end, total_is_adjacent) of the stated number, including "about" before it."""
    p = claim.params
    if p.stated_value is None:
        return None
    numbers = find_numbers(claim.text)
    candidates = [n for n in numbers if abs(n.value - p.stated_value) < 1e-9 and n.high == p.stated_high]
    if p.unit == "percent":
        candidates = [n for n in candidates if n.percent] or candidates
    if not candidates:
        return None
    n = candidates[0]
    start, end, adjacent = n.start, n.end, False
    later = [m for m in numbers if m.start >= n.end]
    if later and later[0].is_total and _TOTAL_JOIN.match(claim.text[n.end:later[0].start]):
        end, adjacent = later[0].end, True
    approx = _APPROX_BEFORE.search(claim.text[:start])
    if approx:
        start = approx.start()
    return start, end, adjacent


def _exact(claim: Claim, fact: Fact, adjacent_total: bool) -> str | None:
    """The exact value to write in place of the stated one."""
    unit = claim.params.unit or ("percent" if claim.type == ClaimType.SHARE else "count")
    if fact.numerator is None and fact.value is None:
        return None
    if unit == "count" and fact.numerator is not None and fact.denominator is not None and not adjacent_total:
        if claim.params.stated_total is not None:
            return f"{fact.numerator:,}"  # the total is already written elsewhere in the sentence
    try:
        return format_fact(fact, unit)
    except ValueError:
        return None


def _contradicted_number(claim: Claim, result: ClaimResult) -> list[_Edit]:
    if result.verdict != Verdict.CONTRADICTED:
        return []
    fact = result.fact
    if claim.type == ClaimType.COMPARISON:
        return _flip_direction(claim, fact)
    if claim.params.unit == "all":
        return _coverage_quantifier(claim, fact)
    span = _number_span(claim)
    if span is None:
        return []
    start, end, adjacent = span
    replacement = _exact(claim, fact, adjacent) if fact is not None else None
    return [_Edit(start, end, [replacement or result.correct_value or "a different value"])]


def _flip_direction(claim: Claim, fact: Fact | None) -> list[_Edit]:
    if fact is None or fact.value is None or claim.params.direction not in DIRECTIONS:
        return []
    actual = "no different" if fact.value == 0 else ("higher" if fact.value > 0 else "lower")
    for word in DIRECTIONS[claim.params.direction]:
        for m in re.finditer(rf"\b{word}\b", claim.text, re.IGNORECASE):
            if re.match(r"\s+than\s+(?:about\s+|around\s+|roughly\s+)?\d", claim.text[m.end():], re.IGNORECASE):
                continue
            return [_Edit(m.start(), m.end(), [actual])]
    return []


def _coverage_quantifier(claim: Claim, fact: Fact | None) -> list[_Edit]:
    if fact is None or fact.numerator is None or fact.denominator is None:
        return []
    m = re.search(r"\b(?:every|each|all)\b", claim.text, re.IGNORECASE)
    if m is None:
        return []
    return [_Edit(m.start(), m.end(), [f"{fact.numerator:,} of {fact.denominator:,}"])]


# --- rule 2 ----------------------------------------------------------------------------------


def _vague_amount(claim: Claim, result: ClaimResult) -> list[_Edit]:
    fact = result.fact
    if fact is None or result.verdict == Verdict.INSUFFICIENT_EVIDENCE:
        return []
    edits: list[_Edit] = []
    if claim.params.approximate:
        span = _number_span(claim)
        exact = _exact(claim, fact, span[2]) if span else None
        if span and exact:
            edits.append(_Edit(span[0], span[1], [exact]))
    if fact.numerator is not None and fact.denominator is not None:
        for m in VAGUE_AMOUNT.finditer(claim.text):
            edits.append(_Edit(m.start(), m.end(), [f"{fact.numerator:,} of {fact.denominator:,}"]))
    return edits


# --- rules 3 and 4 ---------------------------------------------------------------------------


def _term_spans(text: str, terms: list[str]) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    for term in terms:
        words = r"\s+".join(re.escape(w) for w in term.split())
        for m in re.finditer(rf"(?<!\w){words}(?!\w)", text, re.IGNORECASE):
            spans.append((m.start(), m.end(), term))
    return sorted(spans)


def _merge_runs(text: str, spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    runs: list[list[int]] = []
    for start, end in sorted(spans):
        if runs and (start <= runs[-1][1] or _JOINER.match(text[runs[-1][1]:start])):
            runs[-1][1] = max(runs[-1][1], end)
        else:
            runs.append([start, end])
    return [(a, b) for a, b in runs]


def _clinical_and_cause(claim: Claim, result: ClaimResult) -> list[_Edit]:
    if not claim.clinical_terms:
        return []
    text = claim.text
    spans = _term_spans(text, claim.clinical_terms)
    cause = [(a, b) for a, b, term in spans if term in CAUSE_TERMS]
    clinical = [(a, b) for a, b, term in spans if term not in CAUSE_TERMS]
    # A clinical span that overlaps a cause span is left to the cause rule.
    clinical = [(a, b) for a, b in clinical if not any(a < cb and ca < b for ca, cb in cause)]

    edits = [_Edit(a, b) for a, b in _merge_runs(text, clinical)]
    edits += [_Edit(a, b, [ASSOCIATION]) for a, b in _merge_runs(text, cause)]
    if not edits:
        return []
    needed = claim.needed_data or result.missing_evidence or "data this release does not contain"
    first = min(edits, key=lambda e: e.start)
    first.inserts.append(NOT_ANSWERABLE_NOTE.format(needed=needed))
    return edits


# --- rule 5 ----------------------------------------------------------------------------------


def _over_general(claim: Claim, result: ClaimResult) -> list[_Edit]:
    if result.fact is None or not OVER_GENERAL.search(claim.text):
        return []
    n = result.fact.denominator
    scope = SCOPE_WITH_N.format(n=n) if n else SCOPE
    stop = _FINAL_STOP.search(claim.text)
    at = stop.start() if stop else len(claim.text.rstrip())
    return [_Edit(at, at, [scope])]


# --- assembling the segments -----------------------------------------------------------------


def _segments(text: str, edits: list[_Edit]) -> list[LadderSegment]:
    merged: list[_Edit] = []
    for edit in sorted(edits, key=lambda e: (e.start, e.end)):
        last = merged[-1] if merged else None
        if last and last.end > last.start and edit.start < last.end:  # overlaps a strike
            last.end = max(last.end, edit.end)
            last.inserts += edit.inserts
        else:
            merged.append(_Edit(edit.start, edit.end, list(edit.inserts)))

    segments: list[LadderSegment] = []
    pos = 0
    for edit in merged:
        if edit.start > pos:
            segments.append(LadderSegment(text[pos:edit.start]))
        if edit.end > edit.start:
            segments.append(LadderSegment(text[edit.start:edit.end], struck=True))
        segments += [LadderSegment(t, inserted=True) for t in edit.inserts if t]
        pos = max(pos, edit.end)
    if pos < len(text):
        segments.append(LadderSegment(text[pos:]))
    return segments or [LadderSegment(text)]

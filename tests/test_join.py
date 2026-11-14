"""The join: a sentence's parts decide its verdict, and an all-agreeing sentence must be covered by its parts."""

from dataclasses import replace

from second_opinion.audit import _combine_parts
from second_opinion.extract import _compound, classify_sentence
from second_opinion.model import Claim, ClaimResult, ClaimType, SentenceInfo, Solidity, Verdict

TP53 = "TP53 mutations dominate basal-like tumors, at 85% compared with 10% in Luminal A."
BASAL = ("TP53 is mutated in 85% of basal-like tumors.", "basal-like tumors, at 85%")
LUMA = ("TP53 is mutated in 10% of Luminal A tumors.", "10% in Luminal A")


def part(k: int, statement: str, label: str) -> Claim:
    read = classify_sentence(SentenceInfo(0, statement, None), f"C1.{k}")
    if read is None:
        read = Claim(f"C1.{k}", statement, 0, ClaimType.UNMAPPED)
    return replace(read, part_label=label, source="ai")


def sentence(text: str, *parts: tuple[str, str]) -> Claim:
    return _compound(SentenceInfo(0, text, "C1"), "C1", [part(k, s, l) for k, (s, l) in enumerate(parts, start=1)])


def result(claim: Claim, verdict: Verdict, **extra) -> ClaimResult:
    return ClaimResult(claim=claim, verdict=verdict, solidity=Solidity.NOT_APPLICABLE, fact=None,
                       correct_value=extra.pop("correct_value", None), missing_evidence=extra.pop("missing", None),
                       variants=[], flips_on=[], skeptic=None, ladder=[], limitation=None, **extra)


def join(claim: Claim, *verdicts: Verdict, **extra) -> ClaimResult:
    return _combine_parts(claim, [result(p, v, **extra) for p, v in zip(claim.parts, verdicts)])


def test_parts_that_cover_the_sentence_and_agree_are_supported() -> None:
    joined = join(sentence(TP53, BASAL, LUMA), Verdict.SUPPORTED, Verdict.SUPPORTED)
    # "TP53" sits outside both spans, but each part's reading names it
    assert joined.verdict == Verdict.SUPPORTED and joined.claim.coverage_gaps == []


def test_a_contradicted_part_decides() -> None:
    claim = sentence(TP53, BASAL, LUMA)
    joined = _combine_parts(claim, [result(claim.parts[0], Verdict.SUPPORTED),
                                    result(claim.parts[1], Verdict.CONTRADICTED, correct_value="12.0% (6 of 50)")])
    assert joined.verdict == Verdict.CONTRADICTED and joined.correct_value == "12.0% (6 of 50)"


def test_a_contradicted_part_decides_even_when_the_parts_leave_words_uncovered() -> None:
    text = TP53[:-1] + " and 37% in HER2-enriched tumors."
    joined = join(sentence(text, BASAL, LUMA), Verdict.CONTRADICTED, Verdict.SUPPORTED)
    assert joined.verdict == Verdict.CONTRADICTED


def test_agreeing_parts_that_leave_a_figure_outside_every_span_are_not_supported() -> None:
    text = TP53[:-1] + " and 37% in HER2-enriched tumors."
    joined = join(sentence(text, BASAL, LUMA), Verdict.SUPPORTED, Verdict.SUPPORTED)
    assert joined.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert joined.claim.coverage_gaps == ["37%", "HER2-enriched"]  # export, decision and the web say "not fully read"
    assert '"37%" and "HER2-enriched"' in joined.missing_evidence
    assert len(joined.parts) == 2 and all(p.verdict == Verdict.SUPPORTED for p in joined.parts)


def test_a_supported_and_an_insufficient_part_are_insufficient() -> None:
    claim = sentence(TP53, BASAL, LUMA)
    joined = _combine_parts(claim, [result(claim.parts[0], Verdict.SUPPORTED),
                                    result(claim.parts[1], Verdict.INSUFFICIENT_EVIDENCE, missing="No data")])
    assert joined.verdict == Verdict.INSUFFICIENT_EVIDENCE and "No data" in joined.missing_evidence


def test_a_group_an_ai_plan_used_counts_for_the_join() -> None:
    text = "Among Luminal A tumors, PIK3CA was mutated in 45%."
    claim = _compound(SentenceInfo(0, text, "C1"), "C1",
                      [Claim("C1.1", "PIK3CA is mutated in 45% of Luminal A tumors.", 0, ClaimType.UNMAPPED,
                             source="ai", part_label="PIK3CA was mutated in 45%")])
    plan = {"answerable": True,
            "plan": {"op": "share", "where": [{"field": "subtype_rna", "op": "eq", "value": "Luminal A"}],
                     "numerator": [{"field": "attribute", "attribute": "mutation", "op": "eq", "value": "PIK3CA"}]},
            "stated": {"kind": "percent", "span": "45%", "value": 45}, "rationale": "share"}
    assert join(claim, Verdict.SUPPORTED).verdict == Verdict.INSUFFICIENT_EVIDENCE  # "Luminal A" is in no span
    assert join(claim, Verdict.SUPPORTED, ai_plan=plan).verdict == Verdict.SUPPORTED  # the plan filtered on it

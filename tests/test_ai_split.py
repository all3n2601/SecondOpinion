"""The AI split at /extract: a sentence the rules only half read becomes self-contained statements.

Every test uses a ScriptedClient: nothing here talks to a real model.
"""

import pytest

from second_opinion.ai.client import AIError, ScriptedClient
from second_opinion.ai.split import SplitPart, SplitRejected, split_gated, split_sentence
from second_opinion.extract import extract_claims
from second_opinion.model import Claim, ClaimType, ExtractResult, SentenceInfo

TP53 = "TP53 mutations dominate basal-like tumors, at 85% compared with 10% in Luminal A."
TP53_SPLIT = {"parts": [
    {"span": "basal-like tumors, at 85%", "statement": "TP53 is mutated in 85% of basal-like tumors."},
    {"span": "10% in Luminal A", "statement": "TP53 is mutated in 10% of Luminal A tumors."},
]}
NODES = "Deaths rise with nodal involvement: 44 of 516 N0 patients died, against 15 of 77 N3 patients."
MALE = "Twelve of the primary tumors came from male patients."
AGES = "Their ages ranged from 44 to 84 years."


def one_claim(text: str, previous: str | None = None, source: str = "rules") -> ExtractResult:
    index = 1 if previous else 0
    sentences = ([SentenceInfo(0, previous, None)] if previous else []) + [SentenceInfo(index, text, "C1")]
    return ExtractResult(sentences=sentences, claims=[Claim("C1", text, index, ClaimType.UNMAPPED, source=source)])


# ------------------------------------------------------------------ split_sentence


def test_a_valid_split_comes_back_as_parts() -> None:
    parts = split_sentence(TP53, None, ScriptedClient([TP53_SPLIT]))
    assert parts == [SplitPart("basal-like tumors, at 85%", "TP53 is mutated in 85% of basal-like tumors."),
                     SplitPart("10% in Luminal A", "TP53 is mutated in 10% of Luminal A tumors.")]


def test_a_split_that_invents_a_number_is_retried_then_rejected() -> None:
    invented = {"parts": [{"span": "basal-like tumors, at 85%", "statement": "TP53 is mutated in 90% of basal-like tumors."},
                          {"span": "10% in Luminal A", "statement": "TP53 is mutated in 10% of Luminal A tumors."}]}
    client = ScriptedClient([invented, invented])
    with pytest.raises(SplitRejected):
        split_sentence(TP53, None, client)
    assert len(client.calls) == 2
    assert '"90%" is not in its span' in client.calls[1][1]  # the correction names the problem


def test_a_corrected_split_is_accepted() -> None:
    invented = {"parts": [{"span": "basal-like tumors, at 85%", "statement": "TP53 is mutated in 90% of basal-like tumors."}]}
    client = ScriptedClient([invented, TP53_SPLIT])
    assert len(split_sentence(TP53, None, client)) == 2


def test_spans_that_miss_a_figure_are_rejected() -> None:
    half = {"parts": [{"span": "44 of 516 N0 patients died", "statement": "44 of 516 N0 patients died."}]}
    with pytest.raises(SplitRejected):
        split_sentence(NODES, None, ScriptedClient([half, half]))


@pytest.mark.parametrize("answer", [
    {"parts": []},  # the sentence states figures: an empty split is not an answer
    {"parts": [{"span": "basal-like tumours at 85%", "statement": "TP53 is mutated in 85% of basal-like tumors."},
               {"span": "10% in Luminal A", "statement": "TP53 is mutated in 10% of Luminal A tumors."}]},  # not verbatim
    {"parts": [{"span": "basal-like tumors, at 85%", "statement": "TP53 is mutated in 85% of HER2-enriched tumors."},
               {"span": "10% in Luminal A", "statement": "TP53 is mutated in 10% of Luminal A tumors."}]},  # new group
    {"split": "no"},
])
def test_other_bad_splits_are_rejected(answer) -> None:
    with pytest.raises(SplitRejected):
        split_sentence(TP53, None, ScriptedClient([answer, answer]))


def test_a_group_from_the_previous_sentence_is_allowed() -> None:
    previous = "Basal-like tumors were the most aggressive."
    sentence = "In them, TP53 was mutated in 85%."
    answer = {"parts": [{"span": "TP53 was mutated in 85%", "statement": "TP53 is mutated in 85% of basal-like tumors."}]}
    assert len(split_sentence(sentence, previous, ScriptedClient([answer]))) == 1
    with pytest.raises(SplitRejected):
        split_sentence(sentence, None, ScriptedClient([answer, answer]))  # without it, "basal-like" is new


# ------------------------------------------------------------------ split_gated


def test_a_gated_sentence_splits_into_statements_the_rules_read_completely() -> None:
    result = extract_claims(TP53)
    assert result.claims[0].type == ClaimType.UNMAPPED and result.claims[0].coverage_gaps  # gated
    claim = split_gated(result, ScriptedClient([TP53_SPLIT])).claims[0]
    assert claim.id == "C1" and claim.text == TP53 and claim.coverage_gaps == []
    assert [p.id for p in claim.parts] == ["C1.1", "C1.2"]
    assert [p.type for p in claim.parts] == [ClaimType.SHARE, ClaimType.SHARE]
    assert [p.part_label for p in claim.parts] == ["basal-like tumors, at 85%", "10% in Luminal A"]
    assert all(p.source == "ai" and p.original_text == TP53 and not p.coverage_gaps for p in claim.parts)
    assert [p.params.stated_value for p in claim.parts] == [85.0, 10.0]


def test_a_back_reference_is_resolved_from_the_previous_sentence() -> None:
    answer = {"parts": [{"span": AGES, "statement": "The male patients' ages ranged from 44 to 84 years."}]}
    result = one_claim(AGES, previous=MALE, source="ai")  # the AI claim finder recovered it
    client = ScriptedClient([answer])
    claim = split_gated(result, client).claims[0]
    assert MALE in client.calls[0][1]  # the model saw the previous sentence
    (part,) = claim.parts
    assert "male patients" in part.text and part.type == ClaimType.UNMAPPED  # left for an AI plan at /audit
    assert part.source == "ai" and claim.source == "ai"


def test_a_rejected_split_leaves_the_gated_claim_unchanged() -> None:
    result = extract_claims(TP53)
    bad = {"parts": []}
    assert split_gated(result, ScriptedClient([bad, bad])).claims[0] == result.claims[0]


def test_an_ai_error_leaves_the_gated_claim_unchanged() -> None:
    result = extract_claims(TP53)
    assert split_gated(result, ScriptedClient([AIError("timed out")])).claims[0] == result.claims[0]


def test_only_unmapped_claims_are_split() -> None:
    result = extract_claims("TP53 is mutated in 85% of basal-like tumors. Patients on tamoxifen lived longer.")
    assert [c.type for c in result.claims] == [ClaimType.SHARE, ClaimType.NOT_ANSWERABLE]
    client = ScriptedClient([])
    assert split_gated(result, client) == result and client.calls == []


def test_no_client_is_the_rules_result() -> None:
    result = extract_claims(TP53)
    assert split_gated(result, None) is result

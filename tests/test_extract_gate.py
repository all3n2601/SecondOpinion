"""The coverage gate at extraction: a rules reading that leaves part of the sentence unused gives "can't check"."""

import dataclasses

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app
from second_opinion.audit import audit_claims
from second_opinion.extract import GATED, classify_sentence, extract_claims, gate
from second_opinion.model import Claim, ClaimParams, ClaimType, SentenceInfo, Verdict
from tests.test_coverage import COMPLETE, INCOMPLETE, PRACTICE

# INCOMPLETE sentences the rules make no verdict-giving reading of: no claim ("Their ages ...") or an UNMAPPED one,
# which the gate leaves as it is (the audit already says "can't check").
RULES_DO_NOT_READ = {
    "Their ages ranged from 44 to 84 years.",
    "CBFB was mutated in 18 tumors, the same number as SF3B1.",
    "In all, 432 tumors carry a high-level amplification of at least one of ERBB2, MYC or CCND1, about a third of the cohort.",
}
GATED_ROWS = [(s, w) for s, w in INCOMPLETE if s not in RULES_DO_NOT_READ]

api = TestClient(app)


def _rules_type(sentence: str) -> ClaimType | None:
    claim = classify_sentence(SentenceInfo(index=0, text=sentence, claim_id=None), "C1")
    return claim.type if claim is not None else None


@pytest.mark.parametrize(("sentence", "word"), GATED_ROWS)
def test_incomplete_sentence_extracts_as_unmapped_with_its_gap(sentence: str, word: str) -> None:
    claims = extract_claims(sentence).claims
    assert len(claims) == 1
    claim = claims[0]
    assert claim.type == ClaimType.UNMAPPED
    assert word in claim.coverage_gaps
    assert claim.needed_data is not None and word in claim.needed_data
    assert claim.parts == []


@pytest.mark.parametrize("sentence", sorted(RULES_DO_NOT_READ))
def test_sentence_the_rules_do_not_read_is_left_as_the_rules_give_it(sentence: str) -> None:
    assert _rules_type(sentence) in (None, ClaimType.UNMAPPED)
    assert all(c.type == ClaimType.UNMAPPED and c.coverage_gaps == [] for c in extract_claims(sentence).claims)


@pytest.mark.parametrize("sentence", COMPLETE)
def test_complete_sentence_keeps_its_rules_type(sentence: str) -> None:
    claims = extract_claims(sentence).claims
    expected = _rules_type(sentence)
    assert [c.type for c in claims] == ([expected] if expected else [])
    assert all(c.coverage_gaps == [] for c in claims)


def test_gate_keeps_identity_and_names_the_words() -> None:
    sentence = "Deaths rise with nodal involvement: 44 of 516 N0 patients died, against 15 of 77 N3 patients."
    claim = classify_sentence(SentenceInfo(index=4, text=sentence, claim_id=None), "C7")
    assert claim is not None and claim.type != ClaimType.UNMAPPED
    claim.original_text = "**" + sentence + "**"
    gated = gate(claim)
    assert (gated.id, gated.text, gated.sentence_index, gated.original_text) == ("C7", sentence, 4, "**" + sentence + "**")
    assert gated.type == ClaimType.UNMAPPED
    assert gated.coverage_gaps == ["N0", "15", "77", "N3"]
    assert gated.needed_data == GATED.format(words='"N0", "15", "77" and "N3"')
    assert gated.params == ClaimParams() and gated.parts == []


def test_gate_leaves_complete_not_answerable_and_unmapped_claims_alone() -> None:
    complete = classify_sentence(SentenceInfo(index=0, text=COMPLETE[0], claim_id=None), "C1")
    assert gate(complete) is complete
    not_answerable = Claim(id="C1", text="Patients with 85% ER treated with tamoxifen did better.", sentence_index=0,
                           type=ClaimType.NOT_ANSWERABLE, needed_data="treatment data")
    assert gate(not_answerable) is not_answerable
    unmapped = Claim(id="C1", text="Of 12 tumors, 3 were odd.", sentence_index=0, type=ClaimType.UNMAPPED,
                     needed_data="why the rules did not check it")
    assert gate(unmapped) is unmapped and unmapped.coverage_gaps == []


def test_classify_endpoint_applies_the_gate() -> None:
    sentence, word = INCOMPLETE[0]
    body = api.post("/classify", json={"text": sentence, "sentence_index": 2, "claim_id": "C9"}).json()
    assert (body["id"], body["type"], body["sentence_index"]) == ("C9", "UNMAPPED", 2)
    assert word in body["coverage_gaps"]


def test_extract_endpoint_returns_coverage_gaps() -> None:
    sentence, word = INCOMPLETE[1]
    claim = api.post("/extract", json={"report_text": sentence}).json()["claims"][0]
    assert claim["type"] == "UNMAPPED" and word in claim["coverage_gaps"]


@pytest.mark.parametrize(("sentence", "word"), GATED_ROWS)
def test_incomplete_sentence_audits_as_cant_check_naming_the_word(sentence: str, word: str, release_dir) -> None:
    claims = extract_claims(sentence).claims
    result = audit_claims(claims, release_dir, ai_client=None).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert word in result.missing_evidence


def test_audit_endpoint_accepts_a_gated_claim_posted_back(release_dir) -> None:
    sentence, word = INCOMPLETE[0]
    claim = api.post("/extract", json={"report_text": sentence}).json()["claims"][0]
    response = api.post("/audit", json={"release_dir": str(release_dir), "claims": [claim]})
    assert response.status_code == 200
    result = response.json()["claims"][0]
    assert result["verdict"] == "insufficient_evidence" and word in result["missing_evidence"]
    assert result["claim"]["coverage_gaps"] == claim["coverage_gaps"]


def test_practice_report_still_audits_supported_contradicted_insufficient(release_dir) -> None:
    claims = extract_claims(PRACTICE.read_text(encoding="utf-8")).claims
    assert all(c.coverage_gaps == [] for c in claims)
    audit = audit_claims(claims, release_dir, ai_client=None)
    assert [c.verdict for c in audit.claims] == [
        Verdict.SUPPORTED, Verdict.CONTRADICTED, Verdict.INSUFFICIENT_EVIDENCE]


def test_audit_json_export_does_not_carry_coverage_gaps(release_dir) -> None:
    from second_opinion.export import build_audit_json, validate_audit_json

    sentence, word = INCOMPLETE[0]
    doc = build_audit_json(audit_claims(extract_claims(sentence).claims, release_dir, ai_client=None))
    assert validate_audit_json(doc) == []
    assert "coverage_gaps" not in str(doc)
    assert word in doc["findings"][0]["summary"]


def test_claim_round_trips_coverage_gaps() -> None:
    claim = Claim(id="C1", text="x", sentence_index=0, type=ClaimType.UNMAPPED, coverage_gaps=["N0"])
    assert dataclasses.asdict(claim)["coverage_gaps"] == ["N0"]

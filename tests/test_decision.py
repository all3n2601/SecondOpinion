import json
from pathlib import Path

from pydantic import TypeAdapter

from second_opinion.decision import SIGN_OFF, final_verdict, suggest_decision
from second_opinion.model import AuditResult, Decision, Review, Solidity, Verdict

FIXTURE = Path(__file__).parent / "fixtures" / "practice_audit_result.json"


def load_fixture() -> AuditResult:
    return TypeAdapter(AuditResult).validate_python(json.loads(FIXTURE.read_text()))


def _without(audit: AuditResult, *ids: str) -> AuditResult:
    audit.claims = [c for c in audit.claims if c.claim.id not in ids]
    return audit


def test_practice_fixture_suggests_fix_a_problem():
    s = suggest_decision(load_fixture())
    assert s.decision == Decision.FIX
    assert s.rule.startswith("Rule 2")
    assert any("C2" in r for r in s.reasons)
    assert s.sign_off == SIGN_OFF == ["Data-use reviewer", "Principal investigator"]


def test_practice_would_change_names_the_fix_and_the_missing_data():
    s = suggest_decision(load_fixture())
    assert "If C2 were reworded to 49.9% (421 of 844), it could be published" in s.would_change
    assert any("treatment-response data" in w and "C3 could be tested" in w for w in s.would_change)


def test_without_contradiction_suggests_narrow():
    s = suggest_decision(_without(load_fixture(), "C2"))
    assert s.decision == Decision.NARROW
    assert any("C3" in r for r in s.reasons)


def test_fragile_claim_suggests_narrow():
    audit = _without(load_fixture(), "C2", "C3")
    audit.claims[0].solidity = Solidity.FRAGILE
    audit.claims[0].flips_on = ["subtype_source=study_2012_label"]
    s = suggest_decision(audit)
    assert s.decision == Decision.NARROW
    assert any("subtype_source=study_2012_label" in w for w in s.would_change)


def test_only_supported_robust_claims_proceed():
    s = suggest_decision(_without(load_fixture(), "C2", "C3"))
    assert s.decision == Decision.PROCEED
    assert s.rule.startswith("Rule 4")
    assert s.would_change


def test_checksum_mismatch_note_stops_everything():
    audit = load_fixture()
    audit.notes.append("Checksum mismatch: clinical.tsv")
    s = suggest_decision(audit)
    assert s.decision == Decision.STOP
    assert any("clinical.tsv" in r for r in s.reasons)


def test_missing_sha256_stops():
    audit = _without(load_fixture(), "C2", "C3")
    audit.release.files[1]["sha256"] = ""
    s = suggest_decision(audit)
    assert s.decision == Decision.STOP
    assert any("survival.tsv" in r for r in s.reasons)


def test_override_that_supports_c2_leaves_c3_open():
    audit = load_fixture()
    audit.claims[1].review = Review(
        decision="override", final_verdict=Verdict.SUPPORTED,
        reason="Report uses a different denominator", reviewer_role="Researcher",
    )
    assert final_verdict(audit.claims[1]) == Verdict.SUPPORTED
    s = suggest_decision(audit)
    assert s.decision == Decision.NARROW
    assert any("C2" in r and "Researcher" in r for r in s.reasons)


def test_empty_audit_proceeds_but_says_nothing_was_checked():
    audit = load_fixture()
    audit.claims = []
    s = suggest_decision(audit)
    assert s.decision == Decision.PROCEED
    assert any("No claims" in r for r in s.reasons)

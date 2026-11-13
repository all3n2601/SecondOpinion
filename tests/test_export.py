import json
import subprocess
import sys
from pathlib import Path

from second_opinion.export import build_audit_json, validate_audit_json
from second_opinion.model import Decision, DecisionChoice, Review, Solidity, Verdict
from tests.test_decision import load_fixture

ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = ROOT / "docs" / "challenge" / "format" / "validate.py"


def _finding(doc: dict, cid: str) -> dict:
    return next(f for f in doc["findings"] if f["id"] == cid)


def test_practice_fixture_exports_a_valid_file():
    doc = build_audit_json(load_fixture(), decision=None)
    assert validate_audit_json(doc) == []
    c2 = _finding(doc, "C2")
    assert (c2["kind"], c2["claim_verdict"], c2["correct_value"]) == (
        "claim_check", "contradicted", "49.9% (421 of 844)",
    )


def test_header_fields():
    doc = build_audit_json(load_fixture(), None)
    assert doc["format_version"] == "0.2"
    assert doc["producer"] == {
        "team": "SecondOpinion", "product": "Research Claim Auditor", "track": "evidence-navigator",
    }
    assert doc["data"]["dataset"] == "TCGA-BRCA"
    assert doc["data"]["releases"][0]["name"] == "A"
    assert len(doc["data"]["releases"][0]["files"]) == 5
    assert doc["question"] == "Are the claims in the report supported by release A?"
    assert "verdict" not in doc


def test_decision_sets_top_level_verdict():
    choice = DecisionChoice(choice=Decision.FIX, reason="C2 is wrong", reviewer_role="Data-use reviewer")
    doc = build_audit_json(load_fixture(), choice)
    assert doc["verdict"] == "Fix a problem"
    assert validate_audit_json(doc) == []


def test_correct_value_only_for_contradicted():
    doc = build_audit_json(load_fixture(), None)
    assert all(("correct_value" in f) == (f["claim_verdict"] == "contradicted") for f in doc["findings"])


def test_summaries_severity_and_confidence():
    doc = build_audit_json(load_fixture(), None)
    c1, c2, c3 = (_finding(doc, c) for c in ("C1", "C2", "C3"))
    assert c1["summary"] == "Recomputed from the data: 535 of 1,101."
    assert c2["summary"] == "49.9% (421 of 844) in the data, not what the report says."
    assert c3["summary"] == (
        "The data cannot answer this; would need: treatment and treatment-response data."
    )
    assert [c1["severity"], c2["severity"], c3["severity"]] == ["none", "medium", "low"]
    assert c2["confidence"] == "high"  # robust under every variant
    assert c3["confidence"] == "high"  # keyword rule
    assert all(f["needs_human_review"] is True for f in doc["findings"])
    assert c2["limitation"] == "Subtype calls exist for 844 of 1,101 primary tumors."
    assert "limitation" not in c1


def test_fragile_claim_is_medium_confidence_and_says_where_it_flips():
    audit = load_fixture()
    audit.claims[1].solidity = Solidity.FRAGILE
    audit.claims[1].flips_on = ["subtype_source=study_2012_label"]
    c2 = _finding(build_audit_json(audit, None), "C2")
    assert c2["confidence"] == "medium"
    assert "fragile: flips on subtype_source=study_2012_label" in c2["evidence"][0]["note"]


def test_evidence_points_at_files_or_the_claim():
    doc = build_audit_json(load_fixture(), None)
    c1, c2, c3 = (_finding(doc, c) for c in ("C1", "C2", "C3"))
    assert [e["id"] for e in c1["evidence"]][0] == "clinical.tsv"
    assert len(c1["evidence"]) == 5
    assert c2["evidence"] == [{
        "kind": "file", "id": "clinical.tsv", "release": "A",
        "note": "primary tumors with a PAM50 RNA-seq call that are Luminal A; robust: 8 of 8 ways of counting agree",
    }]
    assert c3["evidence"] == [{"kind": "claim", "id": "C3", "note": "no data field can test this claim"}]


def test_override_changes_final_verdict():
    audit = load_fixture()
    audit.claims[1].review = Review(
        decision="override", final_verdict=Verdict.SUPPORTED,
        reason="Report counts a different group", reviewer_role="Researcher",
    )
    c2 = _finding(build_audit_json(audit, None), "C2")
    assert c2["claim_verdict"] == "supported"
    assert "correct_value" not in c2
    assert c2["severity"] == "none"
    assert "Researcher" in c2["summary"]


def test_official_validator_accepts_output(tmp_path):
    choice = DecisionChoice(choice=Decision.FIX, reason="C2 is wrong", reviewer_role="Data-use reviewer")
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(build_audit_json(load_fixture(), choice), indent=2))
    run = subprocess.run([sys.executable, str(VALIDATOR), str(path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.startswith("valid")


def test_empty_audit_still_validates():
    audit = load_fixture()
    audit.claims = []
    doc = build_audit_json(audit, None)
    assert doc["findings"] == []
    assert validate_audit_json(doc) == []


def test_validator_reports_problems():
    doc = build_audit_json(load_fixture(), None)
    doc["findings"][0]["evidence"] = []
    del doc["question"]
    errors = validate_audit_json(doc)
    assert any("question" in e for e in errors)
    assert any("evidence" in e for e in errors)


def test_output_is_plain_json():
    json.dumps(build_audit_json(load_fixture(), None))  # no enums or dataclasses left inside

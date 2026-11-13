from datetime import date

from second_opinion.decision import suggest_decision
from second_opinion.export import RESEARCH_ONLY, build_decision_record, corrected_wording
from second_opinion.model import Decision, DecisionChoice, Review, Verdict
from tests.test_decision import load_fixture

CHOICE = DecisionChoice(
    choice=Decision.FIX, reason="C2 overstates the Luminal A share", reviewer_role="Data-use reviewer",
)


def _reviewed():
    audit = load_fixture()
    for r in audit.claims:
        r.review = Review(decision="accept", final_verdict=r.verdict, reason="", reviewer_role="Researcher")
    return audit


def _record(audit=None, choice=CHOICE):
    audit = audit or _reviewed()
    return build_decision_record(audit, choice, suggest_decision(audit), today=date(2026, 11, 14))


def test_record_has_the_key_facts():
    md = _record()
    for text in ("421 of 844", "C1", "C2", "C3", "Principal investigator", RESEARCH_ONLY,
                 "2026-11-14", "0.1.0", "Fix a problem", "C2 overstates the Luminal A share",
                 "Rule 2", "39eb3be0fb86e6a5"):
        assert text in md, text


def test_sections_are_in_order():
    md = _record()
    headings = [line for line in md.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Report and release", "## Decision", "## Claims", "## Important limitations",
        "## Who must sign off", "## What would change this decision",
    ]
    assert md.rstrip().endswith(RESEARCH_ONLY)


def test_override_reason_is_recorded_with_both_verdicts():
    audit = _reviewed()
    audit.claims[1].review = Review(
        decision="override", final_verdict=Verdict.SUPPORTED,
        reason="Report counts | a different group", reviewer_role="Researcher",
    )
    md = _record(audit)
    row = next(line for line in md.splitlines() if line.startswith("| C2 "))
    assert "contradicted" in row and "supported" in row
    assert "Report counts \\| a different group" in row  # pipes escaped inside the table


def test_choice_differing_from_suggestion_is_flagged():
    choice = DecisionChoice(choice=Decision.PROCEED, reason="Accept as is", reviewer_role="Program leader")
    md = _record(choice=choice)
    assert "differs from the suggested decision (Fix a problem)" in md


def test_limitations_include_release_notes():
    md = _record()
    assert "No RNA file in this release." in md
    assert "Subtype calls exist for 844 of 1,101 primary tumors." in md


def test_corrected_wording_drops_struck_text():
    c2 = load_fixture().claims[1]
    assert corrected_wording(c2) == (
        "Luminal A is the largest RNA subtype, accounting for **49.9% (421 of 844)** "
        "of primary tumors with an RNA subtype call."
    )

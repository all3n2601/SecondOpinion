"""Our own test reports with hand-worked answers (Task B7).

Parsing is checked on every run. Verdicts need the real release (SO_RELEASE_DIR) and are
skipped without it. A verdict failure lists every mismatch at once, with the sentence and the
expected and actual verdict, so it can be sent straight to the owner: parsing problems to Benoy,
checks and verdicts to Allen.
"""

import json
from pathlib import Path

import pytest

from second_opinion.extract import extract_claims

REPORTS = Path(__file__).resolve().parent / "reports"
REPORT_FILES = sorted(REPORTS.glob("report_*.md"))


def _expected(report: Path) -> list[dict]:
    return json.loads(report.with_suffix(".expected.json").read_text(encoding="utf-8"))


def _match(claims, expected):
    """Pair each expected row with the one claim whose text contains `claim_contains`."""
    pairs = []
    for row in expected:
        found = [c for c in claims if row["claim_contains"] in c.text]
        assert len(found) == 1, f"{row['claim_contains']!r} matched {len(found)} claims"
        pairs.append((row, found[0]))
    return pairs


def test_reports_exist():
    assert len(REPORT_FILES) >= 3
    for report in REPORT_FILES:
        assert report.with_suffix(".expected.json").is_file(), f"{report.name} has no expected file"


@pytest.mark.parametrize("report", REPORT_FILES, ids=lambda p: p.stem)
def test_report_claims_are_found_and_typed(report):
    claims = extract_claims(report.read_text(encoding="utf-8")).claims
    expected = _expected(report)
    assert len(claims) == len(expected), [c.text for c in claims]
    for row, claim in _match(claims, expected):
        assert claim.type.value == row["type"], claim.text


@pytest.mark.realdata
@pytest.mark.parametrize("report", REPORT_FILES, ids=lambda p: p.stem)
def test_report_verdicts(report, release_dir):
    from second_opinion.audit import NO_RNA_NOTE, audit_claims

    claims = extract_claims(report.read_text(encoding="utf-8")).claims
    result = audit_claims(claims, release_dir)
    no_rna = NO_RNA_NOTE in result.notes
    by_id = {r.claim.id: r for r in result.claims}

    mismatches = []
    for row, claim in _match(claims, _expected(report)):
        want = row["verdict"]
        if no_rna and "verdict_no_rna" in row:
            want = row["verdict_no_rna"]
            if want is None:
                continue  # this claim's answer depends on the RNA file
        got = by_id[claim.id]
        if got.verdict.value != want:
            detail = got.correct_value or got.missing_evidence or ""
            mismatches.append(f"{claim.text!r}: expected {want}, got {got.verdict.value} ({detail}) - {row['why']}")
    assert not mismatches, "\n" + "\n".join(mismatches)

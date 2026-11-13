"""Claims beyond counts and subtype shares: attributes, bounds, word amounts, ranks, ratios, statistics,
multi-part sentences, unavailable measures, survival comparisons, and the guards that keep a run alive.

Verdicts on the real release are covered by tests/reports/report_4 and report_5 (test_own_reports.py).
"""

import pandas as pd
import pytest

from second_opinion import audit as audit_module
from second_opinion.audit import _honest_need, audit_claims
from second_opinion.export import build_audit_json, validate_audit_json
from second_opinion.extract import extract_claims, find_amounts
from second_opinion.model import Claim, ClaimParams, ClaimType, Fact, Verdict
from second_opinion.verdict import judge
from tests.helpers import make_mini_release


def claim(text: str) -> Claim:
    claims = extract_claims(text).claims
    assert len(claims) == 1, [c.text for c in claims]
    return claims[0]


# --- extraction --------------------------------------------------------------------------------

@pytest.mark.parametrize("text, kind, attribute, category", [
    ("Roughly 15 percent of primary tumors are HER2-positive.", ClaimType.SHARE, "her2_status", "positive"),
    ("About 77% of tumors are ER+.", ClaimType.SHARE, "er_status", "positive"),
    ("Some 30% of tumors are estrogen receptor negative.", ClaimType.SHARE, "er_status", "negative"),
    ("Approximately 12% of primary tumors are triple-negative.", ClaimType.SHARE, "triple_negative", "triple-negative"),
    ("TP53 is mutated in about a third of primary tumors.", ClaimType.SHARE, "mutation", "TP53"),
    ("GATA3 mutations occur in more than 10% of tumors.", ClaimType.SHARE, "mutation", "GATA3"),
    ("ERBB2 is amplified in about 12% of tumors.", ClaimType.SHARE, "amplification", "ERBB2"),
    ("HER2 amplification is seen in 12% of tumors.", ClaimType.SHARE, "amplification", "ERBB2"),
    ("Stage II tumors make up about half of primary tumors.", ClaimType.SHARE, "stage", "Stage II"),
    ("Stage IIA tumors are 33% of staged tumors.", ClaimType.SHARE, "stage", "Stage IIA"),
    ("Lobular carcinomas make up about 18% of primary tumors.", ClaimType.SHARE, "histology", "lobular"),
    ("Most patients were postmenopausal.", ClaimType.SHARE, "menopause", "post"),
    ("About 14% of patients died during follow-up.", ClaimType.SHARE, "vital_status", "deceased"),
    ("More than 150 deaths are recorded.", ClaimType.COUNT, "vital_status", "deceased"),
    ("PIK3CA is the most frequently mutated gene.", ClaimType.RANK, "mutation", "PIK3CA"),
    ("Luminal B is the second most common subtype.", ClaimType.RANK, "subtype", "Luminal B"),
    ("Normal-like is the least common subtype.", ClaimType.RANK, "subtype", "Normal-like"),
    ("Basal-like tumors outnumber HER2-enriched tumors by about two to one.", ClaimType.RATIO, "subtype", "Basal-like"),
    ("There are twice as many Luminal A as Luminal B tumors.", ClaimType.RATIO, "subtype", "Luminal A"),
    ("TP53 mutations are more common in Basal-like than in Luminal A tumors.", ClaimType.COMPARISON, "mutation", "TP53"),
])
def test_attribute_claims_are_read(text, kind, attribute, category):
    c = claim(text)
    assert c.type is kind
    assert (c.params.attribute, c.params.category) == (attribute, category)


def test_word_amounts_and_bounds():
    third = claim("TP53 is mutated in about a third of primary tumors.").params
    assert third.unit == "percent" and abs(third.stated_value - 100 / 3) < 1e-9 and third.approximate
    most = claim("Most patients were postmenopausal.").params
    assert (most.stated_value, most.bound) == (50.0, "gt")
    nearly = claim("Nearly all primary tumors have copy number data.").params
    assert (nearly.unit, nearly.stated_value, nearly.bound) == ("percent", 90.0, "gte")
    fewer = claim("Fewer than 1% of patients are male.").params
    assert (fewer.stated_value, fewer.bound) == (1.0, "lt")
    at_least = claim("At least 1,000 primary tumors have survival data.").params
    assert (at_least.stated_value, at_least.bound) == (1000.0, "gte")
    no_more = [a for a in find_amounts("No more than 20 samples are metastatic.") if not a.words]
    assert no_more[0].bound == "lte"
    one_in_ten = [a for a in find_amounts("One in ten tumors is HER2-enriched.") if a.words]
    assert one_in_ten[0].value == 10.0


def test_subgroups_are_the_population_not_the_claim():
    c = claim("About 80% of triple-negative tumors are Basal-like.")
    assert (c.params.attribute, c.params.category) == ("subtype", "Basal-like")
    assert (c.params.within_attribute, c.params.within_category) == ("triple_negative", "triple-negative")
    cov = claim("Protein data covers most triple-negative tumors.")
    assert cov.type is ClaimType.COVERAGE and cov.params.within_attribute == "triple_negative"
    age = claim("Among triple-negative tumors, the median age was 55 years.")
    assert age.type is ClaimType.STATISTIC and age.params.within_attribute == "triple_negative"


def test_top_n_rank_names_both_genes():
    c = claim("TP53 and PIK3CA are the two most frequently mutated genes.")
    assert (c.type, c.params.top_n, c.params.category, c.params.category_b) == (ClaimType.RANK, 2, "TP53", "PIK3CA")


@pytest.mark.parametrize("text, need", [
    ("Ki-67 staining was high in most Luminal B tumors.", "Ki-67"),
    ("Tumor grade was higher in Basal-like tumors.", "grade"),
    ("Black women are more likely to have triple-negative tumors.", "race"),
    ("Obese patients more often had ER-positive tumors.", "body-mass"),
    ("ER-positive patients live longer than ER-negative patients.", "survival analysis"),
    ("Patients with Basal-like tumors have worse overall survival.", "survival analysis"),
    ("Tumors with BRCA1 mutations are best treated with PARP inhibitors.", "treatment"),
    ("HER2-positive patients benefit from trastuzumab.", "treatment"),
    ("The cohort is large enough for a Luminal A versus Basal-like comparison.", "sample-size"),
])
def test_claims_the_data_cannot_answer(text, need):
    c = claim(text)
    assert c.type is ClaimType.NOT_ANSWERABLE
    assert need in c.needed_data


@pytest.mark.parametrize("text", [
    "TCGA's breast cancer cohort is one of the most widely used public cancer datasets.",
    "Protein measurements add a useful layer.",
    "We recommend future work combine all available layers.",
    "Multi-omic studies depend on samples having every data layer.",
    "Subtype labels should be read with care.",
    "Could HER2-positive tumors be more common than reported?",
    "This summary looks at how PAM50 subtypes are spread across the TCGA-BRCA release.",
    "RPPA protein levels can be compared with clinical receptor status.",
])
def test_sentences_that_are_not_claims_stay_out(text):
    assert extract_claims(text).claims == []


def test_two_counts_in_one_sentence_are_two_parts():
    c = claim("There are 7 metastatic samples and 139 normal-tissue samples.")
    assert [(p.id, p.params.subject, p.params.stated_value) for p in c.parts] == [
        ("C1.1", "metastatic_samples", 7.0), ("C1.2", "normal_tissue_samples", 139.0)]
    assert c.parts[0].part_label == "7 metastatic samples"


def test_about_covers_every_number_in_a_list():
    c = claim("About 77% of tumors are ER-positive and 66% are PR-positive.")
    assert [p.params.approximate for p in c.parts] == [True, True]
    assert [p.params.attribute for p in c.parts] == ["er_status", "pr_status"]


def test_a_share_with_a_rank_checks_both():
    c = claim("Luminal B is the largest RNA subtype, at about 23% of subtyped tumors.")
    assert [p.type for p in c.parts] == [ClaimType.SHARE, ClaimType.RANK]
    assert c.type is ClaimType.SHARE


def test_two_values_of_one_attribute_are_not_read_as_one():
    assert claim("Luminal A and Basal-like tumors make up 70% of subtyped tumors.").type is ClaimType.UNMAPPED
    assert claim("Roughly 80 percent of patients have a TP53 or PIK3CA mutation.").type is ClaimType.UNMAPPED


# --- verdicts ------------------------------------------------------------------------------------

def _fact(value, numerator=None, denominator=None, **extra) -> Fact:
    return Fact("x", value, numerator, denominator, [], ["clinical.tsv"], "n = 1", extra=extra)


@pytest.mark.parametrize("bound, stated, ours, ok", [
    ("gt", 150, 151, True), ("gt", 150, 150, False), ("gte", 150, 150, True),
    ("lt", 1, 1.09, False), ("lte", 20, 20, True),
])
def test_bounds(bound, stated, ours, ok):
    count = Claim("C1", "t", 0, ClaimType.COUNT, ClaimParams(unit="count", stated_value=stated, bound=bound))
    assert (judge(count, _fact(ours, ours))[0] is Verdict.SUPPORTED) is ok


def test_percent_bound_uses_the_exact_share():
    share = Claim("C1", "t", 0, ClaimType.SHARE, ClaimParams(unit="percent", stated_value=1.0, bound="lt"))
    verdict, correct = judge(share, _fact(100 * 12 / 1097, 12, 1097))
    assert verdict is Verdict.CONTRADICTED and correct == "1.1% (12 of 1,097)"


@pytest.mark.parametrize("stated, approx, a, b, ok", [
    (2, True, 141, 67, True), (3, False, 421, 141, True), (2, False, 421, 192, True), (3, True, 141, 67, False),
])
def test_ratios(stated, approx, a, b, ok):
    c = Claim("C1", "t", 0, ClaimType.RATIO, ClaimParams(unit="ratio", stated_value=stated, approximate=approx))
    verdict, correct = judge(c, _fact(a / b, a, b))
    assert (verdict is Verdict.SUPPORTED) is ok
    if not ok:
        assert correct == f"{a / b:.2f} to 1 ({a} vs {b})"


def test_rank_and_top_n():
    extra = dict(leader="PIK3CA", leader_count=273, total=791, ranks="TP53 2nd (264 of 791)")
    first = Claim("C1", "t", 0, ClaimType.RANK, ClaimParams(unit="rank", stated_value=1, category="TP53"))
    verdict, correct = judge(first, _fact(2.0, 264, 791, **extra))
    assert verdict is Verdict.CONTRADICTED and "PIK3CA is the most common (273 of 791)" in correct
    top2 = Claim("C1", "t", 0, ClaimType.RANK, ClaimParams(unit="rank", stated_value=2, top_n=2))
    assert judge(top2, _fact(2.0, 264, 791, **extra))[0] is Verdict.SUPPORTED


def test_statistic_rounds_to_the_stated_precision():
    c = Claim("C1", "t", 0, ClaimType.STATISTIC, ClaimParams(unit="years", stated_value=58, measure="median"))
    assert judge(c, _fact(58.0, None, 1097))[0] is Verdict.SUPPORTED
    assert judge(c, _fact(58.5, None, 1097))[0] is Verdict.CONTRADICTED  # 58.5 rounds half up to 59
    about = Claim("C1", "t", 0, ClaimType.STATISTIC, ClaimParams(unit="years", stated_value=57, approximate=True))
    assert judge(about, _fact(58.0, None, 1097))[0] is Verdict.SUPPORTED


# --- the audit on the mini release ----------------------------------------------------------------

def test_attribute_checks_on_the_mini_release(mini_release):
    claims = extract_claims(
        "About 60% of primary tumors are ER-positive. "
        "TP53 is mutated in about a third of primary tumors. "
        "There are 7 metastatic samples and 2 normal-tissue samples."
    ).claims
    result = audit_claims(claims, mini_release)
    er, tp53, counts = result.claims
    # ER: 6 Positive, 3 Negative, 1 Indeterminate among the 10 primaries -> 6 of 9
    assert (er.fact.numerator, er.fact.denominator, er.fact.unknown_count) == (6, 9, 1)
    assert er.verdict is Verdict.CONTRADICTED and er.correct_value == "66.7% (6 of 9)"
    mutation = pd.read_csv(mini_release / "mutation_gene_level.tsv.gz", sep="\t", index_col=0)
    primary = [s for s in mutation.columns if s[13:15] == "01"]
    assert tp53.fact.numerator == int((mutation.loc["TP53", primary] > 0).sum())
    assert tp53.fact.denominator == len(primary)
    assert counts.verdict is Verdict.CONTRADICTED  # 1 metastatic sample, not 7; 2 normal samples is right
    assert [p.verdict for p in counts.parts] == [Verdict.CONTRADICTED, Verdict.SUPPORTED]
    assert counts.correct_value == "1"


def test_a_failing_check_never_stops_the_audit(mini_release, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setitem(audit_module.CHECKS, ClaimType.COUNT, boom)
    claims = extract_claims("The release has 10 primary tumors. Luminal A is 30% of subtyped primary tumors.").claims
    result = audit_claims(claims, mini_release)
    assert result.claims[0].verdict is Verdict.INSUFFICIENT_EVIDENCE
    assert "by hand" in result.claims[0].missing_evidence
    assert result.claims[1].fact is not None  # the next claim is still checked


def test_a_missing_gene_is_insufficient_not_an_error(mini_release):
    result = audit_claims(extract_claims("BRCA2 is mutated in 5% of tumors.").claims, mini_release)
    assert result.claims[0].verdict is Verdict.INSUFFICIENT_EVIDENCE
    assert "BRCA2" in result.claims[0].missing_evidence


def test_multi_part_finding_lists_every_part_and_validates(mini_release):
    claims = extract_claims("There are 7 metastatic samples and 2 normal-tissue samples.").claims
    doc = build_audit_json(audit_claims(claims, mini_release))
    assert validate_audit_json(doc) == []
    (finding,) = doc["findings"]
    assert finding["claim_text"] == "There are 7 metastatic samples and 2 normal-tissue samples."
    assert finding["claim_verdict"] == "contradicted" and finding["correct_value"] == "1"
    assert '"7 metastatic samples": contradicted' in finding["summary"]
    assert '"2 normal-tissue samples": supported' in finding["summary"]
    assert [e["id"] for e in finding["evidence"] if e["kind"] == "claim"] == ["C1.1", "C1.2"]


def test_the_ai_is_never_allowed_to_say_present_data_is_missing():
    assert "the release does hold the data" in _honest_need("Gene-level mutation calls for GATA3")
    assert "the release does hold the data" in _honest_need("Vital status or death-event data for each patient")
    assert _honest_need("Treatment records for each patient") == "Treatment records for each patient"


def test_cli_reads_a_report_with_a_byte_order_mark(tmp_path):
    from second_opinion.cli import read_report

    path = tmp_path / "report.md"
    path.write_bytes("﻿The release has 1,101 primary tumors.".encode("utf-8"))
    assert read_report(str(path)) == "The release has 1,101 primary tumors."
    path.write_bytes("Caf\xe9 tumors.".encode("cp1252"))
    assert read_report(str(path)) == "Café tumors."


def test_mini_release_fixture_still_has_no_rna(tmp_path):
    folder = make_mini_release(tmp_path / "r")
    assert not (folder / "rna_hiseq.tsv.gz").exists()


def test_slide_counts_use_the_slide_manifest_when_there_is_one(tmp_path):
    folder = make_mini_release(tmp_path / "raw")
    claims = extract_claims("There are 2 diagnostic slides and 1 frozen section.").claims
    without = audit_claims(claims, folder).claims[0]
    assert without.verdict is Verdict.INSUFFICIENT_EVIDENCE and "slide_manifest.csv" in without.missing_evidence
    pd.DataFrame({
        "slide_barcode": ["TCGA-AA-0001-01A-01-DX1", "TCGA-AA-0002-01A-01-DX1", "TCGA-AA-0001-01A-01-TS1"],
        "sample_id": ["TCGA-AA-0001-01", "TCGA-AA-0002-01", "TCGA-AA-0001-01"],
        "slide_kind": ["diagnostic (FFPE)", "diagnostic (FFPE)", "frozen, top section"],
    }).to_csv(tmp_path / "slide_manifest.csv", index=False)  # one level above raw/, as in release A
    with_manifest = audit_claims(claims, folder).claims[0]
    assert with_manifest.verdict is Verdict.SUPPORTED
    assert [p.fact.numerator for p in with_manifest.parts] == [2, 1]

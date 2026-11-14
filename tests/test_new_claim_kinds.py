"""Claims beyond counts and subtype shares: attributes, bounds, word amounts, ranks, ratios, statistics,
multi-part sentences, unavailable measures, survival comparisons, and the guards that keep a run alive.

Verdicts on the real release are covered by tests/reports/report_4 and report_5 (test_own_reports.py).
"""

import pandas as pd
import pytest

from second_opinion import audit as audit_module
from second_opinion.audit import _honest_need, audit_claims
from second_opinion.export import build_audit_json, validate_audit_json
from second_opinion.extract import classify_sentence, extract_claims, find_amounts
from second_opinion.model import Claim, ClaimParams, ClaimType, Fact, SentenceInfo, Verdict
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
    sentence = "There are 2 diagnostic slides and 1 frozen section."
    # The coverage gate gives no verdict: the count check counts tumors with a slide, the sentence counts slides.
    [gated] = extract_claims(sentence).claims
    assert (gated.type, gated.coverage_gaps) == (ClaimType.UNMAPPED, ["slides"])
    # The rules reading itself still reads the slide manifest.
    claims = [classify_sentence(SentenceInfo(index=0, text=sentence, claim_id=None), "C1")]
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


# --- category unions: "stage III or IV", "stage III or higher" ---------------------------------------------

@pytest.mark.parametrize("sentence, category", [
    ("Between 20% and 25% of staged tumours are stage III or IV.", "Stage III or IV"),
    ("Over a quarter of staged tumours are stage III or higher.", "Stage III or IV"),
    ("About 25% of staged tumours are stage III or above.", "Stage III or IV"),
    ("Three quarters of staged tumours are stage II or lower.", "Stage I or II"),
    ("About 74% of staged tumours are stage I or II.", "Stage I or II"),
])
def test_stage_unions_are_one_group(sentence, category):
    c = claim(sentence)
    assert (c.type, c.params.attribute, c.params.category) == (ClaimType.SHARE, "stage", category)


def test_stage_union_counts_every_stage_in_it(release_dir):
    over = claim("Over a quarter of staged tumours are stage III or higher.")
    between = claim("Between 20% and 25% of staged tumours are stage III or IV.")
    [a, b] = audit_claims([over, between], release_dir).claims
    assert (a.fact.numerator, a.fact.denominator) == (270, 1075)  # III 250 + IV 20, of 1,075 staged
    assert (a.verdict, b.verdict) == (Verdict.SUPPORTED, Verdict.CONTRADICTED)


# --- "outnumber" with a stated ratio: the ratio is the claim, not just "more" ------------------------------

@pytest.mark.parametrize("sentence, value, bound, approximate", [
    ("Postmenopausal women outnumber premenopausal women about three to one.", 3, None, True),
    ("Basal-like tumours outnumber HER2-enriched tumours by more than two to one.", 2, "gt", False),
    ("Luminal A tumours outnumber Basal-like tumours ten to one.", 10, None, False),
    ("Luminal A tumours outnumber Basal-like tumours by roughly 3:1.", 3, None, True),
    ("Luminal A tumours outnumber Basal-like tumours.", 1, "gt", False),
])
def test_outnumber_keeps_the_stated_ratio(sentence, value, bound, approximate):
    c = claim(sentence)
    assert c.type is ClaimType.RATIO
    assert (c.params.stated_value, c.params.bound, c.params.approximate) == (value, bound, approximate)


# --- the size of a stated difference: "higher ... by about 3 units" ------------------------------------------

@pytest.mark.parametrize("sentence, value, bound, approximate", [
    ("Mean ERALPHA protein is higher in ER-positive than in ER-negative tumours by about 3 units.", 3, None, True),
    ("ERALPHA protein is higher in ER-positive tumours by 3.1 units.", 3.1, None, False),
    ("ERALPHA protein is higher in ER-positive tumours by more than 2 units.", 2, "gt", False),
])
def test_comparison_keeps_the_stated_difference(sentence, value, bound, approximate):
    c = claim(sentence)
    assert c.type is ClaimType.COMPARISON
    assert (c.params.unit, c.params.stated_value, c.params.bound, c.params.approximate) == ("difference", value, bound, approximate)


def _diff_fact(value):
    return Fact("x", value, None, None, [], [], "", extra={"n_a": 529, "n_b": 169})


@pytest.mark.parametrize("sentence, difference, verdict", [
    ("ERALPHA protein is higher in ER-positive tumours by about 3 units.", 3.05, Verdict.SUPPORTED),
    ("ERALPHA protein is higher in ER-positive tumours by about 30 units.", 3.05, Verdict.CONTRADICTED),
    ("ERALPHA protein is higher in ER-positive tumours by 3.1 units.", 3.05, Verdict.SUPPORTED),
    ("ERALPHA protein is higher in ER-positive tumours by 3.2 units.", 3.05, Verdict.CONTRADICTED),
    ("ERALPHA protein is higher in ER-positive tumours by more than 2 units.", 3.05, Verdict.SUPPORTED),
    ("ERALPHA protein is higher in ER-positive tumours by more than 4 units.", 3.05, Verdict.CONTRADICTED),
    ("ERALPHA protein is higher in ER-positive tumours by about 3 units.", -3.05, Verdict.CONTRADICTED),
])
def test_comparison_judges_the_stated_difference(sentence, difference, verdict):
    assert judge(claim(sentence), _diff_fact(difference))[0] == verdict


# --- facts about the files themselves: genes and proteins measured --------------------------------------------

@pytest.mark.parametrize("sentence, layer, value, bound", [
    ("The mutation file lists more than 40,000 genes.", "mutation", 40000, "gt"),
    ("Copy number calls are given for 24,776 genes.", "copy_number", 24776, None),
    ("The protein panel measures 131 proteins.", "protein", 131, None),
    ("RNA expression is reported for about 20,000 genes.", "rna", 20000, None),
])
def test_feature_counts_are_about_the_file(sentence, layer, value, bound):
    c = claim(sentence)
    assert (c.type, c.params.subject, c.params.stated_value, c.params.bound) == (ClaimType.COUNT, f"features:{layer}", value, bound)


def test_feature_count_in_a_coverage_sentence_is_its_own_part():
    c = claim("Protein data cover 742 primary tumours measured across 131 proteins.")
    assert [(p.type, p.params.subject, p.params.stated_value) for p in c.parts] == [
        (ClaimType.COVERAGE, "has_protein", 742), (ClaimType.COUNT, "features:protein", 131)]


def test_feature_count_reads_the_files_rows(tmp_path):
    folder = make_mini_release(tmp_path / "r")
    protein = pd.read_csv(folder / "protein_rppa.tsv.gz", sep="\t", index_col=0)
    mutation = pd.read_csv(folder / "mutation_gene_level.tsv.gz", sep="\t", index_col=0)
    claims = [claim(f"The protein panel measures {len(protein)} proteins."),
              claim(f"The mutation file lists {len(mutation) + 1} genes.")]
    [a, b] = audit_claims(claims, folder).claims
    assert (a.verdict, a.fact.value) == (Verdict.SUPPORTED, len(protein))
    assert (b.verdict, b.fact.value) == (Verdict.CONTRADICTED, len(mutation))


@pytest.mark.parametrize("sentence, direction", [
    ("PIK3CA mutations are rarest in Basal-like tumours.", "lower"),
    ("TP53 mutations are commonest in Basal-like tumours.", None),
    ("PIK3CA mutations were least frequent among Basal-like tumours.", "lower"),
])
def test_rarest_in_a_group_ranks_the_groups_by_rate(sentence, direction):
    c = claim(sentence)
    assert c.type is ClaimType.RANK
    assert (c.params.measure, c.params.within_attribute, c.params.within_category, c.params.direction) == (
        "rate", "subtype", "Basal-like", direction)


# --- ages written as words, and "diagnosed before forty" ----------------------------------------------------------

@pytest.mark.parametrize("sentence, ctype, category, value, bound", [
    ("Patients aged seventy or more account for over a third of primary tumours.", ClaimType.SHARE, "gte70", 100 / 3, "gt"),
    ("Under one in fifteen primary tumours come from patients diagnosed before forty.", ClaimType.SHARE, "lt40", 100 / 15, "lt"),
    ("Fewer than 300 primary tumours come from patients diagnosed before fifty.", ClaimType.COUNT, "lt50", 300, "lt"),
])
def test_word_ages_name_an_age_group(sentence, ctype, category, value, bound):
    c = claim(sentence)
    assert (c.type, c.params.attribute, c.params.category, c.params.bound) == (ctype, "age_group", category, bound)
    assert c.params.stated_value == pytest.approx(value)


def test_word_age_groups_on_the_real_release(release_dir):
    claims = [claim("Patients aged seventy or more account for over a third of primary tumours."),
              claim("Under one in fifteen primary tumours come from patients diagnosed before forty."),
              claim("Fewer than 300 primary tumours come from patients diagnosed before fifty.")]
    verdicts = [r.verdict for r in audit_claims(claims, release_dir).claims]
    assert verdicts == [Verdict.CONTRADICTED, Verdict.CONTRADICTED, Verdict.SUPPORTED]  # 21.0%, 6.9%, 297


# --- ratios of two rates: "eight times as common in Basal-like as in Luminal A" ------------------------------------

@pytest.mark.parametrize("sentence, attribute, category, group_a, group_b, value", [
    ("TP53 mutations are roughly eight times as common in Basal-like as in Luminal A tumours.",
     "mutation", "TP53", "Basal-like", "Luminal A", 8),
    ("TP53 mutations are 8 times more common in Basal-like than in Luminal A tumours.",
     "mutation", "TP53", "Basal-like", "Luminal A", 8),
    ("PIK3CA is mutated twice as often in Luminal A as in Basal-like tumours.",
     "mutation", "PIK3CA", "Luminal A", "Basal-like", 2),
    ("Lobular carcinomas are three times as likely to be Luminal A as ductal carcinomas.",
     "subtype", "Luminal A", "lobular", "ductal", 3),
])
def test_ratio_of_rates_compares_the_rate_in_each_group(sentence, attribute, category, group_a, group_b, value):
    c = claim(sentence)
    p = c.params
    assert (c.type, p.measure, p.attribute, p.category) == (ClaimType.RATIO, "rate", attribute, category)
    assert (p.within_category, p.category_b, p.stated_value) == (group_a, group_b, value)


def test_ratio_of_rates_on_the_real_release(release_dir):
    claims = [claim("TP53 mutations are 8 times more common in Basal-like than in Luminal A tumours."),
              claim("TP53 mutations are four times as common in Basal-like as in Luminal A tumours.")]
    eight, four = audit_claims(claims, release_dir).claims
    assert eight.fact.value == pytest.approx((90 / 106) / (31 / 301))
    assert (eight.verdict, four.verdict) == (Verdict.SUPPORTED, Verdict.CONTRADICTED)
    assert four.correct_value.startswith("8.24 to 1 (84.9% vs 10.3%")


# --- ages as statistics, not counts: "the oldest patient was 90 at diagnosis" ----------------------------------------

@pytest.mark.parametrize("sentence, stat, value", [
    ("The oldest patient was 90 at diagnosis.", "max", 90),
    ("The youngest patient was diagnosed at 26.", "min", 26),
    ("The oldest patient at diagnosis was ninety.", "max", 90),
    ("The typical patient was diagnosed at fifty-eight, going by the median.", "median", 58),
    ("The median age at diagnosis was fifty-eight years.", "median", 58),
])
def test_ages_are_statistics(sentence, stat, value):
    c = claim(sentence)
    assert (c.type, c.params.measure, c.params.stated_value) == (ClaimType.STATISTIC, stat, value)


# --- groups compared and ranked by median age, without numbers --------------------------------------------------

@pytest.mark.parametrize("sentence, direction, group_a, group_b", [
    ("Basal-like patients were diagnosed younger than Luminal A patients.", "lower", "Basal-like", "Luminal A"),
    ("Luminal A patients were older at diagnosis than Basal-like patients.", "higher", "Luminal A", "Basal-like"),
    ("Lobular carcinomas were diagnosed older than ductal carcinomas.", "higher", "lobular", "ductal"),
])
def test_median_age_comparison(sentence, direction, group_a, group_b):
    c = claim(sentence)
    p = c.params
    assert (c.type, p.measure, p.direction, p.within_category, p.category_b) == (
        ClaimType.COMPARISON, "median_age", direction, group_a, group_b)


@pytest.mark.parametrize("sentence, category, direction", [
    ("Basal-like patients were the youngest at diagnosis of any RNA subtype.", "Basal-like", "lower"),
    ("Luminal A patients were the oldest at diagnosis of any RNA subtype.", "Luminal A", None),
])
def test_median_age_rank(sentence, category, direction):
    c = claim(sentence)
    p = c.params
    assert (c.type, p.measure, p.within_category, p.direction, p.stated_value) == (
        ClaimType.RANK, "median_age", category, direction, 1)


def test_median_age_groups_on_the_real_release(release_dir):
    claims = [claim("Basal-like patients were diagnosed younger than Luminal A patients."),
              claim("Basal-like patients were the youngest at diagnosis of any RNA subtype."),
              claim("Luminal A patients were the oldest at diagnosis of any RNA subtype.")]
    younger, youngest, oldest = audit_claims(claims, release_dir).claims
    assert (younger.verdict, younger.fact.value) == (Verdict.SUPPORTED, -7)  # 54 vs 61
    assert youngest.verdict == Verdict.CONTRADICTED and "Normal-like" in youngest.correct_value  # 53 < 54
    assert oldest.verdict == Verdict.SUPPORTED


# --- agreement between the RNA-seq call and the 2012 study label --------------------------------------------------

@pytest.mark.parametrize("sentence, value", [
    ("Where both the RNA-seq call and the 2012 label exist, the two agree for 90% of tumors.", 90),
    ("The RNA-seq PAM50 call and the 2012 consortium label are concordant in about nine in ten tumours.", 90),
])
def test_label_agreement_is_its_own_claim(sentence, value):
    c = claim(sentence)
    assert (c.type, c.params.subject, c.params.stated_value) == (ClaimType.AGREEMENT, "subtype_sources", value)


def test_label_agreement_counts_tumours_with_both_labels(tmp_path):
    folder = make_mini_release(tmp_path / "r")
    clin = pd.read_csv(folder / "clinical.tsv", sep="\t")
    p = clin[clin.sampleID.str[13:15] == "01"]
    both = p[p.PAM50Call_RNAseq.notna() & p.PAM50_mRNA_nature2012.notna()]
    from second_opinion.variants import normalise_subtype
    agree = int((both.PAM50Call_RNAseq.map(normalise_subtype) == both.PAM50_mRNA_nature2012.map(normalise_subtype)).sum())
    [r] = audit_claims([claim("Where both the RNA-seq call and the 2012 label exist, the two agree for 90% of tumors.")], folder).claims
    assert (r.fact.numerator, r.fact.denominator) == (agree, len(both))


@pytest.mark.parametrize("sentence", [
    "Under the 2012 consortium labels, Normal-like is the rarest group, at under 2% of labelled tumors.",
    "By the 2012 study labels, Luminal A accounts for 231 tumours.",
])
def test_the_2012_labels_pick_the_second_subtype_source(sentence):
    c = claim(sentence)
    assert all(p.params.subtype_source == "study_2012_label" for p in (c.parts or [c]))


def test_rna_calls_stay_the_default_source():
    assert claim("Luminal A accounts for 421 primary tumours.").params.subtype_source is None


# --- a count of one subtype is a count of that subtype, never of every tumour ------------------------------------

@pytest.mark.parametrize("sentence, category, value", [
    ("There are 421 Luminal A tumours.", "Luminal A", 421),
    ("141 primary tumours are Basal-like.", "Basal-like", 141),
    ("Luminal A accounts for 421 primary tumours.", "Luminal A", 421),
    ("By the 2012 study labels, Luminal A accounts for 231 tumours.", "Luminal A", 231),
])
def test_a_subtype_count_names_the_subtype(sentence, category, value):
    c = claim(sentence)
    assert (c.type, c.params.attribute, c.params.category, c.params.stated_value) == (ClaimType.COUNT, "subtype", category, value)


def test_subtype_counts_on_the_real_release(release_dir):
    claims = [claim("There are 421 Luminal A tumours."), claim("By the 2012 study labels, Luminal A accounts for 231 tumours."),
              claim("There are 425 Luminal A tumours.")]
    assert [r.verdict for r in audit_claims(claims, release_dir).claims] == [Verdict.SUPPORTED, Verdict.SUPPORTED, Verdict.CONTRADICTED]


# --- one value in two groups, each with its own figure; a subgroup named "of the tumours scored X" --------------------

@pytest.mark.parametrize("sentence, target, parts", [
    ("TP53 mutations are concentrated in basal-like tumors, where 85% carry one, against roughly one in ten Luminal A tumors.",
     ("mutation", "TP53"), [("Basal-like", 85.0), ("Luminal A", 10.0)]),
    ("Three in four stage IV patients died during follow-up, compared with fewer than one in ten stage I patients.",
     ("vital_status", "deceased"), [("Stage IV", 75.0), ("Stage I", 10.0)]),
])
def test_a_figure_for_each_group(sentence, target, parts):
    c = claim(sentence)
    got = [((p.params.attribute, p.params.category), p.params.within_category, p.params.stated_value) for p in c.parts]
    assert got == [(target, group, value) for group, value in parts]


def test_a_subgroup_named_before_its_status():
    c = claim("Just over half of the tumors scored HER2-positive by immunohistochemistry carry an ERBB2 amplification.")
    p = c.params
    assert (p.attribute, p.category, p.within_attribute, p.within_category, p.bound) == (
        "amplification", "ERBB2", "her2_status", "positive", "gt")


def test_coverage_among_tumours_with_a_known_status():
    c = claim("The ER protein comparison includes 698 primary tumors with both RPPA data and a definitive ER result.")
    p = c.params
    assert (c.type, p.subject, p.within_attribute, p.within_category, p.stated_value) == (
        ClaimType.COVERAGE, "has_protein", "er_status", "any", 698)


# --- years of diagnosis and lymph-node counts ------------------------------------------------------------------

@pytest.mark.parametrize("sentence, category", [
    ("Most tumors in the release were diagnosed in 2010 or later.", "gte2010"),
    ("Less than 1% of primary tumours were diagnosed before 1990.", "lt1990"),
    ("About 44% of tumours were diagnosed since 2010.", "gte2010"),
])
def test_year_of_diagnosis_groups(sentence, category):
    c = claim(sentence)
    assert (c.type, c.params.attribute, c.params.category) == (ClaimType.SHARE, "diagnosis_year", category)


def test_year_range_and_node_statistics_on_the_real_release(release_dir):
    claims = [claim("Diagnoses span the years 1988 to 2013."), claim("Most tumors in the release were diagnosed in 2010 or later."),
              claim("Less than 1% of primary tumours were diagnosed before 1990."),
              claim("The median number of positive lymph nodes was one."),
              claim("The median number of positive lymph nodes was three.")]
    verdicts = [r.verdict for r in audit_claims(claims, release_dir).claims]
    assert verdicts == [Verdict.SUPPORTED, Verdict.CONTRADICTED, Verdict.SUPPORTED, Verdict.SUPPORTED, Verdict.CONTRADICTED]


@pytest.mark.parametrize("sentence", [
    "None of the male patients had a Basal-like tumour.",
    "No male patient had a Basal-like tumour.",
])
def test_zero_inside_a_group(sentence, release_dir):
    c = claim(sentence)
    assert (c.params.attribute, c.params.category, c.params.within_attribute, c.params.within_category, c.params.stated_value) == (
        "subtype", "Basal-like", "sex", "male", 0)
    [r] = audit_claims([c], release_dir).claims
    assert r.verdict == Verdict.SUPPORTED  # male primary tumours: Luminal B 5, Luminal A 4, no call 3


@pytest.mark.parametrize("sentence, attribute, category, position", [
    ("TTN ranks third among mutated genes.", "mutation", "TTN", 3),
    ("Luminal B comes in second among the RNA subtypes.", "subtype", "Luminal B", 2),
    ("Lobular carcinoma ranks second among histological types.", "histology", "lobular", 2),
])
def test_placement_words_are_ranks(sentence, attribute, category, position):
    c = claim(sentence)
    assert (c.type, c.params.attribute, c.params.category, c.params.stated_value) == (ClaimType.RANK, attribute, category, position)


def test_tumours_without_a_recorded_age(release_dir):
    c = claim("Not a single primary tumour lacks an age at diagnosis.")
    assert (c.type, c.params.subject, c.params.stated_value) == (ClaimType.COUNT, "unknown_age_primary_tumors", 0)
    [r] = audit_claims([c], release_dir).claims
    assert (r.verdict, r.fact.value) == (Verdict.CONTRADICTED, 4)


# --- counts of two different attributes against each other ------------------------------------------------------

@pytest.mark.parametrize("sentence, bound, verdict", [
    ("HER2-positive tumours by immunohistochemistry are fewer than ERBB2-amplified tumours.", "lt", Verdict.CONTRADICTED),
    ("HER2-positive tumours outnumber ERBB2-amplified tumours.", "gt", Verdict.SUPPORTED),
    ("More tumours are HER2-positive by IHC than ERBB2-amplified.", "gt", Verdict.SUPPORTED),
])
def test_two_attributes_counted_against_each_other(sentence, bound, verdict, release_dir):
    c = claim(sentence)
    p = c.params
    assert (c.type, p.attribute, p.category, p.attribute_b, p.category_b, p.bound) == (
        ClaimType.RATIO, "her2_status", "positive", "amplification", "ERBB2", bound)
    [r] = audit_claims([c], release_dir).claims
    assert (r.verdict, r.fact.numerator, r.fact.denominator) == (verdict, 164, 133)

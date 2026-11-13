from pathlib import Path

import pytest

from second_opinion.extract import classify_sentence, extract_claims
from second_opinion.model import ClaimType, SentenceInfo

PRACTICE_BRIEF = Path(__file__).resolve().parents[1] / "docs/challenge/products/research-claim-auditor/practice_brief.md"


def claim(text):  # helper: classify one sentence
    return extract_claims(text).claims[0]


# --- the practice brief ---------------------------------------------------------------------

def test_practice_count():
    c = claim("Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data.")
    assert c.type is ClaimType.COUNT
    assert (c.params.stated_value, c.params.stated_total, c.params.subject) == (535, 1101, "all_five_layers")
    assert c.params.unit == "count"
    assert c.params.approximate is False


def test_practice_share():
    c = claim("Luminal A is the largest RNA subtype, accounting for about 62% of primary tumors with an RNA subtype call.")
    assert c.type is ClaimType.SHARE
    assert (c.params.stated_value, c.params.unit, c.params.approximate, c.params.subtype) == (62, "percent", True, "Luminal A")
    assert c.params.decimals == 0


def test_practice_not_answerable():
    c = claim("Patients whose tumors had the highest ER-alpha protein responded best to hormone therapy, which suggests protein data could guide treatment research.")
    assert c.type is ClaimType.NOT_ANSWERABLE and "responded" in c.clinical_terms and "treatment" in c.needed_data


def test_practice_brief_gives_exactly_three_claims():
    result = extract_claims(PRACTICE_BRIEF.read_text(encoding="utf-8"))
    assert [c.id for c in result.claims] == ["C1", "C2", "C3"]
    assert [c.type for c in result.claims] == [ClaimType.COUNT, ClaimType.SHARE, ClaimType.NOT_ANSWERABLE]


def test_sentence_claim_ids_point_at_claims():
    result = extract_claims(PRACTICE_BRIEF.read_text(encoding="utf-8"))
    linked = {s.claim_id: s.index for s in result.sentences if s.claim_id}
    assert linked == {c.id: c.sentence_index for c in result.claims}
    assert sum(s.claim_id is None for s in result.sentences) == len(result.sentences) - 3


def test_plan_wording_of_the_count():
    c = claim("535 of 1,101 primary tumors have all five data layers.")
    assert c.type is ClaimType.COUNT
    assert (c.params.stated_value, c.params.stated_total, c.params.subject) == (535, 1101, "all_five_layers")


# --- number forms ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, value, high, approx", [
    ("Luminal B makes up nearly 23% of subtyped tumors.", 23, None, True),
    ("Basal-like is between 15 and 18 percent of subtyped primary tumors.", 15, 18, False),
    ("Basal-like is 15–18 % of subtyped primary tumors.", 15, 18, False),
    ("Basal-like is 15-18% of subtyped primary tumors.", 15, 18, False),
    ("Basal-like is 15% to 18% of subtyped primary tumors.", 15, 18, False),
    ("Her2 is 7.9% of subtyped primary tumors.", 7.9, None, False),
    ("Luminal A is 62 % of subtyped primary tumors.", 62, None, False),
    ("Luminal A is ~62% of subtyped primary tumors.", 62, None, True),
    ("Luminal A is roughly 62 percent of subtyped primary tumors.", 62, None, True),
    ("Luminal A is approximately 62% of subtyped primary tumors.", 62, None, True),
])
def test_number_forms(text, value, high, approx):
    c = claim(text)
    assert c.type is ClaimType.SHARE
    assert c.params.unit == "percent"
    assert (c.params.stated_value, c.params.stated_high, c.params.approximate) == (value, high, approx)


def test_decimals_follow_the_text():
    assert claim("Luminal A is 49.9% of subtyped primary tumors.").params.decimals == 1
    assert claim("Luminal A is 49.90% of subtyped primary tumors.").params.decimals == 2


@pytest.mark.parametrize("raw", ["LumA", "Luminal A", "Luminal-A", "luminal a"])
def test_subtype_spelling(raw):
    assert claim(f"{raw} is 49.9% of subtyped primary tumors.").params.subtype == "Luminal A"


@pytest.mark.parametrize("raw, name", [
    ("Basal", "Basal-like"), ("Basal-like", "Basal-like"), ("HER2-enriched", "HER2-enriched"),
    ("Her2", "HER2-enriched"), ("LumB", "Luminal B"), ("Normal-like", "Normal-like"),
])
def test_other_subtype_spellings(raw, name):
    assert claim(f"{raw} tumors are 10% of subtyped primary tumors.").params.subtype == name


def test_share_as_n_of_m():
    c = claim("421 of 844 subtyped primary tumors are Luminal A.")
    assert c.type is ClaimType.SHARE
    assert (c.params.unit, c.params.stated_value, c.params.stated_total) == ("count", 421, 844)


def test_her2_positive_is_not_the_her2_subtype():
    # IHC status, not the PAM50 subtype: a share of HER2 status, never of the HER2-enriched subtype.
    c = claim("HER2-positive tumors make up 15% of primary tumors.")
    assert c.type is ClaimType.SHARE
    assert (c.params.attribute, c.params.category, c.params.subtype) == ("her2_status", "positive", None)


def test_two_subtypes_in_one_sentence_is_not_one_share():
    # "together" makes them one group (Luminal = A + B), never a claim about Luminal A alone
    c = claim("Luminal A and Luminal B together make up 70% of subtyped tumors.")
    assert (c.type, c.params.attribute, c.params.category) == (ClaimType.SHARE, "subtype", "Luminal")
    assert claim("Luminal A and Basal-like tumors make up 70% of subtyped tumors.").type is ClaimType.UNMAPPED


# --- comparison -----------------------------------------------------------------------------

def test_comparison_two_groups():
    c = claim("ER-alpha protein is higher in ER-positive tumors than in ER-negative tumors.")
    assert c.type is ClaimType.COMPARISON
    p = c.params
    assert (p.direction, p.measure, p.group_a, p.group_b) == ("higher", "ER-alpha protein", "ER-positive", "ER-negative")


def test_comparison_lower_and_one_group():
    c = claim("ER-negative tumors have lower ERα levels.")
    assert c.type is ClaimType.COMPARISON
    assert (c.params.direction, c.params.measure, c.params.group_a, c.params.group_b) == ("lower", "ER-alpha protein", "ER-negative", None)


def test_comparison_unknown_measure_is_passed_on():
    c = claim("PTEN protein is lower in ER-negative tumors than in ER-positive tumors.")
    assert c.type is ClaimType.COMPARISON and c.params.measure == "PTEN protein"


def test_more_than_n_is_not_a_comparison():
    c = claim("More than 500 ER-positive tumors have ER-alpha protein data.")
    assert c.type is not ClaimType.COMPARISON


# --- coverage -------------------------------------------------------------------------------

@pytest.mark.parametrize("text, subject", [
    ("Every primary tumor has protein data.", "has_protein"),
    ("All primary tumors have survival data.", "has_survival"),
    ("All 1,101 primary tumors have mutation calls.", "has_mutation"),
    ("Each primary tumor has copy-number data.", "has_copy_number"),
    ("Every primary tumor has RNA-seq data.", "has_rna"),
])
def test_coverage_every(text, subject):
    c = claim(text)
    assert c.type is ClaimType.COVERAGE
    assert (c.params.unit, c.params.subject) == ("all", subject)


def test_coverage_with_a_count():
    c = claim("1,080 of the 1,101 primary tumors have survival data.")
    assert c.type is ClaimType.COVERAGE
    assert (c.params.unit, c.params.subject, c.params.stated_value, c.params.stated_total) == ("count", "has_survival", 1080, 1101)


def test_coverage_with_a_percent():
    c = claim("About 80% of primary tumors have protein data.")
    assert c.type is ClaimType.COVERAGE
    assert (c.params.unit, c.params.subject, c.params.stated_value, c.params.approximate) == ("percent", "has_protein", 80, True)


def test_rna_subtype_is_not_an_rna_layer():
    c = claim("All primary tumors with an RNA subtype call have protein data.")
    assert c.params.subject == "has_protein"


# --- count ----------------------------------------------------------------------------------

@pytest.mark.parametrize("text, value, subject", [
    ("The release has 1,101 primary tumors.", 1101, "primary_tumors"),
    ("The release contains 1,247 samples.", 1247, "samples"),
    ("There are 1,098 patients.", 1098, "patients"),
    ("12 samples are from male patients.", 12, "male_samples"),
    ("Twelve samples are male.", 12, "male_samples"),
    ("The release includes 139 normal tissue samples.", 139, "normal_tissue_samples"),
    ("Seven samples are metastatic.", 7, "metastatic_samples"),
    ("There are 1,085 female primary tumors.", 1085, "female_primary_tumors"),
])
def test_count_subjects(text, value, subject):
    c = claim(text)
    assert c.type is ClaimType.COUNT
    assert (c.params.stated_value, c.params.subject) == (value, subject)


def test_approximate_count():
    c = claim("Roughly 1,100 primary tumors are in the release.")
    assert (c.type, c.params.stated_value, c.params.approximate) == (ClaimType.COUNT, 1100, True)


def test_count_range():
    c = claim("The release has between 1,000 and 1,200 primary tumors.")
    assert (c.type, c.params.stated_value, c.params.stated_high) == (ClaimType.COUNT, 1000, 1200)


def test_bound_count_is_not_checked_as_exact():
    # "more than 500" is a one-sided bound; checking it as "exactly 500" would be wrong.
    c = claim("More than 500 primary tumors have all five data layers.")
    assert c.type is ClaimType.COUNT
    assert (c.params.stated_value, c.params.bound) == (500.0, "gt")


def test_some_layers_is_a_layer_overlap_count():
    c = claim("Of the 1,101 primary tumors, 800 have mutation and protein data.")
    assert (c.type, c.params.subject, c.params.stated_value) == (ClaimType.COUNT, "layers:mutation+protein", 800.0)
    assert claim("Some 355 tumours have RNA but no protein data.").type is ClaimType.UNMAPPED


# --- what is not a claim, and what is kept as unmapped --------------------------------------

def test_sentence_with_no_claim_is_skipped():
    assert extract_claims("Protein measurements add a useful layer.").claims == []


def test_median_age_is_a_statistic():
    c = claim("The median age was 58 years.")
    assert c.type is ClaimType.STATISTIC
    assert (c.params.measure, c.params.stated_value) == ("median", 58.0)


def test_unknown_number_sentence_is_kept_as_unmapped():
    assert claim("The cohort was assembled over 11 sites.").type is ClaimType.UNMAPPED


@pytest.mark.parametrize("text", [
    "The PAM50 classifier assigns subtypes.",
    "TP53 is often mutated.",
    "See Figure 2 for details.",
    "The 2012 study labels differ from the RNA calls.",
    "Data come from TCGA-BRCA.",
])
def test_numbers_that_are_not_data(text):
    assert extract_claims(text).claims == []


def test_empty_report():
    result = extract_claims("   ")
    assert (result.sentences, result.claims) == ([], [])


def test_claim_ids_count_claims_only():
    result = extract_claims("An intro sentence. The release has 1,101 primary tumors. Nothing here. Every primary tumor has protein data.")
    assert [c.id for c in result.claims] == ["C1", "C2"]
    assert [c.sentence_index for c in result.claims] == [1, 3]


def test_classify_sentence_returns_none_for_plain_text():
    assert classify_sentence(SentenceInfo(0, "A plain sentence.", None), "C1") is None

# --- end to end with the audit pipeline (tiny generated release, no real data) ---------------

def test_practice_brief_claims_run_through_the_audit(mini_release):
    from second_opinion.audit import audit_claims
    from second_opinion.model import Verdict

    claims = extract_claims(PRACTICE_BRIEF.read_text(encoding="utf-8")).claims
    result = audit_claims(claims, mini_release)
    assert [r.claim.id for r in result.claims] == ["C1", "C2", "C3"]
    assert result.claims[2].verdict is Verdict.INSUFFICIENT_EVIDENCE
    assert "treatment" in result.claims[2].missing_evidence


def test_filtered_counts_are_not_judged_against_everyone(mini_release):
    from second_opinion.audit import audit_claims
    from second_opinion.model import Verdict

    claims = extract_claims("Two samples are male.").claims
    result = audit_claims(claims, mini_release)
    assert result.claims[0].verdict is not Verdict.CONTRADICTED


def test_claims_carry_the_sentence_as_written_and_repeats_give_one_claim():
    report = "**Luminal A** is the largest subtype, at about 62%.\n\nLuminal A is the largest subtype, at about 62%."
    result = extract_claims(report)
    assert [c.original_text for c in result.claims] == ["**Luminal A** is the largest subtype, at about 62%."]


def test_an_age_is_not_a_count_of_the_noun_before_it():
    assert claim("HER2-enriched tumors are more aggressive, and the median age at diagnosis was 58 years.").type is ClaimType.UNMAPPED


def test_male_and_female_counts_in_one_sentence_are_two_parts():
    c = claim("There are 1,085 female patients and 12 male patients.")
    assert [(p.params.subject, p.params.stated_value) for p in c.parts] == [
        ("female_patients", 1085.0), ("male_patients", 12.0)]


def test_a_sentence_about_named_genes_is_not_a_layer_coverage_claim():
    c = claim("Roughly 80 percent of patients with a mutation call have a TP53 or PIK3CA mutation.")
    assert c.type is ClaimType.UNMAPPED


def test_layer_coverage_without_a_gene_is_still_coverage():
    assert claim("About 72% of primary tumors have a mutation call.").type is ClaimType.COVERAGE

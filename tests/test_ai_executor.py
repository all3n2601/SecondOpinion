"""The AI layer's deterministic core: validate a query plan, run it on the release, judge the claim.

Expected numbers are computed here with plain pandas on the files, never by calling the executor.
"""

import dataclasses

import pandas as pd
import pytest
from pydantic import ValidationError

from second_opinion.ai.executor import PlanRejected, execute_plan, judge_plan, run_plan, validate_plan
from second_opinion.ai.plan import QueryPlan
from second_opinion.model import Fact, Verdict
from second_opinion.release import Release, load_release
from tests.helpers import MINI

AGE = "age_at_initial_pathologic_diagnosis"
ER = "breast_carcinoma_estrogen_receptor_status"
HER2 = "lab_proc_her2_neu_immunohistochemistry_receptor_status"
SENTENCE = "About 16.7% of subtyped primary tumors are Basal-like."


# ---------------------------------------------------------------- helpers


def qp(plan, stated=None, **kw):
    body = {"answerable": True, "plan": plan, "stated": stated, "rationale": "test"}
    body.update(kw)
    return QueryPlan.model_validate(body)


def f(field, value=None, op="eq"):
    d = {"field": field, "op": op}
    if value is not None or op != "is_known":
        d["value"] = value
    return d


def count_plan(where=(), of="samples"):
    return {"op": "count", "of": of, "where": list(where)}


def share_plan(numerator, where=()):
    return {"op": "share", "where": list(where), "numerator": list(numerator)}


NUM = {"kind": "count", "span": "10", "value": 10}


def stated_for(span, kind="count", **kw):
    return {"kind": kind, "span": span, **kw}


def run_code(fact: Fact, release: Release) -> dict:
    """Execute the pasteable snippet the way a reviewer would."""
    ns = {"r": release, "pd": pd}
    exec(fact.code, ns)  # noqa: S102 - the code under test, run in a scratch namespace
    return ns


@pytest.fixture
def mini(mini_release):
    return load_release(mini_release)


@pytest.fixture
def clin(mini_release):
    return pd.read_csv(mini_release / "clinical.tsv", sep="\t")


@pytest.fixture
def mini_age(mini):
    """The mini release with an age and a HER2 status column added (the mini files have neither)."""
    c = mini.clinical.copy()
    c[AGE] = [30, 40, 50, 60, 70, 80, None, 45, 55, 65, 35, 36, 90]
    c[HER2] = ["Positive", "Negative", "Negative", "Equivocal", None, "Positive", "Negative", None, "Negative",
               "Positive", "Negative", "Negative", "Positive"]
    return dataclasses.replace(mini, clinical=c)


def primary(df):
    return df[df.sampleID.str[13:15] == "01"]


# ---------------------------------------------------------------- the schema stops unknown operations


def test_unknown_op_is_rejected_by_pydantic_before_it_reaches_the_executor():
    with pytest.raises(ValidationError):
        qp({"op": "exec", "code": "__import__('os')"}, NUM)
    with pytest.raises(ValidationError):
        qp({"op": "count", "where": [{"field": "password", "op": "eq", "value": "x"}]}, NUM)


# ---------------------------------------------------------------- validate_plan: filters


def test_not_answerable_is_rejected(mini):
    q = QueryPlan(answerable=False, needed_data="treatment records")
    with pytest.raises(PlanRejected, match="not answerable"):
        validate_plan(q, "Patients on tamoxifen did better.", mini)


def test_answerable_without_plan_or_stated_is_rejected(mini):
    with pytest.raises(PlanRejected):
        validate_plan(qp(None, NUM), "There are 10 primary tumors.", mini)
    with pytest.raises(PlanRejected):
        validate_plan(qp(count_plan(), None), "There are 10 primary tumors.", mini)


@pytest.mark.parametrize(
    "flt",
    [
        f("sample_type", "tumor"),
        f("sample_type", ["primary", "other"], op="in"),
        f("sex", "other"),
        f("sex", 1.0),
        f("subtype_rna", "Luminal C"),
        f("subtype_2012", "Basal-like or 1==1"),
        f("er_status", "maybe"),
        f("her2_status", "equivocal"),
        f("has_layer", "methylation"),
        f("age_years", "58", op="gt"),
        f("age_years", 58.0, op="in"),
        f("age_years", float("nan"), op="gt"),
        f("sex", "female", op="gt"),
        f("sample_type", "primary", op="lte"),
        f("sex", op="eq"),
        f("sex", "female", op="is_known"),
        f("sex", "female", op="in"),
        f("sex", ["female"], op="eq"),
        f("sex", [], op="in"),
        f("has_layer", op="is_known"),
    ],
)
def test_illegal_filters_are_rejected(mini_age, flt):
    with pytest.raises(PlanRejected):
        validate_plan(qp(count_plan([flt]), NUM), "There are 10 samples.", mini_age)


@pytest.mark.parametrize(
    "field", ["sample_type", "sex", "subtype_rna", "subtype_2012", "er_status", "her2_status", "has_layer"]
)
def test_injection_in_a_filter_value_is_inert(mini_age, field):
    evil = 'x" or 1==1'
    for flt in (f(field, evil), f(field, [evil, "primary"], op="in")):
        with pytest.raises(PlanRejected):
            validate_plan(qp(count_plan([flt]), NUM), "There are 10 samples.", mini_age)
        with pytest.raises(PlanRejected):
            execute_plan(qp(count_plan([flt]), NUM), mini_age)


def test_injection_in_measure_and_group_is_inert(mini):
    for measure, a in (("ERALPHA'] or True or ['", "positive"), ("ERALPHA", '__import__("os")')):
        plan = {"op": "compare_means", "measure": measure, "group_field": "er_status", "group_a": a, "group_b": "negative"}
        with pytest.raises(PlanRejected):
            validate_plan(qp(plan, stated_for("higher", "direction", relation="more")), "ER is higher in higher.", mini)


def test_legal_values_are_accepted_case_insensitively(mini_age):
    plan = count_plan([f("sample_type", "Primary"), f("sex", "FEMALE"), f("subtype_rna", "LumA"),
                       f("er_status", "Positive"), f("has_layer", "Protein"), f("age_years", 20, op="gte")])
    validate_plan(qp(plan, NUM), "There are 10 samples.", mini_age)


def test_missing_column_is_named(mini):
    with pytest.raises(PlanRejected, match=AGE):
        validate_plan(qp(count_plan([f("age_years", 50, op="gt")]), NUM), "There are 10 samples.", mini)
    with pytest.raises(PlanRejected, match="lab_proc_her2_neu"):
        validate_plan(qp(count_plan([f("her2_status", "positive")]), NUM), "There are 10 samples.", mini)
    with pytest.raises(PlanRejected, match="PAM50Call_RNAseq"):
        no_col = dataclasses.replace(mini, clinical=mini.clinical.drop(columns=["PAM50Call_RNAseq"]))
        validate_plan(qp(count_plan([f("subtype_rna", "Basal-like")]), NUM), "There are 10 samples.", no_col)


def test_has_layer_rna_without_an_rna_file_is_rejected(mini):
    assert mini.rna_ids is None
    with pytest.raises(PlanRejected, match="no RNA file in this release"):
        validate_plan(qp(count_plan([f("has_layer", "rna")]), NUM), "There are 10 samples.", mini)


def test_has_layer_rna_is_allowed_when_the_release_has_one(mini):
    with_rna = dataclasses.replace(mini, rna_ids={"TCGA-AA-0001-01", "TCGA-AA-0002-01"})
    q = qp(count_plan([f("has_layer", "rna")]), stated_for("2", value=2))
    fact, verdict, _ = run_plan("There are 2 samples with RNA.", q, with_rna)
    assert (fact.numerator, verdict) == (2, Verdict.SUPPORTED)
    assert "rna_hiseq.tsv.gz" in fact.files


def test_share_needs_a_numerator(mini):
    with pytest.raises(PlanRejected):
        validate_plan(qp(share_plan([]), stated_for("50%", "percent", value=50)), "50% are x.", mini)


# ---------------------------------------------------------------- validate_plan: compare / rank / order


def compare(measure="ERALPHA", field="er_status", a="positive", b="negative"):
    return {"op": "compare_means", "measure": measure, "group_field": field, "group_a": a, "group_b": b}


HIGHER = stated_for("higher", "direction", relation="more")
SENT_ER = "ER-alpha is higher in ER-positive tumors."


def test_compare_measure_must_exist_in_the_protein_file(mini):
    with pytest.raises(PlanRejected, match="BRCA1"):
        validate_plan(qp(compare(measure="BRCA1"), HIGHER), SENT_ER, mini)


def test_compare_measure_matches_case_insensitively_with_the_files_spelling(mini):
    q = qp(compare(measure="eralpha"), stated_for("higher", "direction", relation="more"))
    validate_plan(q, SENT_ER, mini)
    assert "ERALPHA" in execute_plan(q, mini).code


@pytest.mark.parametrize(
    "field, a, b",
    [("er_status", "female", "male"), ("sex", "positive", "negative"), ("er_status", "positive", "positive"),
     ("her2_status", "high", "low")],
)
def test_compare_groups_must_fit_the_group_field(mini_age, field, a, b):
    with pytest.raises(PlanRejected):
        validate_plan(qp(compare(field=field, a=a, b=b), HIGHER), SENT_ER, mini_age)


def test_rank_and_order_categories_must_be_subtypes(mini):
    bad_rank = {"op": "rank", "category_field": "subtype_rna", "category": "Luminal C"}
    with pytest.raises(PlanRejected):
        validate_plan(qp(bad_rank, stated_for("2nd", "rank", value=2)), "Luminal C is 2nd.", mini)
    bad_order = {"op": "order", "category_field": "subtype_rna", "category_a": "Basal-like", "category_b": "Basal-like"}
    with pytest.raises(PlanRejected):
        validate_plan(qp(bad_order, stated_for("more", "relation", relation="more")), "Basal-like is more.", mini)


def test_stated_kind_must_fit_the_plan_op(mini):
    rank = {"op": "rank", "category_field": "subtype_rna", "category": "Luminal B"}
    sent = "Luminal B is 2% of tumors."
    q = qp(rank, stated_for("2%", "percent", value=2))
    with pytest.raises(PlanRejected):
        validate_plan(q, sent, mini)
    with pytest.raises(PlanRejected):
        judge_plan(sent, q, Fact("x", 2, None, None, [], [], ""))
    with pytest.raises(PlanRejected):  # a direction needs its relation
        validate_plan(qp(compare(), stated_for("higher", "direction")), SENT_ER, mini)


# ---------------------------------------------------------------- validate_plan: the stated claim is quoted honestly


def pct_plan():
    return share_plan([f("subtype_rna", "Basal-like")], where=[f("sample_type", "primary")])


def test_span_must_appear_in_the_sentence(mini):
    q = qp(pct_plan(), stated_for("about 20%", "percent", value=20, approximate=True))
    with pytest.raises(PlanRejected, match="span"):
        validate_plan(q, SENTENCE, mini)


def test_span_matches_ignoring_case_and_whitespace(mini):
    q = qp(pct_plan(), stated_for("about   16.7%", "percent", value=16.7))
    validate_plan(q, "Overall,  ABOUT 16.7%\nof subtyped primary tumors are Basal-like.", mini)


def test_empty_span_is_rejected(mini):
    with pytest.raises(PlanRejected):
        validate_plan(qp(pct_plan(), stated_for("", "percent", value=16.7)), SENTENCE, mini)


@pytest.mark.parametrize(
    "sentence, span, kind, extra",
    [
        ("Basal-like tumors are 16.7% of the total.", "16.7%", "percent", {"value": 16.7}),
        ("Basal-like tumors are 62% of the total.", "62%", "percent", {"value": 62}),
        ("There are 1,101 primary tumors in all.", "1,101", "count", {"value": 1101}),
        ("There are 1101 primary tumors in all.", "1101", "count", {"value": 1101}),
        ("535 of 1,101 tumors have all layers.", "535 of 1,101", "count", {"value": 535, "total": 1101}),
        ("Basal-like tumors are 55-65% of the total.", "55-65%", "percent", {"value": 55, "high": 65}),
        ("Basal-like tumors are one in six of the total.", "one in six", "percent", {"value": 16.7}),
        ("Basal-like tumors are 1 in 6 of the total.", "1 in 6", "percent", {"value": 16.7}),
        ("Basal-like tumors are half of the total.", "half", "percent", {"value": 50}),
        ("Basal-like tumors are a third of the total.", "a third", "percent", {"value": 33.3}),
        ("Basal-like tumors are two thirds of the total.", "two thirds", "percent", {"value": 66.7}),
        ("Basal-like tumors are a quarter of the total.", "a quarter", "percent", {"value": 25}),
        ("Basal-like tumors are three quarters of the total.", "three quarters", "percent", {"value": 75}),
        ("There are twelve primary tumors in all.", "twelve", "count", {"value": 12}),
        ("There are three primary tumors in all.", "three", "count", {"value": 3}),
        ("Luminal B is the second most common subtype.", "second most common", "rank", {"value": 2}),
        ("Luminal B is the most common subtype.", "most common", "rank", {"value": 1}),
        ("Men contribute barely a dozen of the primary tumours.", "barely a dozen", "count", {"value": 12}),
        ("GATA3 is mutated in ninety-seven tumours.", "ninety-seven", "count", {"value": 97}),
        ("A hundred and thirty-nine samples are normal tissue.", "A hundred and thirty-nine", "count", {"value": 139}),
        ("Nearly eleven hundred primary tumours are in the release.", "eleven hundred", "count", {"value": 1100}),
        ("Under one in fifteen tumours are HER2-enriched.", "one in fifteen", "percent", {"value": 6.67}),
        ("Nine in every hundred tumours are HER2-enriched.", "Nine in every hundred", "percent", {"value": 9}),
        ("ERBB2 is amplified in one tumour in eight.", "one tumour in eight", "percent", {"value": 12.5}),
    ],
)
def test_numbers_derivable_from_the_sentence_are_accepted(mini, sentence, span, kind, extra):
    plan = {"count": share_plan([f("sex", "male")]), "percent": pct_plan(),
            "rank": {"op": "rank", "category_field": "subtype_rna", "category": "Luminal B"}}[kind]
    validate_plan(qp(plan, stated_for(span, kind, **extra)), sentence, mini)


@pytest.mark.parametrize(
    "sentence, span, kind, extra",
    [
        ("Roughly 20% of the tumors are Basal-like.", "Roughly 20%", "percent", {"value": 16.7}),
        ("Basal-like tumors are one in six of the total.", "one in six", "percent", {"value": 20}),
        ("Basal-like tumors are one in six of the total.", "one in six", "percent", {"value": 17}),
        ("Basal-like tumors are half of the total.", "half", "percent", {"value": 55}),
        ("There are 1,101 primary tumors in all.", "1,101", "count", {"value": 1011}),
        ("535 of 1,101 tumors have all layers.", "535 of 1,101", "count", {"value": 535, "total": 1100}),
        ("Basal-like tumors are 55-65% of the total.", "55-65%", "percent", {"value": 55, "high": 70}),
        ("Luminal B is the second most common subtype.", "second most common", "rank", {"value": 3}),
        ("Basal-like tumors are many of the total.", "many", "percent", {"value": 3}),
        ("GATA3 is mutated in ninety-seven tumours.", "ninety-seven", "count", {"value": 7}),
        ("GATA3 is mutated in ninety-seven tumours.", "ninety-seven", "count", {"value": 90}),
        ("Deep PTEN deletions appear in five dozen tumours.", "five dozen", "count", {"value": 5}),
    ],
)
def test_invented_numbers_are_rejected(mini, sentence, span, kind, extra):
    plan = {"count": share_plan([f("sex", "male")]), "percent": pct_plan(),
            "rank": {"op": "rank", "category_field": "subtype_rna", "category": "Luminal B"}}[kind]
    with pytest.raises(PlanRejected, match="not in the sentence"):
        validate_plan(qp(plan, stated_for(span, kind, **extra)), sentence, mini)


def test_digits_inside_names_are_not_numbers(mini):
    # "HER2" and "PAM50" contain digits that the report never states as a number
    q = qp(pct_plan(), stated_for("HER2", "percent", value=2))
    with pytest.raises(PlanRejected, match="not in the sentence"):
        validate_plan(q, "HER2 and PAM50 tumors are common.", mini)


# ---------------------------------------------------------------- execute: count


def count_of(plan, mini_dir_or_release, stated_value=1):
    return execute_plan(qp(plan, stated_for("1", value=stated_value)), mini_dir_or_release)


def test_count_each_sample_type_and_sex(mini, clin):
    assert count_of(count_plan(), mini).value == len(clin)
    assert count_of(count_plan([f("sample_type", "primary")]), mini).value == MINI["primary"] == len(primary(clin))
    assert count_of(count_plan([f("sample_type", "normal_tissue")]), mini).value == MINI["normal"]
    assert count_of(count_plan([f("sample_type", "metastatic")]), mini).value == MINI["metastasis"]
    assert count_of(count_plan([f("sample_type", ["primary", "metastatic"], op="in")]), mini).value == 11
    assert count_of(count_plan([f("sex", "male")]), mini).value == (clin.gender == "MALE").sum() == 2
    assert count_of(count_plan([f("sex", "female")]), mini).value == (clin.gender == "FEMALE").sum()
    assert count_of(count_plan([f("sex", op="is_known")]), mini).value == clin.gender.notna().sum()


def test_count_fact_shape_and_reproducing_code(mini):
    fact = count_of(count_plan([f("sample_type", "primary")]), mini)
    assert (fact.value, fact.numerator, fact.denominator) == (10, 10, None)
    assert fact.files == ["clinical.tsv"] and len(fact.sample_ids) == 10
    assert fact.label and "primary" in fact.label
    assert run_code(fact, mini)["n"] == 10


def test_count_each_status_subtype_and_layer_filter(mini, clin):
    assert count_of(count_plan([f("subtype_rna", "Luminal A")]), mini).value == (clin.PAM50Call_RNAseq == "LumA").sum()
    assert count_of(count_plan([f("subtype_rna", "LumA"), f("sample_type", "primary")]), mini).value == MINI["luma_rna_primary"]
    assert count_of(count_plan([f("subtype_2012", "Luminal A"), f("sample_type", "primary")]), mini).value == MINI["luma_2012_primary"]
    assert count_of(count_plan([f("subtype_rna", ["Luminal A", "Basal-like"], op="in")]), mini).value == (
        clin.PAM50Call_RNAseq.isin(["LumA", "Basal"]).sum())
    assert count_of(count_plan([f("er_status", "positive")]), mini).value == (clin[ER] == "Positive").sum()
    assert count_of(count_plan([f("er_status", "negative")]), mini).value == (clin[ER] == "Negative").sum()
    assert count_of(count_plan([f("er_status", op="is_known")]), mini).value == clin[ER].isin(["Positive", "Negative"]).sum()
    for layer, ids in (("survival", mini.survival_ids), ("mutation", mini.mutation_ids),
                       ("copy_number", mini.copy_number_ids), ("protein", mini.protein_ids)):
        fact = count_of(count_plan([f("has_layer", layer)]), mini)
        assert fact.value == clin.sampleID.isin(ids).sum()
    layered = count_of(count_plan([f("sample_type", "primary"), f("has_layer", "survival"), f("has_layer", "mutation"),
                                   f("has_layer", "copy_number"), f("has_layer", "protein")]), mini)
    assert layered.value == MINI["all_layers_primary"]
    assert layered.files == ["clinical.tsv", "survival.tsv", "mutation_gene_level.tsv.gz",
                             "copy_number_gistic.tsv.gz", "protein_rppa.tsv.gz"]


def test_count_age_and_her2_filters(mini_age):
    c = mini_age.clinical
    assert count_of(count_plan([f("age_years", 60, op="gt")]), mini_age).value == (c[AGE] > 60).sum()
    assert count_of(count_plan([f("age_years", 60, op="gte")]), mini_age).value == (c[AGE] >= 60).sum()
    assert count_of(count_plan([f("age_years", 40, op="lt")]), mini_age).value == (c[AGE] < 40).sum()
    assert count_of(count_plan([f("age_years", 40, op="lte")]), mini_age).value == (c[AGE] <= 40).sum()
    assert count_of(count_plan([f("age_years", 45, op="eq")]), mini_age).value == (c[AGE] == 45).sum()
    assert count_of(count_plan([f("age_years", op="is_known")]), mini_age).value == c[AGE].notna().sum()
    assert count_of(count_plan([f("her2_status", "positive")]), mini_age).value == (c[HER2] == "Positive").sum()


def test_combined_filters_are_anded(mini_age, clin):
    plan = count_plan([f("sample_type", "primary"), f("sex", "female"), f("er_status", "positive"),
                       f("age_years", 45, op="gte"), f("subtype_rna", "Luminal A")])
    fact = count_of(plan, mini_age)
    c = mini_age.clinical
    expect = c[(c.sampleID.str[13:15] == "01") & (c.gender == "FEMALE") & (c[ER] == "Positive")
               & (c[AGE] >= 45) & (c.PAM50Call_RNAseq == "LumA")]
    assert fact.value == len(expect) and sorted(fact.sample_ids) == sorted(expect.sampleID)
    assert run_code(fact, mini_age)["n"] == len(expect)


def test_count_patients_counts_distinct_people(mini):
    fact = count_of(count_plan([f("has_layer", "survival")], of="patients"), mini)
    ids = [s for s in mini.clinical.sampleID if s in mini.survival_ids]
    assert fact.value == len({s[:12] for s in ids})
    assert run_code(fact, mini)["n"] == fact.value


def test_sex_filter_reports_samples_left_out_for_unknown_sex(mini, clin):
    fact = count_of(count_plan([f("sample_type", "primary"), f("sex", "female")]), mini)
    assert fact.extra["excluded_unknown_sex"] == primary(clin).gender.isna().sum() == MINI["unknown_sex_primary"]


# ---------------------------------------------------------------- execute: share


def test_share_of_subtype_among_called_primary_tumors(mini, clin):
    q = qp(share_plan([f("subtype_rna", "Luminal A")], where=[f("sample_type", "primary")]), stated_for("40%", "percent", value=40))
    fact = execute_plan(q, mini)
    p = primary(clin)
    called = p[p.PAM50Call_RNAseq.notna()]
    n = (called.PAM50Call_RNAseq == "LumA").sum()
    assert (fact.numerator, fact.denominator) == (n, len(called)) == (3, MINI["rna_subtyped_primary"])
    assert fact.value == pytest.approx(100 * n / len(called))
    assert fact.unknown_count == len(p) - len(called)
    assert len(fact.sample_ids) == n and set(fact.sample_ids) <= set(p.sampleID)
    ns = run_code(fact, mini)
    assert (ns["n"], ns["total"]) == (n, len(called)) and ns["percent"] == pytest.approx(fact.value)
    assert ns["n_unrecorded"] == fact.unknown_count


def test_share_of_women_uses_those_with_a_recorded_sex(mini, clin):
    q = qp(share_plan([f("sex", "female")]), stated_for("80%", "percent", value=80))
    fact = execute_plan(q, mini)
    known = clin[clin.gender.notna()]
    assert (fact.numerator, fact.denominator) == ((known.gender == "FEMALE").sum(), len(known))
    assert fact.unknown_count == clin.gender.isna().sum() == 1


def test_share_with_is_known_numerator_does_not_filter_the_denominator(mini, clin):
    q = qp(share_plan([f("er_status", op="is_known")]), stated_for("90%", "percent", value=90))
    fact = execute_plan(q, mini)
    assert fact.denominator == len(clin) and fact.numerator == clin[ER].isin(["Positive", "Negative"]).sum()


def test_share_numerator_combines_filters(mini, clin):
    q = qp(share_plan([f("er_status", "positive"), f("subtype_rna", "Luminal A")], where=[f("sample_type", "primary")]),
           stated_for("40%", "percent", value=40))
    fact = execute_plan(q, mini)
    p = primary(clin)
    called = p[p[ER].isin(["Positive", "Negative"]) & p.PAM50Call_RNAseq.notna()]
    hit = called[(called[ER] == "Positive") & (called.PAM50Call_RNAseq == "LumA")]
    assert (fact.numerator, fact.denominator) == (len(hit), len(called))
    assert fact.unknown_count == len(p) - len(called)
    assert run_code(fact, mini)["n"] == len(hit)


def test_share_with_no_rows_is_rejected(mini):
    q = qp(share_plan([f("sex", "male")], where=[f("sample_type", "normal_tissue"), f("sex", "male")]),
           stated_for("5%", "percent", value=5))
    with pytest.raises(PlanRejected, match="no rows"):
        execute_plan(q, mini)


# ---------------------------------------------------------------- execute: compare_means


def test_compare_means_matches_pandas_on_primary_tumors_by_default(mini, clin):
    fact = execute_plan(qp(compare(), HIGHER), mini)
    p = primary(clin).set_index("sampleID")[ER]
    pos = [s for s in mini.protein.columns if s in p.index and p[s] == "Positive"]
    neg = [s for s in mini.protein.columns if s in p.index and p[s] == "Negative"]
    ma, mb = mini.protein.loc["ERALPHA", pos].mean(), mini.protein.loc["ERALPHA", neg].mean()
    assert fact.value == pytest.approx(ma - mb)
    assert (fact.extra["n_a"], fact.extra["n_b"]) == (len(pos), len(neg))
    assert fact.extra["mean_a"] == round(ma, 3) and fact.extra["mean_b"] == round(mb, 3)
    assert sorted(fact.sample_ids) == sorted(pos + neg)
    assert fact.files == ["clinical.tsv", "protein_rppa.tsv.gz"]
    assert run_code(fact, mini)["difference"] == pytest.approx(ma - mb)


def test_compare_means_where_can_widen_the_population(mini, clin):
    wide = execute_plan(qp({**compare(), "where": [f("sample_type", ["primary", "normal_tissue"], op="in")]}, HIGHER), mini)
    default = execute_plan(qp(compare(), HIGHER), mini)
    s = clin.set_index("sampleID")[ER]
    inc = [x for x in mini.protein.columns if x in s.index and x[13:15] in ("01", "11") and s[x] in ("Positive", "Negative")]
    assert len(wide.sample_ids) == len(inc) >= len(default.sample_ids)


def test_compare_means_by_sex(mini, clin):
    fact = execute_plan(qp(compare(field="sex", a="female", b="male"), HIGHER), mini)
    g = primary(clin).set_index("sampleID").gender
    fem = [s for s in mini.protein.columns if s in g.index and g[s] == "FEMALE"]
    mal = [s for s in mini.protein.columns if s in g.index and g[s] == "MALE"]
    assert fact.value == pytest.approx(mini.protein.loc["ERALPHA", fem].mean() - mini.protein.loc["ERALPHA", mal].mean())


def test_compare_means_with_an_empty_group_is_rejected(mini):
    q = qp({**compare(), "where": [f("sample_type", "normal_tissue")]}, HIGHER)  # no normal sample has protein data
    with pytest.raises(PlanRejected, match="no .* samples"):
        execute_plan(q, mini)


# ---------------------------------------------------------------- execute: summary_stat, rank, order


@pytest.mark.parametrize("stat", ["median", "mean", "min", "max"])
def test_summary_stat_age(mini_age, stat):
    q = qp({"op": "summary_stat", "field": "age_years", "stat": stat, "where": [f("sample_type", "primary")]},
           stated_for("58", "number", value=58))
    fact = execute_plan(q, mini_age)
    c = primary(mini_age.clinical)
    ages = c[AGE].dropna()
    assert fact.value == pytest.approx(getattr(ages, stat)())
    assert (fact.numerator, fact.denominator, fact.unknown_count) == (len(ages), len(c), len(c) - len(ages))
    assert fact.unknown_count == 1 and sorted(fact.sample_ids) == sorted(c[c[AGE].notna()].sampleID)
    assert run_code(fact, mini_age)["result"] == pytest.approx(fact.value)


def test_rank_among_called_primary_tumors(mini, clin):
    p = primary(clin)
    counts = p.PAM50Call_RNAseq.value_counts()
    for name, raw in (("Luminal A", "LumA"), ("Luminal B", "LumB"), ("Basal-like", "Basal")):
        q = qp({"op": "rank", "category_field": "subtype_rna", "category": name, "where": [f("sample_type", "primary")]},
               stated_for("1", "rank", value=1))
        fact = execute_plan(q, mini)
        assert fact.value == 1 + (counts > counts[raw]).sum()
        assert fact.extra[f"count_{name}"] == counts[raw]
        assert fact.extra[f"share_{name}"] == pytest.approx(100 * counts[raw] / counts.sum(), abs=0.05)
        assert fact.unknown_count == len(p) - counts.sum()
        assert run_code(fact, mini)["rank"] == fact.value
    assert execute_plan(q, mini).extra["count_HER2-enriched"] == 1


def test_order_is_count_a_minus_count_b(mini, clin):
    q = qp({"op": "order", "category_field": "subtype_2012", "category_a": "Luminal A", "category_b": "Basal-like",
            "where": [f("sample_type", "primary")]}, stated_for("more", "relation", relation="more"))
    fact = execute_plan(q, mini)
    p = primary(clin)
    a, b = (p.PAM50_mRNA_nature2012 == "Luminal A").sum(), (p.PAM50_mRNA_nature2012 == "Basal-like").sum()
    assert fact.value == a - b
    assert (fact.extra["count_a"], fact.extra["count_b"]) == (a, b)
    assert run_code(fact, mini)["difference"] == a - b


# ---------------------------------------------------------------- judge_plan


def fact_pct(n, d):
    return Fact("x", 100 * n / d, n, d, [], ["clinical.tsv"], "")


def share_q(span, kind="percent", **kw):
    return qp(pct_plan(), stated_for(span, kind, **kw))


def test_judge_percent_rounds_to_the_spans_precision():
    fact = fact_pct(141, 844)  # 16.706...
    assert judge_plan(SENTENCE, share_q("16.7%", value=16.7), fact) == (Verdict.SUPPORTED, None)
    assert judge_plan(SENTENCE, share_q("17%", value=17), fact) == (Verdict.SUPPORTED, None)
    assert judge_plan(SENTENCE, share_q("16.8%", value=16.8), fact) == (Verdict.CONTRADICTED, "16.7% (141 of 844)")


def test_judge_approximate_percent_and_the_honesty_of_the_flag():
    fact = fact_pct(141, 844)
    near = "Roughly 18% of subtyped primary tumors are Basal-like."
    assert judge_plan(near, share_q("Roughly 18%", value=18, approximate=True), fact)[0] == Verdict.SUPPORTED
    far = "Roughly 25% of subtyped primary tumors are Basal-like."
    assert judge_plan(far, share_q("Roughly 25%", value=25, approximate=True), fact)[0] == Verdict.CONTRADICTED
    # the model cannot widen the tolerance: the sentence says 18% flatly
    flat = "18% of subtyped primary tumors are Basal-like."
    assert judge_plan(flat, share_q("18%", value=18, approximate=True), fact)[0] == Verdict.CONTRADICTED


def test_judge_percent_range_and_fraction_words():
    fact = fact_pct(141, 844)
    rng = "Between 15 and 18% of subtyped primary tumors are Basal-like."
    assert judge_plan(rng, share_q("15 and 18%", value=15, high=18), fact)[0] == Verdict.SUPPORTED
    assert judge_plan("Between 10 and 12% of subtyped primary tumors are Basal-like.",
                      share_q("10 and 12%", value=10, high=12), fact)[0] == Verdict.CONTRADICTED
    sixth = "One in six of the subtyped primary tumors are Basal-like."
    assert judge_plan(sixth, share_q("One in six", value=16.7), fact)[0] == Verdict.SUPPORTED
    assert judge_plan(sixth, share_q("One in six", value=16.7), fact_pct(210, 844))[0] == Verdict.CONTRADICTED


def test_judge_percent_bound_comes_from_the_sentences_words():
    fact = fact_pct(76, 1097)  # 6.93%, just over one in fifteen (6.67%)
    under = "Under one in fifteen primary tumours come from patients diagnosed before forty."
    assert judge_plan(under, share_q("Under one in fifteen", value=6.67, relation="less"), fact)[0] == Verdict.CONTRADICTED
    # the model's relation flag is not what decides: the sentence's own word is
    assert judge_plan(under, share_q("one in fifteen", value=6.67), fact)[0] == Verdict.CONTRADICTED
    over = "Over one in fifteen primary tumours come from patients diagnosed before forty."
    assert judge_plan(over, share_q("one in fifteen", value=6.67, relation="less"), fact)[0] == Verdict.SUPPORTED


def test_judge_count_bound_comes_from_the_sentences_words():
    q = qp(count_plan([f("sample_type", "primary")]), stated_for("300", "count", value=300))
    fewer = "Fewer than 300 primary tumours come from patients diagnosed before fifty."
    assert judge_plan(fewer, q, Fact("x", 297, 297, None, [], [], ""))[0] == Verdict.SUPPORTED
    assert judge_plan(fewer, q, Fact("x", 300, 300, None, [], [], ""))[0] == Verdict.CONTRADICTED
    at_least = "At least 300 primary tumours come from patients diagnosed before fifty."
    assert judge_plan(at_least, q, Fact("x", 300, 300, None, [], [], ""))[0] == Verdict.SUPPORTED


def test_judge_count_on_a_share_plan_checks_the_stated_total():
    sentence = "535 of 1,101 tumors have all layers."
    q = qp(share_plan([f("has_layer", "protein")]), stated_for("535 of 1,101", "count", value=535, total=1101))
    assert judge_plan(sentence, q, Fact("x", 48.6, 535, 1101, [], [], "")) == (Verdict.SUPPORTED, None)
    verdict, correct = judge_plan(sentence, q, Fact("x", 48.0, 535, 1114, [], [], ""))
    assert verdict == Verdict.CONTRADICTED and correct == "535 of 1,114"


def test_judge_count_plan():
    q = qp(count_plan([f("sample_type", "primary")]), stated_for("1,101", "count", value=1101))
    sent = "There are 1,101 primary tumors."
    assert judge_plan(sent, q, Fact("x", 1101, 1101, None, [], [], ""))[0] == Verdict.SUPPORTED
    verdict, correct = judge_plan(sent, q, Fact("x", 1100, 1100, None, [], [], ""))
    assert (verdict, correct) == (Verdict.CONTRADICTED, "1,100")
    approx = "There are about 1,090 primary tumors."
    qa = qp(count_plan([f("sample_type", "primary")]), stated_for("about 1,090", "count", value=1090))
    assert judge_plan(approx, qa, Fact("x", 1101, 1101, None, [], [], ""))[0] == Verdict.SUPPORTED


def rank_q(category, value, span="second"):
    return qp({"op": "rank", "category_field": "subtype_rna", "category": category},
              stated_for(span, "rank", value=value))


def rank_fact(rank, counts):
    extra = {f"count_{k}": v for k, v in counts.items()}
    extra.update({f"share_{k}": round(100 * v / sum(counts.values()), 1) for k, v in counts.items()})
    return Fact("x", rank, None, None, [], [], "", extra=extra)


COUNTS = {"Luminal A": 421, "Luminal B": 192, "Basal-like": 141, "HER2-enriched": 67, "Normal-like": 23}


def test_judge_rank():
    sent = "Luminal B is the second most common subtype."
    assert judge_plan(sent, rank_q("Luminal B", 2, "second"), rank_fact(2, COUNTS)) == (Verdict.SUPPORTED, None)
    verdict, correct = judge_plan(sent, rank_q("Luminal B", 3, "second"), rank_fact(2, COUNTS))
    assert verdict == Verdict.CONTRADICTED  # (the quote check is validate_plan's job, not judge's)
    assert correct.startswith("Luminal B is 2nd of 5: Luminal A 421, Luminal B 192, Basal-like 141")
    assert correct.endswith("Normal-like 23")


def order_q(relation):
    return qp({"op": "order", "category_field": "subtype_rna", "category_a": "HER2-enriched", "category_b": "Basal-like"},
              stated_for("rarer", "relation", relation=relation))


def order_fact(a, b):
    return Fact("x", a - b, None, None, [], [], "", extra={"count_a": a, "count_b": b})


def test_judge_order():
    sent = "HER2-enriched tumors are rarer than Basal-like tumors."
    assert judge_plan(sent, order_q("less"), order_fact(67, 141)) == (Verdict.SUPPORTED, None)
    verdict, correct = judge_plan(sent, order_q("less"), order_fact(200, 141))
    assert verdict == Verdict.CONTRADICTED and "HER2-enriched 200" in correct and "Basal-like 141" in correct
    assert judge_plan(sent, order_q("more"), order_fact(67, 141))[0] == Verdict.CONTRADICTED
    assert judge_plan(sent, order_q("less"), order_fact(5, 5))[0] == Verdict.CONTRADICTED  # a tie is neither


def test_judge_comparison_direction():
    sent = SENT_ER
    fact = Fact("x", 3.051, None, None, [], [], "", extra={"n_a": 529, "n_b": 169})
    assert judge_plan(sent, qp(compare(), HIGHER), fact) == (Verdict.SUPPORTED, None)
    verdict, correct = judge_plan(sent, qp(compare(), stated_for("lower", "direction", relation="less")), fact)
    assert verdict == Verdict.CONTRADICTED and "3.05" in correct and "529" in correct
    num = "The ER-alpha difference was 3.05."
    qn = qp(compare(), stated_for("3.05", "number", value=3.05))
    assert judge_plan(num, qn, fact)[0] == Verdict.SUPPORTED
    assert judge_plan("The ER-alpha difference was 2.9.", qp(compare(), stated_for("2.9", "number", value=2.9)), fact)[0] == Verdict.CONTRADICTED


def stat_q(stat, span, value, **kw):
    return qp({"op": "summary_stat", "field": "age_years", "stat": stat}, stated_for(span, "number", value=value, **kw))


def stat_fact(value, n=1094, rows=1242):
    return Fact("x", value, n, rows, [], [], "", unknown_count=rows - n)


def test_judge_summary_stat():
    sent = "The median age at diagnosis was 58 years."
    assert judge_plan(sent, stat_q("median", "58 years", 58), stat_fact(58.0)) == (Verdict.SUPPORTED, None)
    verdict, correct = judge_plan(sent, stat_q("median", "58 years", 58), stat_fact(59.0))
    assert (verdict, correct) == (Verdict.CONTRADICTED, "median 59.0 years (n=1,094)")
    assert judge_plan(sent, stat_q("median", "58 years", 58), stat_fact(58.4))[0] == Verdict.SUPPORTED  # rounds to 58
    mean = "The mean age was 58.2 years."
    assert judge_plan(mean, stat_q("mean", "58.2 years", 58.2), stat_fact(58.1795))[0] == Verdict.SUPPORTED
    assert judge_plan(mean, stat_q("mean", "58.2 years", 58.2), stat_fact(58.31))[0] == Verdict.CONTRADICTED
    around = "The mean age was around 60 years."
    assert judge_plan(around, stat_q("mean", "around 60 years", 60), stat_fact(59.0))[0] == Verdict.SUPPORTED
    assert judge_plan(around, stat_q("mean", "around 60 years", 60), stat_fact(55.0))[0] == Verdict.CONTRADICTED


def test_judge_summary_stat_bound_comes_from_the_sentences_words():
    over = "The median age at diagnosis was over 55 years."
    assert judge_plan(over, stat_q("median", "55 years", 55), stat_fact(58.0))[0] == Verdict.SUPPORTED
    assert judge_plan(over, stat_q("median", "55 years", 55), stat_fact(54.0))[0] == Verdict.CONTRADICTED
    under = "The youngest patient was under 30 at diagnosis."
    assert judge_plan(under, stat_q("min", "30", 30), stat_fact(26.0))[0] == Verdict.SUPPORTED


# ---------------------------------------------------------------- run_plan on the mini release


def test_run_plan_validates_before_executing(mini):
    q = qp(pct_plan(), stated_for("about 20%", "percent", value=20))
    with pytest.raises(PlanRejected):
        run_plan(SENTENCE, q, mini)


def test_run_plan_on_the_mini_release(mini):
    # 3 of 7 RNA-called primary tumors are Luminal A: 42.9%
    sent = "About 43% of subtyped primary tumors are Luminal A."
    q = qp(share_plan([f("subtype_rna", "Luminal A")], where=[f("sample_type", "primary")]),
           stated_for("About 43%", "percent", value=43, approximate=True))
    fact, verdict, correct = run_plan(sent, q, mini)
    assert (fact.numerator, fact.denominator, verdict, correct) == (3, 7, Verdict.SUPPORTED, None)
    wrong = "42% of subtyped primary tumors are Luminal A."
    q2 = qp(share_plan([f("subtype_rna", "Luminal A")], where=[f("sample_type", "primary")]), stated_for("42%", "percent", value=42))
    assert run_plan(wrong, q2, mini)[1:] == (Verdict.CONTRADICTED, "42.9% (3 of 7)")


# ---------------------------------------------------------------- the real release


@pytest.fixture
def real(release_dir):
    return load_release(release_dir)


@pytest.fixture
def real_clin(release_dir):
    return pd.read_csv(release_dir / "clinical.tsv", sep="\t", low_memory=False)


@pytest.mark.realdata
def test_real_sample_type_and_sex_counts(real, real_clin):
    code = real_clin.sampleID.str[13:15]
    for flt, expect in ((f("sample_type", "primary"), 1101), (f("sample_type", "normal_tissue"), 139),
                        (f("sample_type", "metastatic"), 7), (f("sex", "male"), 13)):
        assert (code == "01").sum() == 1101
        fact = execute_plan(qp(count_plan([flt]), stated_for("1", value=1)), real)
        assert fact.value == expect, flt
    male_primary = execute_plan(qp(count_plan([f("sample_type", "primary"), f("sex", "male")]), stated_for("1", value=1)), real)
    assert male_primary.value == 12 == ((code == "01") & (real_clin.gender == "MALE")).sum()
    assert male_primary.extra["excluded_unknown_sex"] == ((code == "01") & real_clin.gender.isna()).sum()


@pytest.mark.realdata
def test_real_release_rna_plan_matches_the_rna_file(real):
    """`fetch.py --no-rna` leaves the RNA file out: an RNA plan is then rejected, never run on missing data."""
    plan = qp(count_plan([f("has_layer", "rna")]), NUM)
    if real.rna_ids is None:
        with pytest.raises(PlanRejected, match="no RNA file in this release"):
            validate_plan(plan, "There are 10 samples.", real)
    else:
        validate_plan(plan, "There are 10 samples.", real)


@pytest.mark.realdata
def test_real_er_alpha_difference(real, real_clin):
    q = qp(compare(), HIGHER)
    fact, verdict, _ = run_plan(SENT_ER, q, real)
    p = real_clin[real_clin.sampleID.str[13:15] == "01"].set_index("sampleID")[ER]
    pos = [s for s in real.protein.columns if s in p.index and p[s] == "Positive"]
    neg = [s for s in real.protein.columns if s in p.index and p[s] == "Negative"]
    assert (len(pos), len(neg)) == (529, 169) == (fact.extra["n_a"], fact.extra["n_b"])
    assert fact.value == pytest.approx(real.protein.loc["ERALPHA", pos].mean() - real.protein.loc["ERALPHA", neg].mean())
    assert round(fact.value, 3) == 3.051 and verdict == Verdict.SUPPORTED
    assert run_code(fact, real)["difference"] == pytest.approx(fact.value)


@pytest.mark.realdata
def test_real_case_a_exact_percent(real):
    plan = share_plan([f("subtype_rna", "Basal-like")], where=[f("sample_type", "primary")])
    q = qp(plan, stated_for("About 16.7%", "percent", value=16.7, approximate=True))
    fact, verdict, correct = run_plan(SENTENCE, q, real)
    assert (fact.numerator, fact.denominator) == (141, 844)
    assert (verdict, correct) == (Verdict.SUPPORTED, None)
    assert run_code(fact, real)["n"] == 141


@pytest.mark.realdata
def test_real_case_b_one_in_six(real):
    sent = "Basal-like tumors make up roughly one in six of the subtyped primary tumors."
    plan = share_plan([f("subtype_rna", "Basal-like")], where=[f("sample_type", "primary")])
    q = qp(plan, stated_for("roughly one in six", "percent", value=16.7, approximate=True))
    fact, verdict, _ = run_plan(sent, q, real)
    assert (fact.numerator, fact.denominator, verdict) == (141, 844, Verdict.SUPPORTED)


@pytest.mark.realdata
def test_real_case_c_luminal_b_is_second(real, real_clin):
    sent = "Luminal B is the second most common subtype."
    plan = {"op": "rank", "category_field": "subtype_rna", "category": "Luminal B", "where": [f("sample_type", "primary")]}
    q = qp(plan, stated_for("second most common", "rank", value=2))
    fact, verdict, correct = run_plan(sent, q, real)
    p = real_clin[real_clin.sampleID.str[13:15] == "01"].PAM50Call_RNAseq.value_counts()
    assert dict(p) == {"LumA": 421, "LumB": 192, "Basal": 141, "Her2": 67, "Normal": 23}
    assert (fact.value, verdict, correct) == (2, Verdict.SUPPORTED, None)
    assert fact.extra["count_Luminal A"] == 421 and fact.extra["count_Luminal B"] == 192
    wrong = qp(plan, stated_for("third most common", "rank", value=3))
    v2, c2 = run_plan("Luminal B is the third most common subtype.", wrong, real)[1:]
    assert v2 == Verdict.CONTRADICTED and c2.startswith("Luminal B is 2nd of 5: Luminal A 421, Luminal B 192")


@pytest.mark.realdata
def test_real_case_d_her2_rarer_than_basal(real):
    sent = "HER2-enriched tumors are rarer than Basal-like tumors."
    plan = {"op": "order", "category_field": "subtype_rna", "category_a": "HER2-enriched", "category_b": "Basal-like",
            "where": [f("sample_type", "primary")]}
    fact, verdict, _ = run_plan(sent, qp(plan, stated_for("rarer than", "relation", relation="less")), real)
    assert (fact.extra["count_a"], fact.extra["count_b"], fact.value) == (67, 141, -74)
    assert verdict == Verdict.SUPPORTED
    assert run_plan("HER2-enriched tumors are more common than Basal-like tumors.",
                    qp(plan, stated_for("more common than", "relation", relation="more")), real)[1] == Verdict.CONTRADICTED


@pytest.mark.realdata
@pytest.mark.parametrize("sentence, span, approximate", [
    ("Women make up 98% of the samples in this release.", "98%", False),
    ("Women make up roughly 98% of the samples in this release.", "roughly 98%", True),
    ("Women make up 99% of the samples in this release.", "99%", False),
])
def test_real_case_e_women_share_follows_the_truth(real, real_clin, sentence, span, approximate):
    value = float(span.split()[-1].rstrip("%"))
    known = real_clin[real_clin.gender.notna()]
    truth = 100 * (known.gender == "FEMALE").sum() / len(known)
    q = qp(share_plan([f("sex", "female")]), stated_for(span, "percent", value=value, approximate=approximate))
    fact, verdict, correct = run_plan(sentence, q, real)
    assert (fact.numerator, fact.denominator) == ((known.gender == "FEMALE").sum(), len(known))
    assert fact.unknown_count == real_clin.gender.isna().sum()
    holds = abs(truth - value) <= 2 if approximate else round(truth) == value
    assert verdict == (Verdict.SUPPORTED if holds else Verdict.CONTRADICTED)
    assert (correct is None) == holds
    if not holds:
        assert correct.startswith(f"{truth:.1f}%")


@pytest.mark.realdata
@pytest.mark.parametrize("claimed", [58, 57])
def test_real_case_f_median_age_follows_the_truth(real, real_clin, claimed):
    sent = f"The median age at diagnosis was {claimed} years."
    truth = real_clin[AGE].dropna().median()
    q = qp({"op": "summary_stat", "field": "age_years", "stat": "median"}, stated_for(f"{claimed} years", "number", value=claimed))
    fact, verdict, correct = run_plan(sent, q, real)
    assert fact.value == truth and fact.numerator == real_clin[AGE].notna().sum()
    assert fact.unknown_count == real_clin[AGE].isna().sum()
    assert verdict == (Verdict.SUPPORTED if round(truth) == claimed else Verdict.CONTRADICTED)
    if correct:
        assert correct.startswith(f"median {truth:.1f} years (n=")


# ---------------------------------------------------------------- attribute filters: every attribute the rules read


def af(attribute, value=None, op="eq"):
    return {"field": "attribute", "attribute": attribute, "op": op, "value": value}


def test_attribute_filter_on_a_gene_matches_the_mutation_file(mini):
    q = qp(share_plan([af("mutation", "TP53")], where=[f("sample_type", "primary"), f("has_layer", "mutation")]),
           stated_for("50%", "percent", value=50))
    fact = execute_plan(q, mini)
    calls = mini.mutation()
    ids = [i for i in calls.columns if i in set(mini.primary_ids())]
    assert (fact.numerator, fact.denominator) == (int((calls.loc["TP53", ids] > 0).sum()), len(ids))
    assert run_code(fact, mini)["n"] == fact.numerator


def test_attribute_filter_rejects_what_the_release_lacks(mini):
    q = qp(count_plan([af("mutation", "NOTAGENE")]), NUM)
    with pytest.raises(PlanRejected, match="NOTAGENE"):
        validate_plan(q, "10 tumours carry it.", mini)
    with pytest.raises(PlanRejected, match="attribute"):
        validate_plan(qp(count_plan([{"field": "attribute", "op": "eq", "value": "TP53"}]), NUM), "10 tumours.", mini)


def test_attribute_filter_names_must_be_on_the_list():
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({"answerable": True, "plan": count_plan([af("tumour_size", "big")]), "stated": NUM})


@pytest.mark.parametrize("attribute, value, op, expected", [
    ("stage", ["Stage III", "Stage IV"], "in", 270),
    ("pr_status", "positive", "eq", 699),
    ("histology", "lobular", "eq", 203),
    ("vital_status", "deceased", "eq", 151),
    ("amplification", "ERBB2", "eq", 133),
    ("triple_negative", "triple-negative", "eq", 116),
])
def test_attribute_filters_on_the_real_release(real, attribute, value, op, expected):
    q = qp(count_plan([f("sample_type", "primary"), af(attribute, value, op)]), NUM)
    fact = execute_plan(q, real)
    assert fact.value == expected
    assert run_code(fact, real)["n"] == expected


# ---------------------------------------------------------------- zero claims and missing values


@pytest.mark.parametrize("sentence, span", [
    ("None of the male patients had a Basal-like tumour.", "None"),
    ("Not a single primary tumour lacks an age at diagnosis.", "Not a single"),
    ("No men had a Basal-like tumour.", "No men"),
])
def test_a_stated_zero_is_derivable_from_zero_words(mini, sentence, span):
    validate_plan(qp(count_plan([f("sex", "male")]), stated_for(span, "count", value=0)), sentence, mini)


def test_zero_needs_a_zero_word(mini):
    with pytest.raises(PlanRejected, match="not in the sentence"):
        validate_plan(qp(count_plan([f("sex", "male")]), stated_for("male", "count", value=0)), "Some male tumours exist.", mini)


def test_is_unknown_keeps_rows_without_a_value(mini_age, clin):
    q = qp(count_plan([f("sample_type", "primary"), f("age_years", op="is_unknown")]), stated_for("Not a single", "count", value=0))
    fact = execute_plan(q, mini_age)
    p = primary(mini_age.clinical)
    assert fact.value == int(pd.to_numeric(p[AGE], errors="coerce").isna().sum()) == 1
    assert run_code(fact, mini_age)["n"] == fact.value


# ---------------------------------------------------------------- numeric fields, group comparisons, group and gene ranks

PRIMARY = f("sample_type", "primary")


@pytest.mark.parametrize("field, stat, expected", [
    ("diagnosis_year", "min", 1988), ("diagnosis_year", "max", 2013), ("positive_lymph_nodes", "median", 1),
])
def test_summary_stat_of_other_numeric_fields(real, field, stat, expected):
    fact = execute_plan(qp({"op": "summary_stat", "field": field, "stat": stat, "where": [PRIMARY]}, NUM), real)
    assert fact.value == expected
    assert run_code(fact, real)["result"] == expected


def test_range_stat_judges_both_ends(real):
    sentence = "Diagnoses span the years 1988 to 2013."
    q = qp({"op": "summary_stat", "field": "diagnosis_year", "stat": "range", "where": [PRIMARY]},
           stated_for("1988 to 2013", "number", value=1988, high=2013))
    assert run_plan(sentence, q, real)[1] == Verdict.SUPPORTED
    wrong = qp(q.plan.model_dump(), stated_for("1988 to 2014", "number", value=1988, high=2014))
    assert run_plan("Diagnoses span the years 1988 to 2014.", wrong, real)[1] == Verdict.CONTRADICTED


def test_numeric_field_filters(real):
    q = qp(count_plan([PRIMARY, f("diagnosis_year", 1990, "lt")]), NUM)
    assert execute_plan(q, real).value == 3


def subtype(name):
    return f("subtype_rna", name)


def test_compare_groups_by_count(real):
    q = qp({"op": "compare_groups", "measure": "count", "compare": "difference", "where": [PRIMARY],
            "group_a": [f("her2_status", "positive")], "group_b": [af("amplification", "ERBB2")]},
           stated_for("fewer than", "relation", relation="less"))
    sentence = "HER2-positive tumours by immunohistochemistry are fewer than ERBB2-amplified tumours."
    fact, verdict, _ = run_plan(sentence, q, real)
    assert (fact.value, fact.extra["a"], fact.extra["b"], verdict) == (31, 164, 133, Verdict.CONTRADICTED)
    assert run_code(fact, real)["result"] == 31


def test_compare_groups_by_share_as_a_ratio(real):
    q = qp({"op": "compare_groups", "measure": "share", "compare": "ratio",
            "where": [PRIMARY, f("has_layer", "mutation")], "numerator": [af("mutation", "TP53")],
            "group_a": [subtype("Basal-like")], "group_b": [subtype("Luminal A")]},
           stated_for("roughly eight times", "number", value=8))
    sentence = "TP53 mutations are roughly eight times as common in Basal-like as in Luminal A tumours."
    fact, verdict, _ = run_plan(sentence, q, real)
    assert fact.value == pytest.approx((90 / 106) / (31 / 301))
    assert verdict == Verdict.SUPPORTED
    assert run_code(fact, real)["result"] == pytest.approx(fact.value)


def test_compare_groups_by_median(real):
    q = qp({"op": "compare_groups", "measure": "stat", "field": "age_years", "stat": "median", "compare": "difference",
            "where": [PRIMARY], "group_a": [subtype("Basal-like")], "group_b": [subtype("Luminal A")]},
           stated_for("younger", "direction", relation="less"))
    fact, verdict, _ = run_plan("Basal-like patients were diagnosed younger than Luminal A patients.", q, real)
    assert (fact.value, verdict) == (-7, Verdict.SUPPORTED)


@pytest.mark.parametrize("sentence, span, order, verdict", [
    ("Basal-like patients were the youngest at diagnosis of any RNA subtype.", "youngest", "lowest", Verdict.CONTRADICTED),
    ("Normal-like patients were the youngest at diagnosis of any RNA subtype.", "youngest", "lowest", Verdict.SUPPORTED),
    ("Luminal A patients were the oldest at diagnosis of any RNA subtype.", "oldest", "highest", Verdict.SUPPORTED),
])
def test_rank_groups_by_median_age(real, sentence, span, order, verdict):
    category = sentence.split(" patients")[0]
    q = qp({"op": "rank_groups", "measure": "stat", "field": "age_years", "stat": "median", "order": order,
            "where": [PRIMARY], "category_field": "subtype_rna", "category": category},
           stated_for(span, "rank", value=1))
    fact, got, _ = run_plan(sentence, q, real)
    assert got == verdict
    assert run_code(fact, real)["rank"] == fact.value


def test_rank_groups_by_share(real):
    q = qp({"op": "rank_groups", "measure": "share", "order": "lowest", "where": [PRIMARY, f("has_layer", "mutation")],
            "numerator": [af("mutation", "PIK3CA")], "category_field": "subtype_rna", "category": "Basal-like"},
           stated_for("rarest", "rank", value=1))
    assert run_plan("PIK3CA mutations are rarest in Basal-like tumours.", q, real)[1] == Verdict.SUPPORTED


def test_rank_of_a_mutated_gene(real):
    q = qp({"op": "rank", "category_field": "mutated_gene", "category": "TTN", "where": [PRIMARY]},
           stated_for("third", "rank", value=3))
    fact, verdict, _ = run_plan("TTN ranks third among mutated genes.", q, real)
    assert (fact.value, verdict) == (3, Verdict.SUPPORTED)
    assert run_code(fact, real)["rank"] == 3


@pytest.mark.parametrize("value", ["IV", "stage iv", "Stage 4", "4"])
def test_stage_values_are_normalised(real, value):
    q = qp(count_plan([PRIMARY, af("stage", value)]), NUM)
    assert execute_plan(q, real).value == 20


@pytest.mark.parametrize("sentence, span, value, fact, verdict", [
    ("Most tumors in the release were diagnosed in 2010 or later.", "Most", 50, fact_pct(484, 1095), Verdict.CONTRADICTED),
    ("Most tumors in the release were diagnosed before 2013.", "Most", 50, fact_pct(900, 1095), Verdict.SUPPORTED),
    ("Nearly all lobular tumours are ER-positive.", "Nearly all", 90, fact_pct(190, 198), Verdict.SUPPORTED),
    ("A minority of tumours are ER-negative.", "A minority", 50, fact_pct(238, 1046), Verdict.SUPPORTED),
])
def test_vague_amounts_are_quotable_with_their_bound(mini, sentence, span, value, fact, verdict):
    q = share_q(span, value=value)
    validate_plan(q, sentence, mini)
    assert judge_plan(sentence, q, fact)[0] == verdict

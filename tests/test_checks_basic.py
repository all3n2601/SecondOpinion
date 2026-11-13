import dataclasses

import pytest

from second_opinion.checks import CHECKS, CannotCheck
from second_opinion.checks.population import population, subtype_column
from second_opinion.model import Claim, ClaimParams, ClaimType
from second_opinion.release import load_release
from second_opinion.variants import PRIMARY_VARIANT, Variant, all_variants
from tests.helpers import MINI


def count_claim(subject, total=None):
    return Claim("C1", "...", 0, ClaimType.COUNT, ClaimParams(None, None, total, "count", subject=subject))


def share_claim(subtype):
    return Claim("C1", "...", 0, ClaimType.SHARE, ClaimParams(None, unit="percent", subtype=subtype))


def coverage_claim(subject):
    return Claim("C1", "...", 0, ClaimType.COVERAGE, ClaimParams(unit="all", subject=subject))


def variant_from_id(variant_id):
    return Variant(*variant_id.split("|"))


@pytest.mark.realdata
def test_practice_count(release_dir):
    f = CHECKS[ClaimType.COUNT](count_claim("all_five_layers", 1101), load_release(release_dir), PRIMARY_VARIANT)
    assert (f.numerator, f.denominator) == (535, 1101)
    if load_release(release_dir).rna_ids is None:
        assert f.extra["note"] == "no RNA file in this release; counted four layers"


@pytest.mark.realdata
@pytest.mark.parametrize(
    "variant_id, num, den",
    [
        ("rna_call|everyone|primary_tumors", 421, 844),
        ("rna_call|women_only|primary_tumors", 416, 833),
        ("study_2012_label|everyone|primary_tumors", 231, 522),
        ("rna_call|everyone|all_samples", 434, 956),
    ],
)
def test_luminal_a_share_by_variant(release_dir, variant_id, num, den):
    f = CHECKS[ClaimType.SHARE](share_claim("Luminal A"), load_release(release_dir), variant_from_id(variant_id))
    assert (f.numerator, f.denominator) == (num, den)
    assert round(f.value, 1) == round(100 * num / den, 1)
    assert len(f.sample_ids) == den


@pytest.mark.realdata
def test_real_code_snippet_reproduces_the_share(release_dir):
    r = load_release(release_dir)
    f = CHECKS[ClaimType.SHARE](share_claim("LumA"), r, PRIMARY_VARIANT)
    scope = {"r": r}
    exec(f.code, scope)
    assert (scope["n"], scope["total"]) == (f.numerator, f.denominator) == (421, 844)


def test_share_ignores_spelling(mini_release):
    r = load_release(mini_release)
    share = CHECKS[ClaimType.SHARE]
    a, b, c = (share(share_claim(s), r, PRIMARY_VARIANT) for s in ("LumA", "Luminal A", "Luminal-A"))
    assert (a.numerator, a.denominator) == (b.numerator, b.denominator) == (c.numerator, c.denominator)
    assert a.numerator == MINI["luma_rna_primary"]
    assert a.denominator == MINI["rna_subtyped_primary"]
    assert a.unknown_count == MINI["primary"] - MINI["rna_subtyped_primary"]
    assert "Luminal A" in a.label and "RNA-seq" in a.label


def test_share_2012_source_uses_other_column(mini_release):
    r = load_release(mini_release)
    v = Variant("study_2012_label", "everyone", "primary_tumors")
    f = CHECKS[ClaimType.SHARE](share_claim("Luminal A"), r, v)
    assert (f.numerator, f.denominator) == (MINI["luma_2012_primary"], MINI["study_2012_subtyped_primary"])
    assert subtype_column(v) == "PAM50_mRNA_nature2012"


def test_metastasis_not_counted_as_primary(mini_release):
    r = load_release(mini_release)
    f = CHECKS[ClaimType.SHARE](share_claim("LumA"), r, PRIMARY_VARIANT)
    assert "TCGA-AA-0011-06" not in f.sample_ids
    g = CHECKS[ClaimType.SHARE](share_claim("LumA"), r, Variant("rna_call", "everyone", "all_samples"))
    assert "TCGA-AA-0011-06" in g.sample_ids
    assert g.numerator == MINI["luma_rna_primary"] + 1


def test_women_only_counts_unknown_sex(mini_release):
    r = load_release(mini_release)
    v = Variant("rna_call", "women_only", "primary_tumors")
    f = CHECKS[ClaimType.SHARE](share_claim("LumA"), r, v)
    assert f.extra["excluded_unknown_sex"] == MINI["unknown_sex_primary"]
    pop = population(r, v)
    assert len(pop) == MINI["primary"] - MINI["male_primary"] - MINI["unknown_sex_primary"]
    assert set(pop["gender"]) == {"FEMALE"}
    assert pop.attrs["excluded_unknown_sex"] == MINI["unknown_sex_primary"]
    assert population(r, PRIMARY_VARIANT).attrs["excluded_unknown_sex"] == 0


def test_every_variant_runs_on_mini(mini_release):
    r = load_release(mini_release)
    for v in all_variants():
        f = CHECKS[ClaimType.SHARE](share_claim("Luminal A"), r, v)
        assert f.denominator is not None and f.numerator <= f.denominator


def test_rna_claim_without_rna_file_cannot_be_checked(mini_release):
    r = load_release(mini_release)
    with pytest.raises(CannotCheck, match="no RNA file in this release"):
        CHECKS[ClaimType.COVERAGE](coverage_claim("has_rna"), r, PRIMARY_VARIANT)


def test_all_five_layers_notes_missing_rna(mini_release):
    r = load_release(mini_release)
    f = CHECKS[ClaimType.COUNT](count_claim("all_five_layers"), r, PRIMARY_VARIANT)
    assert (f.numerator, f.denominator) == (MINI["all_layers_primary"], MINI["primary"])
    assert f.extra["note"] == "no RNA file in this release; counted four layers"
    assert "rna" not in f.code and "survival.tsv" in f.files[1]
    scope = {"r": r}
    exec(f.code, scope)
    assert (scope["n"], scope["total"]) == (f.numerator, f.denominator)
    assert set(f.sample_ids) == set(scope["have"])


def test_all_five_layers_includes_rna_when_present(mini_release):
    r = load_release(mini_release)
    r.rna_ids = set(r.primary_ids()[:4])  # pretend an RNA file exists
    f = CHECKS[ClaimType.COUNT](count_claim("all_five_layers"), r, PRIMARY_VARIANT)
    assert "note" not in f.extra
    assert set(f.sample_ids) <= r.rna_ids
    assert f.files[-1] == "rna_hiseq.tsv.gz"


def test_count_subjects(mini_release):
    r = load_release(mini_release)
    count = CHECKS[ClaimType.COUNT]
    assert count(count_claim("primary_tumors"), r, PRIMARY_VARIANT).numerator == MINI["primary"]
    assert count(count_claim("samples"), r, PRIMARY_VARIANT).numerator == MINI["samples"]
    patients = count(count_claim("patients"), r, PRIMARY_VARIANT)
    assert patients.numerator == len({s[:12] for s in r.clinical["sampleID"]})
    with pytest.raises(CannotCheck):
        count(count_claim("something_else"), r, PRIMARY_VARIANT)


def test_coverage_lists_missing_samples(mini_release):
    r = load_release(mini_release)
    cov = CHECKS[ClaimType.COVERAGE]
    f = cov(coverage_claim("has_protein"), r, PRIMARY_VARIANT)
    primary = set(r.primary_ids())
    assert f.denominator == MINI["primary"]
    assert set(f.sample_ids) == primary - r.protein_ids
    assert f.numerator == MINI["primary"] - len(f.sample_ids)
    assert f.numerator < f.denominator  # "every primary tumor has protein" is false in the mini release
    scope = {"r": r}
    exec(f.code, scope)
    assert sorted(scope["missing"]) == sorted(f.sample_ids)
    for subject, layer in [("has_survival", "survival"), ("has_mutation", "mutation"), ("has_copy_number", "copy_number")]:
        g = cov(coverage_claim(subject), r, PRIMARY_VARIANT)
        assert set(g.sample_ids) == primary - r.layer_ids(layer)


@pytest.mark.realdata
def test_real_coverage_denominator(release_dir):
    r = load_release(release_dir)
    f = CHECKS[ClaimType.COVERAGE](coverage_claim("has_protein"), r, PRIMARY_VARIANT)
    assert f.denominator == len(r.primary_ids()) == 1101
    assert f.numerator + len(f.sample_ids) == 1101


@pytest.mark.parametrize("subtype", ["Claudin-low", "Luminal C", "Basel-like", "HER3"])
def test_unrecognised_subtype_cannot_be_checked(mini_release, subtype):
    with pytest.raises(CannotCheck, match=f"this release has no '{subtype}' subtype"):
        CHECKS[ClaimType.SHARE](share_claim(subtype), load_release(mini_release), PRIMARY_VARIANT)


def test_known_subtype_with_no_samples_is_a_real_zero(mini_release):
    r = load_release(mini_release)
    r.clinical = r.clinical.assign(PAM50Call_RNAseq=r.clinical["PAM50Call_RNAseq"].replace("Normal", None))
    f = CHECKS[ClaimType.SHARE](share_claim("Normal-like"), r, PRIMARY_VARIANT)
    assert (f.numerator, f.denominator) == (0, MINI["rna_subtyped_primary"] - 1)
    assert f.value == 0


@pytest.mark.parametrize(
    "variant, column",
    [(PRIMARY_VARIANT, "PAM50Call_RNAseq"), (Variant("study_2012_label", "everyone", "primary_tumors"), "PAM50_mRNA_nature2012")],
)
def test_missing_subtype_column_cannot_be_checked(mini_release, variant, column):
    r = load_release(mini_release)
    r = dataclasses.replace(r, clinical=r.clinical.drop(columns=[column]))
    with pytest.raises(CannotCheck, match=column):
        CHECKS[ClaimType.SHARE](share_claim("Luminal A"), r, variant)

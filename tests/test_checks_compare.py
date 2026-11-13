import dataclasses

import pytest

from second_opinion.checks import CHECKS, CannotCheck
from second_opinion.model import Claim, ClaimParams, ClaimType, Verdict
from second_opinion.release import load_release
from second_opinion.variants import PRIMARY_VARIANT, Variant
from second_opinion.verdict import judge


def compare_claim(direction="higher", measure="ER-alpha protein", a="ER-positive", b="ER-negative"):
    params = ClaimParams(direction=direction, measure=measure, group_a=a, group_b=b)
    return Claim("C9", "...", 0, ClaimType.COMPARISON, params)


def run(claim, release, variant=PRIMARY_VARIANT):
    return CHECKS[ClaimType.COMPARISON](claim, release, variant)


@pytest.mark.realdata
def test_er_alpha_matches_reference_analysis_a1(release_dir):
    f = run(compare_claim(), load_release(release_dir))
    assert (f.extra["n_a"], f.extra["n_b"]) == (529, 169)
    assert round(f.value, 3) == 3.051
    assert (f.extra["mean_a"], f.extra["mean_b"]) == (2.179, -0.872)
    assert len(f.sample_ids) == 698
    assert f.files == ["clinical.tsv", "protein_rppa.tsv.gz"]
    assert (f.numerator, f.denominator) == (None, None)


@pytest.mark.realdata
def test_swapped_groups_flip_the_sign(release_dir):
    f = run(compare_claim(a="ER-negative", b="ER-positive"), load_release(release_dir))
    assert round(f.value, 3) == -3.051
    assert (f.extra["n_a"], f.extra["n_b"]) == (169, 529)


@pytest.mark.realdata
def test_her2_protein_by_her2_status(release_dir):
    claim = compare_claim(measure="HER2 protein", a="HER2-positive", b="HER2-negative")
    f = run(claim, load_release(release_dir))
    assert f.extra["n_a"] > 0 and f.extra["n_b"] > 0
    assert f.value > 0


@pytest.mark.realdata
def test_real_code_snippet_reproduces_the_difference(release_dir):
    r = load_release(release_dir)
    f = run(compare_claim(), r)
    scope = {"r": r}
    exec(f.code, scope)
    assert scope["difference"] == pytest.approx(f.value)


@pytest.mark.realdata
def test_judge_end_to_end_on_real_data(release_dir):
    f = run(compare_claim(), load_release(release_dir))
    assert judge(compare_claim("higher"), f)[0] == Verdict.SUPPORTED
    assert judge(compare_claim("lower"), f)[0] == Verdict.CONTRADICTED


# Mini release ER-alpha values (see tests/helpers.py), primary tumors in the protein file:
#   Positive: 0001 -0.5, 0002 0.25, 0003 1.5, 0004 -1.0, 0007 (MALE) 0.25, 0008 (no sex) 1.5  -> sum 2.0, mean 1/3
#   Negative: 0005 -0.5;  0009 is Indeterminate and is left out.
def test_mini_primary_variant(mini_release):
    f = run(compare_claim(), load_release(mini_release))
    assert (f.extra["n_a"], f.extra["n_b"]) == (6, 1)
    assert f.extra["mean_a"] == 0.333 and f.extra["mean_b"] == -0.5
    assert f.value == pytest.approx(1 / 3 + 0.5)
    assert len(f.sample_ids) == 7
    assert "TCGA-CC-0009-01" not in f.sample_ids


def test_mini_women_only_drops_men_and_unknown_sex(mini_release):
    variant = Variant("rna_call", "women_only", "primary_tumors")
    f = run(compare_claim(), load_release(mini_release), variant)
    assert (f.extra["n_a"], f.extra["n_b"]) == (4, 1)
    assert f.value == pytest.approx(0.0625 + 0.5)


def test_mini_all_samples_scope_adds_normal_tissue(mini_release):
    r = load_release(mini_release)
    r.protein = r.protein.copy()
    r.protein["TCGA-AA-0001-11"] = [2.0, 0.0, 0.0]  # a Positive solid-tissue normal
    primary = run(compare_claim(), r)
    everything = run(compare_claim(), r, Variant("rna_call", "everyone", "all_samples"))
    assert primary.extra["n_a"] == 6
    assert everything.extra["n_a"] == 7
    assert everything.extra["mean_a"] == round((2.0 + 2.0) / 7, 3)


@pytest.mark.parametrize(
    "spelling", ["ER-alpha protein", "ER alpha", "ERα", "estrogen receptor alpha protein", "er_alpha"]
)
def test_measure_spellings(mini_release, spelling):
    f = run(compare_claim(measure=spelling), load_release(mini_release))
    assert f.value == pytest.approx(1 / 3 + 0.5)


def test_mini_swapped_groups(mini_release):
    f = run(compare_claim(a="ER-negative", b="ER-positive"), load_release(mini_release))
    assert f.value == pytest.approx(-(1 / 3 + 0.5))
    assert (f.extra["n_a"], f.extra["n_b"]) == (1, 6)


def test_mini_her2_groups_are_not_in_the_mini_clinical_file(mini_release):
    claim = compare_claim(measure="HER2 protein", a="HER2-positive", b="HER2-negative")
    with pytest.raises(CannotCheck):
        run(claim, load_release(mini_release))


def test_mini_code_snippet_reproduces_the_difference(mini_release):
    r = load_release(mini_release)
    f = run(compare_claim(), r)
    scope = {"r": r}
    exec(f.code, scope)
    assert scope["difference"] == pytest.approx(f.value)


def test_unknown_measure_cannot_be_checked(mini_release):
    with pytest.raises(CannotCheck, match="this release has no blood pressure measurement"):
        run(compare_claim(measure="blood pressure"), load_release(mini_release))


def test_missing_measure_or_unknown_group_cannot_be_checked(mini_release):
    r = load_release(mini_release)
    with pytest.raises(CannotCheck):
        run(compare_claim(measure=None), r)
    with pytest.raises(CannotCheck):
        run(compare_claim(a="ER-sideways"), r)


def test_protein_file_without_the_row_cannot_be_checked(mini_release):
    r = load_release(mini_release)
    r = dataclasses.replace(r, protein=r.protein.drop(index="ERALPHA"))
    with pytest.raises(CannotCheck, match="no ER-alpha protein measurement"):
        run(compare_claim(), r)


def test_group_with_no_samples_cannot_be_checked(mini_release):
    r = load_release(mini_release)
    r = dataclasses.replace(r, protein=r.protein[["TCGA-AA-0001-01", "TCGA-AA-0002-01"]])  # no Negative
    with pytest.raises(CannotCheck):
        run(compare_claim(), r)


def test_judge_end_to_end_on_mini(mini_release):
    f = run(compare_claim(), load_release(mini_release))
    assert judge(compare_claim("higher"), f)[0] == Verdict.SUPPORTED
    assert judge(compare_claim("lower"), f)[0] == Verdict.CONTRADICTED


ER_POSITIVE_SPELLINGS = [
    "ER-positive", "estrogen receptor positive", "estrogen-receptor-positive", "ER+", "ER\uff0b",
    "ER-pos", "ER positive", "ER-positive tumors", "ER-positive tumours", "Estrogen Receptor-Positive",
]
ER_NEGATIVE_SPELLINGS = [
    "ER-negative", "estrogen receptor negative", "estrogen-receptor-negative", "ER-neg", "ER negative",
    "ER\u2212", "ER-", "ER neg", "ER-negative tumors", "Estrogen Receptor-Negative",
]
ER_MEASURE_SPELLINGS = [
    "ER-alpha protein levels", "ER alpha protein expression", "ER\u03b1 protein", "estrogen receptor alpha", "ER-alpha protein expression level", "ERalpha",
]


@pytest.mark.parametrize("positive", ER_POSITIVE_SPELLINGS)
@pytest.mark.parametrize("negative", ER_NEGATIVE_SPELLINGS)
def test_er_group_spellings_resolve_to_the_right_side(mini_release, positive, negative):
    r = load_release(mini_release)
    f = run(compare_claim(a=positive, b=negative), r)
    assert (f.extra["n_a"], f.extra["n_b"]) == (6, 1)
    g = run(compare_claim(a=negative, b=positive), r)
    assert (g.extra["n_a"], g.extra["n_b"]) == (1, 6)


@pytest.mark.parametrize("measure", ER_MEASURE_SPELLINGS)
def test_er_measure_spellings_are_flexible(mini_release, measure):
    f = run(compare_claim(measure=measure), load_release(mini_release))
    assert f.value == pytest.approx(1 / 3 + 0.5)


def test_missing_er_group_is_the_opposite_of_the_other_in_any_spelling(mini_release):
    r = load_release(mini_release)
    f = run(compare_claim(a="estrogen receptor positive", b=None), r)
    assert (f.extra["n_a"], f.extra["n_b"]) == (6, 1)
    f = run(compare_claim(a=None, b="ER\u2212"), r)
    assert (f.extra["n_a"], f.extra["n_b"]) == (6, 1)


@pytest.mark.parametrize("bad", ["ER-sideways", "ER", "estrogen", "HER2-positive", "positive", "negative", "neg"])
def test_unmatched_er_group_names_still_cannot_be_checked(mini_release, bad):
    with pytest.raises(CannotCheck):
        run(compare_claim(a=bad), load_release(mini_release))


@pytest.mark.parametrize("bad", ["ER-beta protein", "estrogen receptor beta", "progesterone receptor", "ER", "protein"])
def test_unmatched_er_measure_names_still_cannot_be_checked(mini_release, bad):
    with pytest.raises(CannotCheck, match="this release has no"):
        run(compare_claim(measure=bad), load_release(mini_release))


# The mini clinical file has no HER2 status column, so HER2 names are checked by their error: a
# recognised name reaches the "no status" error, an unrecognised one the "no ... grouping" error.
@pytest.mark.parametrize("measure", ["HER2 protein expression", "HER2 protein", "HER2/neu protein", "HER2 protein levels"])
@pytest.mark.parametrize("a, b", [("HER2-positive", "HER2-negative"), ("HER2+", "HER2-"), ("HER2 neg", "HER2 pos"),
                                  ("HER2-positive tumors", "HER2 negative")])
def test_her2_names_are_recognised(mini_release, measure, a, b):
    with pytest.raises(CannotCheck, match="status for its samples"):
        run(compare_claim(measure=measure, a=a, b=b), load_release(mini_release))


def test_er_group_does_not_match_a_her2_measure(mini_release):
    with pytest.raises(CannotCheck, match="no ER-positive grouping|no .* grouping"):
        run(compare_claim(measure="HER2 protein", a="ER-positive", b="ER-negative"), load_release(mini_release))

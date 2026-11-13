import numpy as np
import pandas as pd
import pytest

from second_opinion.model import Claim, ClaimParams, ClaimType, SkepticResult
from second_opinion.release import load_release
from second_opinion.skeptic import leave_one_site_out, shuffle_test, skeptic_for


def _groups(n_a, n_b):
    return pd.Series(["pos"] * n_a + ["neg"] * n_b)


def test_clear_difference_has_small_p():
    rng = np.random.default_rng(1)
    values = pd.Series(np.concatenate([rng.normal(3, 1, 60), rng.normal(0, 1, 60)]))
    assert shuffle_test(values, _groups(60, 60)) < 0.05


def test_identical_groups_have_large_p():
    values = pd.Series([1.0, 2.0, 3.0, 4.0] * 20)
    groups = pd.Series(["a", "a", "b", "b", "b", "b", "a", "a"] * 10)
    assert shuffle_test(values, groups) > 0.2


def test_p_uses_plus_one_smoothing():
    values = pd.Series([10.0] * 30 + [0.0] * 30)
    assert shuffle_test(values, _groups(30, 30), n=99) == pytest.approx(1 / 100)


def test_fixed_seed_is_repeatable():
    rng = np.random.default_rng(2)
    values = pd.Series(rng.normal(0, 1, 50))
    groups = _groups(25, 25)
    assert shuffle_test(values, groups, seed=7) == shuffle_test(values, groups, seed=7)


def test_shuffle_needs_two_groups():
    with pytest.raises(ValueError):
        shuffle_test(pd.Series([1.0, 2.0]), pd.Series(["a", "a"]))


def test_one_site_drives_the_effect():
    # Sites S1-S3: no difference. Site S4: a huge one that makes the overall difference positive.
    values, groups, sites = [], [], []
    for site in ("S1", "S2", "S3"):
        values += [0.0, 0.0, 0.2, 0.2]
        groups += ["a", "a", "b", "b"]
        sites += [site] * 4
    values += [10.0, 10.0, 0.0, 0.0]
    groups += ["a", "a", "b", "b"]
    sites += ["S4"] * 4
    flips = leave_one_site_out(pd.Series(values), pd.Series(groups), pd.Series(sites))
    assert flips == ["S4"]


def test_no_site_flips_a_consistent_effect():
    values = pd.Series([2.0, 2.1, 0.0, 0.1] * 3)
    groups = pd.Series(["a", "a", "b", "b"] * 3)
    sites = pd.Series(["S1"] * 4 + ["S2"] * 4 + ["S3"] * 4)
    assert leave_one_site_out(values, groups, sites) == []


def test_site_holding_all_of_one_group_is_not_a_flip():
    # Dropping S2 leaves no "b" samples: no difference to compare, so it is not reported as a flip.
    values = pd.Series([1.0, 1.0, 0.0, 0.0])
    groups = pd.Series(["a", "a", "b", "b"])
    sites = pd.Series(["S1", "S1", "S2", "S2"])
    assert leave_one_site_out(values, groups, sites) == []


def _er_claim():
    return Claim(
        "C1", "ER-alpha protein is higher in ER-positive tumors.", 0, ClaimType.COMPARISON,
        ClaimParams(direction="higher", measure="ER-alpha protein", group_a="ER-positive", group_b="ER-negative"),
    )


def test_skeptic_for_a_comparison(mini_release):
    result = skeptic_for(_er_claim(), load_release(mini_release))
    assert isinstance(result, SkepticResult)
    assert 0 < result.shuffle_p <= 1
    assert result.n_sites >= 1
    assert isinstance(result.site_flips, list)


def test_skeptic_for_other_claim_types_is_none(mini_release):
    claim = Claim("C1", "x", 0, ClaimType.COUNT, ClaimParams(stated_value=10, subject="primary_tumors"))
    assert skeptic_for(claim, load_release(mini_release)) is None


def test_skeptic_for_an_unknown_measure_is_none(mini_release):
    claim = _er_claim()
    claim.params.measure = "PTEN protein"
    assert skeptic_for(claim, load_release(mini_release)) is None


def test_skeptic_runs_inside_the_audit(mini_release):
    from second_opinion.audit import audit_claims

    result = audit_claims([_er_claim()], mini_release)
    assert result.claims[0].skeptic is not None


@pytest.mark.realdata
def test_er_alpha_difference_survives_shuffling(release_dir):
    result = skeptic_for(_er_claim(), load_release(release_dir))
    assert result.shuffle_p < 0.01
    assert result.n_sites > 10

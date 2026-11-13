import pytest

from second_opinion.model import Claim, ClaimParams, ClaimType, Fact, Verdict
from second_opinion.verdict import format_fact, judge


def make_fact(num, den, value=None, **kw):
    if value is None:
        value = round(100 * num / den, 1) if den else num
    return Fact(label="x", value=value, numerator=num, denominator=den,
                sample_ids=[], files=[], code="", **kw)


def make_claim(ctype, **params):
    return Claim(id="C1", text="t", sentence_index=0, type=ctype, params=ClaimParams(**params))


@pytest.mark.parametrize("params, num, den, expected", [
    (dict(stated_value=62, unit="percent", approximate=True), 421, 844, Verdict.CONTRADICTED),
    (dict(stated_value=50, unit="percent", approximate=True), 421, 844, Verdict.SUPPORTED),
    (dict(stated_value=49.9, unit="percent", decimals=1), 421, 844, Verdict.SUPPORTED),
    (dict(stated_value=50.0, unit="percent", decimals=1), 421, 844, Verdict.CONTRADICTED),
    (dict(stated_value=50, unit="percent"), 421, 844, Verdict.SUPPORTED),
    (dict(stated_value=45, stated_high=55, unit="percent"), 421, 844, Verdict.SUPPORTED),
    (dict(stated_value=55, stated_high=65, unit="percent"), 421, 844, Verdict.CONTRADICTED),
    (dict(stated_value=535, unit="count", stated_total=1101), 535, 1101, Verdict.SUPPORTED),
    (dict(stated_value=540, unit="count", stated_total=1101), 535, 1101, Verdict.CONTRADICTED),
    (dict(stated_value=540, unit="count", approximate=True), 535, 1101, Verdict.SUPPORTED),
    (dict(stated_value=600, unit="count", approximate=True), 535, 1101, Verdict.CONTRADICTED),
    (dict(stated_value=535, unit="count", stated_total=1200), 535, 1101, Verdict.CONTRADICTED),
    (dict(stated_value=540, unit="count", stated_total=1101, approximate=True), 535, 1101,
     Verdict.SUPPORTED),
])
def test_judge(params, num, den, expected):
    ctype = ClaimType.COUNT if params["unit"] == "count" else ClaimType.SHARE
    verdict, correct = judge(make_claim(ctype, **params), make_fact(num, den))
    assert verdict == expected
    assert (correct is None) == (expected == Verdict.SUPPORTED)


def test_contradicted_returns_correct_value():
    claim = make_claim(ClaimType.SHARE, stated_value=62, unit="percent", approximate=True)
    assert judge(claim, make_fact(421, 844)) == (Verdict.CONTRADICTED, "49.9% (421 of 844)")


def test_contradicted_count_correct_value():
    claim = make_claim(ClaimType.COUNT, stated_value=540, unit="count", stated_total=1101)
    assert judge(claim, make_fact(535, 1101))[1] == "535 of 1,101"


def test_comparison_direction():
    claim = make_claim(ClaimType.COMPARISON, direction="higher", group_a="ER-positive")
    assert judge(claim, make_fact(None, None, value=3.051)) == (Verdict.SUPPORTED, None)
    fact = make_fact(None, None, value=-0.2, extra={"n_a": 169, "n_b": 529})
    verdict, correct = judge(claim, fact)
    assert verdict == Verdict.CONTRADICTED
    assert correct == "ER-positive mean is lower: difference -0.2 (169 vs 529 samples)"


def test_comparison_lower_and_zero():
    lower = make_claim(ClaimType.COMPARISON, direction="lower")
    assert judge(lower, make_fact(None, None, value=-1.0))[0] == Verdict.SUPPORTED
    assert judge(lower, make_fact(None, None, value=1.0))[0] == Verdict.CONTRADICTED
    assert judge(lower, make_fact(None, None, value=0.0))[0] == Verdict.CONTRADICTED


def test_coverage_claim_with_missing_samples_is_contradicted():
    claim = make_claim(ClaimType.COVERAGE, unit="all")
    verdict, correct = judge(claim, make_fact(535, 1101))
    assert verdict == Verdict.CONTRADICTED
    assert correct == "535 of 1,101 primary tumors have it; 566 are missing"


def test_coverage_complete_is_supported():
    claim = make_claim(ClaimType.COVERAGE, unit="all")
    assert judge(claim, make_fact(1101, 1101)) == (Verdict.SUPPORTED, None)


@pytest.mark.parametrize("ctype", [ClaimType.NOT_ANSWERABLE, ClaimType.UNMAPPED])
def test_unjudgeable_types_raise(ctype):
    with pytest.raises(ValueError):
        judge(make_claim(ctype), make_fact(1, 2))


def test_missing_value_raises():
    claim = make_claim(ClaimType.SHARE, stated_value=50, unit="percent")
    fact = Fact(label="x", value=None, numerator=None, denominator=None,
                sample_ids=[], files=[], code="")
    with pytest.raises(ValueError):
        judge(claim, fact)


def test_format_fact():
    assert format_fact(make_fact(421, 844), "percent") == "49.9% (421 of 844)"
    assert format_fact(make_fact(535, 1101), "count") == "535 of 1,101"


# --- review fixes: half-up display, strict ranges, decimals inference, tolerance edges ---

def test_format_fact_rounds_percent_half_up_on_exact_fraction():
    # 1 of 16 = 6.25% exactly; fact.value is the half-even float 6.2, display must be half-up
    assert format_fact(make_fact(1, 16), "percent") == "6.3% (1 of 16)"
    assert format_fact(make_fact(1, 16, value=6.2), "percent") == "6.3% (1 of 16)"
    assert format_fact(make_fact(1, 8), "percent") == "12.5% (1 of 8)"


def test_format_fact_percent_without_counts_uses_half_up_on_value():
    fact = make_fact(None, None, value=6.25)
    assert format_fact(fact, "percent") == "6.3%"


def test_judge_and_display_agree_on_exact_tie():
    stated_low = make_claim(ClaimType.SHARE, stated_value=6.2, unit="percent", decimals=1)
    verdict, correct = judge(stated_low, make_fact(1, 16))
    assert verdict == Verdict.CONTRADICTED
    assert correct == "6.3% (1 of 16)"
    stated_ok = make_claim(ClaimType.SHARE, stated_value=6.3, unit="percent", decimals=1)
    assert judge(stated_ok, make_fact(1, 16)) == (Verdict.SUPPORTED, None)


@pytest.mark.parametrize("stated_low, stated_high, num, den, expected", [
    (55, 65, 546, 1000, Verdict.CONTRADICTED),   # 54.6 rounds to 55 but is outside the range
    (55, 65, 550, 1000, Verdict.SUPPORTED),      # lower edge, inclusive
    (55, 65, 650, 1000, Verdict.SUPPORTED),      # upper edge, inclusive
    (55, 65, 654, 1000, Verdict.CONTRADICTED),   # 65.4 rounds to 65 but is outside
    (55, 65, 600, 1000, Verdict.SUPPORTED),
])
def test_percent_range_is_strict_on_unrounded_value(stated_low, stated_high, num, den, expected):
    claim = make_claim(ClaimType.SHARE, stated_value=stated_low, stated_high=stated_high,
                       unit="percent")
    verdict, correct = judge(claim, make_fact(num, den))
    assert verdict == expected
    assert (correct is None) == (expected == Verdict.SUPPORTED)


@pytest.mark.parametrize("stated, decimals, num, den, expected", [
    (49.9, None, 421, 844, Verdict.SUPPORTED),     # inferred 1 decimal; 49.88 -> 49.9
    (50.0, None, 421, 844, Verdict.SUPPORTED),     # integer-valued -> 0 decimals; 49.88 -> 50
    (62.0, None, 421, 844, Verdict.CONTRADICTED),
    (49.8, None, 421, 844, Verdict.CONTRADICTED),
    (7.25, None, 29, 400, Verdict.SUPPORTED),      # inferred 2 decimals
    (7.2, None, 29, 400, Verdict.CONTRADICTED),    # inferred 1 decimal; 7.25 -> 7.3
    (50.0, 1, 421, 844, Verdict.CONTRADICTED),     # explicit decimals always wins
    (49.9, 0, 421, 844, Verdict.CONTRADICTED),     # explicit 0 wins over inference from 49.9
])
def test_decimals_inferred_when_missing(stated, decimals, num, den, expected):
    claim = make_claim(ClaimType.SHARE, stated_value=stated, unit="percent", decimals=decimals)
    assert judge(claim, make_fact(num, den))[0] == expected


@pytest.mark.parametrize("stated, expected", [
    (52.0, Verdict.SUPPORTED),     # exactly 2.0 points above 50.0
    (48.0, Verdict.SUPPORTED),     # exactly 2.0 points below
    (52.01, Verdict.CONTRADICTED),
    (47.99, Verdict.CONTRADICTED),
])
def test_approximate_percent_boundary(stated, expected):
    claim = make_claim(ClaimType.SHARE, stated_value=stated, unit="percent", approximate=True)
    assert judge(claim, make_fact(500, 1000))[0] == expected


@pytest.mark.parametrize("stated, expected", [
    (1020, Verdict.SUPPORTED),     # exactly 2% of OUR 1000
    (980, Verdict.SUPPORTED),
    (1021, Verdict.CONTRADICTED),
    (979, Verdict.CONTRADICTED),
])
def test_approximate_count_boundary(stated, expected):
    claim = make_claim(ClaimType.COUNT, stated_value=stated, unit="count", approximate=True)
    assert judge(claim, make_fact(1000, 2000))[0] == expected

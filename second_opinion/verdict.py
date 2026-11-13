"""Verdict rules: given a claim and the Fact we computed, decide supported or contradicted.

Tolerance rules (Global Constraints): an exact number is supported if it equals ours after
rounding to the report's own precision; an approximate one is supported within 2 percentage
points (shares) or 2% of the count (counts). Anything else is contradicted.
"""

from decimal import ROUND_HALF_UP, Decimal

from second_opinion.model import Claim, ClaimType, Fact, Verdict

PERCENT_TOLERANCE_POINTS = Decimal("2")
COUNT_TOLERANCE_FRACTION = Decimal("0.02")
_EPS = 1e-9


def _num(n: float) -> str:
    return f"{n:,.0f}" if float(n).is_integer() else f"{n:,}"


def format_fact(fact: Fact, unit: str | None) -> str:
    """'49.9% (421 of 844)' for percents, '535 of 1,101' for counts."""
    has_counts = fact.numerator is not None and fact.denominator is not None
    if unit == "percent":
        if fact.value is None:
            raise ValueError("fact has no value to format")
        text = f"{_round_half_up(_percent(fact), 1):.1f}%"
        return f"{text} ({fact.numerator:,} of {fact.denominator:,})" if has_counts else text
    # counts (and anything else): numerator with its denominator
    numerator = fact.numerator if fact.numerator is not None else fact.value
    if numerator is None:
        raise ValueError("fact has no value to format")
    if fact.denominator is not None:
        return f"{_num(numerator)} of {fact.denominator:,}"
    return _num(numerator)


def _dec(x: float) -> Decimal:
    """Exact decimal for a float as written (repr), so 49.9 is 49.9 and not 49.89999..."""
    return Decimal(repr(x))


def _round_half_up(x: Decimal | float, decimals: int) -> Decimal:
    value = x if isinstance(x, Decimal) else _dec(float(x))
    return value.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def _percent(fact: Fact) -> Decimal:
    """Our percent, exact when the counts are known, so ties round the same way everywhere."""
    if fact.numerator is not None and fact.denominator:
        return Decimal(100) * _dec(fact.numerator) / _dec(fact.denominator)
    if fact.value is None:
        raise ValueError("fact has no value")
    return _dec(float(fact.value))


def _infer_decimals(stated: float) -> int:
    """Digits after the point as written: 62.0 -> 0, 49.9 -> 1, 7.25 -> 2."""
    if float(stated).is_integer():
        return 0
    exponent = _dec(float(stated)).as_tuple().exponent
    return max(0, -exponent)


def _unit(claim: Claim) -> str:
    unit = claim.params.unit
    if unit:
        return unit
    if claim.type == ClaimType.COUNT:
        return "count"
    if claim.type in (ClaimType.SHARE, ClaimType.AGREEMENT):
        return "percent"
    raise ValueError(f"claim {claim.id} has no unit")


def _judge_percent(claim: Claim, fact: Fact) -> bool:
    p = claim.params
    ours = _percent(fact)
    stated = _dec(p.stated_value)
    if p.stated_high is not None:
        # strict: our unrounded value must lie inside the range
        return stated <= ours <= _dec(p.stated_high)
    if p.approximate:
        return abs(ours - stated) <= PERCENT_TOLERANCE_POINTS
    decimals = p.decimals if p.decimals is not None else _infer_decimals(p.stated_value)
    return _round_half_up(ours, decimals) == stated


def _judge_count(claim: Claim, fact: Fact) -> bool:
    p = claim.params
    ours = fact.numerator if fact.numerator is not None else fact.value
    if p.stated_total is not None:
        if fact.denominator is None:
            raise ValueError("fact has no denominator to compare with the stated total")
        if abs(fact.denominator - p.stated_total) > _EPS:
            return False
    if p.stated_high is not None:
        return p.stated_value - _EPS <= ours <= p.stated_high + _EPS
    if p.approximate:
        return abs(_dec(ours) - _dec(p.stated_value)) <= COUNT_TOLERANCE_FRACTION * abs(_dec(ours))
    return abs(ours - p.stated_value) < _EPS


def _judge_comparison(claim: Claim, fact: Fact) -> tuple[Verdict, str | None]:
    p = claim.params
    if p.direction not in ("higher", "lower"):
        raise ValueError(f"claim {claim.id} has no direction")
    ok = fact.value != 0 and (fact.value > 0) == (p.direction == "higher")
    if ok:
        return Verdict.SUPPORTED, None
    group = p.group_a or "Group A"
    diff = f"{round(fact.value, 3):g}"
    if fact.value == 0:
        text = f"{group} mean is the same: difference {diff}"
    else:
        actual = "higher" if fact.value > 0 else "lower"
        text = f"{group} mean is {actual}: difference {diff}"
    n_a, n_b = fact.extra.get("n_a"), fact.extra.get("n_b")
    if n_a is not None and n_b is not None:
        text += f" ({int(n_a):,} vs {int(n_b):,} samples)"
    return Verdict.CONTRADICTED, text


def _judge_coverage(fact: Fact) -> tuple[Verdict, str | None]:
    if fact.numerator is None or fact.denominator is None:
        raise ValueError("coverage claim needs numerator and denominator")
    if fact.numerator == fact.denominator:
        return Verdict.SUPPORTED, None
    missing = fact.denominator - fact.numerator
    return Verdict.CONTRADICTED, (
        f"{fact.numerator:,} of {fact.denominator:,} primary tumors have it; "
        f"{missing:,} are missing"
    )


def judge(claim: Claim, fact: Fact) -> tuple[Verdict, str | None]:
    """Return (verdict, correct_value). correct_value is set only when contradicted."""
    if claim.type in (ClaimType.NOT_ANSWERABLE, ClaimType.UNMAPPED):
        raise ValueError(f"{claim.type.value} claims are not judged here; route them separately")
    if fact.value is None:
        raise ValueError(f"fact for claim {claim.id} has no value")

    if claim.type == ClaimType.COMPARISON:
        return _judge_comparison(claim, fact)

    unit = _unit(claim)
    if unit == "all":
        return _judge_coverage(fact)
    if claim.params.stated_value is None:
        raise ValueError(f"claim {claim.id} has no stated value")

    ok = _judge_percent(claim, fact) if unit == "percent" else _judge_count(claim, fact)
    if ok:
        return Verdict.SUPPORTED, None
    return Verdict.CONTRADICTED, format_fact(fact, unit)

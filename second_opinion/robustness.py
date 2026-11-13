"""Robustness: redo a claim's check under all eight "count it differently" variants."""

from dataclasses import fields

from second_opinion.checks import CHECKS, CannotCheck
from second_opinion.model import Claim, Solidity, Verdict, VariantResult
from second_opinion.release import Release
from second_opinion.variants import PRIMARY_VARIANT, Variant, all_variants
from second_opinion.verdict import judge


def _run_one(claim: Claim, release: Release, variant: Variant) -> VariantResult:
    check = CHECKS.get(claim.type)
    if check is None:
        return VariantResult(variant.id, None, None)
    try:
        fact = check(claim, release, variant)
        verdict, _ = judge(claim, fact)
    except (CannotCheck, ValueError):
        return VariantResult(variant.id, None, None)
    except Exception:  # noqa: BLE001 - a variant that cannot run gives no verdict, never an error
        return VariantResult(variant.id, None, None)
    return VariantResult(variant.id, fact, verdict)


def run_variants(claim: Claim, release: Release) -> list[VariantResult]:
    """One VariantResult per variant, in `all_variants()` order; uncheckable ones carry None."""
    return [_run_one(claim, release, v) for v in all_variants()]


def _differing_choices(variant_id: str) -> list[str]:
    """The choices (as "field=value") where this variant departs from PRIMARY_VARIANT."""
    values = variant_id.split("|")
    names = [f.name for f in fields(Variant)]
    return [
        f"{name}={value}"
        for name, value in zip(names, values)
        if value != getattr(PRIMARY_VARIANT, name)
    ]


def solidity_of(variants: list[VariantResult], primary: Verdict) -> tuple[Solidity, list[str]]:
    """HOLDS_EVERYWHERE if every variant that gave a verdict agrees with `primary`, else FRAGILE.

    The flips name the choices that differ from the primary variant in each disagreeing variant
    (joined with " + " when several differ); single-choice flips come first.
    """
    judged = [v for v in variants if v.verdict is not None]
    if not judged:
        return Solidity.NOT_APPLICABLE, []
    flipped = [_differing_choices(v.variant_id) for v in judged if v.verdict != primary]
    if not flipped:
        return Solidity.HOLDS_EVERYWHERE, []
    flips: list[str] = []
    for choices in sorted((c for c in flipped if c), key=len):  # stable: keeps variant order
        text = " + ".join(choices)
        if text not in flips:
            flips.append(text)
    return Solidity.FRAGILE, flips

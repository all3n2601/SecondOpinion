"""SHARE claims: share of one subtype among samples that have a subtype call."""

from second_opinion.checks.base import CannotCheck
from second_opinion.checks.population import population, population_code, population_noun, subtype_column
from second_opinion.model import Claim, Fact
from second_opinion.release import RELEASE_FILES, Release
from second_opinion.variants import Variant, normalise_subtype

_SUBTYPES = ("Luminal A", "Luminal B", "HER2-enriched", "Basal-like", "Normal-like")
_SOURCE_WORDS = {
    "rna_call": "PAM50 RNA-seq subtype call",
    "study_2012_label": "2012 study PAM50 subtype label",
}


def check_share(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Denominator = samples in the population that HAVE a call; unknown_count = those with none."""
    if claim.params.attribute:  # "77% are ER-positive", "TP53 is mutated in a third of tumors"
        from second_opinion.checks.attribute import check_attribute_share

        return check_attribute_share(claim, release, variant)
    if not claim.params.subtype:
        raise CannotCheck("claim names no subtype")
    subtype = normalise_subtype(claim.params.subtype)
    if subtype not in _SUBTYPES:
        raise CannotCheck(f"this release has no '{claim.params.subtype}' subtype")
    col = subtype_column(variant)
    if col not in release.clinical.columns:
        raise CannotCheck(f"this release's clinical file has no {col} column")

    pop = population(release, variant)
    called = pop[pop[col].notna()]
    hit = called[called[col].map(normalise_subtype) == subtype]
    unknown = len(pop) - len(called)

    code = (
        "from second_opinion.variants import normalise_subtype\n"
        + population_code(variant)
        + f'\ncalled = pop[pop["{col}"].notna()]'
        + f'\nhit = called[called["{col}"].map(normalise_subtype) == "{subtype}"]'
        + "\nn, total = len(hit), len(called)\nn_no_call = len(pop) - len(called)\npercent = 100 * n / total"
    )
    extra: dict[str, float | int | str] = {}
    if pop.attrs.get("excluded_unknown_sex"):
        extra["excluded_unknown_sex"] = pop.attrs["excluded_unknown_sex"]
    return Fact(
        label=f"{population_noun(variant)} with a {_SOURCE_WORDS[variant.subtype_source]} that are {subtype}",
        value=(100 * len(hit) / len(called)) if len(called) else None,
        numerator=len(hit), denominator=len(called),
        sample_ids=called["sampleID"].astype(str).tolist(),
        files=[RELEASE_FILES["clinical"]], code=code, unknown_count=unknown, extra=extra,
    )

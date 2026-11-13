"""COVERAGE claims: "every primary tumor has <layer>"."""

from dataclasses import replace

from second_opinion.checks.base import CannotCheck
from second_opinion.checks.population import population, population_code
from second_opinion.model import Claim, Fact
from second_opinion.release import RELEASE_FILES, RNA_FILE, Release
from second_opinion.variants import Variant

_LAYER_BY_SUBJECT = {
    "has_protein": "protein",
    "has_survival": "survival",
    "has_mutation": "mutation",
    "has_copy_number": "copy_number",
    "has_rna": "rna",
}
_LAYER_WORDS = {
    "protein": "protein (RPPA) data",
    "survival": "survival data",
    "mutation": "mutation data",
    "copy_number": "copy-number data",
    "rna": "RNA expression data",
}


def check_coverage(claim: Claim, release: Release, variant: Variant) -> Fact:
    """numerator = primary tumors that have the layer, denominator = primary tumors, sample_ids = the MISSING ones."""
    layer = _LAYER_BY_SUBJECT.get(claim.params.subject or "")
    if layer is None:
        raise CannotCheck(f"cannot check coverage of {claim.params.subject!r}")
    if layer == "rna" and release.rna_ids is None:
        raise CannotCheck("no RNA file in this release")

    scoped = replace(variant, sample_scope="primary_tumors")
    noun = "female primary tumors" if variant.sex_filter == "women_only" else "primary tumors"
    files_extra: list[str] = []
    if claim.params.within_attribute:  # "Protein data covers most triple-negative tumors"
        from second_opinion.checks.attribute import scoped as scoped_population

        pop, group_code, noun = scoped_population(claim, release, scoped)
        code_start = group_code
    else:
        pop = population(release, scoped)
        code_start = population_code(scoped)
    primary = pop["sampleID"].astype(str).tolist()
    have_ids = release.layer_ids(layer)
    missing = [i for i in primary if i not in have_ids]
    have = len(primary) - len(missing)

    code = (
        code_start
        + "\nprimary = pop.sampleID.tolist()"
        + f"\nmissing = [s for s in primary if s not in r.{layer}_ids]"
        + "\nn, total = len(primary) - len(missing), len(primary)"
    )
    if not primary and claim.params.within_attribute:
        raise CannotCheck(f"this release has no {noun}")
    extra: dict[str, float | int | str] = {"missing_count": len(missing)}
    if pop.attrs.get("excluded_unknown_sex"):
        extra["excluded_unknown_sex"] = pop.attrs["excluded_unknown_sex"]
    return Fact(
        label=f"{noun} that have {_LAYER_WORDS[layer]}",
        value=(100 * have / len(primary)) if primary else None,
        numerator=have, denominator=len(primary), sample_ids=missing,
        files=[RELEASE_FILES["clinical"], RNA_FILE if layer == "rna" else RELEASE_FILES[layer]],
        code=code, extra=extra,
    )

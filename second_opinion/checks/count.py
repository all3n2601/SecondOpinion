"""COUNT claims: how many primary tumors / samples / patients / samples with all layers."""

from dataclasses import replace

from second_opinion.checks.base import CannotCheck
from second_opinion.checks.population import population, population_code
from second_opinion.model import Claim, Fact
from second_opinion.release import RELEASE_FILES, RNA_FILE, Release
from second_opinion.variants import Variant

_CLINICAL = RELEASE_FILES["clinical"]
_NO_RNA_NOTE = "no RNA file in this release; counted four layers"


def check_count(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Subject sets its own sample scope; only the variant's sex filter is applied."""
    subject = claim.params.subject
    if subject == "all_five_layers":
        return _all_layers(release, variant)
    if subject in ("primary_tumors", "samples", "patients"):
        scope = "primary_tumors" if subject == "primary_tumors" else "all_samples"
        pop = population(release, replace(variant, sample_scope=scope))
        ids = pop["sampleID"].astype(str).tolist()
        code = population_code(replace(variant, sample_scope=scope))
        if subject == "patients":
            patients = sorted({i[:12] for i in ids})
            label = "patients with at least one sample"
            code += "\npatients = pop.sampleID.str[:12].unique()\nn = len(patients)"
            ids, value = patients, len(patients)
        else:
            label = "primary tumors" if subject == "primary_tumors" else "samples (all sample types)"
            code += "\nn = len(pop)"
            value = len(ids)
        if variant.sex_filter == "women_only":
            label = "female " + label
        return Fact(
            label=label, value=value, numerator=value, denominator=None,
            sample_ids=ids, files=[_CLINICAL], code=code,
            extra=_sex_extra(pop),
        )
    raise CannotCheck(f"cannot count {subject!r}")


def _sex_extra(pop) -> dict[str, float | int | str]:
    excluded = pop.attrs.get("excluded_unknown_sex", 0)
    return {"excluded_unknown_sex": excluded} if excluded else {}


def _all_layers(release: Release, variant: Variant) -> Fact:
    pop = population(release, replace(variant, sample_scope="primary_tumors"))
    primary = pop["sampleID"].astype(str).tolist()
    layers = ["survival", "mutation", "copy_number", "protein"]
    files = [_CLINICAL, *(RELEASE_FILES[x] for x in layers)]
    has_rna = release.rna_ids is not None
    if has_rna:
        layers.append("rna")
        files.append(RNA_FILE)
    have_ids = set(primary)
    for layer in layers:
        have_ids &= release.layer_ids(layer)
    have = [i for i in primary if i in have_ids]

    code = population_code(replace(variant, sample_scope="primary_tumors"))
    code += "\nprimary = pop.sampleID.tolist()\nhave = set(primary)"
    code += "".join(f"\nhave &= r.{layer}_ids" if layer != "rna" else "\nhave &= r.rna_ids" for layer in layers)
    code += "\nn, total = len(have), len(primary)"

    extra: dict[str, float | int | str] = _sex_extra(pop)
    if not has_rna:
        extra["note"] = _NO_RNA_NOTE
    return Fact(
        label=f"primary tumors that have all {'five' if has_rna else 'four'} data layers",
        value=len(have), numerator=len(have), denominator=len(primary),
        sample_ids=have, files=files, code=code, extra=extra,
    )

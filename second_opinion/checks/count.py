"""COUNT claims: how many primary tumors / samples / patients / samples with all layers."""

from dataclasses import replace

from second_opinion.checks.base import CannotCheck
from second_opinion.checks.population import population, population_code
from second_opinion.model import Claim, Fact
from second_opinion.release import RELEASE_FILES, RNA_FILE, Release
from second_opinion.variants import Variant

_CLINICAL = RELEASE_FILES["clinical"]

# Sub-groups a count can name ("male_samples", "normal_tissue_primary_tumors", "male+normal_tissue_samples").
# Each is a pandas expression on the clinical rows `pop`, shown in Fact.code, plus a plain-words label.
_NOUNS = ("primary_tumors", "samples", "patients")
_FILTERS: dict[str, tuple[str, str, object]] = {
    "male": ("male", 'pop.gender == "MALE"', lambda pop: pop["gender"] == "MALE"),
    "female": ("female", 'pop.gender == "FEMALE"', lambda pop: pop["gender"] == "FEMALE"),
    "normal_tissue": ("normal-tissue", 'pop.sampleID.str[13:15] == "11"  # solid tissue normal',
                      lambda pop: pop["sampleID"].astype(str).str[13:15] == "11"),
    "metastatic": ("metastatic", 'pop.sampleID.str[13:15] == "06"  # metastasis',
                   lambda pop: pop["sampleID"].astype(str).str[13:15] == "06"),
}


def _split_subject(subject: str) -> tuple[list[str], str]:
    """"male+normal_tissue_samples" -> (["male", "normal_tissue"], "samples"); raises CannotCheck if unknown."""
    for noun in _NOUNS:
        if subject == noun or subject.endswith("_" + noun):
            names = subject[: -len(noun) - 1].split("+") if subject != noun else []
            unknown = [n for n in names if n not in _FILTERS]
            if unknown:
                raise CannotCheck(f"cannot count {subject!r}: no way to filter on {unknown[0]!r}")
            return names, noun
    raise CannotCheck(f"cannot count {subject!r}")
_NO_RNA_NOTE = "no RNA file in this release; counted four layers"


def check_count(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Subject sets its own sample scope; only the variant's sex filter is applied."""
    subject = claim.params.subject
    if subject == "all_five_layers":
        return _all_layers(release, variant)
    filters, noun = _split_subject(subject)
    scope = "primary_tumors" if noun == "primary_tumors" else "all_samples"
    pop = population(release, replace(variant, sample_scope=scope))
    code = population_code(replace(variant, sample_scope=scope))
    for name in filters:
        _, expression, keep = _FILTERS[name]
        pop = pop[keep(pop)]
        code += f"\npop = pop[{expression}]"
    ids = pop["sampleID"].astype(str).tolist()
    if noun == "patients":
        ids = sorted({i[:12] for i in ids})
        label = "patients with at least one sample"
        code += "\npatients = pop.sampleID.str[:12].unique()\nn = len(patients)"
    else:
        label = "primary tumors" if noun == "primary_tumors" else "samples (all sample types)"
        code += "\nn = len(pop)"
    label = " ".join([_FILTERS[n][0] for n in filters] + [label])
    if variant.sex_filter == "women_only":
        label = "female " + label
    return Fact(
        label=label, value=len(ids), numerator=len(ids), denominator=None,
        sample_ids=ids, files=[_CLINICAL], code=code, extra=_sex_extra(pop),
    )


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

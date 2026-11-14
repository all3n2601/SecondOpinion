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
_NOUNS = ("primary_tumors", "samples", "patients", "slides")
_SLIDE_FILTERS = {  # filter -> (words, test on slide_kind)
    "diagnostic": ("diagnostic (FFPE)", lambda kind: kind.str.lower().str.startswith("diagnostic")),
    "frozen": ("frozen-section", lambda kind: kind.str.lower().str.startswith("frozen")),
}
_FILTERS: dict[str, tuple[str, str, object]] = {
    "male": ("male", 'pop.gender == "MALE"', lambda pop: pop["gender"] == "MALE"),
    "female": ("female", 'pop.gender == "FEMALE"', lambda pop: pop["gender"] == "FEMALE"),
    "normal_tissue": ("normal-tissue", 'pop.sampleID.str[13:15] == "11"  # solid tissue normal',
                      lambda pop: pop["sampleID"].astype(str).str[13:15] == "11"),
    "unknown_sex": ("sex-unrecorded", "pop.gender.isna()  # no recorded sex", lambda pop: pop["gender"].isna()),
    "metastatic": ("metastatic", 'pop.sampleID.str[13:15] == "06"  # metastasis',
                   lambda pop: pop["sampleID"].astype(str).str[13:15] == "06"),
}


def _split_subject(subject: str) -> tuple[list[str], str]:
    """"male+normal_tissue_samples" -> (["male", "normal_tissue"], "samples"); raises CannotCheck if unknown."""
    for noun in _NOUNS:
        if subject == noun or subject.endswith("_" + noun):
            names = subject[: -len(noun) - 1].split("+") if subject != noun else []
            known = _SLIDE_FILTERS if noun == "slides" else _FILTERS
            unknown = [n for n in names if n not in known]
            if unknown:
                raise CannotCheck(f"cannot count {subject!r}: no way to filter on {unknown[0]!r}")
            return names, noun
    raise CannotCheck(f"cannot count {subject!r}")
_NO_RNA_NOTE = "no RNA file in this release; counted four layers"


def check_count(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Subject sets its own sample scope; only the variant's sex filter is applied."""
    if claim.params.attribute:  # "151 deaths", "164 HER2-positive tumors", "263 tumors carry a TP53 mutation"
        from second_opinion.checks.attribute import check_attribute_count

        return check_attribute_count(claim, release, variant)
    subject = claim.params.subject
    if subject == "all_five_layers":
        return _all_layers(release, variant)
    if subject and subject.startswith("layers:"):
        return _some_layers(release, variant, subject.split(":", 1)[1].split("+"))
    filters, noun = _split_subject(subject)
    if noun == "slides":
        return _slides(release, filters)
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


_LAYER_WORDS = {"survival": "survival", "mutation": "mutation", "copy_number": "copy-number", "rna": "RNA", "protein": "protein"}


def _some_layers(release: Release, variant: Variant, layers: list[str]) -> Fact:
    """Primary tumors that have every one of the named data layers ("both RNA and protein data")."""
    if "rna" in layers and release.rna_ids is None:
        raise CannotCheck("no RNA file in this release")
    pop = population(release, replace(variant, sample_scope="primary_tumors"))
    primary = pop["sampleID"].astype(str).tolist()
    have_ids = set(primary)
    for layer in layers:
        have_ids &= release.layer_ids(layer)
    have = [i for i in primary if i in have_ids]
    code = population_code(replace(variant, sample_scope="primary_tumors"))
    code += "\nhave = set(pop.sampleID)" + "".join(f"\nhave &= r.{layer}_ids" for layer in layers)
    code += "\nn, total = len(have), len(pop)"
    files = [_CLINICAL] + [RNA_FILE if layer == "rna" else RELEASE_FILES[layer] for layer in layers]
    return Fact(
        label="primary tumors that have " + " and ".join(_LAYER_WORDS[x] for x in layers) + " data",
        value=len(have), numerator=len(have), denominator=len(primary),
        sample_ids=have, files=files, code=code, extra=_sex_extra(pop),
    )


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


def _slides(release: Release, filters: list[str]) -> Fact:
    """Slides in the organizers' slide manifest, optionally of one kind (diagnostic / frozen)."""
    from second_opinion.release import SLIDE_MANIFEST

    slides = release.slides
    if slides is None:
        raise CannotCheck(f"this release folder has no {SLIDE_MANIFEST} (envelope releases ship without it), so slides cannot be counted")
    kind = slides["slide_kind"].astype(str)
    keep = kind.notna()
    code = f'slides = pd.read_csv("{SLIDE_MANIFEST}")'
    words = []
    for name in filters:
        label, test = _SLIDE_FILTERS[name]
        keep &= test(kind)
        words.append(label)
        code += f'\nslides = slides[slides.slide_kind.str.lower().str.startswith("{name}")]'
    code += "\nn = len(slides)"
    chosen = slides[keep.values]
    return Fact(
        label=" ".join(words + ["slides"]), value=len(chosen), numerator=len(chosen), denominator=None,
        sample_ids=sorted(chosen["sample_id"].astype(str).unique().tolist()), files=[SLIDE_MANIFEST], code=code,
    )

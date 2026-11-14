"""COMPARISON claims: difference between two group means of one protein measurement."""

import re
from dataclasses import replace

from second_opinion.checks.base import CannotCheck
from second_opinion.checks.population import population, population_code, population_noun
from second_opinion.model import Claim, Fact
from second_opinion.release import RELEASE_FILES, Release
from second_opinion.variants import Variant


_MINUS = "\u2212\u2012\u2013\u2014\u2010\u2011"  # unicode minus / dashes -> "-"
_PLUS = "\uff0b\u207a"  # fullwidth / superscript plus -> "+"
_NOISE_WORDS = {  # words that may follow a group or measure name without changing what it is
    "tumor", "tumors", "tumour", "tumours", "sample", "samples", "patient", "patients", "case", "cases",
    "cancer", "cancers", "group", "protein", "proteins", "level", "levels", "expression", "abundance",
    "measurement", "measurements", "rppa",
}
_SIGN_WORDS = {"positive": "Positive", "pos": "Positive", "negative": "Negative", "neg": "Negative"}


def _tokens(text: str) -> list[str]:
    """Lower-case words of `text`: unicode minus/plus unified, a trailing "+" / "-" spelt out, alpha spelt out."""
    text = text.strip().translate({ord(c): "-" for c in _MINUS} | {ord(c): "+" for c in _PLUS})
    text = text.replace("\u03b1", " alpha ").replace("\u0251", " alpha ")
    text = re.sub(r"\+\s*$", " positive", text)
    text = re.sub(r"-\s*$", " negative", text)
    return re.findall(r"[a-z0-9]+", text.lower())


# To support another measurement: add a row to _MEASURES (protein row, clinical status column, the
# names a claim may use for the receptor, and the names it may use for the measurement itself) and
# its group names to _GROUPS (clinical status value). Names are compared after normalising
# (lower-case, punctuation dropped, noise words such as "protein levels" / "tumors" removed).
_MEASURES: dict[str, dict] = {
    "ER-alpha protein": {
        "row": "ERALPHA",
        "status_column": "breast_carcinoma_estrogen_receptor_status",
        "receptor_names": ["ER", "estrogen receptor"],
        "measure_names": ["ER alpha", "estrogen receptor alpha", "ERALPHA", "ESR1"],
    },
    "HER2 protein": {
        "row": "HER2",
        "status_column": "lab_proc_her2_neu_immunohistochemistry_receptor_status",
        "receptor_names": ["HER2", "HER2/neu", "HER-2", "HER 2"],
        "measure_names": ["HER2", "HER2/neu", "HER-2", "HER 2"],
    },
}
_GROUPS: dict[str, dict[str, str]] = {  # measure -> {group name: clinical status value}
    "ER-alpha protein": {"ER-positive": "Positive", "ER-negative": "Negative"},
    "HER2 protein": {"HER2-positive": "Positive", "HER2-negative": "Negative"},
}


def _name_key(text: str) -> str:
    """Words of `text` without noise words, run together: "ER-alpha protein levels" -> "eralpha"."""
    return "".join(t for t in _tokens(text) if t not in _NOISE_WORDS)


_MEASURE_BY_KEY = {_name_key(n): name for name, m in _MEASURES.items() for n in m["measure_names"]}
_RECEPTOR_KEYS = {  # measure -> normalised receptor names
    name: {_name_key(n) for n in m["receptor_names"]} for name, m in _MEASURES.items()
}


def _group_status(measure: str, raw: str) -> str | None:
    """"Positive" / "Negative" if `raw` is "<receptor> <sign>" for this measure's receptor, else None.

    The sign is the LAST word and must be a whole word ("neg" never matches inside "positive"), and
    everything before it must be exactly a receptor name, so "ER" alone or "HER2-positive" for the ER
    measure match nothing.
    """
    words = [t for t in _tokens(raw) if t not in _NOISE_WORDS]
    if len(words) < 2 or words[-1] not in _SIGN_WORDS:
        return None
    if "".join(words[:-1]) not in _RECEPTOR_KEYS[measure]:
        return None
    return _SIGN_WORDS[words[-1]]


def _find_measure(claim: Claim) -> str:
    raw = claim.params.measure
    name = _MEASURE_BY_KEY.get(_name_key(raw)) if raw else None
    if name is None:
        raise CannotCheck(f"this release has no {raw or 'named'} measurement")
    return name


def _find_group(measure: str, raw: str | None, other: str | None) -> str:
    """Canonical group name; a missing group is taken to be the opposite of the other one."""
    by_status = {status: g for g, status in _GROUPS[measure].items()}
    if raw is None and other is not None:
        status = _group_status(measure, other)
        if status is not None:
            return by_status["Negative" if status == "Positive" else "Positive"]
    status = _group_status(measure, raw) if raw else None
    if status is None:
        raise CannotCheck(f"this release has no {raw or 'named'} grouping for {measure}")
    return by_status[status]


def _as_attribute_groups(claim: Claim) -> Claim | None:
    """A protein other than ER-alpha or HER2 compared between two named groups, as attribute groups."""
    from second_opinion.extract import find_entities

    p = claim.params
    a = find_entities(p.group_a or "")
    b = find_entities(p.group_b or "")
    if len(a) != 1 or len(b) != 1 or a[0].attribute != b[0].attribute or a[0].category == b[0].category:
        return None
    return replace(claim, params=replace(p, within_attribute=a[0].attribute, within_category=a[0].category,
                                         category_b=b[0].category))


def check_comparison(claim: Claim, release: Release, variant: Variant) -> Fact:
    """value = mean(group_a) - mean(group_b); the primary variant matches reference analysis A1."""
    if claim.params.attribute:  # "TP53 mutations are more common in Basal-like than in Luminal A tumors"
        from second_opinion.checks.attribute import check_share_comparison

        return check_share_comparison(claim, release, variant)
    if claim.params.measure in ("median_age", "mean_age"):  # "Basal-like patients were diagnosed younger than Luminal A patients"
        from second_opinion.checks.attribute import check_age_comparison

        return check_age_comparison(claim, release, variant)
    if claim.params.within_attribute:  # "E-cadherin protein was lower in lobular than in ductal tumours"
        return _protein_by_groups(claim, release, variant)
    if _MEASURE_BY_KEY.get(_name_key(claim.params.measure or "")) is None:
        grouped = _as_attribute_groups(claim)  # "GATA3 protein in ER-positive tumors exceeds that in ER-negative"
        if grouped is not None and _has_protein(release, claim.params.measure or ""):
            return _protein_by_groups(grouped, release, variant)
    measure = _find_measure(claim)
    spec = _MEASURES[measure]
    group_a = _find_group(measure, claim.params.group_a, claim.params.group_b)
    group_b = _find_group(measure, claim.params.group_b, claim.params.group_a)
    status_a, status_b = _GROUPS[measure][group_a], _GROUPS[measure][group_b]
    row, col = spec["row"], spec["status_column"]

    if row not in release.protein.index:
        raise CannotCheck(f"this release has no {measure} measurement")
    if col not in release.clinical.columns:
        raise CannotCheck(f"this release has no {group_a} / {group_b} status for its samples")

    pop = population(release, variant)
    status = pop.set_index("sampleID")[col]
    samples = [s for s in release.protein.columns if s in status.index and status[s] in (status_a, status_b)]
    values = release.protein.loc[row, samples]
    in_a = [s for s in samples if status[s] == status_a]
    in_b = [s for s in samples if status[s] == status_b]
    if not in_a or not in_b:
        empty = group_a if not in_a else group_b
        raise CannotCheck(f"this release has no {empty} samples with a {measure} measurement")
    mean_a, mean_b = float(values[in_a].mean()), float(values[in_b].mean())

    code = (
        population_code(variant)
        + f'\nstatus = pop.set_index("sampleID")["{col}"]'
        + f'\nsamples = [s for s in r.protein.columns if s in status.index and status[s] in ("{status_a}", "{status_b}")]'
        + f'\nvalues = r.protein.loc["{row}", samples]'
        + f'\nmean_a = values[[s for s in samples if status[s] == "{status_a}"]].mean()  # {group_a}'
        + f'\nmean_b = values[[s for s in samples if status[s] == "{status_b}"]].mean()  # {group_b}'
        + "\ndifference = mean_a - mean_b"
    )
    return Fact(
        label=f"mean {measure} in {group_a} minus {group_b} {population_noun(variant)}",
        value=mean_a - mean_b,
        numerator=None, denominator=None,
        sample_ids=samples,
        files=[RELEASE_FILES["clinical"], RELEASE_FILES["protein"]],
        code=code,
        extra={"n_a": len(in_a), "n_b": len(in_b), "mean_a": round(mean_a, 3), "mean_b": round(mean_b, 3)},
    )


def _protein_row(release: Release, measure: str) -> str:
    key = re.sub(r"[^A-Z0-9]", "", re.sub(r"\s+(?:protein|levels?|expression)\b", "", measure, flags=re.IGNORECASE).upper()).replace("ALFA", "ALPHA")
    aliases = {"ESR1": "ERALPHA", "ER": "ERALPHA", "ERBB2": "HER2", "CDH1": "ECADHERIN", "TP53": "P53", "PGR": "PR"}
    key = aliases.get(key, key)
    for name in release.protein.index:
        if re.sub(r"[^A-Z0-9]", "", str(name).upper()) == key:
            return str(name)
    raise CannotCheck(f"this release's protein (RPPA) file has no {measure} measurement")


def _has_protein(release: Release, measure: str) -> bool:
    """The measure names one RPPA protein; a bare receptor name ("ER") is a status, not a protein."""
    if re.sub(r"[^A-Z0-9]", "", measure.upper()) in ("ER", "PR", "PGR", "HER2", "PROTEIN", ""):
        return False
    try:
        _protein_row(release, measure)
    except CannotCheck:
        return False
    return True


def _protein_by_groups(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Mean of one RPPA protein in group A minus group B, groups read from any sample attribute."""
    from second_opinion.checks.attribute import scoped
    from second_opinion.checks.attributes import attribute_values, describe

    p = claim.params
    row = _protein_row(release, p.measure or "")
    sides = []
    for category in (p.within_category, p.category_b):
        frame, code, words = scoped(claim, release, variant, within_category=category)
        samples = [s for s in frame.index if s in release.protein.columns]
        values = release.protein.loc[row, samples].astype(float).dropna()
        if values.empty:
            raise CannotCheck(f"no {words} have a {row} protein measurement")
        sides.append((values, words, code))
    (va, wa, code_a), (vb, wb, _) = sides
    mean_a, mean_b = float(va.mean()), float(vb.mean())
    av = attribute_values(release, population(release, variant), p.within_attribute, p.within_category, variant)
    code = (population_code(variant) + "\n" + av.code.replace("vals", "group")
            + f'\nvalues = r.protein.loc["{row}"]'
            + f'\nmean = lambda g: values[[s for s in group[group == g].index if s in values.index]].mean()'
            + f'\ndifference = mean("{av.hit}") - mean(<{describe(p.within_attribute, p.category_b)}>)')
    return Fact(
        label=f"mean {row} protein (RPPA) in {wa} minus {wb}",
        value=mean_a - mean_b, numerator=None, denominator=None, sample_ids=list(va.index) + list(vb.index),
        files=[RELEASE_FILES["clinical"], RELEASE_FILES["protein"]] + [f for f in av.files if f not in RELEASE_FILES.values()],
        code=code, extra={"n_a": len(va), "n_b": len(vb), "mean_a": round(mean_a, 3), "mean_b": round(mean_b, 3),
                          "group_a_words": wa, "group_b_words": wb},
    )

"""The one place where sample scope and sex filters are applied."""

import pandas as pd

from second_opinion.release import Release
from second_opinion.variants import Variant

_SUBTYPE_COLUMNS = {
    "rna_call": "PAM50Call_RNAseq",
    "study_2012_label": "PAM50_mRNA_nature2012",
}


def subtype_column(variant: Variant) -> str:
    """Clinical column holding the subtype call for this variant."""
    try:
        return _SUBTYPE_COLUMNS[variant.subtype_source]
    except KeyError:
        raise KeyError(f"unknown subtype_source {variant.subtype_source!r}") from None


def population(release: Release, variant: Variant) -> pd.DataFrame:
    """Clinical rows after the variant's sample scope and sex filter.

    Rows with a missing sampleID are dropped. With women_only, rows whose gender is missing are
    excluded and counted in `df.attrs["excluded_unknown_sex"]` (0 for everyone).
    """
    clinical = release.clinical
    df = clinical[clinical["sampleID"].notna()]
    if variant.sample_scope == "primary_tumors":
        df = df[df["sampleID"].astype(str).str[13:15] == "01"]
    elif variant.sample_scope != "all_samples":
        raise KeyError(f"unknown sample_scope {variant.sample_scope!r}")

    excluded = 0
    if variant.sex_filter == "women_only":
        excluded = int(df["gender"].isna().sum())
        df = df[df["gender"] == "FEMALE"]
    elif variant.sex_filter != "everyone":
        raise KeyError(f"unknown sex_filter {variant.sex_filter!r}")

    df = df.copy()
    df.attrs["excluded_unknown_sex"] = excluded
    return df


def population_code(variant: Variant) -> str:
    """Pandas lines that rebuild `pop` (assumes `r = load_release(...)`)."""
    lines = ["pop = r.clinical[r.clinical.sampleID.notna()]"]
    if variant.sample_scope == "primary_tumors":
        lines.append('pop = pop[pop.sampleID.str[13:15] == "01"]  # primary tumors')
    if variant.sex_filter == "women_only":
        lines.append('n_unknown_sex = int(pop.gender.isna().sum())  # left out, sex unknown')
        lines.append('pop = pop[pop.gender == "FEMALE"]')
    return "\n".join(lines)


def population_noun(variant: Variant) -> str:
    """Plain-words name of the population, e.g. "female primary tumors"."""
    noun = "primary tumors" if variant.sample_scope == "primary_tumors" else "samples"
    return f"female {noun}" if variant.sex_filter == "women_only" else noun

"""AGREEMENT claims: how often the RNA-seq PAM50 call and the 2012 study label name the same subtype."""

from dataclasses import replace

from second_opinion.checks.base import CannotCheck
from second_opinion.checks.population import population, population_code, population_noun
from second_opinion.model import Claim, Fact
from second_opinion.release import RELEASE_FILES, Release
from second_opinion.variants import Variant, normalise_subtype

_RNA, _STUDY = "PAM50Call_RNAseq", "PAM50_mRNA_nature2012"


def check_agreement(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Percent of samples with both labels whose two labels agree (Luminal A = LumA, ...)."""
    for col in (_RNA, _STUDY):
        if col not in release.clinical.columns:
            raise CannotCheck(f"this release's clinical file has no {col} column")
    scope = replace(variant, subtype_source="rna_call")
    pop = population(release, scope)
    both = pop[pop[_RNA].notna() & pop[_STUDY].notna()]
    if both.empty:
        raise CannotCheck("no samples have both an RNA-seq call and a 2012 study label")
    agree = both[_RNA].map(normalise_subtype) == both[_STUDY].map(normalise_subtype)
    n, total = int(agree.sum()), len(both)
    code = (population_code(scope) + f'\nboth = pop[pop["{_RNA}"].notna() & pop["{_STUDY}"].notna()]'
            f'\nagree = both["{_RNA}"].map(normalise_subtype) == both["{_STUDY}"].map(normalise_subtype)'
            "\nn, total = int(agree.sum()), len(both)\npercent = 100 * n / total")
    return Fact(
        label=f"{population_noun(scope)} whose RNA-seq PAM50 call matches the 2012 study label, among those with both",
        value=100 * n / total, numerator=n, denominator=total, sample_ids=both["sampleID"].astype(str).tolist(),
        files=[RELEASE_FILES["clinical"]], code=code, unknown_count=len(pop) - total,
    )


def label_pairs(release: Release, variant: Variant):
    """Crosstab of the 2012 study label (rows) against the RNA-seq call (columns), among samples with both."""
    pop = population(release, replace(variant, subtype_source="rna_call"))
    both = pop[pop[_RNA].notna() & pop[_STUDY].notna()]
    return both[_STUDY].map(normalise_subtype).to_frame("study").assign(rna=both[_RNA].map(normalise_subtype).values)


def check_label_pair(claim: Claim, release: Release, variant: Variant) -> Fact:
    """COUNT "label_pair:<study>:<rna>" (tumours the 2012 study put in one subtype and RNA-seq in another), or its
    RANK among the cells where the two labels disagree (1 = the largest)."""
    _, study, rna = (claim.params.subject or "").split(":")
    pairs = label_pairs(release, variant)
    cells = pairs.value_counts()
    n = int(cells.get((study, rna), 0))
    code = (population_code(replace(variant, subtype_source="rna_call"))
            + f'\nboth = pop[pop["{_RNA}"].notna() & pop["{_STUDY}"].notna()]'
            f'\nstudy, rna = both["{_STUDY}"].map(normalise_subtype), both["{_RNA}"].map(normalise_subtype)'
            "\ncells = pd.crosstab(study, rna)")
    if claim.params.measure == "label_pair":  # the rank of this cell among the disagreements
        off = cells[[a != b for a, b in cells.index]]
        rank = 1 + int((off > n).sum())
        listing = "; ".join(f"2012 {a} / RNA {b}: {int(k)}" for (a, b), k in off.head(4).items())
        return Fact(label=f"rank of 2012 {study} called {rna} by RNA-seq among the disagreeing label pairs",
                    value=float(rank), numerator=None, denominator=None, sample_ids=[], files=[RELEASE_FILES["clinical"]],
                    code=code + "\noff = cells.stack()[lambda c: [a != b for a, b in c.index]].sort_values(ascending=False)",
                    extra={"leader": listing.split(";")[0], "ranks": listing})
    return Fact(label=f"samples the 2012 study labelled {study} and RNA-seq calls {rna}", value=n, numerator=n,
                denominator=None, sample_ids=[], files=[RELEASE_FILES["clinical"]],
                code=code + f'\nn = int(cells.loc["{study}", "{rna}"])')

"""Checks over sample attributes: shares, counts, rankings, ratios, summary statistics, group comparisons.

Every check here reads labels through `attributes.attribute_values`, so a share, a count and a ranking
of the same thing always agree with each other.
"""

from __future__ import annotations

import pandas as pd

from second_opinion.checks.attributes import (
    NODES_COLUMN,
    YEAR_COLUMN,
    ATTRIBUTE_NOUNS,
    CLINICAL,
    age_values,
    attribute_values,
    clinical_frame,
    describe,
    gene_frequencies,
    gene_symbol,
)
from second_opinion.checks.base import CannotCheck
from second_opinion.checks.population import population, population_code, population_noun
from second_opinion.model import Claim, Fact
from second_opinion.release import Release
from second_opinion.variants import Variant

def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _noun(variant: Variant) -> str:
    return population_noun(variant)


def scoped(claim: Claim, release: Release, variant: Variant, within_category: str | None = None):
    """(frame, code, words): the population after the variant's scope and the claim's subgroup, if any."""
    p = claim.params
    pop = population(release, variant)
    frame = clinical_frame(pop)
    code = population_code(variant) + '\npop = pop.drop_duplicates("sampleID").set_index("sampleID", drop=False)'
    words = _noun(variant)
    category = within_category if within_category is not None else p.within_category
    if p.within_attribute:
        anyone = category == "any"  # "with a definitive ER result": every sample with a recorded value
        w = attribute_values(release, frame, p.within_attribute, None if anyone else category, variant)
        keep = (w.values.notna() if anyone else (w.values == w.hit)).reindex(frame.index, fill_value=False).astype(bool)
        frame = frame[keep.values]
        code += "\n" + w.code.replace("vals", "group") + ("\npop = pop[group.notna()]" if anyone else f'\npop = pop[group == "{w.hit}"]')
        words = (f"{words} with a recorded {ATTRIBUTE_NOUNS.get(p.within_attribute, p.within_attribute)}" if anyone
                 else f"{describe(p.within_attribute, category)} {words}")
    frame.attrs["excluded_unknown_sex"] = pop.attrs.get("excluded_unknown_sex", 0)
    return frame, code, words


def _sex_extra(frame: pd.DataFrame) -> dict[str, float | int | str]:
    excluded = frame.attrs.get("excluded_unknown_sex", 0)
    return {"excluded_unknown_sex": excluded} if excluded else {}


def _tally(claim: Claim, release: Release, variant: Variant, category: str | None = None, within: str | None = None):
    p = claim.params
    frame, code, words = scoped(claim, release, variant, within)
    wanted = category if category is not None else p.category
    av = attribute_values(release, frame, p.attribute, None if wanted == "any" else wanted, variant)
    known = av.values.notna()
    hits = known.copy() if wanted == "any" else (av.values == av.hit) & known  # "any": every sample with a recorded value
    return frame, code, words, av, hits, known


def check_attribute_share(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Percent of the samples with a known value that have the claimed one (e.g. ER-positive among ER-known)."""
    p = claim.params
    if p.attribute == "slide_kind" and p.subject == "slides":  # a share of slides, not of samples
        from second_opinion.checks.attributes import slide_kind_counts
        from second_opinion.release import SLIDE_MANIFEST

        counts = slide_kind_counts(release)
        n, total = int(counts.get(p.category, 0)), int(counts.sum())
        return Fact(
            label=f"{p.category} slides among all slides (read from {SLIDE_MANIFEST})", value=100 * n / total if total else None,
            numerator=n, denominator=total, sample_ids=[], files=[SLIDE_MANIFEST],
            code=(f'kind = pd.read_csv("{SLIDE_MANIFEST}").slide_kind.str.lower().str.extract(r"^(diagnostic|frozen)")[0]'
                  f'\nn, total = int((kind == "{p.category}").sum()), int(kind.notna().sum())'),
        )
    frame, code, words, av, hits, known = _tally(claim, release, variant)
    n, total = int(hits.sum()), int(known.sum())
    if total == 0:
        raise CannotCheck(f"no {words} have a recorded {ATTRIBUTE_NOUNS.get(p.attribute, p.attribute)}")
    code += "\n" + av.code + f'\nknown = vals.notna()\nn, total = int((vals == "{av.hit}").sum()), int(known.sum())\npercent = 100 * n / total'
    return Fact(
        label=f"{words} with a recorded {ATTRIBUTE_NOUNS.get(p.attribute, p.attribute)} that are {describe(p.attribute, p.category)} (read from {av.source})",
        value=100 * n / total, numerator=n, denominator=total,
        sample_ids=[str(s) for s in hits[hits].index], files=av.files, code=code,
        unknown_count=len(frame) - total, extra=_sex_extra(frame),
    )


def check_attribute_count(claim: Claim, release: Release, variant: Variant) -> Fact:
    """How many samples (or distinct patients) have the claimed value."""
    p = claim.params
    frame, code, words, av, hits, known = _tally(claim, release, variant)
    ids = [str(s) for s in hits[hits].index]
    by_patient = (p.subject or "").endswith("patients") or p.attribute in ("vital_status", "dss_status")
    code += "\n" + av.code
    if p.category == "any":  # "PAM50 calls are available for 844 tumors": samples with any recorded value
        code += "\nn = int(vals.notna().sum())"
        return Fact(
            label=f"{words} with a recorded {ATTRIBUTE_NOUNS.get(p.attribute, p.attribute)} (read from {av.source})",
            value=len(ids), numerator=len(ids), denominator=None, sample_ids=ids, files=av.files, code=code,
            unknown_count=len(frame) - len(ids), extra=_sex_extra(frame),
        )
    if by_patient:
        ids = sorted({s[:12] for s in ids})
        code += f'\nn = pop[vals == "{av.hit}"].sampleID.str[:12].nunique()  # distinct patients'
        noun = "patients"
    else:
        code += f'\nn = int((vals == "{av.hit}").sum())'
        noun = words
    total = int(known.sum())
    return Fact(
        label=f"{describe(p.attribute, p.category)} {noun if by_patient else words} (read from {av.source})",
        value=len(ids), numerator=len(ids), denominator=total if p.stated_total is not None else None,
        sample_ids=ids, files=av.files, code=code, unknown_count=len(frame) - total,
        extra={"known": total, **_sex_extra(frame)},
    )


def check_rank(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Where a category ranks by size (1 = most common); for genes, among all genes in the mutation file."""
    p = claim.params
    if p.measure == "rate":
        return _rate_rank(claim, release, variant)
    if p.measure == "median_age":
        return _age_rank(claim, release, variant)
    if p.measure == "label_pair":  # "the largest single disagreement" between the 2012 label and the RNA-seq call
        from second_opinion.checks.agreement import check_label_pair

        return check_label_pair(claim, release, variant)
    if p.measure and not p.attribute and p.within_attribute:  # "Mean HER2 protein was highest in HER2-enriched"
        return _protein_rank(claim, release, variant)
    if p.attribute in ("mutation", "amplification", "deletion", "gain", "loss"):
        return _gene_rank(claim, release, variant)
    frame, code, words, av, hits, known = _tally(claim, release, variant)
    counts = av.values[known].value_counts()
    if counts.empty:
        raise CannotCheck(f"no {words} have a recorded {ATTRIBUTE_NOUNS.get(p.attribute, p.attribute)}")
    wanted = [av.hit] + ([_label(release, frame, p.attribute, p.category_b, variant)] if p.category_b else [])
    return _rank_fact(claim, counts, wanted, int(known.sum()), words, av.files,
                      code + "\n" + av.code + "\ncounts = vals.value_counts()  # rank 1 = most common", av.source, len(frame))


def _label(release, frame, attribute, category, variant) -> str:
    return attribute_values(release, frame, attribute, category, variant).hit


def _gene_rank(claim: Claim, release: Release, variant: Variant) -> Fact:
    p = claim.params
    frame, code, words = scoped(claim, release, variant)
    counts, n_samples = gene_frequencies(release, list(frame.index), p.attribute)
    if n_samples == 0:
        raise CannotCheck(f"no {words} are in the mutation file")
    genes = [gene_symbol(g) for g in (p.category, p.category_b) if g]
    for g in genes:
        if g not in counts.index:
            raise CannotCheck(f"the mutation file has no {g} row")
    test = {"mutation": "> 0", "amplification": ">= 2", "deletion": "<= -2", "gain": ">= 1", "loss": "<= -1"}[p.attribute]
    matrix = "r.mutation()" if p.attribute == "mutation" else "r.copy_number()"
    code += (f"\nm = {matrix}[[s for s in pop.sampleID if s in {matrix}.columns]]"
             f"\ncounts = (m {test}).sum(axis=1).sort_values(ascending=False)  # rank 1 = most often")
    return _rank_fact(claim, counts, genes, n_samples, words, [CLINICAL, _file(p.attribute)], code,
                      f"{_file(p.attribute)}", len(frame), gene=True)


def _file(attribute: str) -> str:
    from second_opinion.release import RELEASE_FILES
    return RELEASE_FILES["mutation"] if attribute == "mutation" else RELEASE_FILES["copy_number"]


def _rank_fact(claim, counts: pd.Series, wanted: list[str], total: int, words: str, files, code, source, pop_size,
               gene: bool = False) -> Fact:
    """Fact.value = the worst (largest) competition rank among `wanted`; extra holds the leaders."""
    p = claim.params
    least = p.direction == "lower"
    ordered = counts.sort_values(ascending=least, kind="stable")
    ranks = {}
    for name in wanted:
        n = int(ordered.get(name, 0))
        better = (ordered < n).sum() if least else (ordered > n).sum()
        ranks[name] = int(better) + 1
    worst = max(ranks.values())
    lead_name, lead_n = str(ordered.index[0]), int(ordered.iloc[0])
    extra: dict[str, float | int | str] = {
        "leader": lead_name, "leader_count": lead_n, "total": total, "least": 1 if least else 0,
        "ranks": "; ".join(f"{name} {ordinal(r)} ({int(ordered.get(name, 0)):,} of {total:,})" for name, r in ranks.items()),
    }
    first = wanted[0]
    n_first = int(ordered.get(first, 0))
    # how close is the call: the gap to the neighbour that would change the rank
    position = list(ordered.index).index(first) if first in ordered.index else None
    if position is not None:
        neighbour = ordered.index[position + 1] if position + 1 < len(ordered) else None
        if position > 0:
            neighbour = ordered.index[position - 1]
        if neighbour is not None:
            extra["neighbour"] = str(neighbour)
            extra["neighbour_count"] = int(ordered[neighbour])
    thing = "genes" if gene else f"{ATTRIBUTE_NOUNS.get(p.attribute, p.attribute)} values"
    return Fact(
        label=f"rank of {', '.join(wanted)} among {thing} by how many {words} have it (read from {source})",
        value=float(worst), numerator=n_first, denominator=total,
        sample_ids=[], files=list(files), code=code, unknown_count=pop_size - total if not gene else 0, extra=extra,
    )


def check_ratio(claim: Claim, release: Release, variant: Variant) -> Fact:
    """count(category) / count(category_b) within the same population."""
    p = claim.params
    if not p.category_b:
        raise CannotCheck("the claim names only one group")
    if p.attribute == "slide_kind":  # "Diagnostic slides outnumber frozen sections": count slides, not samples
        from second_opinion.checks.attributes import slide_kind_counts
        from second_opinion.release import SLIDE_MANIFEST

        counts = slide_kind_counts(release)
        a, b = int(counts.get(p.category, 0)), int(counts.get(p.category_b, 0))
        if b == 0:
            raise CannotCheck(f"the slide manifest has no {p.category_b} slides")
        return Fact(
            label=f"{p.category} vs {p.category_b} slides (read from {SLIDE_MANIFEST})", value=a / b, numerator=a,
            denominator=b, sample_ids=[], files=[SLIDE_MANIFEST],
            code=(f'kind = pd.read_csv("{SLIDE_MANIFEST}").slide_kind.str.lower().str.extract(r"^(diagnostic|frozen)")[0]'
                  f'\na, b = (kind == "{p.category}").sum(), (kind == "{p.category_b}").sum()\nratio = a / b'),
            extra={"n_a": a, "n_b": b},
        )
    if p.measure == "rate":  # "eight times as common in Basal-like as in Luminal A": one rate over the other
        return _rate_ratio(claim, release, variant)
    if p.attribute_b and p.attribute_b != p.attribute:  # "HER2-positive tumours outnumber ERBB2-amplified tumours"
        return _attribute_ratio(claim, release, variant)
    frame, code, words, av, hits, known = _tally(claim, release, variant)
    if p.attribute in ("mutation", "amplification", "deletion", "gain", "loss"):  # two genes: each has its own calls
        _, _, _, av_b, hits_b, _ = _tally(claim, release, variant, category=p.category_b)
        a, b = int(hits.sum()), int(hits_b.sum())
        hit_b = av_b.hit
    else:
        hit_b = _label(release, frame, p.attribute, p.category_b, variant)
        a, b = int(hits.sum()), int(((av.values == hit_b) & known).sum())
    if b == 0:
        raise CannotCheck(f"no {describe(p.attribute, p.category_b)} {words} to compare with")
    code += "\n" + av.code + f'\na, b = int((vals == "{av.hit}").sum()), int((vals == "{hit_b}").sum())\nratio = a / b'
    return Fact(
        label=f"{describe(p.attribute, p.category)} vs {describe(p.attribute, p.category_b)} {words} (read from {av.source})",
        value=a / b, numerator=a, denominator=b, sample_ids=[], files=av.files, code=code,
        extra={"n_a": a, "n_b": b, **_sex_extra(frame)},
    )


def check_statistic(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Median / mean / youngest / oldest age at diagnosis over the population (one row per sample)."""
    p = claim.params
    stat = p.measure or "median"
    frame, code, words = scoped(claim, release, variant)
    if stat.startswith("os_"):  # "the median recorded overall survival time is under three years"
        stat = stat[3:]
        survival = release.survival
        if survival is None or "OS.time" not in survival.columns:
            raise CannotCheck("this release's survival file has no OS.time column")
        by_sample = survival.drop_duplicates("sample").set_index("sample")["OS.time"]
        days = pd.to_numeric(pd.Series([by_sample.get(s) for s in frame.index], index=frame.index), errors="coerce")
        known = days.dropna() / 365.25
        if known.empty:
            raise CannotCheck(f"no {words} have a recorded survival time")
        value = {"median": known.median, "mean": known.mean, "min": known.min, "max": known.max}[stat]()
        code += ('\ndays = pop.sampleID.map(r.survival.drop_duplicates("sample").set_index("sample")["OS.time"])'
                 f"\nvalue = (days.dropna() / 365.25).{stat}()  # years")
        return Fact(
            label=f"{stat} recorded overall survival time (years; survival.tsv OS.time / 365.25) of {words}",
            value=float(value), numerator=None, denominator=int(len(known)), sample_ids=[],
            files=[CLINICAL, "survival.tsv"], code=code, unknown_count=len(frame) - len(known),
            extra={"no_age_word": 1, **_sex_extra(frame)},
        )
    if stat.startswith(("year_", "nodes_")):  # "Diagnoses span 1988 to 2013", "the median number of positive nodes"
        what, stat = stat.split("_", 1)
        col = YEAR_COLUMN if what == "year" else NODES_COLUMN
        if col not in release.clinical.columns:
            raise CannotCheck(f"this release's clinical file has no {col} column")
        known = pd.to_numeric(frame[col], errors="coerce").dropna()
        noun = "year of diagnosis" if what == "year" else "number of positive lymph nodes (H&E)"
        if known.empty:
            raise CannotCheck(f"no {words} have a recorded {noun}")
        value = {"median": known.median, "mean": known.mean, "min": known.min, "max": known.max,
                 "mode": lambda: known.mode().iloc[0]}[stat]()
        code += (f'\nvalues = pd.to_numeric(pop["{col}"], errors="coerce").dropna()'
                 + ("\nvalue = values.mode().iloc[0]  # the most common" if stat == "mode" else f"\nvalue = values.{stat}()"))
        return Fact(
            label=f"{stat} {noun} of {words} (read from {col})", value=float(value), numerator=None,
            denominator=int(len(known)), sample_ids=[], files=[CLINICAL], code=code,
            unknown_count=len(frame) - len(known), extra={"plain": noun, **_sex_extra(frame)},
        )
    ages, col = age_values(release, frame, variant)
    known = ages.dropna()
    if known.empty:
        raise CannotCheck(f"no {words} have a recorded age at diagnosis")
    value = {"median": known.median, "mean": known.mean, "min": known.min, "max": known.max}[stat]()
    code += f'\nages = pd.to_numeric(pop["{col}"], errors="coerce").dropna()\nvalue = ages.{stat}()'
    return Fact(
        label=f"{stat} age at diagnosis (years) of {words} with a recorded age (read from {col})",
        value=float(value), numerator=None, denominator=int(len(known)), sample_ids=[], files=[CLINICAL],
        code=code, unknown_count=len(frame) - len(known), extra=_sex_extra(frame),
    )


def check_share_comparison(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Share of the claimed value in group A minus group B, in percentage points."""
    p = claim.params
    if not (p.within_attribute and p.within_category and p.category_b):
        raise CannotCheck("the claim does not name two groups to compare")
    sides = []
    for group in (p.within_category, p.category_b):
        frame, code, words, av, hits, known = _tally(claim, release, variant, within=group)
        n, total = int(hits.sum()), int(known.sum())
        if total == 0:
            raise CannotCheck(f"no {words} have a recorded {ATTRIBUTE_NOUNS.get(p.attribute, p.attribute)}")
        sides.append((n, total, words, av, code))
    (na, ta, wa, av, code_a), (nb, tb, wb, _, _) = sides
    pa, pb = 100 * na / ta, 100 * nb / tb
    code = code_a.replace(f'== "{p.within_category}"', "== GROUP") + "\n" + av.code + (
        f'\nshare = lambda g: 100 * (vals[group == g] == "{av.hit}").sum() / vals[group == g].notna().sum()'
        f'\ndifference = share("{p.within_category}") - share("{p.category_b}")  # percentage points'
    )
    return Fact(
        label=f"share {describe(p.attribute, p.category)}: {wa} minus {wb} (percentage points, read from {av.source})",
        value=pa - pb, numerator=None, denominator=None, sample_ids=[], files=av.files, code=code,
        extra={"n_a": ta, "n_b": tb, "hits_a": na, "hits_b": nb, "share_a": round(pa, 1), "share_b": round(pb, 1),
               "group_a": wa, "group_b": wb},
    )


def _attribute_ratio(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Samples with one attribute's value against samples with another's (each among the whole population)."""
    p = claim.params
    frame, code, words = scoped(claim, release, variant)
    av_a = attribute_values(release, frame, p.attribute, p.category, variant)
    av_b = attribute_values(release, frame, p.attribute_b, p.category_b, variant)
    a, b = int((av_a.values == av_a.hit).sum()), int((av_b.values == av_b.hit).sum())
    if b == 0:
        raise CannotCheck(f"no {describe(p.attribute_b, p.category_b)} {words} to compare with")
    code += ("\n" + av_a.code.replace("vals", "vals_a") + "\n" + av_b.code.replace("vals", "vals_b")
             + f'\na, b = int((vals_a == "{av_a.hit}").sum()), int((vals_b == "{av_b.hit}").sum())\nratio = a / b')
    return Fact(
        label=f"{describe(p.attribute, p.category)} vs {describe(p.attribute_b, p.category_b)} {words}",
        value=a / b, numerator=a, denominator=b, sample_ids=[], files=sorted(set(av_a.files) | set(av_b.files)), code=code,
        extra={"n_a": a, "n_b": b, **_sex_extra(frame)},
    )


def _rate_ratio(claim: Claim, release: Release, variant: Variant) -> Fact:
    """The share of the claimed value in group A divided by its share in group B."""
    p = claim.params
    sides = []
    for group in (p.within_category, p.category_b):
        frame, code, words, av, hits, known = _tally(claim, release, variant, within=group)
        n, total = int(hits.sum()), int(known.sum())
        if total == 0:
            raise CannotCheck(f"no {words} have a recorded {ATTRIBUTE_NOUNS.get(p.attribute, p.attribute)}")
        sides.append((n, total, words, av, code))
    (na, ta, wa, av, code_a), (nb, tb, wb, _, _) = sides
    if nb == 0:
        raise CannotCheck(f"no {wb} are {describe(p.attribute, p.category)}, so there is no ratio")
    ra, rb = 100 * na / ta, 100 * nb / tb
    code = code_a.replace(f'== "{p.within_category}"', "== GROUP") + "\n" + av.code + (
        f'\nshare = lambda g: 100 * (vals[group == g] == "{av.hit}").sum() / vals[group == g].notna().sum()'
        f'\nratio = share("{p.within_category}") / share("{p.category_b}")'
    )
    return Fact(
        label=f"share {describe(p.attribute, p.category)}: {wa} divided by {wb} (read from {av.source})",
        value=ra / rb, numerator=None, denominator=None, sample_ids=[], files=av.files, code=code,
        extra={"rate_a": round(ra, 1), "rate_b": round(rb, 1), "hits_a": na, "n_a": ta, "hits_b": nb, "n_b": tb,
               "group_a": wa, "group_b": wb},
    )


def _median_ages(claim: Claim, release: Release, variant: Variant):
    """Median age at diagnosis of every group of the claim's grouping attribute, and the code that computes it."""
    p = claim.params
    pop = population(release, variant)
    frame = clinical_frame(pop)
    groups = attribute_values(release, frame, p.within_attribute, p.within_category, variant)
    ages, col = age_values(release, frame, variant)
    known = ages.notna() & groups.values.notna()
    stat = "mean" if p.measure == "mean_age" else "median"
    medians = ages[known].groupby(groups.values[known]).agg(stat)
    sizes = ages[known].groupby(groups.values[known]).size()
    code = (population_code(variant) + '\npop = pop.drop_duplicates("sampleID").set_index("sampleID", drop=False)\n'
            + groups.code.replace("vals", "group")
            + f'\nage = pd.to_numeric(pop["{col}"], errors="coerce")\nmedians = age.groupby(group).{stat}()')
    return groups, medians, sizes, code


def check_age_comparison(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Median age at diagnosis of group A minus group B: "Basal-like patients were diagnosed younger than Luminal A"."""
    p = claim.params
    groups, medians, sizes, code = _median_ages(claim, release, variant)
    hit_b = _label(release, clinical_frame(population(release, variant)), p.within_attribute, p.category_b, variant)
    for hit in (groups.hit, hit_b):
        if hit not in medians.index:
            raise CannotCheck(f"no {describe(p.within_attribute, hit)} {_noun(variant)} have a recorded age")
    a, b = float(medians[groups.hit]), float(medians[hit_b])
    code += f'\ndifference = medians["{groups.hit}"] - medians["{hit_b}"]  # years'
    return Fact(
        label=f"{p.measure.split('_')[0]} age at diagnosis: {describe(p.within_attribute, groups.hit)} minus {describe(p.within_attribute, hit_b)} (years)",
        value=a - b, numerator=None, denominator=None, sample_ids=[], files=groups.files, code=code,
        extra={"n_a": int(sizes[groups.hit]), "n_b": int(sizes[hit_b]), "median_a": a, "median_b": b, "what": f"{p.measure.split('_')[0]} age"},
    )


def _age_rank(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Where one group's median age at diagnosis ranks among all groups ("the youngest", "the oldest")."""
    p = claim.params
    groups, medians, sizes, code = _median_ages(claim, release, variant)
    if groups.hit not in medians.index:
        raise CannotCheck(f"no {describe(p.within_attribute, p.within_category)} {_noun(variant)} have a recorded age")
    least = p.direction == "lower"
    ordered = medians.sort_values(ascending=least, kind="stable")
    mine = medians[groups.hit]
    rank = int((ordered < mine).sum() if least else (ordered > mine).sum()) + 1
    lead = str(ordered.index[0])
    lines = "; ".join(f"{k} {ordered[k]:g} (n={int(sizes[k]):,})" for k in ordered.index)
    code += f'\nrank = medians.rank(ascending={least}, method="min")["{groups.hit}"]  # 1 = the {"youngest" if least else "oldest"}'
    return Fact(
        label=f"rank of {groups.hit} by median age at diagnosis among {ATTRIBUTE_NOUNS.get(p.within_attribute)} groups",
        value=float(rank), numerator=None, denominator=None, sample_ids=[], files=groups.files, code=code,
        extra={"leader": f"{lead} ({ordered[lead]:g})", "ranks": lines, "least": 1 if least else 0, "age": 1},
    )


def _rate_rank(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Rank of one group's rate (e.g. deaths among Basal-like) against every other group of the same attribute."""
    p = claim.params
    pop = population(release, variant)
    frame = clinical_frame(pop)
    groups = attribute_values(release, frame, p.within_attribute, p.within_category, variant)
    target = attribute_values(release, frame, p.attribute, p.category, variant)
    known = target.values.notna()
    rates: dict[str, tuple[int, int]] = {}
    for label in sorted({g for g in groups.values.dropna().unique()}):
        in_group = (groups.values == label) & known
        total = int(in_group.sum())
        if total:
            rates[str(label)] = (int(((target.values == target.hit) & in_group).sum()), total)
    if groups.hit not in rates:
        raise CannotCheck(f"no {describe(p.within_attribute, p.within_category)} {_noun(variant)} have a recorded value")
    share = pd.Series({k: 100 * n / t for k, (n, t) in rates.items()})
    least = p.direction == "lower"
    ordered = share.sort_values(ascending=least, kind="stable")
    mine = share[groups.hit]
    rank = int((ordered < mine).sum() if least else (ordered > mine).sum()) + 1
    lead = str(ordered.index[0])
    lines = "; ".join(f"{k} {share[k]:.1f}% ({rates[k][0]:,} of {rates[k][1]:,})" for k in ordered.index)
    code = (population_code(variant) + "\n" + groups.code.replace("vals", "group") + "\n" + target.code
            + f'\nrate = (vals == "{target.hit}").groupby(group).mean() * 100  # among samples with a known value'
            + "\nrank = rate.rank(ascending=False)")
    return Fact(
        label=f"rank of {groups.hit} by the share of {describe(p.attribute, p.category)} among {ATTRIBUTE_NOUNS.get(p.within_attribute)} groups",
        value=float(rank), numerator=rates[groups.hit][0], denominator=rates[groups.hit][1], sample_ids=[],
        files=sorted(set(groups.files) | set(target.files)), code=code,
        extra={"leader": f"{lead} ({share[lead]:.1f}%)", "leader_count": rates[lead][0], "total": rates[lead][1],
               "ranks": lines, "least": 1 if least else 0, "rate": 1},
    )


def _protein_rank(claim: Claim, release: Release, variant: Variant) -> Fact:
    """Rank of one group by its mean (or median) RPPA level of a protein, against every other group of the attribute."""
    import re

    from second_opinion.checks.compare import _protein_row
    from second_opinion.release import RELEASE_FILES

    p = claim.params
    row = _protein_row(release, p.measure or "")
    stat = "median" if re.search(r"\bmedian\b", claim.text, re.IGNORECASE) else "mean"
    pop = population(release, variant)
    frame = clinical_frame(pop)
    groups = attribute_values(release, frame, p.within_attribute, p.within_category, variant)
    values = release.protein.loc[row].astype(float)
    levels: dict[str, tuple[float, int]] = {}
    for label in sorted({g for g in groups.values.dropna().unique()}):
        ids = [s for s in groups.values.index[(groups.values == label).values] if s in values.index]
        v = values[ids].dropna()
        if len(v):
            levels[str(label)] = (float(getattr(v, stat)()), len(v))
    if groups.hit not in levels:
        raise CannotCheck(f"no {describe(p.within_attribute, p.within_category)} {_noun(variant)} have a {row} protein measurement")
    level = pd.Series({k: v for k, (v, _) in levels.items()})
    least = p.direction == "lower"
    ordered = level.sort_values(ascending=least, kind="stable")
    mine = level[groups.hit]
    rank = int((ordered < mine).sum() if least else (ordered > mine).sum()) + 1
    lead = str(ordered.index[0])
    lines = "; ".join(f"{k} {level[k]:.2f} (n = {levels[k][1]:,})" for k in ordered.index)
    code = (population_code(variant) + "\n" + groups.code.replace("vals", "group")
            + f'\nvalues = r.protein.loc["{row}"]'
            + f"\nlevel = values.groupby(group.reindex(values.index)).{stat}()  # per group"
            + f"\nrank = level.rank(ascending={least})")
    return Fact(
        label=f"rank of {groups.hit} by {stat} {row} protein (RPPA) among {ATTRIBUTE_NOUNS.get(p.within_attribute)} groups",
        value=float(rank), numerator=None, denominator=levels[groups.hit][1], sample_ids=[],
        files=[RELEASE_FILES["clinical"], RELEASE_FILES["protein"]] + [f for f in groups.files if f not in RELEASE_FILES.values()],
        code=code,
        extra={"leader": f"{lead} ({stat} {level[lead]:.2f})", "ranks": lines, "least": 1 if least else 0, "protein": stat,
               "mean_a": round(mine, 3)},
    )

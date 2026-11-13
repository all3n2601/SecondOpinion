"""Skeptic tests for comparison claims: does the difference survive two honest attacks?

1. Shuffle the labels: if group membership were random, how often would a difference at least
   this large appear? (A permutation p-value; small means the difference is not a fluke of labels.)
2. Leave one hospital out: drop each tissue source site in turn; if dropping one site flips the
   sign of the difference, that site is carrying the result.

These only describe the release. They are not clinical evidence and set no verdict.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from second_opinion.checks import CHECKS, CannotCheck
# The comparison check's own lookup tables, so the skeptic uses exactly the same groups and samples.
from second_opinion.checks.compare import _GROUPS, _MEASURES, _find_group, _find_measure
from second_opinion.model import Claim, ClaimType, SkepticResult
from second_opinion.release import Release
from second_opinion.variants import PRIMARY_VARIANT

SITE_COLUMN = "tissue_source_site"
N_SHUFFLES = 200
SEED = 0


def _two_groups(groups: pd.Series) -> tuple[object, object]:
    labels = sorted(groups.dropna().unique(), key=str)
    if len(labels) != 2:
        raise ValueError(f"need exactly two groups, got {len(labels)}")
    return labels[0], labels[1]


def _difference(values: np.ndarray, in_first: np.ndarray) -> float:
    return float(values[in_first].mean() - values[~in_first].mean())


def shuffle_test(values: pd.Series, groups: pd.Series, n: int = N_SHUFFLES, seed: int = SEED) -> float:
    """Share of label shuffles whose |mean difference| >= the real one, smoothed: (hits + 1) / (n + 1)."""
    first, _ = _two_groups(groups)
    vals = values.to_numpy(dtype=float)
    in_first = (groups == first).to_numpy()
    observed = abs(_difference(vals, in_first))
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(n):
        shuffled = rng.permutation(in_first)
        if abs(_difference(vals, shuffled)) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (n + 1)


def leave_one_site_out(values: pd.Series, groups: pd.Series, sites: pd.Series) -> list[str]:
    """Sites whose removal flips the sign of mean(first group) - mean(second group).

    Group order is the sorted unique group labels. A site whose removal leaves a group empty is
    skipped (there is nothing left to compare), not reported as a flip.
    """
    first, _ = _two_groups(groups)
    vals = values.to_numpy(dtype=float)
    in_first = (groups == first).to_numpy()
    site_arr = sites.astype(str).to_numpy()
    full_sign = np.sign(_difference(vals, in_first))
    flips: list[str] = []
    for site in sorted(set(site_arr)):
        keep = site_arr != site
        if not in_first[keep].any() or in_first[keep].all():
            continue
        sign = np.sign(_difference(vals[keep], in_first[keep]))
        if sign != full_sign:
            flips.append(site)
    return flips


def skeptic_for(claim: Claim, release: Release) -> SkepticResult | None:
    """Both tests for a COMPARISON claim on its primary-variant samples; None for anything else.

    Returns None (rather than raising) when the comparison cannot be checked in this release:
    the audit already reports why through the check itself.
    """
    if claim.type != ClaimType.COMPARISON:
        return None
    try:
        fact = CHECKS[ClaimType.COMPARISON](claim, release, PRIMARY_VARIANT)
        measure = _find_measure(claim)
        group_a = _find_group(measure, claim.params.group_a, claim.params.group_b)
        group_b = _find_group(measure, claim.params.group_b, claim.params.group_a)
    except (CannotCheck, KeyError, ValueError):
        return None

    spec = _MEASURES[measure]
    clinical = release.clinical[release.clinical["sampleID"].notna()]
    clinical = clinical[~clinical["sampleID"].duplicated()].set_index("sampleID")
    samples = [s for s in fact.sample_ids if s in clinical.index]

    status = clinical.loc[samples, spec["status_column"]]
    wanted = {_GROUPS[measure][group_a]: group_a, _GROUPS[measure][group_b]: group_b}
    groups = status.map(wanted)
    values = release.protein.loc[spec["row"], samples].astype(float)
    if SITE_COLUMN in clinical.columns:
        sites = clinical.loc[samples, SITE_COLUMN].fillna("unknown").astype(str)
    else:  # TCGA barcode: TCGA-<site>-<patient>-...
        sites = pd.Series([s[5:7] for s in samples], index=samples)

    keep = groups.notna() & values.notna()
    groups, values, sites = groups[keep], values[keep], sites[keep]
    try:
        p = shuffle_test(values, groups)
        flips = leave_one_site_out(values, groups, sites)
    except ValueError:
        return None
    return SkepticResult(shuffle_p=round(p, 4), n_sites=int(sites.nunique()), site_flips=flips)

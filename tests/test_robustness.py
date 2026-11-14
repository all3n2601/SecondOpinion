import pytest

from second_opinion import robustness
from second_opinion.audit import audit_claims
from second_opinion.checks import CannotCheck
from second_opinion.model import Claim, ClaimParams, ClaimType, Solidity, Verdict, VariantResult
from second_opinion.release import load_release
from second_opinion.robustness import run_variants, solidity_of
from second_opinion.variants import all_variants
from tests.test_audit import practice_claims

S, C = Verdict.SUPPORTED, Verdict.CONTRADICTED

NUMBERS = {  # variant id -> (numerator, denominator) for "Luminal A" share
    "rna_call|everyone|primary_tumors": (421, 844),
    "rna_call|women_only|primary_tumors": (416, 833),
    "rna_call|everyone|all_samples": (434, 956),
    "rna_call|women_only|all_samples": (428, 943),
    "study_2012_label|everyone|primary_tumors": (231, 522),
    "study_2012_label|women_only|primary_tumors": (230, 516),
    "study_2012_label|everyone|all_samples": (231, 522),
    "study_2012_label|women_only|all_samples": (230, 516),
}


def share_claim(stated: float, approximate: bool = True) -> Claim:
    return Claim(
        "X1", f"About {stated:g}% are Luminal A.", 0, ClaimType.SHARE,
        ClaimParams(stated_value=stated, unit="percent", approximate=approximate,
                    subject="primary_tumors", subtype="Luminal A"),
    )


def vr(variant_id: str, verdict: Verdict | None) -> VariantResult:
    return VariantResult(variant_id, None, verdict)


IDS = [v.id for v in all_variants()]


# ---- real data -------------------------------------------------------------------------

@pytest.mark.realdata
def test_practice_62_percent_holds_everywhere(release_dir):
    claim = practice_claims()[1]
    results = run_variants(claim, load_release(release_dir))
    assert [r.variant_id for r in results] == IDS
    assert len(results) == 8
    assert all(r.verdict == C for r in results)
    assert {r.variant_id: (r.fact.numerator, r.fact.denominator) for r in results} == NUMBERS
    solidity, flips = solidity_of(results, C)
    assert solidity == Solidity.HOLDS_EVERYWHERE
    assert flips == []


@pytest.mark.realdata
def test_45_percent_claim_is_fragile(release_dir):
    claim = share_claim(45)
    results = run_variants(claim, load_release(release_dir))
    verdicts = {r.variant_id: r.verdict for r in results}
    # 45 +/- 2 -> 43..47: 49.9 (rna, primary) is out; 45.4 and 44.3/44.6 are in.
    assert verdicts["rna_call|everyone|primary_tumors"] == C
    assert verdicts["rna_call|women_only|primary_tumors"] == C
    assert all(v == S for k, v in verdicts.items() if k not in
               ("rna_call|everyone|primary_tumors", "rna_call|women_only|primary_tumors"))
    solidity, flips = solidity_of(results, C)
    assert solidity == Solidity.FRAGILE
    # Every other flipping variant includes one of these two choices, so it adds nothing to say.
    assert flips == [
        "sample_scope=all_samples",         # rna|everyone|all_samples
        "subtype_source=study_2012_label",  # study|everyone|primary_tumors
    ]


@pytest.mark.realdata
def test_audit_pipeline_fills_variants(release_dir):
    audit = audit_claims(practice_claims() + [share_claim(45)], release_dir)
    c1, c2, c3, c45 = audit.claims
    assert len(c2.variants) == 8
    assert c2.solidity == Solidity.HOLDS_EVERYWHERE
    assert c2.flips_on == []
    assert c1.variants == [] and c1.solidity == Solidity.NOT_APPLICABLE
    assert c3.variants == [] and c3.flips_on == []
    assert c45.solidity == Solidity.FRAGILE
    assert "subtype_source=study_2012_label" in c45.flips_on


# ---- solidity_of units -----------------------------------------------------------------

def test_all_same_holds_everywhere():
    assert solidity_of([vr(i, C) for i in IDS], C) == (Solidity.HOLDS_EVERYWHERE, [])


def test_single_choice_flip():
    vs = [vr(i, C) for i in IDS]
    vs[4] = vr(IDS[4], S)  # study_2012_label|everyone|primary_tumors
    assert solidity_of(vs, C) == (Solidity.FRAGILE, ["subtype_source=study_2012_label"])


def test_two_choice_flip_is_joined():
    vs = [vr(i, C) for i in IDS]
    vs[6] = vr(IDS[6], S)  # study_2012_label|women_only|primary_tumors
    assert solidity_of(vs, C) == (
        Solidity.FRAGILE, ["subtype_source=study_2012_label + sex_filter=women_only"])


def test_single_choice_flips_listed_first():
    vs = [vr(i, C) for i in IDS]
    vs[3] = vr(IDS[3], S)  # rna|women_only|all_samples: two choices, earlier in variant order
    vs[2] = vr(IDS[2], S)  # rna|women_only|primary_tumors: sex_filter only
    vs[1] = vr(IDS[1], S)  # rna|everyone|all_samples: sample_scope only
    # the two-choice flip is already explained by either choice alone, so it is not listed
    assert solidity_of(vs, C) == (Solidity.FRAGILE, ["sample_scope=all_samples", "sex_filter=women_only"])


def test_a_combination_is_listed_only_when_no_part_flips_alone():
    from second_opinion.robustness import minimal_flips

    assert minimal_flips(["a=1 + b=2", "c=3", "a=1 + c=3", "b=2 + d=4"]) == ["c=3", "a=1 + b=2", "b=2 + d=4"]
    assert minimal_flips(["a=1", "a=1"]) == ["a=1"]


def test_missing_variants_are_ignored_but_none_at_all_is_not_applicable():
    vs = [vr(i, None) for i in IDS]
    assert solidity_of(vs, C) == (Solidity.NOT_APPLICABLE, [])
    assert solidity_of([], C) == (Solidity.NOT_APPLICABLE, [])
    vs[2] = vr(IDS[2], C)
    assert solidity_of(vs, C) == (Solidity.HOLDS_EVERYWHERE, [])


# ---- run_variants with a check that cannot run for some variants -----------------------

def test_uncheckable_variants_get_none(mini_release, monkeypatch):
    real = robustness.CHECKS[ClaimType.SHARE]

    def picky(claim, release, variant):
        if variant.subtype_source == "study_2012_label":
            raise CannotCheck("no 2012 labels here")
        return real(claim, release, variant)

    monkeypatch.setattr(robustness, "CHECKS", {ClaimType.SHARE: picky})
    results = run_variants(share_claim(50), load_release(mini_release))
    assert [r.variant_id for r in results] == IDS
    for r in results:
        if r.variant_id.startswith("study_2012_label"):
            assert r.fact is None and r.verdict is None
        else:
            assert r.fact is not None and r.verdict is not None


def test_missing_check_for_type_gives_all_none(mini_release):
    claim = Claim("N1", "x", 0, ClaimType.NOT_ANSWERABLE, needed_data="y")
    results = run_variants(claim, load_release(mini_release))
    assert len(results) == 8 and all(r.verdict is None and r.fact is None for r in results)


@pytest.mark.realdata
def test_multi_part_caveat_lists_each_thing_once(release_dir):
    """A four-part sentence gets one short caveat, not four full caveats one after another."""
    from second_opinion.audit import audit_claims
    from second_opinion.extract import extract_claims

    text = ("CDH1 was mutated in 59% of lobular carcinomas but only 1.6% of ductal carcinomas, and PIK3CA mutations "
            "occurred in 48.5% of Luminal A tumors versus 6.6% of Basal-like tumors.")
    result = audit_claims(extract_claims(text).claims, release_dir).claims[0]
    assert len(result.parts) == 4
    caveat = result.limitation
    assert caveat.count("A gene counts as mutated") == 1
    assert caveat.count("Read from") == 1 and "mutation_gene_level.tsv.gz (CDH1, PIK3CA)." in caveat
    assert "Left out for having no mutation call: 59 (59% of lobular), 224 (1.6% of ductal)" in caveat
    assert len(result.flips_on) <= 2

import pytest

from second_opinion.extract import extract_claims
from second_opinion.ladder import build_ladder
from second_opinion.model import ClaimResult, Fact, Solidity, Verdict

COUNT_TEXT = "Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data."
SHARE_TEXT = "Luminal A is the largest RNA subtype, accounting for about 62% of primary tumors with an RNA subtype call."
CLINICAL_TEXT = (
    "Patients whose tumors had the highest ER-alpha protein responded best to hormone therapy, "
    "which suggests protein data could guide treatment research."
)


def claim_of(text):
    return extract_claims(text).claims[0]


def fact(numerator=None, denominator=None, value=None, unknown=0, **extra):
    if value is None and numerator is not None:
        value = 100 * numerator / denominator if denominator else numerator
    return Fact(label="x", value=value, numerator=numerator, denominator=denominator,
                sample_ids=[], files=[], code="", unknown_count=unknown, extra=extra)


def result(claim, verdict, f=None, correct=None, missing=None):
    return ClaimResult(
        claim=claim, verdict=verdict, solidity=Solidity.NOT_APPLICABLE, fact=f, correct_value=correct,
        missing_evidence=missing, variants=[], flips_on=[], skeptic=None, ladder=[], limitation=None,
    )


def honest(segments):
    return "".join(s.text for s in segments if not s.struck)


def struck(segments):
    return [s.text for s in segments if s.struck]


def inserted(segments):
    return [s.text for s in segments if s.inserted]


def assert_well_formed(segments, original):
    assert segments
    assert all(s.text for s in segments), "no segment text may be empty"
    assert not any(s.struck and s.inserted for s in segments)
    assert "".join(s.text for s in segments if not s.inserted) == original, "original words are all kept, in order"


# --- the practice brief ---------------------------------------------------------------------

def test_practice_contradicted_share():
    c = claim_of(SHARE_TEXT)
    segs = build_ladder(c, result(c, Verdict.CONTRADICTED, fact(421, 844), "49.9% (421 of 844)"))
    assert_well_formed(segs, SHARE_TEXT)
    assert "about 62%" in struck(segs)
    assert any("49.9% (421 of 844)" in t for t in inserted(segs))
    text = honest(segs)
    assert "421 of 844" in text and "Luminal A" in text
    assert text == "Luminal A is the largest RNA subtype, accounting for 49.9% (421 of 844) of primary tumors with an RNA subtype call."


def test_practice_matches_the_ui_fixture_shape():
    c = claim_of(SHARE_TEXT)
    segs = build_ladder(c, result(c, Verdict.CONTRADICTED, fact(421, 844), "49.9% (421 of 844)"))
    assert [(s.text, s.struck, s.inserted) for s in segs] == [
        ("Luminal A is the largest RNA subtype, accounting for ", False, False),
        ("about 62%", True, False),
        ("49.9% (421 of 844)", False, True),
        (" of primary tumors with an RNA subtype call.", False, False),
    ]


def test_practice_clinical_sentence():
    c = claim_of(CLINICAL_TEXT)
    segs = build_ladder(c, result(c, Verdict.INSUFFICIENT_EVIDENCE, missing=c.needed_data))
    assert_well_formed(segs, CLINICAL_TEXT)
    assert "responded best to hormone therapy" in struck(segs)
    notes = inserted(segs)
    assert len(notes) == 1 and "treatment" in notes[0] and notes[0].startswith("— not answerable from this data; would need: ")
    # The note sits right after the first struck run, as in the UI fixture.
    i = [s.text for s in segs].index("responded best to hormone therapy")
    assert segs[i + 1].inserted


def test_supported_count_is_one_plain_segment():
    c = claim_of(COUNT_TEXT)
    segs = build_ladder(c, result(c, Verdict.SUPPORTED, fact(535, 1101)))
    assert [(s.text, s.struck, s.inserted) for s in segs] == [(COUNT_TEXT, False, False)]


# --- rule 1: contradicted numbers -----------------------------------------------------------

def test_contradicted_count_with_total_elsewhere_inserts_just_the_number():
    c = claim_of("Of the 1,101 primary tumors in the release, 540 have survival, mutation, copy number, RNA and protein data.")
    segs = build_ladder(c, result(c, Verdict.CONTRADICTED, fact(535, 1101), "535 of 1,101"))
    assert struck(segs) == ["540"]
    assert inserted(segs) == ["535"]


def test_contradicted_n_of_m_strikes_the_pair():
    text = "540 of 1,101 primary tumors have all five data layers."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.CONTRADICTED, fact(535, 1101), "535 of 1,101"))
    assert_well_formed(segs, text)
    assert struck(segs) == ["540 of 1,101"]
    assert honest(segs) == "535 of 1,101 primary tumors have all five data layers."


def test_contradicted_range():
    text = "Basal-like is between 25 and 30 percent of subtyped primary tumors."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.CONTRADICTED, fact(142, 844), "16.8% (142 of 844)"))
    assert_well_formed(segs, text)
    assert struck(segs) == ["between 25 and 30 percent"]
    assert honest(segs) == "Basal-like is 16.8% (142 of 844) of subtyped primary tumors."


def test_contradicted_coverage_every():
    text = "Every primary tumor has protein data."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.CONTRADICTED, fact(870, 1101), "870 of 1,101 primary tumors have it; 231 are missing"))
    assert_well_formed(segs, text)
    assert struck(segs) == ["Every"]
    assert honest(segs).startswith("870 of 1,101")


def test_contradicted_comparison_flips_the_direction_word():
    text = "ER-alpha protein is lower in ER-positive tumors than in ER-negative tumors."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.CONTRADICTED, fact(value=3.051, n_a=529, n_b=169), "ER-positive mean is higher: difference 3.051 (529 vs 169 samples)"))
    assert_well_formed(segs, text)
    assert struck(segs) == ["lower"]
    assert "higher" in inserted(segs)


# --- rule 2: vague amounts ------------------------------------------------------------------

def test_supported_approximate_share_gets_the_exact_number():
    text = "Luminal A is about 50% of primary tumors with an RNA subtype call."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.SUPPORTED, fact(421, 844)))
    assert_well_formed(segs, text)
    assert struck(segs) == ["about 50%"]
    assert inserted(segs) == ["49.9% (421 of 844)"]


def test_vague_word_without_a_number():
    text = "Most primary tumors have survival data, and 1,080 of 1,101 do."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.SUPPORTED, fact(1080, 1101)))
    assert_well_formed(segs, text)
    assert "Most" in struck(segs)
    assert "1,080 of 1,101" in inserted(segs)


# --- rule 4: cause words --------------------------------------------------------------------

def test_cause_word_becomes_association():
    text = "ER-alpha drives growth in these tumors."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.INSUFFICIENT_EVIDENCE, missing=c.needed_data))
    assert_well_formed(segs, text)
    assert "drives" in struck(segs)
    assert "was associated with" in inserted(segs)
    assert any("cause or prediction" in t for t in inserted(segs))


# --- rule 5: over-generalising --------------------------------------------------------------

def test_over_generalising_gets_the_scope():
    text = "Luminal A is 49.9% of breast cancer patients."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.SUPPORTED, fact(421, 844)))
    assert_well_formed(segs, text)
    assert honest(segs) == "Luminal A is 49.9% of breast cancer patients in this TCGA-BRCA release, among 844 primary tumors."


def test_over_generalising_without_a_denominator():
    text = "In general, the release has 1,101 primary tumors."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.SUPPORTED, fact(1101, None, value=1101)))
    assert honest(segs).endswith("primary tumors in this TCGA-BRCA release.")


# --- edges ----------------------------------------------------------------------------------

def test_unmapped_claim_is_left_as_written():
    text = "The median age was 58 years."
    c = claim_of(text)
    segs = build_ladder(c, result(c, Verdict.INSUFFICIENT_EVIDENCE, missing="No check exists yet for this kind of claim"))
    assert [(s.text, s.struck, s.inserted) for s in segs] == [(text, False, False)]


@pytest.mark.parametrize("verdict", list(Verdict))
def test_never_raises_and_never_empty(verdict):
    for text in (COUNT_TEXT, SHARE_TEXT, CLINICAL_TEXT, "Every primary tumor has protein data."):
        c = claim_of(text)
        segs = build_ladder(c, result(c, verdict, fact(10, 20), "50.0% (10 of 20)" if verdict is Verdict.CONTRADICTED else None))
        assert_well_formed(segs, text)


def test_ladder_runs_inside_the_audit(mini_release):
    from second_opinion.audit import audit_claims

    claims = extract_claims(SHARE_TEXT + " " + CLINICAL_TEXT).claims
    audited = audit_claims(claims, mini_release)
    for r in audited.claims:
        assert r.ladder and all(s.text for s in r.ladder)

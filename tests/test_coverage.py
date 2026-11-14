"""Coverage: what a sentence states, what a reading used, and what it left unused."""

from pathlib import Path

import pytest

from second_opinion.ai.plan import CountPlan, Filter, QueryPlan, SharePlan, Stated
from second_opinion.coverage import Uses, missing, reading_uses, sentence_demands
from second_opinion.extract import extract_claims
from second_opinion.model import Claim, ClaimParams, ClaimType

PRACTICE = Path(__file__).resolve().parents[1] / "apps" / "web" / "public" / "practice_brief.md"

INCOMPLETE = [  # (sentence, a word that must be reported missing)
    ("TP53 mutations dominate basal-like tumors, at 85% compared with 10% in Luminal A.", "basal-like"),
    ("Deaths rise with nodal involvement: 44 of 516 N0 patients died, against 15 of 77 N3 patients.", "N0"),
    ("Frozen sections outnumber diagnostic slides, 1,978 to 1,133.", "slides"),
    ("Their ages ranged from 44 to 84 years.", "Their"),
    ("CBFB was mutated in 18 tumors, the same number as SF3B1.", "SF3B1"),
    ("In all, 432 tumors carry a high-level amplification of at least one of ERBB2, MYC or CCND1, about a third of the cohort.", "a third"),
    # Replaces the brief's "PAM50 call" row: "PAM50 call" is neither a group, a counted thing nor a qualifier in the
    # design, and the rules' reading of that sentence uses all its figures. This row skips a qualifier (40x) instead.
    ("Of the 1,133 diagnostic slides, 714 were scanned at 40x.", "40x"),
]
COMPLETE = [
    "Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data.",
    "The release contains 1,247 samples from 1,101 patients.",
    "About 77% of tumors with a known ER status are ER-positive (808 of 1,046).",
    "PIK3CA is the most frequently mutated gene, altered in 273 of 791 tumors.",
    "Gene-level GISTIC2 calls were used, with a value of 2 treated as high-level amplification.",  # no figure demanded
]


def _rules_uses(sentence: str) -> Uses:
    """What today's rules reading of the sentence used; nothing when the rules make no claim of it."""
    claims = extract_claims(sentence).claims
    return reading_uses(claims[0]) if claims else Uses()


@pytest.mark.parametrize(("sentence", "word"), INCOMPLETE)
def test_incomplete_rules_reading_names_the_unused_word(sentence: str, word: str) -> None:
    assert word in missing(sentence, _rules_uses(sentence))


@pytest.mark.parametrize("sentence", COMPLETE)
def test_complete_rules_reading_leaves_nothing(sentence: str) -> None:
    assert missing(sentence, _rules_uses(sentence)) == []


def test_practice_brief_claims_are_complete() -> None:
    claims = extract_claims(PRACTICE.read_text()).claims
    assert len(claims) == 3
    for claim in claims:
        assert missing(claim.text, reading_uses(claim)) == [], claim.text


def test_missing_words_come_in_sentence_order() -> None:
    sentence = "Deaths rise with nodal involvement: 44 of 516 N0 patients died, against 15 of 77 N3 patients."
    assert missing(sentence, _rules_uses(sentence)) == ["N0", "15", "77", "N3"]


@pytest.mark.parametrize("sentence", [
    "TP53 is mutated in many tumors.",
    "Subtypes come from the PAM50 classifier.",
    "Stage IIA tumors are common.",
    "Stage 2 tumors are common.",
    "The cohort was first described in 2010.",
    "HER2 3+ tumors are HER2-positive by IHC.",
    "Gene-level GISTIC2 calls were used, with a value of 2 treated as high-level amplification.",
])
def test_name_like_numbers_demand_no_figure(sentence: str) -> None:
    assert sentence_demands(sentence).figures == []


def test_figures_include_words_ranges_and_cut_offs() -> None:
    d = sentence_demands("About a third of the 1,101 patients over 60 were aged 26-89, and twelve of the tumors relapsed.")
    words = [f.words for f in d.figures]
    assert words == ["a third", "1,101", "60", "26", "89", "twelve"]
    assert [f.value for f in d.figures][1:] == [1101, 60, 26, 89, 12]


def test_age_range_numbers_are_figures() -> None:
    assert [f.value for f in sentence_demands("Their ages ranged from 44 to 84 years.").figures] == [44, 84]


def test_groups_are_deduplicated_and_keyed() -> None:
    d = sentence_demands("Deaths were rarer among ER-positive patients: 80 deaths among 808 ER-positive tumors.")
    assert [g.key for g in d.groups] == ["vital_status:deceased", "er_status:positive"]
    assert d.groups[0].words == "Deaths"


def test_gistic_is_not_a_group() -> None:
    assert sentence_demands("Gene-level GISTIC2 calls were used.").groups == []


def test_back_reference_words() -> None:
    for sentence, words in [
        ("Their ages ranged from 44 to 84 years.", "Their"),
        ("Of these, 12 were male.", "Of these"),
        ("Among them, 30 died.", "Among them"),
        ("A further 12 tumors were Normal-like.", "A further"),
        ("The remaining 40 were HER2-enriched.", "The remaining"),
    ]:
        ref = sentence_demands(sentence).back_reference
        assert ref is not None and ref.words == words, sentence
    assert sentence_demands("It is notable that 62% of tumors are Luminal A.").back_reference is None
    assert sentence_demands("The release contains 1,247 samples.").back_reference is None


def test_back_reference_is_resolved_only_when_the_reading_says_so() -> None:
    sentence = "Of these, 12 were male."
    uses = Uses(figures={12.0}, groups={"sex:male"}, counted={"patients", "tumors"})
    assert missing(sentence, uses) == ["Of these"]
    uses.resolves_back_reference = True
    assert missing(sentence, uses) == []


def test_counted_things() -> None:
    d = sentence_demands("Frozen sections outnumber diagnostic slides, 1,978 to 1,133.")
    assert [(c.words, c.key) for c in d.counted] == [("sections", "slides"), ("slides", "slides")]
    assert [c.key for c in sentence_demands("Of the 1,101 tumor samples, 12 are male.").counted] == ["tumors"]
    assert sentence_demands("Most tumors are ER-positive in general.").counted  # a word amount is a figure
    assert sentence_demands("Tumors are interesting.").counted == []  # no figure, nothing counted


def test_qualifiers() -> None:
    d = sentence_demands("Of the N0 patients, 12 were pT2 and 3 slides were scanned at 40x; 5 were equivocal.")
    assert [q.words for q in d.qualifiers] == ["N0", "pT2", "40x", "equivocal"]
    # slide kinds are groups when the sentence names slides, qualifiers otherwise
    assert [g.key for g in sentence_demands("Of the 1,133 diagnostic slides, 714 are fine.").groups] == ["slide_kind:diagnostic"]
    assert [q.words for q in sentence_demands("Of 1,101 tumors, 1,050 have frozen tissue.").qualifiers] == ["frozen"]
    # an entity's own words are not a qualifier
    assert sentence_demands("Of 1,101 tumors, 20 are HER2-equivocal.").qualifiers == []


def test_reading_uses_collects_params_from_claim_and_parts() -> None:
    sentence = "TP53 mutations dominate basal-like tumors, at 85% compared with 10% in Luminal A."
    claim = extract_claims(sentence).claims[0]
    uses = reading_uses(claim)
    assert {85.0, 10.0} <= uses.figures
    assert {"mutation:TP53", "subtype:Luminal A"} <= uses.groups
    assert "subtype:Basal-like" not in uses.groups
    assert {"tumors", "patients"} <= uses.counted
    # each part adds the span where its label occurs in the sentence
    assert (sentence.index("10% in Luminal A"), sentence.index("10% in Luminal A") + len("10% in Luminal A")) in uses.spans


def test_figure_inside_a_used_span_is_used() -> None:
    sentence = "Of 1,101 tumors, 12 are male."
    uses = Uses(figures={12.0}, groups={"sex:male"}, counted={"tumors"}, spans=[(0, 8)])
    assert missing(sentence, uses) == []
    assert missing(sentence, Uses(figures={12.0}, groups={"sex:male"}, counted={"tumors"})) == ["1,101"]


def test_figures_match_to_the_precision_written() -> None:
    sentence = "Of 1,101 tumors, 49.9% are ER-positive."
    base = {"groups": {"er_status:positive"}, "counted": {"tumors"}}
    assert missing(sentence, Uses(figures={1101.0, 49.94}, **base)) == []
    assert missing(sentence, Uses(figures={1101.0, 50.0}, **base)) == ["49.9%"]


def test_age_and_year_cut_offs_are_used_through_the_group() -> None:
    for sentence in ("Patients over 60 make up 45% of the cohort.", "Tumours diagnosed in 2010 or later number 300."):
        assert missing(sentence, _rules_uses(sentence)) == [], sentence


def test_reading_uses_subject_filters_and_deaths() -> None:
    claim = Claim(id="C1", text="", sentence_index=0, type=ClaimType.COUNT,
                  params=ClaimParams(stated_value=12, subject="male_patients", attribute="vital_status", category="deceased"))
    uses = reading_uses(claim)
    assert {"sex:male", "vital_status:deceased"} <= uses.groups
    assert {"patients", "deaths"} <= uses.counted


def test_reading_uses_from_an_ai_plan() -> None:
    statement = "TP53 is mutated in 85% of basal-like tumors."
    claim = Claim(id="C1", text=statement, sentence_index=0, type=ClaimType.UNMAPPED, source="ai")
    plan = QueryPlan(
        answerable=True,
        plan=SharePlan(where=[Filter(field="subtype_rna", value="Basal-like")],
                       numerator=[Filter(field="attribute", attribute="mutation", value="TP53")]),
        stated=Stated(kind="percent", span="85%", value=85),
    )
    uses = reading_uses(claim, plan)
    assert uses.figures == {85.0}
    assert uses.groups == {"subtype:Basal-like", "mutation:TP53"}
    assert (statement.index("85%"), statement.index("85%") + 3) in uses.spans
    assert missing(statement, uses) == []
    # a plan that drops the subgroup leaves it unused
    plan.plan.where = []
    assert missing(statement, reading_uses(claim, plan)) == ["basal-like"]


def test_ai_plan_counts_samples_and_age_cut_offs() -> None:
    statement = "There are 300 samples from patients over 60."
    claim = Claim(id="C1", text=statement, sentence_index=0, type=ClaimType.UNMAPPED, source="ai")
    plan = QueryPlan(answerable=True, plan=CountPlan(where=[Filter(field="age_years", op="gt", value=60)], of="samples"),
                     stated=Stated(kind="count", span="300 samples", value=300))
    uses = reading_uses(claim, plan)
    assert "samples" in uses.counted and "age_group:gt60" in uses.groups and 60.0 in uses.figures
    assert missing(statement, uses) == []


@pytest.mark.parametrize("sentence", [
    "E-cadherin protein is lower in lobular than in ductal carcinomas.",  # second group of the subgroup's attribute
    "Mutation and copy number data overlap in 785 primary tumors.",  # a data-layer count counts tumors
])
def test_more_complete_rules_readings(sentence: str) -> None:
    assert missing(sentence, _rules_uses(sentence)) == []

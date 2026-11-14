"""Coverage: what a sentence states, what a reading used, and what it left unused."""

from pathlib import Path

import pytest

from second_opinion.ai.plan import CountPlan, Filter, QueryPlan, SharePlan, Stated
from second_opinion.coverage import Uses, missing, reading_uses, sentence_demands
from second_opinion.extract import classify_sentence, split_sentences
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
    # Moved from COMPLETE (controller ruling B): the rules record 273 but not 791 as its total.
    ("PIK3CA is the most frequently mutated gene, altered in 273 of 791 tumors.", "791"),
]
COMPLETE = [
    "Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data.",
    "The release contains 1,247 samples from 1,101 patients.",
    "About 77% of tumors with a known ER status are ER-positive (808 of 1,046).",
    "Gene-level GISTIC2 calls were used, with a value of 2 treated as high-level amplification.",  # no figure demanded
    # Task 3 tunes (the gate was too strict on these readings):
    "12 samples are from male patients.",  # samples counted through the patients' sex
    "Diagnostic (FFPE) slides outnumber frozen sections in the slide manifest.",  # FFPE names the diagnostic group
    "Mutation calls are available for roughly two thirds of primary tumours.",  # "two thirds" is one figure
    "MYC is amplified (GISTIC +2) in roughly one fifth of tumours.",
    "GATA3 mutations were found only in ER-positive tumors.",  # read as "in none of the ER-negative tumors"
    "The protein panel measures 131 proteins.",  # a feature count counts the file's rows
    "The mutation file lists more than 40,000 genes.",
    "The median overall-survival time on record was 843 days, a little over two years.",  # read as 2.308 years
    "The largest single disagreement is a group of 31 tumors that the 2012 study placed in LumB and that RNA-seq calls LumA.",
    "Just over a quarter of patients, 27%, were diagnosed before age 50.",  # the amount word restated as a percent
    "Among infiltrating lobular carcinomas with mutation data, a majority (59%) carried a CDH1 mutation.",
    "Basal-like tumors are almost all ER-negative: 124 of 136 with a known ER status (91.2%).",
    "6 | Luminal A tumors had higher HER3 protein than basal-like tumors (mean 0.36 versus 0.11). | Protein, RNA subtype",
]


def rules_claims(text: str) -> list[Claim]:
    """The rules' own readings of each sentence, before `extract_claims` gates the incomplete ones."""
    infos = split_sentences(text)
    return [c for i, info in enumerate(infos) if (c := classify_sentence(info, f"C{i + 1}")) is not None]


def _rules_uses(sentence: str) -> Uses:
    """What today's rules reading of the sentence used; nothing when the rules make no claim of it."""
    claims = rules_claims(sentence)
    return reading_uses(claims[0]) if claims else Uses()


@pytest.mark.parametrize(("sentence", "word"), INCOMPLETE)
def test_incomplete_rules_reading_names_the_unused_word(sentence: str, word: str) -> None:
    assert word in missing(sentence, _rules_uses(sentence))


@pytest.mark.parametrize("sentence", COMPLETE)
def test_complete_rules_reading_leaves_nothing(sentence: str) -> None:
    assert missing(sentence, _rules_uses(sentence)) == []


def test_practice_brief_claims_are_complete() -> None:
    claims = rules_claims(PRACTICE.read_text())
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
    "9 | PTEN protein was lower in Luminal A than in basal-like tumors. | Protein, RNA subtype",  # a table row number
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
    claim = rules_claims(sentence)[0]
    uses = reading_uses(claim)
    assert {85.0, 10.0} <= uses.figures
    assert {"mutation:TP53", "subtype:Luminal A"} <= uses.groups
    assert "subtype:Basal-like" not in uses.groups
    assert {"tumors", "patients"} <= uses.counted
    # each part adds where its label occurs in the sentence, for the join only: no figure is used by it
    label = sentence.index("10% in Luminal A")
    assert (label, label + len("10% in Luminal A")) in uses.part_spans
    assert uses.spans == []


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


@pytest.mark.parametrize(("sentence", "unused"), [
    ("Mean ER-alpha protein was 2.18 in ER-positive tumors (n = 529) and -0.87 in ER-negative tumors (n = 169), "
     "a gap of about 3.1 units.", ["529", "169", "3.1"]),
    ("CDH1 mutations are concentrated in lobular carcinomas, where 85 of 144 tumors are affected, "
     "against only 9 of 560 ductal tumors.", ["560"]),
    ("Of the 844 primary tumors with a PAM50 call, Luminal A was the most common subtype at 421, roughly half.", ["half"]),
    ("CCND1 amplification was largely confined to ER-positive disease: 158 of 796 ER-positive tumors "
     "versus 12 of 233 ER-negative tumors.", ["233"]),
])
def test_a_part_label_does_not_use_the_figures_inside_it(sentence: str, unused: list[str]) -> None:
    uses = reading_uses(rules_claims(sentence)[0])
    assert uses.part_spans  # the parts' labels cover these figures ...
    gaps = missing(sentence, uses)
    assert all(word in gaps for word in unused), gaps  # ... but the reading never recorded them


def test_a_generated_part_label_falls_back_to_the_parts_figures() -> None:
    sentence = "Patients were diagnosed between the ages of 26 and 89."
    claim = rules_claims(sentence)[0]
    assert [p.part_label for p in claim.parts] == ["youngest 26", "oldest 89"]  # not the sentence's words
    a, b = sentence.index("26"), sentence.index("89")
    assert reading_uses(claim).part_spans == [(a, a + 2), (b, b + 2)]


def test_a_recorded_total_is_used_and_an_unrecorded_one_is_not() -> None:
    sentence = "Of 1,101 tumors, 12 are male."
    base = {"groups": {"sex:male"}, "counted": {"tumors"}}
    assert missing(sentence, Uses(figures={12.0}, **base)) == ["1,101"]
    assert missing(sentence, Uses(figures={12.0, 1101.0}, **base)) == []


def test_subtype_source_qualifies_the_subtype_group() -> None:
    sentence = "Under the 2012 consortium labels, Luminal A accounts for 40% of primary tumors."
    assert [q.key for q in sentence_demands(sentence).qualifiers] == ["subtype_source:study_2012_label"]
    claim = rules_claims(sentence)[0]
    assert claim.params.subtype_source == "study_2012_label"
    assert "subtype_source:study_2012_label" in reading_uses(claim).groups
    assert missing(sentence, reading_uses(claim)) == []
    # a reading of the RNA calls instead leaves the source unused
    claim.params.subtype_source = None
    assert missing(sentence, reading_uses(claim)) == ["Under the 2012 consortium labels"]
    # an AI plan reads the source through a subtype_2012 filter
    plan = QueryPlan(answerable=True, plan=SharePlan(where=[], numerator=[Filter(field="subtype_2012", value="Luminal A")]),
                     stated=Stated(kind="percent", span="40%", value=40))
    assert missing(sentence, reading_uses(claim, plan)) == []


@pytest.mark.parametrize(("sentence", "figures"), [
    ("By IHC 25 of 40 tumors were HER2-positive.", ["25", "40"]),
    ("HER2 1,101 tumors were tested.", ["1,101"]),
    ("HER2 3+ tumors are common, IHC score of 2 is equivocal.", []),
])
def test_ihc_score_pattern_stops_at_the_digit(sentence: str, figures: list[str]) -> None:
    assert [f.words for f in sentence_demands(sentence).figures] == figures


def test_a_fraction_written_in_words_is_one_figure() -> None:
    assert [f.words for f in sentence_demands("Roughly two thirds of tumours have mutation calls.").figures] == ["two thirds"]


@pytest.mark.parametrize(("sentence", "used", "unused"), [
    ("A majority (45%) of lobular tumors carry a CDH1 mutation.", {45.0}, ["majority"]),  # the percent disagrees
    ("A third of tumors are ER-negative, against 35% of lobular tumors.", {35.0}, ["A third"]),  # another statement
    ("A third of tumors are ER-negative and 35% are lobular.", {35.0}, ["A third"]),
    ("A majority (59%) of lobular tumors carry a CDH1 mutation.", set(), ["majority", "59%"]),  # percent unused too
])
def test_an_amount_word_is_used_only_through_an_agreeing_restatement(sentence: str, used: set, unused: list) -> None:
    uses = Uses(figures=used, groups={"histology:lobular", "mutation:CDH1", "er_status:negative"},
                counted={"tumors", "patients"})
    assert missing(sentence, uses) == unused

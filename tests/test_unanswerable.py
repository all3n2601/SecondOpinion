import pytest

from second_opinion.unanswerable import Unanswerable, detect_unanswerable

PRACTICE = (
    "Patients whose tumors had the highest ER-alpha protein responded best to hormone therapy, "
    "which suggests protein data could guide treatment research."
)


def test_practice_sentence():
    found = detect_unanswerable(PRACTICE)
    assert isinstance(found, Unanswerable)
    assert "responded" in found.terms
    assert "responded best" in found.terms
    assert "hormone therapy" in found.terms
    assert "treatment" in found.needed_data
    assert "treatment-response data" in found.needed_data


def test_terms_are_in_sentence_order_without_duplicates():
    found = detect_unanswerable("Therapy helped, and the therapy response was strong.")
    assert found.terms == ["therapy", "response"]


def test_cause_wording_needs_cause_data():
    found = detect_unanswerable("ER-alpha drives growth in these tumors.")
    assert found.terms == ["drives"]
    assert found.needed_data == "experimental or longitudinal data that can test cause or prediction"


@pytest.mark.parametrize("sentence", [
    "TP53 mutation predicts poor outcome.",
    "High HER2 copy number leads to faster growth.",
    "Subtype determines prognosis.",
    "Copy number loss causes the subtype switch.",
])
def test_other_cause_and_prediction_words(sentence):
    assert "cause or prediction" in detect_unanswerable(sentence).needed_data


def test_survival_benefit_needs_treatment_arm_data():
    found = detect_unanswerable("Luminal A tumors showed a survival benefit.")
    assert found.needed_data == "treatment-arm survival data"
    assert detect_unanswerable("Protein-guided care improves survival.").needed_data == "treatment-arm survival data"


def test_plain_survival_data_is_answerable():
    # The release has a survival file, so describing it is fine.
    assert detect_unanswerable("Of the 1,101 primary tumors, 1,080 have survival data.") is None


def test_response_alone_is_flagged_conservatively():
    # Deliberate: "response" by itself triggers. A false flag costs a reviewer one click;
    # a missed treatment claim would get a verdict the data can't back.
    found = detect_unanswerable("The response rate table is attached.")
    assert found is not None
    assert found.needed_data == "treatment-response data"


def test_several_groups_join_needs_without_duplicates():
    found = detect_unanswerable("The treatment predicts response and therapy drives survival benefit.")
    assert found.needed_data == (
        "treatment and outcome data and treatment-response data and "
        "experimental or longitudinal data that can test cause or prediction and treatment-arm survival data"
    )


def test_plain_count_sentence_is_none():
    assert detect_unanswerable(
        "Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data."
    ) is None


def test_whole_words_only():
    assert detect_unanswerable("The therapyx column and causeway site.") is None
    assert detect_unanswerable("Mutation driver genes were counted.") is None


def test_case_insensitive_and_original_casing_not_required():
    found = detect_unanswerable("HORMONE THERAPY was given.")
    assert "hormone therapy" in found.terms


def test_empty_sentence():
    assert detect_unanswerable("") is None


@pytest.mark.parametrize("sentence", [
    "Diagnoses span the years 1988 to 2013.",
    "Diagnoses were made between 1988 and 2013.",
    "Most diagnoses date from after 2005.",
])
def test_diagnoses_of_the_cohort_are_not_diagnostic_advice(sentence):
    assert detect_unanswerable(sentence) is None


def test_a_test_that_diagnoses_is_still_unanswerable():
    assert detect_unanswerable("The assay diagnoses breast cancer early.") is not None

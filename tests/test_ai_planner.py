import json

import pytest

from second_opinion.ai import planner as planner_module
from second_opinion.ai.client import AIError, ScriptedClient
from second_opinion.ai.plan import QueryPlan
from second_opinion.ai.planner import PlanError, build_prompt, plan_claim, release_schema_summary
from second_opinion.release import load_release

SENTENCE = "About 30% of the primary tumors are Luminal A."

GOOD = {
    "answerable": True,
    "plan": {
        "op": "share",
        "where": [{"field": "sample_type", "op": "eq", "value": "primary"}],
        "numerator": [{"field": "subtype_rna", "op": "eq", "value": "Luminal A"}],
    },
    "stated": {"kind": "percent", "span": "30%", "value": 30.0, "approximate": True},
    "rationale": "Share of primary tumors called Luminal A.",
}
UNANSWERABLE = {
    "answerable": False,
    "needed_data": "Treatment records for each patient.",
    "rationale": "The release has no treatment data.",
}


@pytest.fixture
def mini(mini_release):
    return load_release(mini_release)


@pytest.fixture
def real(release_dir):
    return load_release(release_dir)


def all_sample_ids(release):
    ids = set(release.clinical["sampleID"].dropna().astype(str))
    return ids | release.survival_ids | release.mutation_ids | release.copy_number_ids | release.protein_ids


def test_schema_summary_mini(mini):
    summary = release_schema_summary(mini)
    fields = summary["filter_fields"]
    assert fields["sample_type"] == ["primary", "normal_tissue", "metastatic"]
    assert fields["sex"] == ["female", "male"]
    assert fields["subtype_rna"] == ["Luminal A", "Luminal B", "HER2-enriched", "Basal-like", "Normal-like"]
    assert fields["subtype_2012"] == ["Luminal A", "Luminal B", "HER2-enriched", "Basal-like", "Normal-like"]
    assert fields["er_status"] == ["negative", "positive"]
    assert fields["has_layer"] == ["survival", "mutation", "copy_number", "protein"]
    assert summary["has_rna_file"] is False
    assert summary["protein_names"] == ["ERALPHA", "HER2", "AKT"]
    # the mini release has no HER2 status or age column
    assert "her2_status" not in fields and "age_years" not in fields
    assert set(summary["unavailable_fields"]) == {"her2_status", "age_years"}


def test_schema_summary_has_no_row_data_mini(mini):
    text = json.dumps(release_schema_summary(mini))
    for sample_id in all_sample_ids(mini):
        assert sample_id not in text
    assert "TCGA-" not in text


def test_schema_summary_real_release(real):
    summary = release_schema_summary(real)
    fields = summary["filter_fields"]
    assert "primary" in fields["sample_type"]
    assert {"female", "male"} <= set(fields["sex"])
    assert "Luminal A" in fields["subtype_rna"] and "Luminal A" in fields["subtype_2012"]
    assert set(fields["er_status"]) <= {"positive", "negative"} and fields["er_status"]
    assert "ERALPHA" in summary["protein_names"]
    assert isinstance(summary["has_rna_file"], bool)
    assert ("rna" in fields["has_layer"]) == summary["has_rna_file"]


def test_prompt_has_no_sample_ids_or_row_data(real):
    system, user = build_prompt(SENTENCE, release_schema_summary(real))
    text = system + "\n" + user
    assert "TCGA-" not in text
    for sample_id in all_sample_ids(real):
        assert sample_id not in text


def test_prompt_structure(mini):
    summary = release_schema_summary(mini)
    system, user = build_prompt(SENTENCE, summary)
    assert json.dumps(QueryPlan.model_json_schema()) in system
    assert "answerable" in system and "needed_data" in system and "stated.span" in system
    assert SENTENCE in user
    assert "ERALPHA" in user  # the schema summary travels in the user prompt
    assert SENTENCE not in system


def test_worked_examples_validate_and_appear_in_prompt(mini):
    examples = planner_module.WORKED_EXAMPLES
    assert 3 <= len(examples) <= 4
    system, _ = build_prompt(SENTENCE, release_schema_summary(mini))
    for sentence, answer in examples:
        QueryPlan.model_validate(answer)
        assert sentence in system
        assert json.dumps(answer) in system
        if answer["answerable"]:  # spans really are quoted from their sentences
            assert answer["stated"]["span"] in sentence
    ops = {a["plan"]["op"] for _, a in examples if a["answerable"]}
    assert {"share", "rank", "summary_stat"} <= ops
    assert any(not a["answerable"] for _, a in examples)


def test_plan_claim_valid(mini):
    client = ScriptedClient([GOOD])
    plan = plan_claim(SENTENCE, mini, client)
    assert isinstance(plan, QueryPlan) and plan.answerable and plan.plan.op == "share"
    assert len(client.calls) == 1
    system, user = client.calls[0]
    assert SENTENCE in user


def test_plan_claim_unanswerable_round_trip(mini):
    sentence = "Chemotherapy improved survival."
    plan = plan_claim(sentence, mini, ScriptedClient([UNANSWERABLE]))
    assert plan.answerable is False
    assert plan.needed_data == "Treatment records for each patient."
    assert plan.plan is None and plan.stated is None
    assert QueryPlan.model_validate(plan.model_dump()) == plan


def test_invalid_then_valid_retries_once_with_error_text(mini):
    bad = {"answerable": True, "plan": {"op": "delete_everything"}, "stated": None}
    client = ScriptedClient([bad, GOOD])
    plan = plan_claim(SENTENCE, mini, client)
    assert plan.plan.op == "share"
    assert len(client.calls) == 2
    first_user, second_user = client.calls[0][1], client.calls[1][1]
    assert second_user.startswith(first_user)
    assert len(second_user) > len(first_user)
    appended = second_user[len(first_user):]
    assert "plan" in appended  # the validation error names the offending location


def test_extra_fields_rejected_then_retried(mini):
    client = ScriptedClient([{**GOOD, "verdict": "supported"}, GOOD])
    assert plan_claim(SENTENCE, mini, client).answerable
    assert "verdict" in client.calls[1][1]


def test_invalid_twice_raises_plan_error(mini):
    bad = {"answerable": "maybe"}
    client = ScriptedClient([bad, bad, GOOD])
    with pytest.raises(PlanError) as err:
        plan_claim(SENTENCE, mini, client)
    assert isinstance(err.value, AIError)
    assert len(client.calls) == 2  # no third attempt
    assert str(err.value) == "The AI did not produce a valid query plan for this sentence"


def test_answerable_plan_needs_plan_and_stated(mini):
    incomplete = {"answerable": True, "rationale": "x"}
    client = ScriptedClient([incomplete, GOOD])
    assert plan_claim(SENTENCE, mini, client).plan is not None
    assert len(client.calls) == 2


def test_unanswerable_needs_needed_data(mini):
    client = ScriptedClient([{"answerable": False}, UNANSWERABLE])
    assert plan_claim("Chemo helped.", mini, client).needed_data
    assert len(client.calls) == 2


def test_span_must_come_from_the_sentence(mini):
    wrong = {**GOOD, "stated": {**GOOD["stated"], "span": "seventy percent"}}
    client = ScriptedClient([wrong, GOOD])
    assert plan_claim(SENTENCE, mini, client).stated.span == "30%"
    assert "span" in client.calls[1][1]


def test_client_errors_propagate_without_retry(mini):
    client = ScriptedClient([AIError("The AI service timed out"), GOOD])
    with pytest.raises(AIError) as err:
        plan_claim(SENTENCE, mini, client)
    assert not isinstance(err.value, PlanError)
    assert len(client.calls) == 1

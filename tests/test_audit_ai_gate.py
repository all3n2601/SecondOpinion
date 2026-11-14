"""The AI plan gate at /audit: a plan that leaves part of the sentence unused gives "can't check".

Every test uses a ScriptedClient: nothing here talks to a real model. Plans are run on the real release
(SO_RELEASE_DIR) where the sentence names real counts, and on the mini release where only the gate matters.
"""

from second_opinion.ai.client import AIError, ScriptedClient
from second_opinion.ai.plan import Filter, QueryPlan
from second_opinion.audit import AI_COULD_NOT, audit_claims
from second_opinion.coverage import Uses, missing, reading_uses
from second_opinion.extract import GATED
from second_opinion.model import Claim, ClaimType, Verdict


def f(field, value=None, op="eq", attribute=None):
    d = {"field": field, "op": op, "value": value}
    if attribute:
        d["attribute"] = attribute
    return d


def mutated(gene):
    return f("attribute", gene, attribute="mutation")


def answer(plan, span, value, kind="count", **stated):
    return {
        "answerable": True, "plan": plan,
        "stated": {"kind": kind, "span": span, "value": value, **stated}, "rationale": "test",
    }


def count_of(*filters):
    return {"op": "count", "of": "patients", "where": [f("sample_type", "primary"), *filters]}


def unmapped(text: str, **kw) -> Claim:
    return Claim("C1", text, 0, ClaimType.UNMAPPED, **kw)


def audit(claim: Claim, release, *answers):
    client = ScriptedClient(list(answers))
    return audit_claims([claim], release, ai_client=client).claims[0]


def test_a_plan_that_counts_only_the_first_gene_names_the_second(release_dir):
    sentence = "CBFB was mutated in 18 tumors, the same number as SF3B1."
    plan = answer(count_of(mutated("CBFB")), "18 tumors", 18)
    result = audit(unmapped(sentence), release_dir, plan)
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE  # a plain "supported" before the gate
    assert "SF3B1" in result.missing_evidence and "CBFB" not in result.missing_evidence.split("Not checked:")[1]
    assert result.ai_plan is not None and result.ai_plan["plan"]["op"] == "count"
    assert result.correct_value is None


def test_a_plan_that_checks_432_only_leaves_a_third_of_the_cohort_unchecked(release_dir):
    sentence = "432 tumors carry a mutation of PIK3CA, about a third of the cohort."
    plan = answer(count_of(mutated("PIK3CA")), "432 tumors", 432)
    result = audit(unmapped(sentence), release_dir, plan)
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE  # whatever the plan found, contradicted included
    assert "a third" in result.missing_evidence and "432" not in result.missing_evidence.split("Not checked:")[1]
    assert result.ai_plan is not None


def test_a_plan_that_covers_everything_in_the_sentence_keeps_its_verdict(release_dir):
    sentence = "PIK3CA is mutated in 273 of 791 tumors."
    plan = answer(
        {"op": "share", "where": [f("sample_type", "primary")], "numerator": [mutated("PIK3CA")]},
        "273 of 791", 273, total=791,
    )
    result = audit(unmapped(sentence), release_dir, plan)
    assert result.verdict == Verdict.SUPPORTED
    assert result.missing_evidence is None and result.ai_plan is not None


def test_a_plan_that_covers_everything_but_gets_it_wrong_is_still_contradicted(release_dir):
    sentence = "PIK3CA is mutated in 300 of 791 tumors."
    plan = answer(
        {"op": "share", "where": [f("sample_type", "primary")], "numerator": [mutated("PIK3CA")]},
        "300 of 791", 300, total=791,
    )
    result = audit(unmapped(sentence), release_dir, plan)
    assert result.verdict == Verdict.CONTRADICTED and result.correct_value


def test_a_contradicted_plan_with_unused_words_is_still_cannot_check(release_dir):
    sentence = "PIK3CA is mutated in 300 of 791 tumors, the same number as SF3B1."
    plan = answer(
        {"op": "share", "where": [f("sample_type", "primary")], "numerator": [mutated("PIK3CA")]},
        "300 of 791", 300, total=791,
    )
    result = audit(unmapped(sentence), release_dir, plan)
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE and result.correct_value is None
    assert "SF3B1" in result.missing_evidence


def test_an_ai_failure_on_a_gated_claim_keeps_the_gates_reason(mini_release):
    reason = GATED.format(words='"N0"')
    claim = unmapped("Of 7 tumors, 3 were N0.", needed_data=reason, coverage_gaps=["N0"])
    result = audit_claims([claim], mini_release, ai_client=ScriptedClient([{"nonsense": 1}, {"still": "nonsense"}])).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence == reason
    assert AI_COULD_NOT.split("{")[0] not in result.missing_evidence
    assert result.claim.coverage_gaps == ["N0"]


def test_an_ai_that_raises_on_a_gated_claim_keeps_the_gates_reason(mini_release):
    reason = GATED.format(words='"N0"')
    claim = unmapped("Of 7 tumors, 3 were N0.", needed_data=reason, coverage_gaps=["N0"])
    result = audit_claims([claim], mini_release, ai_client=ScriptedClient([AIError("the service is down")])).claims[0]
    assert result.missing_evidence == reason


def test_an_ai_failure_on_an_ordinary_claim_is_unchanged(mini_release):
    claim = unmapped("About 43% of subtyped primary tumors are Luminal A.")
    result = audit_claims([claim], mini_release, ai_client=ScriptedClient([{"nonsense": 1}, {"still": "nonsense"}])).claims[0]
    assert result.missing_evidence.startswith(AI_COULD_NOT.split("{")[0])


def test_a_non_numeric_filter_value_is_a_figure_the_reading_did_not_use() -> None:
    # "sixty" is not a number: the reading simply did not use that figure, and nothing raises
    plan = QueryPlan.model_validate({
        "answerable": True,
        "plan": {"op": "count", "of": "patients", "where": [f("age_years", "sixty", op="gt"), f("positive_lymph_nodes", "many")]},
        "stated": {"kind": "count", "span": "12", "value": 12},
    })
    sentence = "12 patients were older than 60."
    uses = reading_uses(Claim("C1", sentence, 0, ClaimType.UNMAPPED), plan=plan)
    assert isinstance(uses, Uses) and 60.0 not in uses.figures
    assert "60" in missing(sentence, uses)


def test_a_plan_with_no_sample_type_filter_reads_every_sample() -> None:
    sentence = "Women make up 98% of the samples in this release."
    share = {"op": "share", "where": [], "numerator": [f("sex", "female")]}
    stated = {"kind": "percent", "span": "98%", "value": 98}

    def plan(where):
        return QueryPlan.model_validate({"answerable": True, "plan": {**share, "where": where}, "stated": stated})

    claim = Claim("C1", sentence, 0, ClaimType.UNMAPPED)
    assert missing(sentence, reading_uses(claim, plan([]))) == []
    # restricted to primary tumors, the plan did not count samples
    assert missing(sentence, reading_uses(claim, plan([f("sample_type", "primary")]))) == ["samples"]

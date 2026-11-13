"""The AI layer wired into the audit, the /extract route, /ai/status and the audit.json export.

Rules always run first and own every claim they can handle; the AI only sees UNMAPPED claims.
Every test uses a ScriptedClient: nothing here talks to a real model.
"""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from apps.api.app.main import app
from second_opinion.ai.client import AIError, ScriptedClient
from second_opinion.audit import UNMAPPED_MISSING, audit_claims
from second_opinion.export import build_audit_json, validate_audit_json
from second_opinion.model import AuditResult, Claim, ClaimParams, ClaimType, Solidity, Verdict
from tests.test_audit import practice_claims

web = TestClient(app)
VALIDATOR = Path(__file__).resolve().parents[1] / "docs" / "challenge" / "format" / "validate.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "practice_audit_result.json"
PLAIN_PREFIX = "The AI helper could not turn this into a check we can run:"
AI_NOTE = "AI-assisted: the plan was proposed by a model and run by code."

LUMA_SENTENCE = "About 43% of subtyped primary tumors are Luminal A."  # mini release: 3 of 7 = 42.9%
LUMA_WRONG = "42% of subtyped primary tumors are Luminal A."


def unmapped(text: str, cid: str = "C1", source: str = "rules") -> Claim:
    return Claim(cid, text, 0, ClaimType.UNMAPPED, source=source)


def f(field, value=None, op="eq"):
    return {"field": field, "op": op, "value": value}


def share_answer(span: str, value: float, approximate: bool = False, subtype: str = "Luminal A") -> dict:
    return {
        "answerable": True,
        "plan": {
            "op": "share",
            "where": [f("sample_type", "primary")],
            "numerator": [f("subtype_rna", subtype)],
        },
        "stated": {"kind": "percent", "span": span, "value": value, "approximate": approximate},
        "rationale": "Share of primary tumors with that RNA subtype call.",
    }


LUMA_OK = share_answer("About 43%", 43, approximate=True)
NOT_ANSWERABLE = {
    "answerable": False,
    "needed_data": "Treatment records for each patient.",
    "rationale": "The release has no treatment data.",
}


# ------------------------------------------------------------------ audit_claims


def test_a_valid_plan_judges_an_unmapped_claim(mini_release):
    client = ScriptedClient([LUMA_OK])
    result = audit_claims([unmapped(LUMA_SENTENCE)], mini_release, ai_client=client).claims[0]
    assert result.verdict == Verdict.SUPPORTED
    assert (result.fact.numerator, result.fact.denominator) == (3, 7)
    assert result.correct_value is None and result.missing_evidence is None
    assert result.solidity == Solidity.NOT_APPLICABLE
    assert result.variants == [] and result.skeptic is None
    assert result.ai_plan["plan"]["op"] == "share" and result.ai_plan["answerable"] is True
    assert result.limitation.startswith("Checked by a query plan the AI helper proposed; our code ran it on the release.")
    assert "7 of 10" in result.limitation  # the three primary tumors without a call were left out
    assert len(client.calls) == 1


def test_a_contradicted_plan_carries_the_correct_value(mini_release):
    answer = share_answer("42%", 42)
    result = audit_claims([unmapped(LUMA_WRONG)], mini_release, ai_client=ScriptedClient([answer])).claims[0]
    assert result.verdict == Verdict.CONTRADICTED
    assert result.correct_value == "42.9% (3 of 7)"
    assert result.ai_plan is not None and result.limitation
    assert all(not s.struck for s in result.ladder)  # no stated number was parsed, so nothing is struck


def test_a_supported_plan_that_leaves_a_stated_number_unchecked_is_not_supported(mini_release):
    sentence = LUMA_SENTENCE[:-1] + ", and 10 samples have no call."
    result = audit_claims([unmapped(sentence)], mini_release, ai_client=ScriptedClient([LUMA_OK])).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert "Not checked: 10" in result.missing_evidence and '"About 43%"' in result.missing_evidence
    assert result.ai_plan is not None  # the reviewer can still see what the plan tested


def test_a_contradicted_part_still_contradicts_the_whole_sentence(mini_release):
    sentence = LUMA_WRONG[:-1] + ", and 10 samples have no call."
    result = audit_claims([unmapped(sentence)], mini_release, ai_client=ScriptedClient([share_answer("42%", 42)])).claims[0]
    assert result.verdict == Verdict.CONTRADICTED


def test_the_ai_judges_the_sentence_not_the_claim_params(mini_release):
    claim = Claim("C4", LUMA_SENTENCE, 3, ClaimType.UNMAPPED, ClaimParams(stated_value=1.0), source="ai")
    result = audit_claims([claim], mini_release, ai_client=ScriptedClient([LUMA_OK])).claims[0]
    assert result.claim.id == "C4" and result.verdict == Verdict.SUPPORTED


def test_not_answerable_plan_is_insufficient_with_needed_data(mini_release):
    client = ScriptedClient([NOT_ANSWERABLE])
    result = audit_claims([unmapped("Patients on tamoxifen lived longer.")], mini_release, ai_client=client).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence == "Treatment records for each patient."
    assert result.fact is None and result.correct_value is None
    assert result.ai_plan["answerable"] is False
    assert result.ai_plan["needed_data"] == "Treatment records for each patient."


def test_an_invalid_plan_twice_is_insufficient_and_never_raises(mini_release):
    client = ScriptedClient([{"nonsense": 1}, {"still": "nonsense"}])
    result = audit_claims([unmapped(LUMA_SENTENCE)], mini_release, ai_client=client).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence.startswith(PLAIN_PREFIX)
    assert result.fact is None and result.ai_plan is None
    assert len(client.calls) == 2


def test_an_ai_error_is_insufficient_and_never_raises(mini_release):
    client = ScriptedClient([AIError("The AI service did not answer in time.")])
    result = audit_claims([unmapped(LUMA_SENTENCE)], mini_release, ai_client=client).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence == f"{PLAIN_PREFIX} The AI service did not answer in time."
    assert result.ai_plan is None


def test_an_unexpected_failure_still_does_not_fail_the_audit(mini_release):
    client = ScriptedClient([RuntimeError("secret-key-123 exploded")])
    result = audit_claims([unmapped(LUMA_SENTENCE)], mini_release, ai_client=client).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence.startswith(PLAIN_PREFIX)
    assert "secret-key-123" not in result.missing_evidence


def test_a_number_the_sentence_does_not_contain_is_rejected(mini_release):
    answer = share_answer("About 43%", 55, approximate=True)  # 55 is not in "About 43% ..."
    result = audit_claims([unmapped(LUMA_SENTENCE)], mini_release, ai_client=ScriptedClient([answer])).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence.startswith(PLAIN_PREFIX) and "not in the sentence" in result.missing_evidence
    assert result.fact is None and result.ai_plan is None


def test_one_bad_claim_does_not_stop_the_others(mini_release):
    client = ScriptedClient([AIError("The AI service is unreachable."), LUMA_OK])
    audit = audit_claims([unmapped("Some sentence.", "C1"), unmapped(LUMA_SENTENCE, "C2")], mini_release, ai_client=client)
    assert [r.verdict for r in audit.claims] == [Verdict.INSUFFICIENT_EVIDENCE, Verdict.SUPPORTED]


def test_rules_handled_claims_never_reach_the_client(mini_release):
    client = ScriptedClient([])
    with_client = audit_claims(practice_claims(), mini_release, ai_client=client)
    assert client.calls == []
    assert with_client == audit_claims(practice_claims(), mini_release, ai_client=None)  # AI is off in tests
    assert all(r.ai_plan is None for r in with_client.claims)


def test_the_ai_is_only_asked_about_unmapped_claims(mini_release):
    client = ScriptedClient([LUMA_OK])
    audit = audit_claims([*practice_claims(), unmapped(LUMA_SENTENCE, "C4")], mini_release, ai_client=client)
    assert len(client.calls) == 1
    assert audit.claims[3].ai_plan is not None and all(r.ai_plan is None for r in audit.claims[:3])


def test_without_a_client_an_unmapped_claim_is_what_it_was(mini_release):
    result = audit_claims([unmapped(LUMA_SENTENCE)], mini_release).claims[0]
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence == UNMAPPED_MISSING and result.ai_plan is None


def test_the_default_client_comes_from_make_client(mini_release, monkeypatch):
    client = ScriptedClient([LUMA_OK])
    monkeypatch.setattr("second_opinion.audit.make_client", lambda: client)
    result = audit_claims([unmapped(LUMA_SENTENCE)], mini_release).claims[0]
    assert result.verdict == Verdict.SUPPORTED and len(client.calls) == 1


def test_the_audit_result_round_trips_with_ai_plan(mini_release):
    audit = audit_claims([unmapped(LUMA_SENTENCE)], mini_release, ai_client=ScriptedClient([LUMA_OK]))
    adapter = TypeAdapter(AuditResult)
    back = adapter.validate_python(json.loads(adapter.dump_json(audit)))
    assert back.claims[0].ai_plan == audit.claims[0].ai_plan


# ------------------------------------------------------------------ the model contract


def test_new_fields_default_so_old_json_stays_valid():
    audit = TypeAdapter(AuditResult).validate_python(json.loads(FIXTURE.read_text()))
    assert all(r.ai_plan is None and r.claim.source == "rules" for r in audit.claims)
    assert Claim("C1", "x", 0, ClaimType.COUNT).source == "rules"


# ------------------------------------------------------------------ audit.json export


def test_an_ai_assisted_finding_is_marked_and_still_validates(mini_release, tmp_path):
    audit = audit_claims([unmapped(LUMA_SENTENCE, "C1"), unmapped("Patients on tamoxifen lived longer.", "C2")],
                         mini_release, ai_client=ScriptedClient([LUMA_OK, NOT_ANSWERABLE]))
    doc = build_audit_json(audit, None)
    assert validate_audit_json(doc) == []
    for finding in doc["findings"]:
        assert all(e["note"].endswith(AI_NOTE) for e in finding["evidence"]), finding["evidence"]
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(doc))
    run = subprocess.run([sys.executable, str(VALIDATOR), str(path)], capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr


def test_a_rules_finding_has_no_ai_note(mini_release):
    doc = build_audit_json(audit_claims(practice_claims(), mini_release), None)
    assert not any(AI_NOTE in e["note"] for f_ in doc["findings"] for e in f_["evidence"])


def test_the_practice_fixture_still_validates():
    audit = TypeAdapter(AuditResult).validate_python(json.loads(FIXTURE.read_text()))
    assert validate_audit_json(build_audit_json(audit, None)) == []


# ------------------------------------------------------------------ /extract

REPORT = (
    "We thank the team. Luminal B is the second most common subtype. "
    "Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data. "
    "Protein data adds a layer."
)


def test_extract_without_ai_is_rules_only():
    body = web.post("/extract", json={"report_text": REPORT}).json()
    assert [c["id"] for c in body["claims"]] == ["C1"]
    assert all(c["source"] == "rules" for c in body["claims"])


def test_extract_recovers_claims_in_sentence_order(monkeypatch):
    client = ScriptedClient([{"claim_indices": [1, 3]}])
    monkeypatch.setattr("apps.api.app.routes.extract.make_client", lambda: client)
    body = web.post("/extract", json={"report_text": REPORT}).json()
    assert [(c["id"], c["sentence_index"], c["source"], c["type"]) for c in body["claims"]] == [
        ("C1", 1, "ai", "UNMAPPED"), ("C2", 2, "rules", "COUNT"), ("C3", 3, "ai", "UNMAPPED"),
    ]
    assert body["claims"][0]["text"] == "Luminal B is the second most common subtype."
    by_index = {s["index"]: s["claim_id"] for s in body["sentences"]}
    assert by_index == {0: None, 1: "C1", 2: "C2", 3: "C3"}
    assert body["claims"][1]["params"]["stated_value"] == 535  # the rules claim is untouched, only renumbered
    assert len(client.calls) == 1
    assert "Of the 1,101 primary tumors" not in client.calls[0][1]  # only unclaimed sentences are sent


def test_extract_ignores_indices_the_model_made_up(monkeypatch):
    monkeypatch.setattr("apps.api.app.routes.extract.make_client", lambda: ScriptedClient([{"claim_indices": [2, 99]}]))
    body = web.post("/extract", json={"report_text": REPORT}).json()
    assert [c["id"] for c in body["claims"]] == ["C1"]  # 2 is a rules claim already; 99 does not exist


def test_extract_ai_error_returns_the_rules_only_result(monkeypatch):
    baseline = web.post("/extract", json={"report_text": REPORT}).json()
    monkeypatch.setattr("apps.api.app.routes.extract.make_client", lambda: ScriptedClient([AIError("down")]))
    response = web.post("/extract", json={"report_text": REPORT})
    assert response.status_code == 200
    assert response.json() == baseline
    assert [c["id"] for c in baseline["claims"]] == ["C1"]


def test_classify_is_unchanged_by_the_ai(monkeypatch):
    monkeypatch.setattr("apps.api.app.routes.extract.make_client", lambda: ScriptedClient([]))
    body = web.post("/classify", json={"text": "A sentence.", "sentence_index": 2, "claim_id": "C7"}).json()
    assert (body["id"], body["type"], body["source"]) == ("C7", "UNMAPPED", "rules")


# ------------------------------------------------------------------ /ai/status

KEY = "sk-super-secret-key"


def test_status_off(monkeypatch):
    monkeypatch.setenv("SO_AI", "off")
    assert web.get("/ai/status").json() == {"enabled": False, "model": None, "host": None, "reason": "AI turned off"}


def test_status_on_never_contains_the_key(monkeypatch):
    monkeypatch.setenv("SO_AI", "on")
    monkeypatch.setenv("SO_AI_API_KEY", KEY)
    monkeypatch.setenv("SO_AI_MODEL", "my-model")
    monkeypatch.setenv("SO_AI_BASE_URL", "http://localhost:20128/v1")
    response = web.get("/ai/status")
    assert response.json() == {"enabled": True, "model": "my-model", "host": "localhost:20128", "reason": None}
    assert KEY not in response.text


def test_status_without_a_key_says_why(monkeypatch):
    monkeypatch.setenv("SO_AI", "on")
    monkeypatch.delenv("SO_AI_API_KEY", raising=False)
    monkeypatch.setenv("SO_AI_MODEL", "my-model")
    body = web.get("/ai/status").json()
    assert body["enabled"] is False and body["reason"] == "No AI key set"


# ------------------------------------------------------------------ the CLI


def test_cli_no_ai_flag_and_banner(mini_release, tmp_path, monkeypatch, capsys):
    from second_opinion import cli

    claims = tmp_path / "claims.json"
    claims.write_text(json.dumps([{"id": "C1", "text": LUMA_SENTENCE, "sentence_index": 0, "type": "UNMAPPED"}]))
    base = ["--release", str(mini_release), "--claims-json", str(claims), "--out", str(tmp_path / "audit.json")]

    cli.main(base)  # AI off by the test environment: no banner
    assert "AI helper" not in capsys.readouterr().out

    monkeypatch.setenv("SO_AI", "on")
    monkeypatch.setenv("SO_AI_API_KEY", KEY)
    monkeypatch.setenv("SO_AI_MODEL", "my-model")
    seen = []
    monkeypatch.setattr("second_opinion.audit.make_client", lambda: seen.append(1) or ScriptedClient([LUMA_OK]))
    cli.main(base)
    assert "AI helper on (my-model)" in capsys.readouterr().out and seen == [1]

    seen.clear()
    cli.main([*base, "--no-ai"])
    out = capsys.readouterr().out
    assert "AI helper" not in out


# ------------------------------------------------------------------ the real release


def truth_pct(mask_hit: pd.Series, mask_pop: pd.Series) -> float:
    return 100 * mask_hit.sum() / mask_pop.sum()


@pytest.mark.realdata
def test_real_release_ai_off_is_unchanged(release_dir):
    client = ScriptedClient([])
    audit = audit_claims(practice_claims(), release_dir, ai_client=client)
    assert client.calls == []
    assert [c.verdict for c in audit.claims] == [Verdict.SUPPORTED, Verdict.CONTRADICTED, Verdict.INSUFFICIENT_EVIDENCE]
    assert audit.claims[1].correct_value == "49.9% (421 of 844)"
    assert audit == audit_claims(practice_claims(), release_dir)
    expected = TypeAdapter(AuditResult).validate_python(json.loads(FIXTURE.read_text()))
    assert [c.verdict for c in audit.claims] == [c.verdict for c in expected.claims]


def real_answers():
    primary = [f("sample_type", "primary")]
    return {
        "basal": (
            "Basal-like tumors make up roughly one in six of the subtyped primary tumors.",
            {"answerable": True,
             "plan": {"op": "share", "where": primary, "numerator": [f("subtype_rna", "Basal-like")]},
             "stated": {"kind": "percent", "span": "roughly one in six", "value": 16.7, "approximate": True}},
        ),
        "second": (
            "Luminal B is the second most common subtype.",
            {"answerable": True,
             "plan": {"op": "rank", "where": primary, "category_field": "subtype_rna", "category": "Luminal B"},
             "stated": {"kind": "rank", "span": "second most common", "value": 2}},
        ),
        "women": (
            "Women make up 98% of the samples in this release.",
            {"answerable": True,
             "plan": {"op": "share", "where": [], "numerator": [f("sex", "female")]},
             "stated": {"kind": "percent", "span": "98%", "value": 98}},
        ),
        "age": (
            "The median age at diagnosis was 58 years.",
            {"answerable": True,
             "plan": {"op": "summary_stat", "field": "age_years", "stat": "median", "where": []},
             "stated": {"kind": "number", "span": "58 years", "value": 58}},
        ),
    }


@pytest.mark.realdata
def test_real_release_end_to_end_through_audit_claims(release_dir):
    answers = real_answers()
    claims = [unmapped(text, f"C{i}") for i, (text, _) in enumerate(answers.values(), start=1)]
    client = ScriptedClient([answer for _, answer in answers.values()])
    basal, second, women, age = audit_claims(claims, release_dir, ai_client=client).claims

    clinical = pd.read_csv(release_dir / "clinical.tsv", sep="\t", low_memory=False)
    primary = clinical[clinical.sampleID.str[13:15] == "01"]
    called = primary[primary.PAM50Call_RNAseq.notna()]
    assert basal.verdict == Verdict.SUPPORTED
    assert (basal.fact.numerator, basal.fact.denominator) == ((called.PAM50Call_RNAseq == "Basal").sum(), len(called))
    assert second.verdict == Verdict.SUPPORTED and second.fact.value == 2
    assert called.PAM50Call_RNAseq.value_counts().index[1] == "LumB"

    known = clinical[clinical.gender.notna()]
    women_truth = truth_pct(known.gender == "FEMALE", known.gender.notna())
    assert women.verdict == (Verdict.SUPPORTED if round(women_truth) == 98 else Verdict.CONTRADICTED)
    assert women.fact.numerator == (known.gender == "FEMALE").sum()

    age_truth = clinical["age_at_initial_pathologic_diagnosis"].dropna().median()
    assert age.verdict == (Verdict.SUPPORTED if round(age_truth) == 58 else Verdict.CONTRADICTED)
    assert age.fact.value == age_truth

    for result in (basal, second, women, age):
        assert result.ai_plan is not None and result.solidity == Solidity.NOT_APPLICABLE
        assert result.limitation.startswith("Checked by a query plan the AI helper proposed")
    assert len(client.calls) == 4

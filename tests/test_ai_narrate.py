"""AI narration: the checker that keeps every number out of model-written prose, and POST /ai/narrate.

Every test uses a ScriptedClient: nothing here talks to a real model.
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app
from second_opinion.ai.client import AIError, ScriptedClient
from second_opinion.ai.narrate import (
    AUDIT_SLOTS,
    BANNED_WORDS,
    CLAIM_SLOTS,
    NarrateClaim,
    NarrateError,
    Narration,
    build_prompt,
    check_narration,
    narrate,
)

web = TestClient(app)


def claims() -> list[NarrateClaim]:
    return [
        NarrateClaim("C1", "supported", "solid", False, "About 62% of HER2-positive tumours were Luminal B."),
        NarrateClaim("C2", "contradicted", "solid", False, "Most samples came from site A."),
    ]


def good() -> dict:
    return {
        "headline": "{contradicted} of {total} claims did not hold up.",
        "caption": "Counts come from the checks run on the data.",
        "claims": {
            "C1": "The report says {stated}; the data agrees.",
            "C2": "The data shows {data_shows}, {direction} the report.",
        },
    }


def with_(**changes) -> dict:
    data = good()
    for key, value in changes.items():
        if key.startswith("c_"):
            data["claims"][key[2:].upper()] = value
        else:
            data[key] = value
    return data


def test_slot_and_word_lists_match_the_constraints():
    assert AUDIT_SLOTS == {"supported", "contradicted", "insufficient", "total", "reviewed", "fragile"}
    assert CLAIM_SLOTS == {"stated", "data_shows", "direction", "agree", "ways"}
    assert {"two", "most", "none", "exceeds", "dozen", "majority"} <= BANNED_WORDS
    assert "someone" not in BANNED_WORDS


def test_valid_answer_passes():
    narration, problems = check_narration(good(), claims())
    assert problems == []
    assert isinstance(narration, Narration)
    assert narration.headline.startswith("{contradicted}")
    assert narration.claims["C2"].startswith("The data shows")


def test_digit_outside_slot_rejected():
    narration, problems = check_narration(with_(headline="2 of {total} claims failed."), claims())
    assert narration is None
    assert any(p.startswith("headline") for p in problems)


@pytest.mark.parametrize("sentence", ["The report says 62% and that is wrong.", "The gap was 0.5 wide."])
def test_percent_and_decimal_rejected(sentence):
    narration, problems = check_narration(with_(c_c1=sentence), claims())
    assert narration is None
    assert any(p.startswith("claims.C1") for p in problems)


@pytest.mark.parametrize("word", ["two", "Most", "none", "lower", "exceeds"])
def test_number_and_comparison_words_rejected(word):
    narration, problems = check_narration(with_(c_c1=f"The report was {word}, to be fair."), claims())
    assert narration is None
    assert any(p.startswith("claims.C1") for p in problems)


@pytest.mark.parametrize("word", ["someone", "overall"])
def test_whole_word_match_only(word):
    narration, problems = check_narration(with_(c_c1=f"{word} should look; {{stated}}."), claims())
    assert problems == []
    assert narration is not None


def test_punctuation_is_stripped_before_lookup():
    narration, problems = check_narration(with_(c_c1="Most, truly."), claims())
    assert narration is None and problems
    narration, problems = check_narration(with_(c_c1="Checked for HER2. Then (HER2)."), claims())
    assert problems == []


def test_letter_digit_name_allowed_only_from_claim_text():
    assert check_narration(with_(c_c1="HER2 looks fine: {stated}."), claims())[1] == []
    narration, problems = check_narration(with_(c_c1="TP53 looks fine: {stated}."), claims())
    assert narration is None
    assert any(p.startswith("claims.C1") for p in problems)
    # a name from C2's text is not allowed in C1's sentence
    other = claims()
    other[1] = NarrateClaim("C2", "contradicted", "solid", False, "TP53 samples came from site A.")
    assert check_narration(with_(c_c1="TP53 looks fine."), other)[0] is None
    assert check_narration(with_(c_c1="her2 looks fine."), claims())[1] == []


def test_headline_may_use_a_name_from_any_claim():
    assert check_narration(with_(headline="HER2 claims: {supported} held up."), claims())[1] == []
    narration, problems = check_narration(with_(headline="TP53 claims held up."), claims())
    assert narration is None and problems[0].startswith("headline")


def test_unknown_and_misplaced_slots_rejected():
    for data in (
        with_(headline="{foo} claims failed."),
        with_(caption="Sorted by {bar}."),
        with_(c_c1="Look at {baz}."),
        with_(headline="The report says {stated}."),
        with_(caption="It shows {data_shows}."),
    ):
        narration, problems = check_narration(data, claims())
        assert narration is None and problems
    assert check_narration(with_(c_c1="{supported} of {total}: {stated}."), claims())[1] == []


def test_stray_braces_rejected():
    narration, problems = check_narration(with_(c_c1="The report says { stated }."), claims())
    assert narration is None and problems


def test_wrong_claim_ids_rejected():
    missing = good()
    del missing["claims"]["C2"]
    narration, problems = check_narration(missing, claims())
    assert narration is None and any("C2" in p for p in problems)
    extra = good()
    extra["claims"]["C9"] = "Something else."
    narration, problems = check_narration(extra, claims())
    assert narration is None and any("C9" in p for p in problems)


def test_wrong_shapes_rejected():
    for data in ({}, {"headline": 3, "caption": "x", "claims": {}}, with_(claims=["C1"]), with_(caption="")):
        narration, problems = check_narration(data, claims())
        assert narration is None and problems


def test_length_caps():
    assert check_narration(with_(headline="a" * 160), claims())[1] == []
    assert check_narration(with_(headline="a" * 161), claims())[0] is None
    assert check_narration(with_(c_c1="a" * 220), claims())[1] == []
    assert check_narration(with_(c_c1="a" * 221), claims())[0] is None
    assert check_narration(with_(caption="a" * 200), claims())[1] == []
    assert check_narration(with_(caption="a" * 201), claims())[0] is None


def bad() -> dict:
    return with_(headline="2 of {total} claims failed.")


def test_retry_then_success():
    client = ScriptedClient([bad(), good()])
    narration = narrate("story", claims(), client)
    assert narration.headline.startswith("{contradicted}")
    assert len(client.calls) == 2
    assert "Your previous answer was rejected" not in client.calls[0][1]
    assert "Your previous answer was rejected" in client.calls[1][1]
    assert "headline" in client.calls[1][1]


def test_retry_then_error():
    client = ScriptedClient([bad(), bad()])
    with pytest.raises(NarrateError, match="did not pass the checks"):
        narrate("story", claims(), client)
    assert len(client.calls) == 2


def test_client_error_propagates_without_retry():
    client = ScriptedClient([AIError("down")])
    with pytest.raises(AIError, match="down"):
        narrate("story", claims(), client)
    assert len(client.calls) == 1


def test_prompt_carries_no_data_values():
    system, user = build_prompt("story", claims())
    both = system + user
    for c in claims():
        assert c.id in user and c.text in user
    for key in ("correct_value", "fact", "sample_ids"):
        assert key not in both
    for slot in AUDIT_SLOTS | CLAIM_SLOTS:
        assert "{" + slot + "}" in system
    assert "headline" in system and "caption" in system


@pytest.mark.parametrize(
    "view,phrase",
    [("story", "no jargon"), ("checklist", "reviewer"), ("evidence", "researcher"), ("raw", "engineer")],
)
def test_prompt_names_the_audience(view, phrase):
    system, _ = build_prompt(view, claims())
    assert phrase in system


def payload(view: str = "story") -> dict:
    return {
        "view": view,
        "claims": [
            {"id": c.id, "verdict": c.verdict, "solidity": c.solidity, "overridden": c.overridden, "text": c.text}
            for c in claims()
        ],
    }


def use_client(monkeypatch, client):
    monkeypatch.setattr("apps.api.app.routes.ai.make_client", lambda: client)


def test_narrate_endpoint_ai_off(monkeypatch):
    use_client(monkeypatch, None)
    res = web.post("/ai/narrate", json=payload())
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "template"
    assert body["reason"] == "The AI helper is off"
    assert body["headline"] is None and body["claims"] is None


def test_narrate_endpoint_ai_ok(monkeypatch):
    use_client(monkeypatch, ScriptedClient([good()]))
    res = web.post("/ai/narrate", json=payload("raw"))
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "ai"
    assert body["headline"] == good()["headline"]
    assert body["claims"] == good()["claims"]
    assert body["reason"] is None


def test_narrate_endpoint_ai_down(monkeypatch):
    use_client(monkeypatch, ScriptedClient([AIError("down")]))
    res = web.post("/ai/narrate", json=payload())
    assert res.status_code == 200
    assert res.json()["source"] == "template"
    assert res.json()["reason"] == "down"


def test_narrate_endpoint_bad_wording_falls_back(monkeypatch):
    use_client(monkeypatch, ScriptedClient([bad(), bad()]))
    res = web.post("/ai/narrate", json=payload())
    assert res.status_code == 200
    assert res.json()["source"] == "template"
    assert res.json()["reason"] == "The AI wording did not pass the checks"


def test_narrate_endpoint_rejects_bad_requests(monkeypatch):
    use_client(monkeypatch, None)
    assert web.post("/ai/narrate", json=payload("poster")).status_code == 422
    too_many = payload()
    too_many["claims"] = too_many["claims"] * 51
    assert web.post("/ai/narrate", json=too_many).status_code == 422
    long_text = payload()
    long_text["claims"][0]["text"] = "a" * 2001
    assert web.post("/ai/narrate", json=long_text).status_code == 422

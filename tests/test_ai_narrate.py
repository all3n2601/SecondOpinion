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
    STORY_JARGON,
    NarrateError,
    Narration,
    build_prompt,
    check_narration,
    narrate,
)

web = TestClient(app)


def claims() -> list[NarrateClaim]:
    return [
        NarrateClaim("C1", "supported", "holds_under_every_variant", False, "About 62% of HER2-positive tumours were Luminal B."),
        NarrateClaim("C2", "contradicted", "holds_under_every_variant", False, "Most samples came from site A."),
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
    # parts_hold: a sentence with several parts says how many parts hold, never one part's {agree} of {ways}
    assert CLAIM_SLOTS == {"stated", "data_shows", "direction", "agree", "ways", "parts_hold"}
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


@pytest.mark.parametrize(
    "sentence",
    [
        "\u0663 of {total} failed.",  # Arabic-Indic three
        "\uff12 of {total} failed.",  # fullwidth 2
        "\u00bd of claims failed.",
        "{total}\u00b2 checks.",
        "\u216b claims.",  # roman numeral twelve
        "\u2154 held up.",
        "tw\u200bo claims failed.",  # zero-width space
        "tw\u03bf claims failed.",  # Greek omicron
    ],
)
def test_unicode_number_tricks_rejected(sentence):
    narration, problems = check_narration(with_(c_c1=sentence), claims())
    assert narration is None
    assert any(p.startswith("claims.C1") for p in problems)
    narration, problems = check_narration(with_(headline=sentence), claims())
    assert narration is None
    assert any(p.startswith("headline") for p in problems)


@pytest.mark.parametrize(
    "sentence",
    [
        "tw\u034fo claims failed.",  # combining grapheme joiner (Mn)
        "tw\ufe0fo claims failed.",  # variation selector
        "t\u0301wo claims failed.",  # combining acute
        "o\u0301ne claim failed.",
        "\u00f3ne claim failed.",  # precomposed o-acute
        "{supported}\uff05 held up.",  # fullwidth percent
        "Half\nthe claims failed.",  # control character
        "Seven\u2009claims failed.",
        "per cent of claims held up.",
    ],
)
def test_allowlist_rejects_hidden_characters(sentence):
    narration, problems = check_narration(with_(c_c1=sentence), claims())
    assert narration is None
    assert any(p.startswith("claims.C1") for p in problems)
    assert check_narration(with_(headline=sentence), claims())[0] is None


@pytest.mark.parametrize(
    "sentence",
    [
        "The report \u201csays\u201d {stated} \u2014 and it\u2019s fine.",
        "A well-known result; follow-up is needed.",
        "A non\u2011breaking hyphen and an en\u2013dash are fine.",
    ],
)
def test_allowlist_keeps_ordinary_typography(sentence):
    narration, problems = check_narration(with_(c_c1=sentence), claims())
    assert problems == []
    assert narration is not None


def test_typographic_punctuation_still_allowed():
    sentence = "The report \u201csays\u201d {stated} \u2014 and it\u2019s fine; the data agrees\u2026"
    narration, problems = check_narration(with_(c_c1=sentence), claims())
    assert problems == []
    assert narration is not None


def test_non_ascii_name_allowed_only_from_claim_text():
    other = claims()
    other[0] = NarrateClaim("C1", "supported", "holds_under_every_variant", False, "Gda\u0144sk had HER\u2082 tumours.")
    assert check_narration(with_(c_c1="Gda\u0144sk and HER2 look fine: {stated}."), other)[1] == []
    assert check_narration(with_(c_c2="Gda\u0144sk looks fine."), other)[0] is None


@pytest.mark.parametrize(
    "sentence",
    [
        "thirty claims failed",
        "a hundred percent held up",
        "zero held up",
        "a third of claims held up",
        "both held up",
        "neither held up",
        "twice the report",
        "greater than the report",
        "exceeded the report",
        "sixty-plus claims held up",
    ],
)
def test_extended_banned_words_rejected(sentence):
    narration, problems = check_narration(with_(c_c1=sentence + "."), claims())
    assert narration is None
    assert any(p.startswith("claims.C1") for p in problems)


def test_prompt_lists_extended_banned_words():
    system, _ = build_prompt("story", claims())
    for word in ("zero", "thirty", "percent", "twice", "neither", "exceeded", "minority", "thousand"):
        assert word in BANNED_WORDS
        assert word in system


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
    other[1] = NarrateClaim("C2", "contradicted", "holds_under_every_variant", False, "TP53 samples came from site A.")
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
            {
                "id": c.id,
                "verdict": c.verdict,
                "solidity": c.solidity,
                "overridden": c.overridden,
                "text": c.text,
                "slots": sorted(c.slots),
            }
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


def test_narrate_endpoint_rejects_duplicate_ids_and_bad_values(monkeypatch):
    use_client(monkeypatch, None)
    dup = payload()
    dup["claims"][1]["id"] = "C1"
    assert web.post("/ai/narrate", json=dup).status_code == 422
    bad_verdict = payload()
    bad_verdict["claims"][0]["verdict"] = "maybe"
    assert web.post("/ai/narrate", json=bad_verdict).status_code == 422
    bad_solidity = payload()
    bad_solidity["claims"][0]["solidity"] = "solid"
    assert web.post("/ai/narrate", json=bad_solidity).status_code == 422
    long_id = payload()
    long_id["claims"][0]["id"] = "C" * 41
    assert web.post("/ai/narrate", json=long_id).status_code == 422


def test_narrate_endpoint_rejects_bad_requests(monkeypatch):
    use_client(monkeypatch, None)
    assert web.post("/ai/narrate", json=payload("poster")).status_code == 422
    too_many = payload()
    too_many["claims"] = [{**too_many["claims"][0], "id": f"C{i}"} for i in range(101)]
    assert web.post("/ai/narrate", json=too_many).status_code == 422
    long_text = payload()
    long_text["claims"][0]["text"] = "a" * 2001
    assert web.post("/ai/narrate", json=long_text).status_code == 422


# ---- Story view: no jargon ----


@pytest.mark.parametrize("word", ["fragile", "Variant", "variants", "verdict", "Verdicts", "robustness", "p-value", "skeptic"])
def test_story_view_rejects_jargon(word):
    sentence = f"The {word} is plain enough: {{stated}}."
    for data, field in ((with_(c_c1=sentence), "claims.C1"), (with_(headline=f"The {word} held up."), "headline"),
                        (with_(caption=f"A {word} line."), "caption")):
        narration, problems = check_narration(data, claims(), "story")
        assert narration is None
        assert any(p.startswith(field) and "jargon" in p for p in problems), problems


def test_story_view_rejects_pam50_even_when_the_claim_names_it():
    named = claims()
    named[0] = NarrateClaim("C1", "supported", "holds_under_every_variant", False, "PAM50 Luminal A was most common.")
    assert check_narration(with_(c_c1="PAM50 looks fine."), named, "checklist")[1] == []
    narration, problems = check_narration(with_(c_c1="PAM50 looks fine."), named, "story")
    assert narration is None and any("jargon" in p for p in problems)


def test_other_views_still_accept_jargon_words():
    for view in ("checklist", "evidence", "raw"):
        data = with_(c_c1="Verdict: supported; not fragile across variants.", caption="Each verdict is checked.")
        assert check_narration(data, claims(), view)[1] == [], view


def test_story_jargon_is_whole_word_and_slots_do_not_count():
    # {fragile} is a slot (a number), not the word; "verdictive" is not the word "verdict".
    data = with_(caption="Could change if counted another way: {fragile}.", c_c1="Unverdicted, robustly put: {stated}.")
    assert check_narration(data, claims(), "story")[1] == []


def test_narrate_retries_story_jargon():
    jargon = with_(caption="{fragile} claims are fragile.")
    client = ScriptedClient([jargon, good()])
    narration = narrate("story", claims(), client)
    assert narration.caption == good()["caption"]
    assert len(client.calls) == 2
    assert "jargon" in client.calls[1][1]
    # the same text is fine outside the story view
    assert narrate("checklist", claims(), ScriptedClient([jargon])).caption == jargon["caption"]


def test_story_prompt_names_the_jargon_and_other_views_do_not():
    story, _ = build_prompt("story", claims())
    for word in STORY_JARGON:
        assert word in story
    checklist, _ = build_prompt("checklist", claims())
    assert "Never use these words" not in checklist


# ---- Prompt: plain descriptions, plain solidity ----


def test_prompt_sends_solidity_as_plain_words():
    fragile = [NarrateClaim("C1", "supported", "holds_under_some_variants", False, "About 62% were female.")]
    system, user = build_prompt("story", fragile)
    for internal in ("holds_under_some_variants", "holds_under_every_variant", "not_applicable"):
        assert internal not in system + user
    assert "could change if counted another way" in user


def test_prompt_describes_slots_in_plain_words():
    system, _ = build_prompt("story", claims())
    assert "{fragile}: how many claims could change if counted another way" in system
    assert "how many ways of counting gave the same answer" in system
    assert '"higher than", "lower than" or "the same as", so follow it with "the report"' in system
    assert "how many are fragile" not in system


def test_prompt_states_singular_counts_and_plain_characters():
    system, _ = build_prompt("checklist", claims())
    assert "Claims reviewed so far: {reviewed}" in system
    assert "A count can be 1" in system
    assert "ASCII letters" in system and "em dash" in system


# ---- Per-claim slot names ----


def test_prompt_lists_each_claims_slot_names_never_values():
    some = [
        NarrateClaim("C1", "supported", "holds_under_every_variant", False, "About 62% were female.", frozenset({"stated", "data_shows"})),
        NarrateClaim("C2", "insufficient_evidence", "not_applicable", False, "Treatment worked.", frozenset()),
    ]
    _, user = build_prompt("evidence", some)
    assert '"slots": ["data_shows", "stated"]' in user
    assert '"slots": []' in user


def test_claim_slot_without_a_value_for_that_claim_rejected():
    limited = claims()
    limited[0] = NarrateClaim(
        "C1", "supported", "holds_under_every_variant", False, limited[0].text, frozenset({"stated", "data_shows"})
    )
    assert check_narration(with_(c_c1="The report says {stated}; the data shows {data_shows}."), limited)[1] == []
    narration, problems = check_narration(with_(c_c1="The data is {direction} the report."), limited)
    assert narration is None
    assert any(p.startswith("claims.C1") and "{direction}" in p and "no value" in p for p in problems)
    # audit-wide slots stay allowed in a claim with no claim slots at all
    bare = [NarrateClaim("C1", "insufficient_evidence", "not_applicable", False, "Treatment worked.", frozenset())]
    data = {"headline": "{total} claims.", "caption": "So far: {reviewed}.", "claims": {"C1": "Out of {total}: no data."}}
    assert check_narration(data, bare)[1] == []
    data["claims"]["C1"] = "The report says {stated}."
    assert check_narration(data, bare)[0] is None


def test_narrate_endpoint_passes_slot_names_through(monkeypatch):
    body = payload()
    body["claims"][1]["slots"] = ["stated"]
    fits = with_(c_c2="The report says {stated}, and the data does not back it up.")
    client = ScriptedClient([fits])
    use_client(monkeypatch, client)
    res = web.post("/ai/narrate", json=body)
    assert res.status_code == 200 and res.json()["source"] == "ai"
    assert '"slots": ["stated"]' in client.calls[0][1]
    # good() gives C2 {data_shows} and {direction}, which C2 has no value for: rejected, then the template
    use_client(monkeypatch, ScriptedClient([good(), good()]))
    res = web.post("/ai/narrate", json=body)
    assert res.json()["source"] == "template"
    assert res.json()["reason"] == "The AI wording did not pass the checks"


def test_narrate_endpoint_rejects_bad_slot_lists(monkeypatch):
    use_client(monkeypatch, None)
    unknown = payload()
    unknown["claims"][0]["slots"] = ["stated", "total"]  # an audit slot is not a claim slot
    assert web.post("/ai/narrate", json=unknown).status_code == 422
    made_up = payload()
    made_up["claims"][0]["slots"] = ["secret"]
    assert web.post("/ai/narrate", json=made_up).status_code == 422
    duplicate = payload()
    duplicate["claims"][0]["slots"] = ["stated", "stated"]
    assert web.post("/ai/narrate", json=duplicate).status_code == 422
    missing = payload()
    del missing["claims"][0]["slots"]
    assert web.post("/ai/narrate", json=missing).status_code == 422
    empty = payload()
    empty["claims"][0]["slots"] = []
    assert web.post("/ai/narrate", json=empty).status_code == 200

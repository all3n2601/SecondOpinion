import pytest

from second_opinion.ai.client import AIError, ScriptedClient
from second_opinion.ai.extract_ai import find_missed_claims
from second_opinion.model import SentenceInfo

SENTENCES = [
    SentenceInfo(0, "The cohort has 1,101 samples.", "C1"),
    SentenceInfo(1, "Most tumours here are of the luminal type.", None),
    SentenceInfo(2, "We recommend a follow-up study.", None),
    SentenceInfo(3, "Chemotherapy lengthened survival.", None),
    SentenceInfo(4, "Another claimed sentence.", "C2"),
]


def test_returns_validated_indices():
    client = ScriptedClient([{"claim_indices": [3, 1]}])
    assert find_missed_claims(SENTENCES, client) == [1, 3]


def test_indices_outside_the_provided_set_are_ignored_and_deduplicated():
    # 0 and 4 already have claims, 9 does not exist, "x"/True/2.5 are not indices
    client = ScriptedClient([{"claim_indices": [1, 0, 4, 9, -1, 1, "x", True, 2.5, 3, 3]}])
    assert find_missed_claims(SENTENCES, client) == [1, 3]


def test_empty_input_makes_no_call():
    client = ScriptedClient([])
    assert find_missed_claims([], client) == []
    assert client.calls == []


def test_all_sentences_already_claims_makes_no_call():
    client = ScriptedClient([])
    only_claims = [s for s in SENTENCES if s.claim_id is not None]
    assert find_missed_claims(only_claims, client) == []
    assert client.calls == []


def test_claim_sentences_are_never_sent_to_the_model():
    client = ScriptedClient([{"claim_indices": []}])
    assert find_missed_claims(SENTENCES, client) == []
    (system, user), = client.calls
    text = system + user
    assert "The cohort has 1,101 samples." not in text
    assert "Another claimed sentence." not in text
    for sentence in SENTENCES:
        if sentence.claim_id is None:
            assert sentence.text in user
            assert f'"index": {sentence.index}' in user


def test_model_cannot_add_sentence_text():
    client = ScriptedClient([{"claim_indices": [1], "new_sentences": ["The model invented this."]}])
    assert find_missed_claims(SENTENCES, client) == [1]


def test_malformed_answer_is_an_ai_error():
    for answer in ({"claims": [1]}, {"claim_indices": "1,2"}, {"claim_indices": None}):
        with pytest.raises(AIError):
            find_missed_claims(SENTENCES, ScriptedClient([answer]))


def test_client_error_propagates():
    with pytest.raises(AIError):
        find_missed_claims(SENTENCES, ScriptedClient([AIError("The AI service timed out")]))

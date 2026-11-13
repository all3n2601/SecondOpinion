from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
PRACTICE_BRIEF = Path(__file__).resolve().parents[1] / "docs/challenge/products/research-claim-auditor/practice_brief.md"


def test_extract_practice_brief():
    response = client.post("/extract", json={"report_text": PRACTICE_BRIEF.read_text(encoding="utf-8")})
    assert response.status_code == 200
    body = response.json()
    assert [c["id"] for c in body["claims"]] == ["C1", "C2", "C3"]
    assert [c["type"] for c in body["claims"]] == ["COUNT", "SHARE", "NOT_ANSWERABLE"]
    claim_sentences = {c["sentence_index"]: c["id"] for c in body["claims"]}
    for sentence in body["sentences"]:
        assert sentence["claim_id"] == claim_sentences.get(sentence["index"])
    assert len(body["sentences"]) > 3


def test_extract_params_survive_the_round_trip():
    body = client.post("/extract", json={"report_text": "Luminal A is about 62% of subtyped primary tumors."}).json()
    params = body["claims"][0]["params"]
    assert (params["stated_value"], params["approximate"], params["subtype"], params["unit"]) == (62, True, "Luminal A", "percent")


def test_extract_empty_report_is_422():
    for text in ("", "   \n  "):
        response = client.post("/extract", json={"report_text": text})
        assert response.status_code == 422
        assert response.json()["detail"] == "The report is empty"


def test_extract_report_with_nothing_to_check():
    response = client.post("/extract", json={"report_text": "Protein measurements add a useful layer. We thank the team."})
    assert response.status_code == 200
    body = response.json()
    assert body["claims"] == []
    assert len(body["sentences"]) == 2


def test_extract_too_long_report_is_422():
    response = client.post("/extract", json={"report_text": "Word. " * 200_000})
    assert response.status_code == 422
    assert "too long" in response.json()["detail"]


def test_extract_missing_field_is_422():
    assert client.post("/extract", json={}).status_code == 422


def test_classify_a_checkable_sentence():
    response = client.post("/classify", json={"text": "The release has 1,101 primary tumors.", "sentence_index": 4})
    assert response.status_code == 200
    body = response.json()
    assert (body["type"], body["sentence_index"], body["params"]["stated_value"]) == ("COUNT", 4, 1101)


def test_classify_sentence_with_nothing_checkable_is_unmapped():
    # The user ticked it, so it becomes a claim and the audit says "no check exists yet".
    body = client.post("/classify", json={"text": "Protein measurements add a useful layer.", "sentence_index": 5}).json()
    assert body["type"] == "UNMAPPED"
    assert body["text"] == "Protein measurements add a useful layer."


def test_classify_uses_the_given_claim_id():
    body = client.post("/classify", json={"text": "A sentence.", "sentence_index": 2, "claim_id": "C7"}).json()
    assert body["id"] == "C7"


def test_classify_empty_sentence_is_422():
    response = client.post("/classify", json={"text": "  ", "sentence_index": 0})
    assert response.status_code == 422
    assert response.json()["detail"] == "The sentence is empty"

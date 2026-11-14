"""Opening a sealed envelope from the Start page: POST /envelope/unseal runs the organizers' unseal.py."""

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app
from second_opinion import envelope
from second_opinion.envelope import EnvelopeError, code_words, envelope_name

client = TestClient(app)
PRACTICE_CODE = "orange meadow pilot lantern"  # public, from the challenge's envelopes/README.md


@pytest.mark.parametrize("raw, name", [("7", "E07"), ("07", "E07"), ("E07", "E07"), ("e7", "E07"), ("12", "E12"),
                                       ("practice", "practice"), (" Practice ", "practice")])
def test_envelope_number_as_unseal_py_names_it(raw, name):
    assert envelope_name(raw) == name


@pytest.mark.parametrize("raw", ["", "seven", "E", "07; rm", "../E07", "1234"])
def test_envelope_number_rejects_anything_else(raw):
    with pytest.raises(EnvelopeError, match="envelope number"):
        envelope_name(raw)


@pytest.mark.parametrize("raw", ["amber falcon river quartz", "Amber-Falcon-River-Quartz", "  amber  falcon river quartz "])
def test_code_words_spaces_hyphens_and_capitals(raw):
    assert code_words(raw) == ["amber", "falcon", "river", "quartz"]


@pytest.mark.parametrize("raw", ["amber falcon river", "amber falcon river quartz extra", "amber falcon river qu4rtz",
                                 "amber falcon river quartz!"])
def test_code_must_be_four_plain_words(raw):
    with pytest.raises(EnvelopeError, match="four words"):
        code_words(raw)


def test_missing_challenge_repo_says_where_it_looked(monkeypatch, tmp_path):
    monkeypatch.setenv("SO_CHALLENGE_DIR", str(tmp_path / "nowhere"))
    with pytest.raises(EnvelopeError, match="challenge repository was not found"):
        envelope.unseal("07", "amber falcon river quartz")


def test_api_turns_errors_into_400_with_the_reason(monkeypatch, tmp_path):
    monkeypatch.delenv("SO_RELEASES_ROOT", raising=False)
    response = client.post("/envelope/unseal", json={"envelope": "07", "code": "too short"})
    assert response.status_code == 400
    assert "four words" in response.json()["detail"]


def test_shared_instance_does_not_open_envelopes(monkeypatch, tmp_path):
    monkeypatch.setenv("SO_RELEASES_ROOT", str(tmp_path))
    response = client.post("/envelope/unseal", json={"envelope": "practice", "code": PRACTICE_CODE})
    assert response.status_code == 400


def _challenge_repo_ready() -> bool:
    try:
        repo = envelope.challenge_repo()
    except EnvelopeError:
        return False
    return (repo / "envelopes" / "sealed" / "practice.sealed").is_file() and (repo / "data" / "tcga-brca" / "raw" / "clinical.tsv").is_file()


@pytest.mark.skipif(not _challenge_repo_ready(), reason="needs the challenge repo with release A fetched")
def test_practice_envelope_opens_and_fills_in_the_start_page(monkeypatch):
    monkeypatch.delenv("SO_RELEASES_ROOT", raising=False)
    response = client.post("/envelope/unseal", json={"envelope": "practice", "code": PRACTICE_CODE})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["envelope"] == "practice"
    assert len(body["checks"]) == 4 and "Envelope practice opened" in body["checks"]
    assert body["report_name"] == "practice_brief.md" and "Luminal A" in body["report_text"]
    assert body["release_a_dir"].endswith("data/tcga-brca/raw")
    assert body["envelope_release_dir"].endswith("envelopes/opened/practice/release")
    assert "release/clinical.tsv" in body["files"]


@pytest.mark.skipif(not _challenge_repo_ready(), reason="needs the challenge repo with release A fetched")
def test_wrong_code_gives_unseal_py_own_message(monkeypatch):
    monkeypatch.delenv("SO_RELEASES_ROOT", raising=False)
    response = client.post("/envelope/unseal", json={"envelope": "practice", "code": "orange meadow pilot llama"})
    assert response.status_code == 400
    assert response.json()["detail"] == "That code doesn't open envelope practice. Check the envelope number and the four words"

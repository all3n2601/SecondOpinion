import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app
from second_opinion import practice
from second_opinion.release import RELEASE_FILES

client = TestClient(app)


def _fill(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name in practice.RELEASE_A_SOURCES:
        (folder / name).write_text("x")
    return folder


@pytest.fixture
def no_local_copy(monkeypatch, tmp_path):
    """No SO_RELEASE_DIR, no sibling challenge repo, and a temp folder inside tmp_path."""
    monkeypatch.delenv("SO_RELEASE_DIR", raising=False)
    monkeypatch.delenv("SO_RELEASES_ROOT", raising=False)
    monkeypatch.setattr(practice, "SIBLING_RAW", tmp_path / "no-challenge-repo")
    monkeypatch.setattr(practice, "temporary_folder", lambda: tmp_path / "temp-release")


def _fake_sources(monkeypatch, files: dict[str, bytes]):
    """Serve `files` from fake URLs, with checksums matching their contents."""
    sources = {name: (f"https://example.test/{name}", hashlib.sha256(data).hexdigest()) for name, data in files.items()}
    monkeypatch.setattr(practice, "RELEASE_A_SOURCES", sources)
    calls: list[str] = []

    def fake_retrieve(url, dest):
        calls.append(url)
        Path(dest).write_bytes(files[url.rsplit("/", 1)[1]])

    monkeypatch.setattr(practice.urllib.request, "urlretrieve", fake_retrieve)
    return calls


def test_sources_cover_every_release_file():
    assert set(RELEASE_FILES.values()) <= set(practice.RELEASE_A_SOURCES)


def test_uses_so_release_dir_when_complete(no_local_copy, monkeypatch, tmp_path):
    folder = _fill(tmp_path / "env-release")
    monkeypatch.setenv("SO_RELEASE_DIR", str(folder))
    found = practice.practice_release()
    assert (found.folder, found.source, found.downloaded) == (folder.resolve(), "environment", [])


def test_uses_challenge_repo_next_to_this_one(no_local_copy, monkeypatch, tmp_path):
    sibling = _fill(tmp_path / "sibling-raw")
    monkeypatch.setattr(practice, "SIBLING_RAW", sibling)
    assert practice.practice_release().source == "challenge_repo"


def test_downloads_into_temporary_folder_then_reuses_it(no_local_copy, monkeypatch, tmp_path):
    calls = _fake_sources(monkeypatch, {"clinical.tsv": b"a", "survival.tsv": b"b"})
    first = practice.practice_release()
    assert first.source == "temporary"
    assert first.folder == (tmp_path / "temp-release").resolve()
    assert sorted(first.downloaded) == ["clinical.tsv", "survival.tsv"]
    assert (first.folder / "clinical.tsv").read_bytes() == b"a"

    second = practice.practice_release()
    assert second.downloaded == [] and len(calls) == 2


def test_checksum_mismatch_is_refused_and_not_kept(no_local_copy, monkeypatch, tmp_path):
    _fake_sources(monkeypatch, {"clinical.tsv": b"a"})
    monkeypatch.setattr(practice, "RELEASE_A_SOURCES", {"clinical.tsv": ("https://example.test/clinical.tsv", "0" * 64)})
    with pytest.raises(practice.PracticeReleaseError, match="checksum"):
        practice.practice_release()
    assert not list((tmp_path / "temp-release").iterdir())


def test_endpoint_returns_folder(no_local_copy, monkeypatch, tmp_path):
    monkeypatch.setattr(practice, "SIBLING_RAW", _fill(tmp_path / "sibling-raw"))
    response = client.post("/practice-release")
    assert response.status_code == 200
    assert response.json()["source"] == "challenge_repo"


def test_endpoint_reports_download_failure(no_local_copy, monkeypatch):
    def boom(url, dest):
        raise OSError("network down")

    monkeypatch.setattr(practice.urllib.request, "urlretrieve", boom)
    response = client.post("/practice-release")
    assert response.status_code == 502
    assert "network down" in response.json()["detail"]


def test_endpoint_refuses_on_shared_instance(no_local_copy, monkeypatch, tmp_path):
    monkeypatch.setenv("SO_RELEASES_ROOT", str(tmp_path))
    assert client.post("/practice-release").status_code == 400

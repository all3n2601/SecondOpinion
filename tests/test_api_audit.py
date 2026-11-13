import dataclasses
import json
import time

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app
from second_opinion.model import Verdict
from tests.helpers import make_mini_release
from tests.test_audit import practice_claims

client = TestClient(app)


def _body(release_dir, claims):
    return {"release_dir": str(release_dir),
            "claims": json.loads(json.dumps([dataclasses.asdict(c) for c in claims], default=str))}


@pytest.mark.realdata
def test_audit_practice_claims_on_real_release(release_dir):
    start = time.perf_counter()
    response = client.post("/audit", json=_body(release_dir, practice_claims()))
    elapsed = time.perf_counter() - start
    assert response.status_code == 200, response.text
    audit = response.json()
    verdicts = [c["verdict"] for c in audit["claims"]]
    assert verdicts == [Verdict.SUPPORTED, Verdict.CONTRADICTED, Verdict.INSUFFICIENT_EVIDENCE]
    assert audit["claims"][1]["correct_value"] == "49.9% (421 of 844)"
    assert elapsed < 10, f"/audit took {elapsed:.1f}s"


def test_audit_on_mini_release(mini_release):
    response = client.post("/audit", json=_body(mini_release, practice_claims()))
    assert response.status_code == 200, response.text
    assert [c["verdict"] for c in response.json()["claims"]][2] == "insufficient_evidence"


def test_bad_release_dir_is_400_naming_the_folder(tmp_path):
    missing = tmp_path / "no_such_release"
    response = client.post("/audit", json=_body(missing, practice_claims()))
    assert response.status_code == 400
    assert "no_such_release" in response.json()["detail"]


def test_release_dir_that_is_a_file_is_400(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    response = client.post("/audit", json=_body(f, []))
    assert response.status_code == 400
    assert "file.txt" in response.json()["detail"]


def test_folder_missing_release_files_is_400_naming_files(tmp_path):
    response = client.post("/audit", json=_body(tmp_path, []))
    assert response.status_code == 400
    assert "clinical.tsv" in response.json()["detail"]


def test_empty_claims_returns_release_checksums(mini_release):
    response = client.post("/audit", json=_body(mini_release, []))
    assert response.status_code == 200
    data = response.json()
    assert data["claims"] == []
    assert len(data["release"]["files"]) == 5
    assert "No RNA file in this release." in data["notes"]


def test_claim_with_missing_parameters_does_not_fail_the_report(mini_release):
    from second_opinion.model import Claim, ClaimParams, ClaimType

    bad = Claim("S1", "Luminal A is a share.", 0, ClaimType.SHARE,
                ClaimParams(unit="percent", subject="primary_tumors", subtype="Luminal A"))
    response = client.post("/audit", json=_body(mini_release, [bad, *practice_claims()]))
    assert response.status_code == 200, response.text
    verdicts = [c["verdict"] for c in response.json()["claims"]]
    assert verdicts[0] == "insufficient_evidence"
    assert len(verdicts) == 4


def test_corrupt_release_is_400_naming_the_file(tmp_path):
    folder = make_mini_release(tmp_path / "corrupt")
    (folder / "clinical.tsv").write_text("")
    response = client.post("/audit", json=_body(folder, []))
    assert response.status_code == 400
    assert "clinical.tsv" in response.json()["detail"]


def test_release_with_junk_gz_is_400_naming_the_file(tmp_path):
    folder = make_mini_release(tmp_path / "junk")
    (folder / "protein_rppa.tsv.gz").write_bytes(b"not gzip at all \x00\xff")
    response = client.post("/audit", json=_body(folder, []))
    assert response.status_code == 400
    assert "protein_rppa.tsv.gz" in response.json()["detail"]


def test_release_dir_is_confined_when_root_is_set(mini_release, monkeypatch):
    monkeypatch.setenv("SO_RELEASES_ROOT", str(mini_release.parent))
    inside = client.post("/audit", json={"release_dir": mini_release.name, "claims": []})
    assert inside.status_code == 200
    for escape in ("../", "../../", str(mini_release.parent.parent), "/etc"):
        response = client.post("/audit", json={"release_dir": escape, "claims": []})
        assert response.status_code == 400
        assert "outside the allowed location" in response.json()["detail"]

import shutil

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app
from second_opinion import roles
from second_opinion.roles import ROLES_FILE, Role, add_role, load_roles


@pytest.fixture
def roles_file(tmp_path, monkeypatch):
    path = tmp_path / "roles.yaml"
    shutil.copy(ROLES_FILE, path)
    monkeypatch.setattr(roles, "ROLES_FILE", path)
    return path


def test_four_default_roles_load():
    got = {r.name: r for r in load_roles()}
    assert list(got) == ["Program leader", "Data-use reviewer", "Researcher", "Data engineer"]
    assert got["Program leader"] == Role(
        "Program leader", ["decision", "counts", "sign_off"], "summary", True, "story"
    )
    assert got["Data-use reviewer"].view == "checklist"
    assert got["Researcher"].view == "evidence"
    assert got["Data engineer"].view == "raw"
    assert got["Data engineer"].sections == ["sample_ids", "files", "code"]
    assert got["Data engineer"].detail == "full"


def test_added_role_survives_reload(roles_file):
    new = Role("Biostatistician", ["robustness", "code"], "full", False, "evidence")
    assert add_role(new)[-1] == new
    assert load_roles(roles_file)[-1] == new
    assert len(load_roles()) == 5


def test_missing_view_comes_from_detail(tmp_path):
    path = tmp_path / "roles.yaml"
    path.write_text(
        "- name: A\n  sections: [decision]\n  detail: summary\n"
        "- name: B\n  sections: [claims]\n  detail: standard\n"
        "- name: C\n  sections: [code]\n  detail: full\n",
        encoding="utf-8",
    )
    assert [r.view for r in load_roles(path)] == ["story", "checklist", "evidence"]


def test_unknown_view_is_rejected(roles_file):
    with pytest.raises(ValueError, match="story, checklist, evidence, raw"):
        add_role(Role("X", ["code"], "full", False, "fancy"))


def test_added_role_without_view_gets_one(roles_file):
    assert add_role(Role("Y", ["code"], "summary", False))[-1].view == "story"
    assert load_roles(roles_file)[-1].view == "story"


def test_duplicate_name_is_rejected(roles_file):
    with pytest.raises(ValueError, match="already exists"):
        add_role(Role(" researcher ", ["code"], "full", False))


def test_unknown_section_is_rejected(roles_file):
    with pytest.raises(ValueError, match="horoscope"):
        add_role(Role("Odd", ["horoscope"], "full", False))


def test_empty_sections_and_name_are_rejected(roles_file):
    with pytest.raises(ValueError):
        add_role(Role("Empty", [], "full", False))
    with pytest.raises(ValueError):
        add_role(Role("  ", ["code"], "full", False))


def test_api_round_trip(roles_file):
    client = TestClient(app)
    assert [r["name"] for r in client.get("/roles").json()][0] == "Program leader"
    body = {"name": "Biostatistician", "sections": ["robustness"], "detail": "full", "explain_terms": False,
            "view": "raw"}
    response = client.post("/roles", json=body)
    assert response.status_code == 200, response.text
    assert response.json()[-1] == body
    assert client.get("/roles").json()[-1] == body
    assert all("view" in r for r in client.get("/roles").json())
    assert "Biostatistician" in roles_file.read_text()


def test_api_rejects_bad_roles_with_a_message(roles_file):
    client = TestClient(app)
    dup = client.post("/roles", json={"name": "Researcher", "sections": ["code"], "detail": "full",
                                      "explain_terms": False})
    assert dup.status_code == 409
    assert "already exists" in dup.json()["detail"]
    bad = client.post("/roles", json={"name": "X", "sections": ["nope"], "detail": "full",
                                      "explain_terms": False})
    assert bad.status_code == 422
    assert "nope" in bad.json()["detail"]
    assert client.post("/roles", json={"name": "X", "sections": ["code"], "detail": "huge"}).status_code == 422

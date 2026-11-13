import dataclasses
import json

from fastapi.testclient import TestClient

from apps.api.app.main import app
from second_opinion.export import validate_audit_json
from second_opinion.model import Review
from tests.test_decision import load_fixture

client = TestClient(app)

CHOICE = {"choice": "Fix a problem", "reason": "C2 is wrong", "reviewer_role": "Data-use reviewer"}


def _plain(obj) -> dict:
    return json.loads(json.dumps(dataclasses.asdict(obj), default=str))


def _audit(reviewed: set[str]) -> dict:
    audit = load_fixture()
    for r in audit.claims:
        if r.claim.id in reviewed:
            r.review = Review(decision="accept", final_verdict=r.verdict, reason="", reviewer_role="Researcher")
    return _plain(audit)


def test_decision_endpoint_suggests_fix():
    response = client.post("/decision", json={"audit": _audit(set())})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["decision"] == "Fix a problem"
    assert "Principal investigator" in body["sign_off"]


def test_export_with_unreviewed_claim_is_422_naming_it():
    response = client.post("/export", json={"audit": _audit({"C1", "C2"}), "decision": CHOICE})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Every claim needs a review before export" in detail
    assert "C3" in detail and "C1" not in detail


def test_export_fully_reviewed_returns_valid_audit_json_and_record():
    response = client.post("/export", json={"audit": _audit({"C1", "C2", "C3"}), "decision": CHOICE})
    assert response.status_code == 200, response.text
    body = response.json()
    assert validate_audit_json(body["audit_json"]) == []
    assert body["audit_json"]["verdict"] == "Fix a problem"
    assert "421 of 844" in body["decision_record_md"]


def test_export_with_no_claims_is_allowed():
    audit = _audit(set())
    audit["claims"] = []
    response = client.post("/export", json={"audit": audit, "decision": CHOICE})
    assert response.status_code == 200, response.text
    assert response.json()["audit_json"]["findings"] == []

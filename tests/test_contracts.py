import dataclasses
import json
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from apps.api.app.main import app
from second_opinion.model import AuditResult, Verdict

FIXTURE = Path(__file__).parent / "fixtures" / "practice_audit_result.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_fixture_is_a_valid_audit_result():
    audit = TypeAdapter(AuditResult).validate_python(load_fixture())
    assert [c.verdict for c in audit.claims] == [
        Verdict.SUPPORTED,
        Verdict.CONTRADICTED,
        Verdict.INSUFFICIENT_EVIDENCE,
    ]
    assert audit.claims[1].correct_value == "49.9% (421 of 844)"
    assert len(audit.claims[1].variants) == 8


def test_audit_result_round_trips_through_json():
    adapter = TypeAdapter(AuditResult)
    audit = adapter.validate_python(load_fixture())
    text = json.dumps(dataclasses.asdict(audit))
    again = adapter.validate_python(json.loads(text))
    assert again == audit
    assert adapter.validate_json(adapter.dump_json(audit)) == audit


def test_stub_endpoints_exist():
    # Newer FastAPI wraps included routers, so read the routes from the OpenAPI schema.
    paths = set(app.openapi()["paths"])
    for path in ("/extract", "/classify", "/audit", "/decision", "/export", "/roles"):
        assert path in paths


def test_stub_endpoints_respond(mini_release):
    client = TestClient(app)
    audit = client.post("/audit", json={"release_dir": str(mini_release), "claims": []})
    assert audit.status_code == 200
    TypeAdapter(AuditResult).validate_python(audit.json())
    assert client.post("/extract", json={"report_text": "Hi."}).json() == {
        "sentences": [{"index": 0, "text": "Hi.", "claim_id": None, "original_text": "Hi."}],
        "claims": [],
    }
    assert client.get("/roles").status_code == 200

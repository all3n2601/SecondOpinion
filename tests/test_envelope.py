"""Rehearsal against an unsealed envelope release (no RNA file, no manifest).

Run after `python envelopes/unseal.py practice orange meadow pilot lantern`:
    SO_ENVELOPE_DIR=<challenge repo>/envelopes/opened/practice/release pytest tests/test_envelope.py
"""

import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app
from second_opinion.audit import audit_claims
from second_opinion.cli import main
from second_opinion.export import validate_audit_json
from second_opinion.model import Verdict
from tests.test_audit import practice_claims

ENVELOPE_DIR = os.environ.get("SO_ENVELOPE_DIR")
pytestmark = pytest.mark.skipif(
    not ENVELOPE_DIR or not Path(ENVELOPE_DIR).is_dir(),
    reason="set SO_ENVELOPE_DIR to an unsealed envelope's release/ folder",
)


def test_practice_claims_on_envelope_release():
    start = time.perf_counter()
    audit = audit_claims(practice_claims(), ENVELOPE_DIR)
    assert time.perf_counter() - start < 10
    assert [c.verdict for c in audit.claims] == [
        Verdict.SUPPORTED, Verdict.CONTRADICTED, Verdict.INSUFFICIENT_EVIDENCE]
    assert "No RNA file in this release." in audit.notes
    assert audit.claims[1].correct_value == "49.9% (421 of 844)"
    assert len(audit.claims[1].variants) == 8


def test_rna_claim_is_insufficient_not_a_crash():
    from second_opinion.model import Claim, ClaimParams, ClaimType
    claim = Claim("C9", "Every primary tumor has RNA data.", 0, ClaimType.COVERAGE,
                  ClaimParams(unit="all", subject="has_rna"))
    result = audit_claims([claim], ENVELOPE_DIR).claims[0]
    assert result.verdict is Verdict.INSUFFICIENT_EVIDENCE
    assert "no rna file" in result.missing_evidence.lower()


def test_api_and_cli_agree_on_envelope(tmp_path):
    claims = practice_claims()
    from dataclasses import asdict
    body = {"release_dir": ENVELOPE_DIR, "claims": [json.loads(json.dumps(asdict(c), default=str)) for c in claims]}
    api = TestClient(app).post("/audit", json=body)
    assert api.status_code == 200
    claims_file = tmp_path / "claims.json"
    claims_file.write_text(json.dumps(body["claims"]))
    out = tmp_path / "audit.json"
    main(["--release", ENVELOPE_DIR, "--claims-json", str(claims_file), "--out", str(out)])
    doc = json.loads(out.read_text())
    assert validate_audit_json(doc) == []
    assert [f["claim_verdict"] for f in doc["findings"]] == [c["verdict"] for c in api.json()["claims"]]

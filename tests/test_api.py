from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "second-opinion-api"}


def test_api_exposes_all_engine_variants():
    response = client.get("/variants")
    assert response.status_code == 200
    variants = response.json()
    assert len(variants) == 8
    assert len({variant["id"] for variant in variants}) == 8
    assert {variant["subtype_source"] for variant in variants} == {
        "rna_call", "study_2012_label"
    }
    assert {variant["sex_filter"] for variant in variants} == {"everyone", "women_only"}
    assert {variant["sample_scope"] for variant in variants} == {
        "primary_tumors", "all_samples"
    }

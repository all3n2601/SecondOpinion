"""The blind scorer's text normalising and matching. Fast: no release data and no AI."""

from tests.blind.score import match, norm


def finding(fid, text, verdict):
    return {"id": fid, "norm": norm(text), "verdict": verdict}


def test_norm_straightens_quotes_dashes_and_markdown():
    assert norm("“Luminal A” – **62%**") == '"luminal a" - 62%'


def test_match_gives_correct_wrong_and_missed():
    entries = [
        {"report": "r1.md", "claim_contains": "808 were ER-positive", "verdict": "supported"},
        {"report": "r1.md", "claim_contains": "about 64% of tumors", "verdict": "contradicted"},
        {"report": "r1.md", "claim_contains": "never picked up", "verdict": "supported"},
    ]
    findings = [
        finding("c1", "808 were ER-positive, roughly 77%", "supported"),
        finding("c2", "PR-positive at about 64% of tumors", "supported"),
        finding("c3", "an unrelated sentence", "supported"),
    ]
    out = match(entries, findings)
    assert [e["outcome"] for e in out] == ["correct", "wrong", "missed"]
    assert out[0]["ours"]["id"] == "c1"
    assert out[1]["ours"]["verdict"] == "supported"
    assert out[2]["ours"] is None

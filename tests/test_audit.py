import json
import sys

import pytest
from pydantic import TypeAdapter

from second_opinion.audit import audit_claims
from second_opinion.export import validate_audit_json
from second_opinion.model import AuditResult, Claim, ClaimParams, ClaimType, Solidity, Verdict

NO_RNA_NOTE = "No RNA file in this release."


def practice_claims() -> list[Claim]:
    """The three practice-report claims, built by hand with the fixture's params."""
    c1 = Claim(
        "C1",
        "Of the 1,101 primary tumors in the release, 535 have survival, mutation, copy number, RNA and protein data.",
        1, ClaimType.COUNT,
        ClaimParams(stated_value=535, stated_total=1101, unit="count", subject="all_five_layers"),
    )
    c2 = Claim(
        "C2", "Luminal A is about 62% of primary tumors with an RNA subtype call.", 2,
        ClaimType.SHARE,
        ClaimParams(stated_value=62, unit="percent", approximate=True,
                    subject="primary_tumors", subtype="Luminal A"),
    )
    c3 = Claim(
        "C3", "Tumors with the highest ER-alpha protein responded best to hormone therapy.", 3,
        ClaimType.NOT_ANSWERABLE, needed_data="treatment and treatment-response data",
        clinical_terms=["responded", "hormone therapy"],
    )
    return [c1, c2, c3]


@pytest.mark.realdata
def test_practice_claims_on_real_release(release_dir):
    audit = audit_claims(practice_claims(), release_dir)
    assert [c.verdict for c in audit.claims] == [
        Verdict.SUPPORTED, Verdict.CONTRADICTED, Verdict.INSUFFICIENT_EVIDENCE]
    assert audit.claims[1].correct_value == "49.9% (421 of 844)"
    assert "treatment" in audit.claims[2].missing_evidence
    assert audit.claims[2].solidity == Solidity.NOT_APPLICABLE
    assert audit.claims[2].fact is None
    assert audit.claims[0].fact.numerator == 535
    assert "844 of 1,101" in audit.claims[1].limitation
    assert "RNA" in audit.claims[0].limitation
    assert audit.release.name == "A" or audit.release.name == release_dir.name
    if audit.release.name == release_dir.name or release_dir.name == "raw":
        assert len(audit.release.files) == 5


def test_empty_claims_returns_checksums(mini_release):
    audit = audit_claims([], mini_release)
    assert audit.claims == []
    names = [f["file"] for f in audit.release.files]
    assert names == sorted(names) and len(names) == 5
    assert all(len(f["sha256"]) == 64 for f in audit.release.files)
    assert audit.release.name == "mini_release"


def test_no_rna_note(mini_release):
    assert NO_RNA_NOTE in audit_claims([], mini_release).notes


def test_release_named_raw_is_release_a(mini_release, tmp_path):
    from tests.helpers import make_mini_release

    raw = make_mini_release(tmp_path / "elsewhere" / "raw")
    assert audit_claims([], raw).release.name == "A"


def test_not_answerable_routes_to_insufficient(mini_release):
    claim = practice_claims()[2]
    (result,) = audit_claims([claim], mini_release).claims
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence == "treatment and treatment-response data"
    assert result.solidity == Solidity.NOT_APPLICABLE
    assert result.fact is None and result.correct_value is None
    assert result.variants == [] and result.flips_on == []


def test_unmapped_routes_to_insufficient(mini_release):
    claim = Claim("C7", "Something odd.", 0, ClaimType.UNMAPPED)
    (result,) = audit_claims([claim], mini_release).claims
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert result.missing_evidence == "No check exists yet for this kind of claim"
    assert result.solidity == Solidity.NOT_APPLICABLE


def test_cannot_check_becomes_insufficient_evidence(mini_release):
    claim = Claim("C4", "Every primary tumor has RNA data.", 0, ClaimType.COVERAGE,
                  ClaimParams(unit="all", subject="has_rna"))
    (result,) = audit_claims([claim], mini_release).claims
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert "no RNA file" in result.missing_evidence
    assert result.fact is None


def test_checked_claims_on_mini_release(mini_release):
    from tests.helpers import MINI

    claims = practice_claims()[:2]
    claims[0].params.stated_value = MINI["all_layers_primary"]
    claims[0].params.stated_total = MINI["primary"]
    results = audit_claims(claims, mini_release).claims
    assert results[0].verdict == Verdict.SUPPORTED
    assert results[1].verdict == Verdict.CONTRADICTED
    n, d = results[1].fact.numerator, results[1].fact.denominator
    assert results[1].correct_value.endswith(f"({n} of {d})")
    assert f"{d} of {MINI['primary']} primary tumors" in results[1].limitation


def test_checksum_mismatch_against_sources_csv(mini_release):
    sources = mini_release.parent / "sources.csv"
    sources.write_text("file,layer,sha256\nclinical.tsv,clinical,deadbeef\nsurvival.tsv,x,\n")
    notes = audit_claims([], mini_release).notes
    assert "Checksum mismatch: clinical.tsv" in notes
    assert "Checksum mismatch: survival.tsv" not in notes  # empty fingerprint is not a claim


def test_matching_sources_csv_adds_no_mismatch(mini_release):
    audit = audit_claims([], mini_release)
    rows = "\n".join(f"{f['file']},x,{f['sha256']}" for f in audit.release.files)
    (mini_release.parent / "sources.csv").write_text("file,layer,sha256\n" + rows + "\n")
    assert not [n for n in audit_claims([], mini_release).notes if n.startswith("Checksum mismatch")]


def test_unrelated_sources_csv_is_skipped_silently(mini_release):
    (mini_release.parent / "sources.csv").write_text("nct_id,title\nNCT1,x\n")
    assert audit_claims([], mini_release).notes == [NO_RNA_NOTE]


def test_missing_release_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        audit_claims([], tmp_path / "nope")


def test_audit_result_round_trips_through_json(mini_release):
    import dataclasses

    audit = audit_claims(practice_claims(), mini_release)
    data = json.loads(json.dumps(dataclasses.asdict(audit), default=str))
    assert TypeAdapter(AuditResult).validate_python(data).claims[1].verdict == audit.claims[1].verdict


def test_cli_with_claims_json_writes_audit_result(mini_release, tmp_path, monkeypatch, capsys):
    import dataclasses

    from second_opinion import cli

    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps([dataclasses.asdict(c) for c in practice_claims()], default=str))
    report = tmp_path / "report.md"
    report.write_text("# report\n")
    out = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", [
        "second-opinion", "--release", str(mini_release), "--report", str(report),
        "--claims-json", str(claims_path), "--out", str(out)])
    cli.main()
    doc = json.loads(out.read_text())  # the CLI writes audit.json (shared findings format)
    assert validate_audit_json(doc) == []
    assert len(doc["findings"]) == 3
    assert doc["findings"][2]["claim_verdict"] == Verdict.INSUFFICIENT_EVIDENCE


def test_cli_bad_release_exits_cleanly(tmp_path, monkeypatch, capsys):
    from second_opinion import cli

    report = tmp_path / "report.md"
    report.write_text("x")
    (tmp_path / "c.json").write_text("[]")
    monkeypatch.setattr(sys, "argv", [
        "second-opinion", "--release", str(tmp_path / "nope"), "--report", str(report),
        "--claims-json", str(tmp_path / "c.json"), "--out", str(tmp_path / "o.json")])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code not in (0, None)
    assert "nope" in capsys.readouterr().err


# --- one bad claim must never fail the whole audit ---------------------------------------------

def _bad_claims() -> list[Claim]:
    share_no_value = Claim("S1", "Luminal A is a share.", 0, ClaimType.SHARE,
                           ClaimParams(unit="percent", subject="primary_tumors", subtype="Luminal A"))
    comparison_no_direction = Claim("K1", "ER-alpha differs.", 1, ClaimType.COMPARISON,
                                    ClaimParams(measure="ER-alpha protein", group_a="ER-positive", group_b="ER-negative"))
    count_total_but_no_denominator = Claim(
        "N1", "10 of 12 primary tumors.", 2, ClaimType.COUNT,
        ClaimParams(stated_value=10, stated_total=12, unit="count", subject="primary_tumors"))
    return [share_no_value, comparison_no_direction, count_total_but_no_denominator]


def test_claims_with_missing_parameters_become_insufficient_evidence(mini_release):
    good = practice_claims()[2]
    audit = audit_claims([*_bad_claims(), good], mini_release)  # must not raise
    assert len(audit.claims) == 4
    for result in audit.claims[:3]:
        assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
        assert result.solidity == Solidity.NOT_APPLICABLE
        assert result.missing_evidence
        assert "Traceback" not in result.missing_evidence
    assert audit.claims[3].verdict == Verdict.INSUFFICIENT_EVIDENCE  # the not-answerable one, untouched
    assert "treatment" in audit.claims[3].missing_evidence


@pytest.mark.realdata
def test_claims_with_missing_parameters_on_real_release(release_dir):
    audit = audit_claims(_bad_claims(), release_dir)
    assert [c.verdict for c in audit.claims] == [Verdict.INSUFFICIENT_EVIDENCE] * 3


def test_missing_stated_value_message_is_plain(mini_release):
    (result,) = audit_claims(_bad_claims()[:1], mini_release).claims
    assert "no number" in result.missing_evidence.lower()


def test_missing_subtype_column_names_the_column(mini_release):
    import pandas as pd

    clinical = pd.read_csv(mini_release / "clinical.tsv", sep="\t").drop(columns=["PAM50Call_RNAseq"])
    clinical.to_csv(mini_release / "clinical.tsv", sep="\t", index=False)
    claim = practice_claims()[1]
    (result,) = audit_claims([claim], mini_release).claims
    assert result.verdict == Verdict.INSUFFICIENT_EVIDENCE
    assert "PAM50Call_RNAseq" in result.missing_evidence
    assert result.fact is None


def _fake_extract(monkeypatch, claims):
    import types

    from second_opinion import cli  # noqa: F401

    module = types.ModuleType("second_opinion.extract")

    class ExtractResult:
        def __init__(self, sentences, claims):
            self.sentences, self.claims = sentences, claims

    module.ExtractResult = ExtractResult
    module.extract_claims = lambda text: ExtractResult(["a sentence."], list(claims))
    monkeypatch.setitem(sys.modules, "second_opinion.extract", module)


def _cli_args(monkeypatch, release, tmp_path):
    report = tmp_path / "report.md"
    report.write_text("Some report text.\n")
    out = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", [
        "second-opinion", "--release", str(release), "--report", str(report), "--out", str(out)])
    return out


def test_cli_uses_claims_from_extract_result(mini_release, tmp_path, monkeypatch):
    from second_opinion import cli

    _fake_extract(monkeypatch, practice_claims())
    out = _cli_args(monkeypatch, mini_release, tmp_path)
    cli.main()
    doc = json.loads(out.read_text())
    assert validate_audit_json(doc) == []
    assert len(doc["findings"]) == 3


def test_cli_with_zero_claims_says_nothing_checkable_and_exits_zero(mini_release, tmp_path, monkeypatch, capsys):
    from second_opinion import cli

    _fake_extract(monkeypatch, [])
    out = _cli_args(monkeypatch, mini_release, tmp_path)
    cli.main()  # must not raise SystemExit(nonzero)
    assert "Nothing checkable found in the report." in capsys.readouterr().out
    doc = json.loads(out.read_text())
    assert validate_audit_json(doc) == []
    assert doc["findings"] == []


def test_missing_optional_column_used_only_by_a_variant_does_not_fail_the_audit(mini_release):
    import pandas as pd

    clinical = pd.read_csv(mini_release / "clinical.tsv", sep="\t").drop(columns=["PAM50_mRNA_nature2012"])
    clinical.to_csv(mini_release / "clinical.tsv", sep="\t", index=False)
    (result,) = audit_claims([practice_claims()[1]], mini_release).claims  # primary check works without it
    assert result.verdict in (Verdict.SUPPORTED, Verdict.CONTRADICTED)

"""Command line: second-opinion --release <dir> --report <report.md|.pdf> [--claims-json c.json] --out audit.json"""

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from second_opinion.model import Claim
from second_opinion.release import ReleaseError


def _fail(message: str) -> "None":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def _load_claims(args: argparse.Namespace) -> list[Claim]:
    if args.claims_json:
        try:
            raw = Path(args.claims_json).read_text(encoding="utf-8")
            return TypeAdapter(list[Claim]).validate_json(raw)
        except FileNotFoundError:
            _fail(f"claims file not found: {args.claims_json}")
        except (ValidationError, ValueError) as exc:
            _fail(f"{args.claims_json} is not a valid list of claims: {exc}")
    try:
        from second_opinion.extract import extract_claims
    except ImportError:
        _fail("claim extraction is not available yet; pass --claims-json <file> with the claims to audit")
    text = read_report(args.report)
    result = extract_claims(text)
    try:  # the optional AI helper flags factual sentences the rules skipped (rules-only on any failure)
        from second_opinion.ai.client import make_client
        from second_opinion.ai.extract_ai import add_missed_claims

        result = add_missed_claims(result, make_client())
    except Exception:  # noqa: BLE001
        pass
    return result.claims


def read_report(path: str) -> str:
    """The report's text: Markdown or text (UTF-8, else Windows-1252), or the text layer of a PDF."""
    from second_opinion.report_file import ReportFileError, read_report_file

    try:
        raw = Path(path).read_bytes()
    except FileNotFoundError:
        _fail(f"report not found: {path}")
    except OSError as exc:
        _fail(f"cannot read the report {path}: {exc}")
    try:
        return read_report_file(raw, path).text
    except ReportFileError as exc:
        _fail(f"{path}: {exc}")


def _print_table(audit) -> None:
    """One line per claim, so a person watching the run sees every verdict at once."""
    try:
        from second_opinion.export import plain_flip
    except ImportError:  # an export module without the helper (tests swap it out)
        def plain_flip(flip: str) -> str:
            return flip

    mark = {"supported": "SUPPORTED   ", "contradicted": "CONTRADICTED", "insufficient_evidence": "INSUFFICIENT"}
    for r in audit.claims:
        text = " ".join(r.claim.text.split())
        print(f"  {r.claim.id:<4} {mark[r.verdict.value]}  {text[:90]}{'...' if len(text) > 90 else ''}")
        if r.correct_value:
            print(f"        data shows: {r.correct_value}")
        elif r.missing_evidence:
            print(f"        would need: {r.missing_evidence[:150]}")
        if r.solidity.value == "holds_under_some_variants" and r.flips_on:
            print(f"        fragile: changes when {plain_flip(r.flips_on[0])}")
        for note in r.notes:
            print(f"        {note}")
    counts = {v: sum(1 for r in audit.claims if r.verdict.value == v) for v in mark}
    print(f"  {len(audit.claims)} claims: {counts['supported']} supported, {counts['contradicted']} contradicted, "
          f"{counts['insufficient_evidence']} insufficient evidence. Every verdict needs a person's review.")


def _json_default(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)  # enums


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="second_opinion")
    parser.add_argument("--release", required=True, help="folder with the five TCGA-BRCA release files")
    parser.add_argument("--report", help="report to audit (Markdown, text or PDF); not needed with --claims-json")
    parser.add_argument("--claims-json", help="JSON list of claims; skips claim extraction")
    parser.add_argument("--out", default="audit.json", help="where to write audit.json")
    parser.add_argument("--no-ai", action="store_true", help="do not use the optional AI helper in this run")
    parser.add_argument("--quiet", action="store_true", help="do not print the verdict table")
    args = parser.parse_args(argv)
    if not args.report and not args.claims_json:
        parser.error("give --report <report.md> (or --claims-json <claims.json>)")

    if args.no_ai:
        os.environ["SO_AI"] = "off"  # the AI layer reads this; later calls in this process see it too
    from second_opinion.ai.config import ai_status
    from second_opinion.audit import audit_claims

    status = ai_status()
    if status["enabled"]:
        print(f"AI helper on ({status['model']})")
    claims = _load_claims(args)
    try:
        audit = audit_claims(claims, args.release)
    except (FileNotFoundError, ReleaseError) as exc:
        _fail(str(exc))

    try:
        from second_opinion.export import build_audit_json, validate_audit_json
    except ImportError:
        build_audit_json = validate_audit_json = None

    out = Path(args.out)
    if build_audit_json is not None:
        document = build_audit_json(audit, None)
        problems = validate_audit_json(document)
        if problems:
            _fail("audit.json does not match the shared format:\n  " + "\n  ".join(problems))
        out.write_text(json.dumps(document, indent=2, default=_json_default), encoding="utf-8")
        if not args.quiet:
            _print_table(audit)
        print(f"Wrote {out} (release {audit.release.name}; passes the shared-format checks)")
    else:
        out.write_text(json.dumps(dataclasses.asdict(audit), indent=2, default=_json_default), encoding="utf-8")
        print(f"Wrote {out} (AuditResult JSON; audit.json export isn't available yet)")
    if not claims:
        print("Nothing checkable found in the report.")


if __name__ == "__main__":
    main()

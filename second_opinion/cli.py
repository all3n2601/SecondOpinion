"""Command line: second-opinion --release <dir> --report <report.md> [--claims-json c.json] --out audit.json"""

import argparse
import dataclasses
import json
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
    try:
        text = Path(args.report).read_text(encoding="utf-8")
    except FileNotFoundError:
        _fail(f"report not found: {args.report}")
    return extract_claims(text).claims


def _json_default(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)  # enums


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="second_opinion")
    parser.add_argument("--release", required=True, help="folder with the five TCGA-BRCA release files")
    parser.add_argument("--report", help="report to audit (Markdown or text); not needed with --claims-json")
    parser.add_argument("--claims-json", help="JSON list of claims; skips claim extraction")
    parser.add_argument("--out", default="audit.json", help="where to write audit.json")
    args = parser.parse_args(argv)
    if not args.report and not args.claims_json:
        parser.error("give --report <report.md> (or --claims-json <claims.json>)")

    from second_opinion.audit import audit_claims

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
        print(f"Wrote {out}")
    else:
        out.write_text(json.dumps(dataclasses.asdict(audit), indent=2, default=_json_default), encoding="utf-8")
        print(f"Wrote {out} (AuditResult JSON; audit.json export isn't available yet)")
    if not claims:
        print("Nothing checkable found in the report.")


if __name__ == "__main__":
    main()

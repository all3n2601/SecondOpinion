"""Audit every *_report.md here twice, rules only and with the AI helper, and score both against the expected verdicts.

Not a pytest test: the AI pass calls the configured model, so its answers can change between runs.

  SO_RELEASE_DIR=../oncosys-hackathon-challenge/data/tcga-brca/raw .venv/bin/python tests/ai_hard/compare.py [name ...]

Names pick reports ("numbers" runs numbers_report.md); with none, every report runs. `--rules` skips the AI pass.
The last run's rows are saved to last_run.json (git-ignored) for the bug list.
"""

import json
import os
import sys
import time
from pathlib import Path

from second_opinion.ai.client import make_client
from second_opinion.ai.extract_ai import add_missed_claims
from second_opinion.audit import audit_claims
from second_opinion.extract import extract_claims

HERE = Path(__file__).resolve().parent
NOT_READ = "not read"  # the sentence never became a claim, so nothing checked it


def _read_number(result) -> float | None:
    """The number the rules or the AI plan read from the sentence."""
    if result.ai_plan and result.ai_plan.get("stated"):
        return result.ai_plan["stated"].get("value")
    return result.claim.params.stated_value


def _score(row: dict, verdict: str, read: float | None) -> str:
    """ok, X (wrong verdict), or luck (right verdict from a misread number)."""
    if verdict != row["verdict"]:
        return "X"
    if "stated" in row and (read is None or min(abs(read * k - row["stated"]) for k in (1, 12, 365.25)) > 0.1 + 0.002 * row["stated"]):
        return "luck"  # (a time read in years is compared in the report's own unit: months or days too)
    return "ok"


def _detail(r) -> str:
    how = "AI plan" if r.ai_plan else r.claim.source
    if r.correct_value:
        return f"{how}, data: {r.correct_value}"
    if r.fact is not None:
        value = f"{r.fact.value:g}" if isinstance(r.fact.value, float) else r.fact.value
        return f"{how}, data: {value} ({r.fact.label[:60]})"
    if r.missing_evidence:
        return f"{how}, needs: {r.missing_evidence[:90]}"
    return how


def run(report: Path, expected: list[dict], release_dir: str, use_ai: bool) -> tuple[dict[str, dict], float]:
    """{claim_contains: row} for every expected row, and the seconds the pass took."""
    if use_ai:
        os.environ.pop("SO_AI", None)
    else:
        os.environ["SO_AI"] = "off"
    started = time.perf_counter()
    extracted = extract_claims(report.read_text(encoding="utf-8"))
    client = make_client()
    if use_ai and client is None:
        sys.exit("The AI helper is off: set SO_AI_API_KEY and SO_AI_MODEL in .env")
    if client is not None:
        extracted = add_missed_claims(extracted, client)
    results = audit_claims(extracted.claims, release_dir, ai_client=client).claims
    rows: dict[str, dict] = {}
    for row in expected:
        found = [r for r in results if row["claim_contains"] in r.claim.text]
        if not found:
            rows[row["claim_contains"]] = {"verdict": NOT_READ, "read": None, "detail": "", "type": None}
            continue
        r = found[0]
        rows[row["claim_contains"]] = {
            "verdict": r.verdict.value, "read": _read_number(r), "detail": _detail(r), "type": r.claim.type.value,
            "plan": r.ai_plan,
        }
    return rows, time.perf_counter() - started


def main() -> None:
    release_dir = os.environ.get("SO_RELEASE_DIR")
    if not release_dir:
        sys.exit("Set SO_RELEASE_DIR to the release A folder")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    with_ai = "--rules" not in sys.argv
    reports = sorted(HERE.glob("*_report.md"))
    if args:
        reports = [r for r in reports if any(r.stem.startswith(a) for a in args)]

    totals = {"rules": 0, "ai": 0, "n": 0}
    saved = []
    for report in reports:
        expected = json.loads(report.with_suffix(".expected.json").read_text(encoding="utf-8"))
        rules, rules_s = run(report, expected, release_dir, use_ai=False)
        ai, ai_s = run(report, expected, release_dir, use_ai=True) if with_ai else (rules, 0.0)
        print(f"\n## {report.stem}  (rules {rules_s:.1f} s, AI {ai_s:.1f} s)")
        print(f"{'claim':<40} {'expected':<22} {'rules':<28} {'with AI':<28} detail (AI pass)")
        for row in expected:
            key, want = row["claim_contains"], row["verdict"]
            r, a = rules[key], ai[key]
            r_mark, a_mark = _score(row, r["verdict"], r["read"]), _score(row, a["verdict"], a["read"])
            totals["rules"] += r_mark == "ok"
            totals["ai"] += a_mark == "ok"
            totals["n"] += 1
            print(f"{key[:39]:<40} {want:<22} {r['verdict'] + ' ' + r_mark:<28} {a['verdict'] + ' ' + a_mark:<28} {a['detail']}")
            saved.append({"report": report.stem, **row, "rules": {**r, "mark": r_mark}, "ai": {**a, "mark": a_mark}})

    (HERE / "last_run.json").write_text(json.dumps(saved, indent=1, default=str), encoding="utf-8")
    print("\nok = right verdict from the right number; luck = right verdict from a misread number; X = wrong")
    print(f"Rules only: {totals['rules']}/{totals['n']}")
    if with_ai:
        print(f"With AI:    {totals['ai']}/{totals['n']}")


if __name__ == "__main__":
    main()

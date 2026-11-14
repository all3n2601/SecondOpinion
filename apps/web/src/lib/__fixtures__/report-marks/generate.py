"""Dump real extractor output for the report-marks tests.

Run from the repo root:  PYTHONUTF8=1 .venv/Scripts/python.exe apps/web/src/lib/__fixtures__/report-marks/generate.py
Pass report paths and `--out DIR` to dump other reports (e.g. every test report, for a one-off placement check).
Each JSON file holds the report text exactly as read and the claims as the web app receives them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from second_opinion.extract import extract_claims

HERE = Path(__file__).resolve().parent
DEFAULT_REPORTS = [
    "docs/challenge/products/research-claim-auditor/practice_brief.md",
    "tests/ai_hard/blindB1_report.md",  # tables, one with a "%" header
    "tests/reports/report_13.md",  # headings, long paragraphs
    "tests/reports/report_11.md",  # a bullet list
    "tests/ai_hard/blindB3_report.md",  # bullets between paragraphs
]


def dump(report: Path, out_dir: Path) -> int:
    # newline="" keeps the file's own line endings, like a browser reading an upload.
    text = report.read_text(encoding="utf-8", newline="")
    claims = [
        {"id": c.id, "text": c.text, "original_text": c.original_text, "sentence_index": c.sentence_index}
        for c in extract_claims(text).claims
    ]
    (out_dir / f"{report.stem}.json").write_text(
        json.dumps({"source": report.as_posix(), "reportText": text, "claims": claims}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    return len(claims)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="*", default=DEFAULT_REPORTS)
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    total = sum(dump(Path(r), args.out) for r in args.reports)
    print(f"{len(args.reports)} reports, {total} claims -> {args.out}")


if __name__ == "__main__":
    main()

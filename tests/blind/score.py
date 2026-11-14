"""Score the auditor against blind test reports and their answer keys.

usage: python tests/blind/score.py SETS_DIR [--ai] [--json OUT]

SETS_DIR holds blindset*/ folders, each with report .md files, key.json and nonclaims.json. Needs the real release in
SO_RELEASE_DIR. Rules only by default (the AI layer is switched off); --ai runs the app's normal path with the AI helper
from .env: it adds the claims the rules missed, then audits with the AI plan executor. The AI mode sends report text to
the configured AI host.

Matching: a key entry matches the first finding whose claim text (or original sentence) contains `claim_contains`, after
`norm` on both sides. A non-claim counts as flagged when a finding contains its `contains` text.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time

# Row labels for the printed table, in order. Every key entry lands in exactly one.
CATEGORIES = (
    "correct",
    "true_called_contradicted",
    "wrong_called_supported",
    "cant_check",
    "other_wrong",
    "not_picked_up",
)


def norm(text: str) -> str:
    """Lower-case, straight quotes and dashes, no markdown marks, single spaces."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace(" ", " ").replace(" ", " ")
    text = re.sub(r"[*_`]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def match(entries: list[dict], findings: list[dict]) -> list[dict]:
    """Each key entry plus `outcome` (correct / wrong / missed) and `ours` (the matched finding, or None).

    `findings` are dicts with `norm` (the normalised claim text plus original text) and `verdict`. The first finding
    containing the entry's normalised `claim_contains` wins.
    """
    results = []
    for entry in entries:
        rows = [f for f in findings if "norm" in f and norm(entry["claim_contains"]) in f["norm"]]
        if not rows:
            outcome, ours = "missed", None
        else:
            ours = rows[0]
            outcome = "correct" if ours["verdict"] == entry["verdict"] else "wrong"
        results.append({**entry, "outcome": outcome, "ours": ours})
    return results


def category(result: dict) -> str:
    """Which table row a matched key entry belongs to."""
    if result["outcome"] == "correct":
        return "correct"
    if result["outcome"] == "missed":
        return "not_picked_up"
    key, ours = result["verdict"], result["ours"]["verdict"]
    if ours == "insufficient_evidence":
        return "cant_check"
    if key == "supported" and ours == "contradicted":
        return "true_called_contradicted"
    if key == "contradicted" and ours == "supported":
        return "wrong_called_supported"
    return "other_wrong"  # e.g. the key says it cannot be checked and we gave a verdict


def _rows(audit) -> list[dict]:
    rows = []
    for r in audit.claims if audit else []:
        rows.append({
            "id": r.claim.id,
            "text": r.claim.text,
            "norm": norm(r.claim.text + " " + (r.claim.original_text or "")),
            "type": getattr(r.claim.type, "value", str(r.claim.type)),
            "verdict": getattr(r.verdict, "value", str(r.verdict)),
            "correct_value": r.correct_value,
            "missing": r.missing_evidence,
            "limitation": r.limitation,
            "source": getattr(r.claim, "source", "rules"),
        })
    return rows


def score_set(folder: str, release_dir: str, client) -> dict:
    """Run every report in one blindset folder and score it against its key."""
    from second_opinion.ai.extract_ai import add_missed_claims
    from second_opinion.audit import audit_claims
    from second_opinion.extract import extract_claims

    with open(os.path.join(folder, "key.json"), encoding="utf-8") as f:
        key = json.load(f)
    with open(os.path.join(folder, "nonclaims.json"), encoding="utf-8") as f:
        nonclaims = json.load(f)
    reports = sorted({e["report"] for e in key} | {n["report"] for n in nonclaims})

    findings: dict[str, list[dict]] = {}
    for report in reports:
        with open(os.path.join(folder, report), encoding="utf-8") as f:
            text = f.read()
        try:
            extracted = extract_claims(text)
            if client is not None:  # what POST /extract returns
                extracted = add_missed_claims(extracted, client)
            claims = extracted.claims
            findings[report] = _rows(audit_claims(claims, release_dir, client) if claims else None)
        except Exception as exc:  # a crash is a result too
            findings[report] = [{"error": f"{type(exc).__name__}: {exc}"}]

    entries: list[dict] = []
    for report in sorted({e["report"] for e in key}):
        entries.extend(match([e for e in key if e["report"] == report], findings.get(report, [])))
    for e in entries:
        e["category"] = category(e)

    flagged, matched = [], {(e["report"], e["ours"]["id"]) for e in entries if e["ours"]}
    for n in nonclaims:
        rows = [f for f in findings.get(n["report"], []) if "norm" in f and norm(n["contains"]) in f["norm"]]
        if rows:
            flagged.append({**n, "finding": rows[0]})
            matched.update((n["report"], f["id"]) for f in rows)
    extras = [
        {"report": rep, **f}
        for rep, rows in findings.items()
        for f in rows
        if "norm" in f and (rep, f["id"]) not in matched
    ]
    errors = [{"report": rep, **f} for rep, rows in findings.items() for f in rows if "error" in f]
    counts = {c: sum(e["category"] == c for e in entries) for c in CATEGORIES}
    return {
        "entries": entries,
        "counts": counts,
        "total": len(entries),
        "nonclaims": len(nonclaims),
        "flagged": flagged,
        "extras": extras,
        "errors": errors,
    }


HEADER = ["set", "correct", "true->contradicted", "wrong->supported", "can't check", "other wrong", "not picked up",
          "non-claims flagged"]


def format_table(sets: dict[str, dict]) -> str:
    """Per-set rows plus a Total row, as a markdown table."""
    rows, total = [], {c: 0 for c in CATEGORIES} | {"total": 0, "flagged": 0, "nonclaims": 0}

    def line(name, counts, n, flagged, nonclaims):
        cells = [name, f"{counts['correct']}/{n}"] + [str(counts[c]) for c in CATEGORIES[1:]]
        return "| " + " | ".join(cells + [f"{flagged}/{nonclaims}"]) + " |"

    for name, s in sets.items():
        rows.append(line(name, s["counts"], s["total"], len(s["flagged"]), s["nonclaims"]))
        for c in CATEGORIES:
            total[c] += s["counts"][c]
        total["total"] += s["total"]
        total["flagged"] += len(s["flagged"])
        total["nonclaims"] += s["nonclaims"]
    rows.append(line("**Total**", total, total["total"], total["flagged"], total["nonclaims"]))
    head = "| " + " | ".join(HEADER) + " |\n|" + "---|" * len(HEADER)
    return head + "\n" + "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sets_dir")
    parser.add_argument("--ai", action="store_true", help="use the AI helper configured in .env, as the app does")
    parser.add_argument("--json", metavar="OUT", help="also write every entry and finding to this file")
    args = parser.parse_args(argv)

    release_dir = os.environ.get("SO_RELEASE_DIR")
    if not release_dir:
        sys.exit("set SO_RELEASE_DIR to the release folder")
    if not args.ai:
        os.environ["SO_AI"] = "off"  # before the AI layer reads its settings

    client = None
    if args.ai:
        from second_opinion.ai.client import make_client

        client = make_client()
        if client is None:
            sys.exit("--ai asked for, but the AI helper is not configured")

    started = time.time()
    sets: dict[str, dict] = {}
    for key_path in sorted(glob.glob(os.path.join(args.sets_dir, "blindset*", "key.json"))):
        folder = os.path.dirname(key_path)
        sets[os.path.basename(folder)] = score_set(folder, release_dir, client)
    if not sets:
        sys.exit(f"no blindset*/key.json under {args.sets_dir}")

    print(format_table(sets))
    unscored = sum(len(s["extras"]) for s in sets.values())
    errors = sum(len(s["errors"]) for s in sets.values())
    print(f"\nmode: {'ai' if args.ai else 'rules only'}; unscored findings: {unscored}; errors: {errors}; "
          f"seconds: {time.time() - started:.0f}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"mode": "ai" if args.ai else "rules", "sets": sets}, f, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())

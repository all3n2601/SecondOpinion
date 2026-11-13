"""Build the organizers' audit.json (shared findings format v0.2) from an AuditResult.

The mapping is fixed so the output is predictable; see Task M2 in the implementation plan.
`validate_audit_json` runs the same checks as docs/challenge/format/validate.py.
"""

import json
from datetime import date
from pathlib import Path

import jsonschema

from .decision import final_verdict
from .verdict import format_fact
from .model import (
    AuditResult,
    ClaimResult,
    ClaimType,
    DecisionChoice,
    DecisionSuggestion,
    Fact,
    Solidity,
    Verdict,
)

AI_ASSISTED_NOTE = "AI-assisted: the plan was proposed by a model and run by code."
RESEARCH_ONLY = "Research prototype. Not a clinical decision system. Verdicts need human review."

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "docs" / "challenge" / "format" / "findings.schema.json"

_SEVERITY = {
    Verdict.CONTRADICTED: "medium",
    Verdict.INSUFFICIENT_EVIDENCE: "low",
    Verdict.SUPPORTED: "none",
}


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def _n_of_m(fact: Fact | None, claim=None) -> str | None:
    if fact is None:
        return None
    if claim is not None and claim.type in (ClaimType.RANK, ClaimType.RATIO, ClaimType.STATISTIC):
        unit = {ClaimType.RANK: "rank", ClaimType.RATIO: "ratio", ClaimType.STATISTIC: "years"}[claim.type]
        try:
            return format_fact(fact, unit)
        except (ValueError, TypeError):
            pass
    if claim is not None and claim.type == ClaimType.COMPARISON and claim.params.attribute and fact.extra:
        x = fact.extra
        return (f"{x['group_a']} {x['share_a']}% ({int(x['hits_a']):,} of {int(x['n_a']):,}) vs "
                f"{x['group_b']} {x['share_b']}% ({int(x['hits_b']):,} of {int(x['n_b']):,})")
    if claim is not None and claim.params.unit == "percent" and fact.numerator is not None and fact.denominator:
        return format_fact(fact, "percent")
    if fact.numerator is not None and fact.denominator is not None:
        return f"{fact.numerator:,} of {fact.denominator:,}"
    if fact.value is not None:
        return f"{fact.value:,g}"
    return None


def _part_line(part: ClaimResult) -> str:
    label = part.claim.part_label or part.claim.text
    if part.verdict == Verdict.CONTRADICTED:
        return f'"{label}": contradicted, the data shows {part.correct_value or _n_of_m(part.fact, part.claim)}'
    if part.verdict == Verdict.SUPPORTED:
        return f'"{label}": supported ({_n_of_m(part.fact, part.claim)})'
    return f'"{label}": cannot be checked ({part.missing_evidence or "no check"})'


def _summary(result: ClaimResult, verdict: Verdict) -> str:
    if result.parts and len(result.parts) > 1 and (result.review is None or result.review.decision != "override"):
        lead = {
            Verdict.CONTRADICTED: "Contradicted in part.",
            Verdict.SUPPORTED: "Every part agrees with the data.",
            Verdict.INSUFFICIENT_EVIDENCE: "Not every part can be checked.",
        }[verdict]
        return lead + " " + "; ".join(_part_line(p) for p in result.parts) + "."
    if verdict == Verdict.CONTRADICTED:
        if result.correct_value:
            text = f"{result.correct_value} in the data, not what the report says."
        else:
            text = "The data does not match what the report says."
    elif verdict == Verdict.SUPPORTED:
        n_of_m = _n_of_m(result.fact, result.claim)
        text = f"Recomputed from the data: {n_of_m}." if n_of_m else "Recomputed from the data."
    else:
        need = result.missing_evidence or result.claim.needed_data or "data this release does not have"
        text = f"The data cannot answer this; would need: {need}."
    review = result.review
    if review is not None and review.decision == "override":
        text += (
            f" Reviewer override by {review.reviewer_role} "
            f"(machine verdict {result.verdict.value}): {review.reason}"
        )
    return text


def _confidence(result: ClaimResult, verdict: Verdict) -> str:
    if result.solidity == Solidity.FRAGILE:
        return "low"  # the verdict changes with a reasonable choice of column or population
    if result.notes:
        return "medium"  # a close call
    if result.solidity == Solidity.HOLDS_EVERYWHERE:
        return "high"
    if verdict == Verdict.INSUFFICIENT_EVIDENCE and result.claim.type == ClaimType.NOT_ANSWERABLE:
        return "high"  # set by the keyword rule, not by a number
    return "medium"


_CHOICE_WORDS = {
    "subtype_source=study_2012_label": "reading the 2012 study's columns instead",
    "sex_filter=women_only": "counting women only",
    "sample_scope=all_samples": "counting every sample type, not just primary tumors",
}


def plain_flip(flip: str) -> str:
    """"subtype_source=study_2012_label + sex_filter=women_only" -> plain words."""
    return " and ".join(_CHOICE_WORDS.get(part.strip(), part.strip()) for part in flip.split("+"))


def _solidity_note(result: ClaimResult) -> str | None:
    if result.solidity == Solidity.FRAGILE:
        single = [f for f in result.flips_on if "+" not in f] or result.flips_on[:1]
        return "fragile: the verdict changes when " + ("; or ".join(plain_flip(f) for f in single) or "counting another way")
    if result.solidity == Solidity.HOLDS_EVERYWHERE and result.variants:
        agree = sum(1 for v in result.variants if v.verdict == result.verdict)
        return f"robust: {agree} of {len(result.variants)} ways of counting agree"
    return None


def _calculation(result: ClaimResult, release_name: str) -> dict | None:
    """The calculation behind a checked claim: what was counted, the numbers and the pandas code."""
    fact = result.fact
    if fact is None or not fact.code:
        return None
    numbers = _n_of_m(fact, result.claim)
    note = f"{fact.label}: {numbers}." if numbers else f"{fact.label}."
    if fact.unknown_count:
        note += f" Left out for a missing value: {fact.unknown_count:,}."
    note += " Code (r = load_release(folder)): " + " | ".join(line for line in fact.code.splitlines() if line.strip())
    if result.ai_plan is not None:
        note += f". {AI_ASSISTED_NOTE}"
    return {"kind": "analysis", "id": f"{result.claim.id}-calculation", "release": release_name, "note": note}


def _evidence(result: ClaimResult, release_name: str) -> list[dict]:
    ai_note = AI_ASSISTED_NOTE if result.ai_plan is not None else None
    if result.parts and len(result.parts) > 1:
        refs: list[dict] = []
        for part in result.parts:
            refs.append({"kind": "claim", "id": part.claim.id, "note": _part_line(part)})
            calc = _calculation(part, release_name)
            if calc:
                refs.append(calc)
        files = list(dict.fromkeys(f for part in result.parts if part.fact for f in part.fact.files))
        refs += [{"kind": "file", "id": name, "release": release_name} for name in files]
        refs += [{"kind": "claim", "id": result.claim.id, "note": n} for n in result.notes]
        return refs
    fact = result.fact
    if fact is not None and fact.files:
        note = "; ".join(p for p in (fact.label, _solidity_note(result)) if p)
        if ai_note:
            note = f"{note}. {ai_note}" if note else ai_note
        refs = [
            {"kind": "file", "id": name, "release": release_name, "note": note}
            for name in fact.files
        ]
        calc = _calculation(result, release_name)
        if calc:
            refs.append(calc)
        refs += [{"kind": "claim", "id": result.claim.id, "note": n} for n in result.notes]
        return refs
    note = "no data field can test this claim"
    return [{"kind": "claim", "id": result.claim.id, "note": f"{note}. {ai_note}" if ai_note else note}]


def _finding(result: ClaimResult, release_name: str) -> dict:
    verdict = final_verdict(result)
    finding: dict = {
        "id": result.claim.id,
        "kind": "claim_check",
        "claim_text": result.claim.original_text or result.claim.text,
        "claim_verdict": verdict.value,
    }
    if verdict == Verdict.CONTRADICTED and result.correct_value:
        finding["correct_value"] = result.correct_value
    finding.update(
        summary=_summary(result, verdict),
        severity=_SEVERITY[verdict],
        confidence=_confidence(result, verdict),
        evidence=_evidence(result, release_name),
    )
    if result.limitation:
        finding["limitation"] = result.limitation
    finding["needs_human_review"] = True
    return finding


def build_audit_json(
    audit: AuditResult, decision: DecisionChoice | None = None, team: str = "Techminds"
) -> dict:
    name = audit.release.name
    doc: dict = {
        "format_version": "0.2",
        "producer": {"team": team, "product": "Research Claim Auditor", "track": "evidence-navigator"},
        "data": {
            "dataset": "TCGA-BRCA",
            "releases": [{"name": name, "files": [dict(f) for f in audit.release.files]}],
        },
        "question": f"Are the claims in the report supported by release {name}?",
    }
    if decision is not None:
        doc["verdict"] = decision.choice.value
    # The checker matches findings to its answer key by claim_text, and a sentence listed twice
    # breaks the match, so a sentence repeated in the report keeps only its first finding.
    seen: set[str] = set()
    findings = []
    for result in audit.claims:
        key = " ".join(result.claim.text.split())
        if key in seen:
            continue
        seen.add(key)
        findings.append(_finding(result, name))
    doc["findings"] = findings
    return doc


def validate_audit_json(doc: dict) -> list[str]:
    """Error messages in the official validator's wording; empty when the file is valid."""
    errors = [
        f"{'/'.join(map(str, e.path)) or '(top)'}: {e.message}"
        for e in jsonschema.Draft202012Validator(_load_schema()).iter_errors(doc)
    ]
    finding_ids = {f.get("id") for f in doc.get("findings", [])}
    repair_ids = {r.get("id") for r in doc.get("repairs", [])}
    for r in doc.get("repairs", []):
        errors += [
            f"repairs/{r.get('id')}: addresses unknown finding '{a}'"
            for a in r.get("addresses", []) if a not in finding_ids
        ]
    for d in doc.get("decisions", []):
        if d.get("repair_id") not in repair_ids:
            errors.append(f"decisions: unknown repair '{d.get('repair_id')}'")
    return errors


# --- Decision Record (Markdown) -------------------------------------------------------------

_SOLIDITY_WORD = {
    Solidity.HOLDS_EVERYWHERE: "robust",
    Solidity.FRAGILE: "fragile",
    Solidity.NOT_APPLICABLE: "n/a",
}


def _cell(text: str) -> str:
    """Make text safe inside one Markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def corrected_wording(result: ClaimResult) -> str:
    """The Claim Ladder's honest sentence: struck text removed, inserted text in bold."""
    if not result.ladder:
        return result.claim.text
    parts = []
    for seg in result.ladder:
        if seg.struck:
            continue
        parts.append(f"**{seg.text}**" if seg.inserted else seg.text)
    joined = "".join(
        p if i == 0 or p.startswith((" ", ",", ".", ";", ":")) or parts[i - 1].endswith(" ") else " " + p
        for i, p in enumerate(parts)
    )
    return " ".join(joined.split())


def _review_cell(result: ClaimResult) -> str:
    review = result.review
    if review is None:
        return "not reviewed"
    if review.decision == "override":
        return (
            f"override to {review.final_verdict.value} by {review.reviewer_role}: "
            f"{review.reason or 'no reason given'}"
        )
    return f"none (accepted by {review.reviewer_role})"


def build_decision_record(
    audit: AuditResult,
    decision: DecisionChoice,
    suggestion: DecisionSuggestion,
    today: date,
    tool_version: str = "0.1.0",
) -> str:
    lines: list[str] = ["# Decision Record", ""]

    lines += ["## Report and release", ""]
    lines.append(f"- Release: **{audit.release.name}** (TCGA-BRCA)")
    lines.append(f"- Date: {today.isoformat()}")
    lines.append(f"- Tool: SecondOpinion {tool_version}")
    lines.append(f"- Claims audited: {len(audit.claims)}")
    lines += ["", "| File | sha256 |", "| --- | --- |"]
    lines += [f"| {_cell(f.get('file', '?'))} | `{f.get('sha256') or 'missing'}` |" for f in audit.release.files]
    lines.append("")

    lines += ["## Decision", ""]
    lines.append(f"- Chosen decision: **{decision.choice.value}**")
    lines.append(f"- Chosen by: {decision.reviewer_role}")
    lines.append(f"- Reason: {decision.reason or 'no reason given'}")
    lines.append(f"- Suggested by the tool: {suggestion.decision.value} ({suggestion.rule})")
    if decision.choice != suggestion.decision:
        lines.append(
            f"- Note: the chosen decision differs from the suggested decision "
            f"({suggestion.decision.value})."
        )
    if suggestion.reasons:
        lines += ["", "Why the tool suggested it:", ""]
        lines += [f"- {r}" for r in suggestion.reasons]
    lines.append("")

    lines += ["## Claims", ""]
    if audit.claims:
        lines += [
            "| Claim | Original text | Machine verdict | Solidity | Corrected wording | Human override |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in audit.claims:
            lines.append(
                f"| {r.claim.id} | {_cell(r.claim.text)} | {r.verdict.value} | "
                f"{_SOLIDITY_WORD[r.solidity]} | {_cell(corrected_wording(r))} | {_cell(_review_cell(r))} |"
            )
    else:
        lines.append("No claims were audited.")
    lines.append("")

    limitations = list(audit.notes) + [
        f"{r.claim.id}: {r.limitation}" for r in audit.claims if r.limitation
    ]
    lines += ["## Important limitations", ""]
    lines += [f"- {item}" for item in limitations] or ["- None recorded."]
    lines.append("")

    lines += ["## Who must sign off", ""]
    lines += [f"- [ ] {who}" for who in suggestion.sign_off]
    lines.append("")

    lines += ["## What would change this decision", ""]
    lines += [f"- {item}" for item in suggestion.would_change] or ["- Nothing recorded."]
    lines += ["", "---", "", RESEARCH_ONLY, ""]
    return "\n".join(lines)

"""Suggest one overall report decision from the claim results.

Rules, in order (first match wins). Each claim counts with its reviewed verdict when a
human review exists, else the machine verdict:

1. A release file has no valid sha256, or a note starts "Checksum mismatch" -> Stop.
2. Any claim contradicted -> Fix a problem.
3. Any claim insufficient_evidence, or any claim fragile -> Narrow the question.
4. Otherwise -> Proceed.

The suggestion is advice for a person; the reviewer chooses the final decision.
"""

import re

from .model import AuditResult, ClaimResult, Decision, DecisionSuggestion, Solidity, Verdict

SIGN_OFF = ["Data-use reviewer", "Principal investigator"]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def final_verdict(result: ClaimResult) -> Verdict:
    """The reviewer's verdict when the claim has been reviewed, else the machine verdict."""
    return result.review.final_verdict if result.review is not None else result.verdict


def _checksum_problems(audit: AuditResult) -> list[str]:
    problems = [
        f"Release file {f.get('file', '?')} has no valid sha256 checksum."
        for f in audit.release.files
        if not _SHA256.match(str(f.get("sha256") or ""))
    ]
    problems += [n for n in audit.notes if n.startswith("Checksum mismatch")]
    return problems


def _claim_reason(result: ClaimResult) -> str:
    cid = result.claim.id
    verdict = final_verdict(result)
    if verdict == Verdict.CONTRADICTED:
        shows = result.correct_value or "a different value"
        text = f"{cid}: contradicted; the data shows {shows}."
    elif verdict == Verdict.INSUFFICIENT_EVIDENCE:
        need = result.missing_evidence or result.claim.needed_data or "data this release does not have"
        text = f"{cid}: insufficient evidence; would need {need}."
    elif result.solidity == Solidity.FRAGILE:
        text = f"{cid}: supported, but fragile (changes on {_flips(result)})."
    else:
        text = f"{cid}: supported."
    if result.review is not None and result.review.decision == "override":
        text += (
            f" Machine verdict was {result.verdict.value}; overridden by "
            f"{result.review.reviewer_role}: {result.review.reason}"
        )
    return text


def _flips(result: ClaimResult) -> str:
    return ", ".join(result.flips_on) or "some ways of counting"


def _would_change(audit: AuditResult) -> list[str]:
    changes: list[str] = []
    for result in audit.claims:
        cid = result.claim.id
        verdict = final_verdict(result)
        if verdict == Verdict.CONTRADICTED:
            value = result.correct_value or "what the data shows"
            changes.append(f"If {cid} were reworded to {value}, it could be published")
        elif verdict == Verdict.INSUFFICIENT_EVIDENCE:
            need = result.missing_evidence or result.claim.needed_data or "the missing data"
            changes.append(f"If {need} were added, {cid} could be tested")
        elif result.solidity == Solidity.FRAGILE:
            changes.append(
                f"If {cid} were limited to the way of counting it depends on "
                f"(it changes on {_flips(result)}), it could be published as narrowed"
            )
    return changes


def suggest_decision(audit: AuditResult) -> DecisionSuggestion:
    claim_reasons = [_claim_reason(r) for r in audit.claims] or [
        "No claims were checked, so nothing in the report has been verified."
    ]
    would_change = _would_change(audit)

    problems = _checksum_problems(audit)
    if problems:
        return DecisionSuggestion(
            decision=Decision.STOP,
            rule="Rule 1: the release files cannot be confirmed by checksum",
            reasons=problems + claim_reasons,
            sign_off=list(SIGN_OFF),
            would_change=[
                "If the release were re-fetched and every file matched its published checksum, "
                "the audit could be rerun"
            ] + would_change,
        )

    verdicts = [final_verdict(r) for r in audit.claims]
    if Verdict.CONTRADICTED in verdicts:
        decision, rule = Decision.FIX, "Rule 2: at least one claim is contradicted"
    elif Verdict.INSUFFICIENT_EVIDENCE in verdicts or any(
        r.solidity == Solidity.FRAGILE for r in audit.claims
    ):
        decision = Decision.NARROW
        rule = "Rule 3: at least one claim cannot be answered by this data or is fragile"
    else:
        decision = Decision.PROCEED
        rule = "Rule 4: every claim is supported and holds however it is counted"
        would_change = would_change or [
            "If a release file changed or a claim were reworded, the audit would need to be rerun"
        ]

    return DecisionSuggestion(
        decision=decision,
        rule=rule,
        reasons=claim_reasons,
        sign_off=list(SIGN_OFF),
        would_change=would_change,
    )

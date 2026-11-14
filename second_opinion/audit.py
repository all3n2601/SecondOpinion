"""The audit pipeline: run every claim through its check and verdict, return an AuditResult.

Skeptic, Claim Ladder and robustness plug in through `_hooks()`; each is imported lazily so
the pipeline keeps working while those modules do not exist (or fail to import).
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from second_opinion.ai.client import AIError, ChatClient, make_client
from second_opinion.ai.executor import PlanRejected, run_plan
from second_opinion.ai.planner import plan_claim
from second_opinion.checks import CHECKS, CannotCheck
from second_opinion.extract import find_numbers
from second_opinion.model import (
    AuditResult,
    Claim,
    ClaimResult,
    ClaimType,
    Fact,
    ReleaseInfo,
    Solidity,
    Verdict,
)
from second_opinion.release import Release, load_release
from second_opinion.variants import PRIMARY_VARIANT
from second_opinion.verdict import judge

NO_RNA_NOTE = "No RNA file in this release."
UNMAPPED_MISSING = "No check exists yet for this kind of claim"
CHECK_FAILED = "The check could not be completed on this release; a person should check this claim by hand"
AI_LIMITATION = "Checked by a query plan the AI helper proposed; our code ran it on the release."
AI_COULD_NOT = "The AI helper could not turn this into a check we can run: {why}"
AI_PARTLY_CHECKED = (
    'Only part of this sentence was checked: "{span}" agrees with the data. Not checked: {numbers}. '
    "A sentence counts as supported only when every part of it is checked."
)
STANDARD_RELEASE_FOLDER = "raw"  # where fetch.py puts the organizers' release; it is "release A"
STANDARD_RELEASE_NAME = "A"
_ROBUSTNESS_TYPES = (ClaimType.SHARE, ClaimType.COMPARISON, ClaimType.RANK, ClaimType.RATIO, ClaimType.STATISTIC)
# A rank whose runner-up is this close (share of the population) is a close call a person should look at.
CLOSE_RANK_POINTS = 2.0
_SEVERITY_ORDER = {Verdict.CONTRADICTED: 0, Verdict.INSUFFICIENT_EVIDENCE: 1, Verdict.SUPPORTED: 2}


@dataclass
class _Hooks:
    skeptic_for: Callable[..., Any] | None = None
    build_ladder: Callable[..., Any] | None = None
    run_variants: Callable[..., Any] | None = None
    solidity_of: Callable[..., Any] | None = None


def _hooks() -> _Hooks:
    """Import the optional modules owned by other tasks; anything missing stays None."""
    hooks = _Hooks()
    try:
        from second_opinion.skeptic import skeptic_for

        hooks.skeptic_for = skeptic_for
    except ImportError:
        pass
    try:
        from second_opinion.ladder import build_ladder

        hooks.build_ladder = build_ladder
    except ImportError:
        pass
    try:
        from second_opinion.robustness import run_variants, solidity_of

        hooks.run_variants, hooks.solidity_of = run_variants, solidity_of
    except ImportError:
        pass
    return hooks


def release_name(folder: Path) -> str:
    """Folder name, except `raw` (the organizers' release) is "A" and an envelope's `release/` is named after the envelope."""
    resolved = folder.resolve()
    if resolved.name == STANDARD_RELEASE_FOLDER:
        return STANDARD_RELEASE_NAME
    if resolved.name == "release" and resolved.parent.name:
        return resolved.parent.name  # envelopes/opened/<E07>/release
    return resolved.name


def _checksum_notes(folder: Path, checksums: dict[str, str]) -> list[str]:
    """Compare with sources.csv if one sits next to or one level above the release folder."""
    for candidate in (folder / "sources.csv", folder.resolve().parent / "sources.csv"):
        if not candidate.is_file():
            continue
        try:
            with open(candidate, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        except (OSError, UnicodeDecodeError, csv.Error):
            return []
        if not rows or "file" not in rows[0] or "sha256" not in rows[0]:
            return []  # some other dataset's sources.csv; nothing to compare
        expected = {r["file"]: (r["sha256"] or "").strip().lower() for r in rows if r.get("file")}
        return [
            f"Checksum mismatch: {name}"
            for name, actual in sorted(checksums.items())
            if expected.get(name) and expected[name] != actual
        ]
    return []


def _limitation(claim: Claim, fact: Fact) -> str | None:
    if claim.type == ClaimType.SHARE and fact.denominator is not None and not claim.params.attribute:
        total = fact.denominator + fact.unknown_count
        return f"Subtype calls exist for {fact.denominator:,} of {total:,} primary tumors."
    if claim.params.subject == "all_five_layers" and fact.extra.get("note"):
        note = str(fact.extra["note"])
        return note[0].upper() + note[1:] + "."
    p = claim.params
    if p.attribute and claim.type in (ClaimType.SHARE, ClaimType.COUNT, ClaimType.RANK, ClaimType.RATIO):
        from second_opinion.checks.attributes import ATTRIBUTE_NOUNS

        noun = ATTRIBUTE_NOUNS.get(p.attribute, p.attribute)
        source = fact.label.rsplit("(read from ", 1)[-1].rstrip(")") if "(read from " in fact.label else "the release"
        known = fact.extra.get("known", fact.denominator if claim.type == ClaimType.SHARE else None)
        text = f"Read from {source}."
        if known is not None and fact.unknown_count:
            text = (f"A {noun} is recorded for {int(known):,} of {int(known) + fact.unknown_count:,} samples in the "
                    f"population; the other {fact.unknown_count:,} are left out. " + text)
        if p.attribute in ("er_status", "pr_status", "her2_status", "hr_status", "triple_negative"):
            text += " Equivocal and indeterminate results count as unknown."
        if p.attribute == "mutation":
            text += " A gene counts as mutated when the gene-level call is 1; the file does not say which variant."
        return text
    if claim.type == ClaimType.STATISTIC and fact.unknown_count:
        return f"Age at diagnosis is recorded for {fact.denominator:,} of {fact.denominator + fact.unknown_count:,} samples."
    if claim.type == ClaimType.COMPARISON and p.attribute:
        return "Shares are compared as they are; no statistical test of the difference was run."
    return None


def _insufficient(claim: Claim, missing: str) -> ClaimResult:
    return ClaimResult(
        claim=claim, verdict=Verdict.INSUFFICIENT_EVIDENCE, solidity=Solidity.NOT_APPLICABLE,
        fact=None, correct_value=None, missing_evidence=missing, variants=[], flips_on=[],
        skeptic=None, ladder=[], limitation=None,
    )


def _plain_reason(exc: Exception) -> str:
    """Turn an expected check/judge error into one plain sentence for `missing_evidence`."""
    if isinstance(exc, KeyError):
        key = str(exc.args[0]) if exc.args else ""
        if key and " " not in key:  # a bare column name, e.g. PAM50Call_RNAseq
            return f"The release has no '{key}' column, so this claim cannot be checked."
        message = key
    else:
        message = str(exc)
    lowered = message.lower()
    if "stated value" in lowered:
        return "The report states no number we can compare against."
    if "direction" in lowered:
        return "The report does not say whether the measure is higher or lower."
    if "denominator" in lowered:
        return "The report states a total we cannot compare against; this release has no matching total."
    message = message.strip().rstrip(".")
    if not message:
        return "This claim is missing information the check needs."
    return f"This claim cannot be checked: {message[0].lower() + message[1:]}."


def _checked(claim: Claim, check: Callable[..., Fact], release: Release, hooks: _Hooks) -> ClaimResult:
    """Run one claim's check and verdict; expected failures become insufficient_evidence."""
    try:
        fact = check(claim, release, PRIMARY_VARIANT)
    except CannotCheck as exc:
        return _insufficient(claim, str(exc))
    except KeyError as exc:  # e.g. the release lacks a column this check reads
        return _insufficient(claim, _plain_reason(exc))
    except Exception:  # noqa: BLE001 - one odd sentence or release must never stop the whole audit
        return _insufficient(claim, CHECK_FAILED)
    try:
        verdict, correct_value = judge(claim, fact)
    except (ValueError, KeyError) as exc:  # the claim lacks a number, direction or total
        return _insufficient(claim, _plain_reason(exc))
    except Exception:  # noqa: BLE001
        return _insufficient(claim, CHECK_FAILED)
    result = ClaimResult(
        claim=claim, verdict=verdict, solidity=Solidity.NOT_APPLICABLE, fact=fact,
        correct_value=correct_value, missing_evidence=None, variants=[],
        flips_on=[], skeptic=None, ladder=[], limitation=_limitation(claim, fact),
    )
    result.notes = _close_call_notes(claim, fact, verdict)
    robust = claim.type in _ROBUSTNESS_TYPES or (claim.type == ClaimType.COUNT and claim.params.attribute)
    if hooks.run_variants and hooks.solidity_of and robust:
        try:
            variants = hooks.run_variants(claim, release)
        except Exception:  # noqa: BLE001 - e.g. a variant needs a column this release lacks
            variants = None  # solidity stays not_applicable; the verdict itself is unaffected
        if variants is not None:
            result.variants = variants
            result.solidity, result.flips_on = hooks.solidity_of(variants, verdict)
    if hooks.skeptic_for:
        try:
            result.skeptic = hooks.skeptic_for(claim, release)
        except Exception:  # noqa: BLE001 - the skeptic is extra evidence; it never fails a claim
            result.skeptic = None
    return result


def _close_call_notes(claim: Claim, fact: Fact, verdict: Verdict) -> list[str]:
    """Plain warnings when a verdict hangs on a small margin, so the reviewer looks twice."""
    notes: list[str] = []
    x = fact.extra
    if claim.type == ClaimType.RANK and "neighbour_count" in x and fact.denominator:
        gap = abs(int(fact.numerator or 0) - int(x["neighbour_count"]))
        points = 100 * gap / fact.denominator
        if points < CLOSE_RANK_POINTS:
            notes.append(
                f"Close call: {claim.params.category} and {x['neighbour']} differ by {gap:,} "
                f"({points:.1f} percentage points of {fact.denominator:,}); a small change in the data could swap them."
            )
    p = claim.params
    if (p.unit == "percent" and p.approximate and p.stated_high is None and not p.bound and fact.numerator is not None
            and fact.denominator):
        from second_opinion.verdict import PERCENT_TOLERANCE_POINTS

        gap = abs(100 * fact.numerator / fact.denominator - float(p.stated_value or 0))
        tolerance = float(PERCENT_TOLERANCE_POINTS)
        if tolerance * 0.75 <= gap <= tolerance * 1.5:
            notes.append(
                f"Close call: the data is {gap:.1f} points from the stated {p.stated_value:g}%, and 'about' allows "
                f"{tolerance:g}; a reviewer should confirm the verdict."
            )
    if p.bound and fact.value is not None and p.stated_value and verdict != Verdict.INSUFFICIENT_EVIDENCE:
        ours = (100 * fact.numerator / fact.denominator) if (p.unit == "percent" and fact.denominator) else float(fact.value)
        if abs(ours - float(p.stated_value)) <= max(1.0, 0.02 * abs(float(p.stated_value))):
            notes.append(f"Close call: the data ({ours:,.1f}) is right at the stated bound ({p.stated_value:g}).")
    return notes


def _combine_parts(claim: Claim, parts: list[ClaimResult]) -> ClaimResult:
    """One result for a sentence with several checks: its worst part decides, every part is kept."""
    worst = min(parts, key=lambda r: _SEVERITY_ORDER[r.verdict])
    verdict = worst.verdict
    deciding = [r for r in parts if r.verdict == verdict]
    labelled = len(parts) > 1
    correct_value = None
    missing = None
    if verdict == Verdict.CONTRADICTED:
        values = [r for r in deciding if r.correct_value]
        if len(values) == 1:
            correct_value = values[0].correct_value
        elif values:
            correct_value = "; ".join(f"{r.claim.part_label}: {r.correct_value}" for r in values)
    elif verdict == Verdict.INSUFFICIENT_EVIDENCE:
        reasons = [r.missing_evidence for r in deciding if r.missing_evidence]
        if labelled and any(r.verdict == Verdict.SUPPORTED for r in parts):
            checked = ", ".join(f'"{r.claim.part_label}"' for r in parts if r.verdict == Verdict.SUPPORTED)
            reasons = [f"{checked} agrees with the data, but the rest could not be checked: " + "; ".join(reasons)]
        missing = "; ".join(dict.fromkeys(reasons)) or UNMAPPED_MISSING
    fragile = [r for r in parts if r.solidity == Solidity.FRAGILE]
    if fragile:
        solidity = Solidity.FRAGILE
    elif all(r.solidity == Solidity.HOLDS_EVERYWHERE for r in parts):
        solidity = Solidity.HOLDS_EVERYWHERE
    else:
        solidity = worst.solidity
    limitations = [r.limitation for r in parts if r.limitation]
    return ClaimResult(
        claim=claim, verdict=verdict, solidity=solidity, fact=worst.fact, correct_value=correct_value,
        missing_evidence=missing, variants=worst.variants,
        flips_on=list(dict.fromkeys(f for r in parts for f in r.flips_on)), skeptic=None,
        ladder=worst.ladder, limitation=" ".join(dict.fromkeys(limitations)) or None, parts=parts,
        notes=list(dict.fromkeys(n for r in parts for n in r.notes)),
    )


def _ai_limitation(fact: Fact) -> str:
    """The standing AI note, plus how many rows were left out for a missing value (as `_limitation` does)."""
    kept = fact.denominator if fact.denominator is not None else fact.numerator
    if fact.unknown_count and kept is not None:
        total = int(kept) + fact.unknown_count
        return f"{AI_LIMITATION} A value is recorded for {int(kept):,} of {total:,} rows; the rest were left out."
    return AI_LIMITATION


# Data every TCGA-BRCA release holds. The AI sometimes says one of these is missing when its query plan
# simply cannot reach it; a reviewer must never be told the release lacks data it has.
_RELEASE_HAS = re.compile(
    r"\bmutat\w*|\bcopy[\s-]?number|\bGISTIC\b|\bsurvival\b|\bvital\s+status\b|\bdeaths?\b|\bdied\b|\bOS\b"
    r"|\bfollow[\s-]?up\b|\bprogesterone\b|\bPR\s+status\b|\bstage\b|\bhistolog\w*|\bmenopaus\w*",
    re.IGNORECASE,
)
_TRULY_MISSING = re.compile(r"\btreat\w*|\btherap\w*|\brespon\w*|\bdrug|\bKi[\s-]?67|\bgrade\b|\brace\b|\bethnic", re.IGNORECASE)
AI_CANNOT_EXPRESS = (
    "a check the AI helper's query plans cannot express yet; the release does hold the data ({what}), so a person "
    "should compute it"
)


def _honest_need(need: str) -> str:
    """The AI's "would need" text, unless it claims the release lacks data it actually holds."""
    found = _RELEASE_HAS.search(need)
    if found and not _TRULY_MISSING.search(need):
        return AI_CANNOT_EXPRESS.format(what=found.group(0).lower())
    return need


def _ai_failed(claim: Claim, why: str) -> ClaimResult:
    why = " ".join(why.split()).rstrip(".")
    return _insufficient(claim, AI_COULD_NOT.format(why=(why or "the answer was not usable") + "."))


def _unchecked_numbers(text: str, span: str, total: float | None) -> list[str]:
    """Numbers the sentence states outside the span the AI plan tested (a plan tests one figure)."""
    start = text.lower().find(" ".join(span.split()).lower())
    if start == -1:
        return []
    end = start + len(" ".join(span.split()))
    return [
        text[n.start:n.end].strip()
        for n in find_numbers(text)
        if not (start <= n.start and n.end <= end) and not n.is_total and n.value != total
    ]


def _ai_checked(claim: Claim, release: Release, client: ChatClient) -> ClaimResult:
    """Ask the AI for a plan for one claim; our code validates, runs and judges it. Never raises."""
    try:
        qp = plan_claim(claim.text, release, client)
        if not qp.answerable:
            result = _insufficient(claim, _honest_need((qp.needed_data or "").strip()) or "Data this release does not contain")
        else:
            fact, verdict, correct_value = run_plan(claim.text, qp, release)
            untested = (
                _unchecked_numbers(claim.text, qp.stated.span, qp.stated.total)
                if verdict == Verdict.SUPPORTED and qp.stated is not None
                else []
            )
            if untested:  # a contradicted part would already show; "supported" needs every part checked
                result = _insufficient(
                    claim, AI_PARTLY_CHECKED.format(span=qp.stated.span, numbers=", ".join(untested))
                )
                result.ai_plan = qp.model_dump(mode="json")
                return result
            result = ClaimResult(
                claim=claim, verdict=verdict, solidity=Solidity.NOT_APPLICABLE, fact=fact,
                correct_value=correct_value, missing_evidence=None, variants=[], flips_on=[],
                skeptic=None, ladder=[], limitation=_ai_limitation(fact),
            )
        result.ai_plan = qp.model_dump(mode="json")
        return result
    except (AIError, PlanRejected) as exc:  # PlanError is an AIError; messages are plain and key-free
        return _ai_failed(claim, str(exc))
    except Exception:  # noqa: BLE001 - the AI layer is optional; one bad claim must never fail the audit
        return _ai_failed(claim, "something unexpected went wrong")


def _audit_one(claim: Claim, release: Release, hooks: _Hooks, client: ChatClient | None = None) -> ClaimResult:
    if claim.parts:
        return _combine_parts(claim, [_audit_one(part, release, hooks, client) for part in claim.parts])
    check = CHECKS.get(claim.type)
    ai_may_try = client is not None and claim.type != ClaimType.NOT_ANSWERABLE and (
        claim.type == ClaimType.UNMAPPED or (claim.source == "ai" and check is None)
    )
    if claim.type == ClaimType.NOT_ANSWERABLE:
        result = _insufficient(claim, claim.needed_data or "Data this release does not contain")
    elif ai_may_try:  # only claims the rules cannot handle; a rules verdict is never overridden
        result = _ai_checked(claim, release, client)
    elif claim.type == ClaimType.UNMAPPED or check is None:
        result = _insufficient(claim, claim.needed_data or UNMAPPED_MISSING)
    else:
        result = _checked(claim, check, release, hooks)
    if hooks.build_ladder:
        try:
            result.ladder = hooks.build_ladder(claim, result)
        except Exception:  # noqa: BLE001 - the ladder is a nicety; a claim it cannot rewrite keeps its text
            result.ladder = []
    return result


def audit_claims(
    claims: list[Claim], release_dir: str | Path, ai_client: ChatClient | None = None
) -> AuditResult:
    """Check every claim against the release in `release_dir` (raises FileNotFoundError or ReleaseError if unusable).

    Rules run first and own every claim they can handle. Claims the rules cannot map go to the AI helper
    when one is configured (`ai_client`, or `make_client()` when None); with AI off nothing changes.
    """
    folder = Path(release_dir)
    release = load_release(folder)
    hooks = _hooks()
    client = ai_client if ai_client is not None else make_client()

    notes: list[str] = []
    if release.rna_ids is None:
        notes.append(NO_RNA_NOTE)
    notes.extend(_checksum_notes(folder, release.checksums))

    return AuditResult(
        release=ReleaseInfo(
            name=release_name(folder),
            files=[{"file": n, "sha256": h} for n, h in sorted(release.checksums.items())],
        ),
        claims=[_audit_one(c, release, hooks, client) for c in claims],
        notes=notes,
    )

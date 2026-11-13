"""The audit pipeline: run every claim through its check and verdict, return an AuditResult.

Skeptic, Claim Ladder and robustness plug in through `_hooks()`; each is imported lazily so
the pipeline keeps working while those modules do not exist (or fail to import).
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from second_opinion.checks import CHECKS, CannotCheck
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
STANDARD_RELEASE_FOLDER = "raw"  # where fetch.py puts the organizers' release; it is "release A"
STANDARD_RELEASE_NAME = "A"
_ROBUSTNESS_TYPES = (ClaimType.SHARE, ClaimType.COMPARISON)


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
    if claim.type == ClaimType.SHARE and fact.denominator is not None:
        total = fact.denominator + fact.unknown_count
        return f"Subtype calls exist for {fact.denominator:,} of {total:,} primary tumors."
    if claim.params.subject == "all_five_layers" and fact.extra.get("note"):
        note = str(fact.extra["note"])
        return note[0].upper() + note[1:] + "."
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
    try:
        verdict, correct_value = judge(claim, fact)
    except (ValueError, KeyError) as exc:  # the claim lacks a number, direction or total
        return _insufficient(claim, _plain_reason(exc))
    result = ClaimResult(
        claim=claim, verdict=verdict, solidity=Solidity.NOT_APPLICABLE, fact=fact,
        correct_value=correct_value, missing_evidence=None, variants=[],
        flips_on=[], skeptic=None, ladder=[], limitation=_limitation(claim, fact),
    )
    if hooks.run_variants and hooks.solidity_of and claim.type in _ROBUSTNESS_TYPES:
        try:
            variants = hooks.run_variants(claim, release)
        except (CannotCheck, KeyError, ValueError):  # a variant needs a column this release lacks
            variants = None  # solidity stays not_applicable; the verdict itself is unaffected
        if variants is not None:
            result.variants = variants
            result.solidity, result.flips_on = hooks.solidity_of(variants, verdict)
    if hooks.skeptic_for:
        result.skeptic = hooks.skeptic_for(claim, release)
    return result


def _audit_one(claim: Claim, release: Release, hooks: _Hooks) -> ClaimResult:
    check = CHECKS.get(claim.type)
    if claim.type == ClaimType.NOT_ANSWERABLE:
        result = _insufficient(claim, claim.needed_data or "Data this release does not contain")
    elif claim.type == ClaimType.UNMAPPED or check is None:
        result = _insufficient(claim, UNMAPPED_MISSING)
    else:
        result = _checked(claim, check, release, hooks)
    if hooks.build_ladder:
        result.ladder = hooks.build_ladder(claim, result)
    return result


def audit_claims(claims: list[Claim], release_dir: str | Path) -> AuditResult:
    """Check every claim against the release in `release_dir` (raises FileNotFoundError or ReleaseError if unusable)."""
    folder = Path(release_dir)
    release = load_release(folder)
    hooks = _hooks()

    notes: list[str] = []
    if release.rna_ids is None:
        notes.append(NO_RNA_NOTE)
    notes.extend(_checksum_notes(folder, release.checksums))

    return AuditResult(
        release=ReleaseInfo(
            name=release_name(folder),
            files=[{"file": n, "sha256": h} for n, h in sorted(release.checksums.items())],
        ),
        claims=[_audit_one(c, release, hooks) for c in claims],
        notes=notes,
    )

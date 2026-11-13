"""API route groups. Each module exposes one `router`; main.py mounts them once."""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter

from second_opinion.model import AuditResult

PRACTICE_FIXTURE = (
    Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "practice_audit_result.json"
)


@lru_cache(maxsize=1)
def _practice_json() -> str:
    return PRACTICE_FIXTURE.read_text()


def practice_audit_result() -> AuditResult:
    """The hand-made expected AuditResult for the practice report (used by stub endpoints)."""
    return TypeAdapter(AuditResult).validate_python(json.loads(_practice_json()))

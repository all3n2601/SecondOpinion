"""Reviewer roles, stored in roles.yaml so a role can be added without touching code."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import yaml

ROLES_FILE = Path(__file__).resolve().parent / "roles.yaml"

VALID_SECTIONS = (
    "decision", "counts", "sign_off",
    "claims", "review_queue", "decision_record",
    "corrected_wording", "robustness", "skeptic",
    "sample_ids", "files", "code",
)
DETAIL_LEVELS = ("summary", "standard", "full")
VALID_VIEWS = ("story", "checklist", "evidence", "raw")
VIEW_FOR_DETAIL = {"summary": "story", "standard": "checklist", "full": "evidence"}


@dataclass
class Role:
    name: str
    sections: list[str] = field(default_factory=list)
    detail: Literal["summary", "standard", "full"] = "standard"
    explain_terms: bool = False
    view: Literal["story", "checklist", "evidence", "raw"] | None = None


def _path(path: Path | None) -> Path:
    return Path(path) if path is not None else ROLES_FILE  # looked up at call time (tests swap it)


def load_roles(path: Path | None = None) -> list[Role]:
    raw = yaml.safe_load(_path(path).read_text(encoding="utf-8")) or []
    roles = []
    for r in raw:
        detail = r.get("detail", "standard")
        roles.append(
            Role(
                name=str(r["name"]),
                sections=[str(s) for s in r.get("sections") or []],
                detail=detail,
                explain_terms=bool(r.get("explain_terms", False)),
                view=r.get("view") or VIEW_FOR_DETAIL.get(detail, "checklist"),
            )
        )
    return roles


class DuplicateRoleError(ValueError):
    pass


def validate_role(role: Role, existing: list[Role]) -> Role:
    """Return a cleaned copy of `role`, or raise ValueError saying what is wrong."""
    name = " ".join(role.name.split())
    if not name:
        raise ValueError("A role needs a name.")
    if any(r.name.casefold() == name.casefold() for r in existing):
        raise DuplicateRoleError(f"A role named '{name}' already exists.")
    if not role.sections:
        raise ValueError("A role needs at least one section.")
    unknown = [s for s in role.sections if s not in VALID_SECTIONS]
    if unknown:
        raise ValueError(
            f"Unknown section(s): {', '.join(unknown)}. Valid sections: {', '.join(VALID_SECTIONS)}."
        )
    if role.detail not in DETAIL_LEVELS:
        raise ValueError(f"Detail must be one of: {', '.join(DETAIL_LEVELS)}.")
    view = role.view or VIEW_FOR_DETAIL[role.detail]
    if view not in VALID_VIEWS:
        raise ValueError(f"View must be one of: {', '.join(VALID_VIEWS)}.")
    sections = list(dict.fromkeys(role.sections))  # drop repeats, keep order
    return Role(name=name, sections=sections, detail=role.detail, explain_terms=bool(role.explain_terms), view=view)


def add_role(role: Role, path: Path | None = None) -> list[Role]:
    target = _path(path)
    roles = load_roles(target)
    roles.append(validate_role(role, roles))
    target.write_text(
        "# Reviewer roles. See VALID_SECTIONS in second_opinion/roles.py for section names.\n"
        "# view: story | checklist | evidence | raw (the Review page layout; defaults from detail)\n"
        + yaml.safe_dump([asdict(r) for r in roles], sort_keys=False, default_flow_style=None),
        encoding="utf-8",
    )
    return roles

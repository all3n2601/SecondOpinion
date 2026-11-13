"""Reviewer roles (in-memory stub until Meghana's M4)."""

from dataclasses import dataclass, field
from typing import Literal

from fastapi import APIRouter

router = APIRouter(tags=["roles"])


@dataclass
class Role:
    name: str
    sections: list[str] = field(default_factory=list)
    detail: Literal["summary", "standard", "full"] = "standard"
    explain_terms: bool = False


_ROLES: list[Role] = [
    Role(name="Reviewer", sections=["claims", "evidence", "decision"], detail="standard"),
]


@router.get("/roles", response_model=list[Role])
def list_roles() -> list[Role]:
    return _ROLES


@router.post("/roles", response_model=list[Role])
def add_role(role: Role) -> list[Role]:
    _ROLES[:] = [r for r in _ROLES if r.name != role.name] + [role]
    return _ROLES

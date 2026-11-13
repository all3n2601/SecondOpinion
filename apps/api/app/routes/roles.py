"""Reviewer roles: list them, or add one (saved to second_opinion/roles.yaml)."""

from fastapi import APIRouter, HTTPException

from second_opinion import roles as roles_store
from second_opinion.roles import DuplicateRoleError, Role

router = APIRouter(tags=["roles"])


@router.get("/roles", response_model=list[Role])
def list_roles() -> list[Role]:
    return roles_store.load_roles()


@router.post("/roles", response_model=list[Role])
def add_role(role: Role) -> list[Role]:
    try:
        return roles_store.add_role(role)
    except DuplicateRoleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

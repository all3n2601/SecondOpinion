"""Audit endpoint: run claims against a release folder and return the AuditResult."""

import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException

from second_opinion.audit import audit_claims
from second_opinion.model import AuditResult, Claim
from second_opinion.release import ReleaseError

from . import practice_audit_result  # noqa: F401  (other routes import it from here)

router = APIRouter(tags=["audit"])


@dataclass
class AuditRequest:
    release_dir: str
    claims: list[Claim]


def _resolve_release_dir(release_dir: str) -> Path:
    """Resolve the client's release folder; confine it to SO_RELEASES_ROOT when that is set.

    Local demos leave it unset so any release folder (for example an unsealed envelope) works.
    Any shared or deployed instance should set it: the caller then can only name folders under it.
    """
    root_setting = os.environ.get("SO_RELEASES_ROOT")
    if not root_setting:
        return Path(release_dir).resolve()
    root = Path(root_setting).resolve()
    folder = (root / release_dir).resolve()  # an absolute release_dir replaces root, then fails the check
    if not folder.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Release folder is outside the allowed location")
    return folder


@router.post("/audit", response_model=AuditResult)
def audit(body: AuditRequest) -> AuditResult:
    # Plain def (not async): the pandas work blocks, so FastAPI runs it in a worker thread.
    folder = _resolve_release_dir(body.release_dir)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Release folder not found: {body.release_dir}")
    try:
        return audit_claims(body.claims, folder)
    except (FileNotFoundError, ReleaseError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

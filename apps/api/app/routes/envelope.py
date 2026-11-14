"""Envelope endpoint: open a judges' sealed envelope with its number and four-word code."""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from second_opinion.envelope import EnvelopeError, unseal

router = APIRouter(tags=["audit"])


class UnsealRequest(BaseModel):
    envelope: str
    code: str


class UnsealResponse(BaseModel):
    envelope: str
    opened_dir: str
    report_name: str | None
    report_text: str | None
    release_a_dir: str
    envelope_release_dir: str
    files: list[str]
    checks: list[str]
    seconds: float
    notes: list[str]


@router.post("/envelope/unseal", response_model=UnsealResponse)
def unseal_envelope(body: UnsealRequest) -> UnsealResponse:
    # Plain def: unsealing takes 10 to 20 seconds, so FastAPI runs it in a worker thread.
    if os.environ.get("SO_RELEASES_ROOT"):
        raise HTTPException(status_code=400, detail="This instance does not open envelopes. Unseal on the demo laptop")
    try:
        opened = unseal(body.envelope, body.code)
    except EnvelopeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UnsealResponse(
        envelope=opened.envelope, opened_dir=str(opened.opened_dir), report_name=opened.report_name,
        report_text=opened.report_text, release_a_dir=str(opened.release_a_dir),
        envelope_release_dir=str(opened.envelope_release_dir), files=opened.files, checks=opened.checks,
        seconds=round(opened.seconds, 1), notes=opened.notes,
    )

"""Practice data endpoint: a release folder for the practice run, so it works without typing one in."""

import os
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from second_opinion.practice import PracticeReleaseError, practice_release

router = APIRouter(tags=["audit"])


class PracticeReleaseResponse(BaseModel):
    release_dir: str
    source: Literal["environment", "challenge_repo", "temporary"]
    downloaded: list[str]


@router.post("/practice-release", response_model=PracticeReleaseResponse)
def get_practice_release() -> PracticeReleaseResponse:
    # Plain def: a first run downloads about 70 MB, so FastAPI runs it in a worker thread.
    if os.environ.get("SO_RELEASES_ROOT"):
        # A shared instance only audits folders under its root; it should not fetch data on request.
        raise HTTPException(
            status_code=400,
            detail="This instance does not fetch practice data. Enter a release folder from its releases folder",
        )
    try:
        found = practice_release()
    except PracticeReleaseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PracticeReleaseResponse(release_dir=str(found.folder), source=found.source, downloaded=found.downloaded)

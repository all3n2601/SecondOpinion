"""Is the optional AI helper on? Never returns the key. Also the AI wording for the Review page."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from second_opinion.ai.client import AIError, make_client
from second_opinion.ai.config import ai_status
from second_opinion.ai.narrate import NarrateClaim, narrate

router = APIRouter(tags=["ai"])


class AIStatus(BaseModel):
    enabled: bool
    model: str | None = None
    host: str | None = None
    reason: str | None = None


@router.get("/ai/status", response_model=AIStatus)
def status() -> AIStatus:
    return AIStatus(**ai_status())


class NarrateClaimIn(BaseModel):
    id: str = Field(max_length=40)
    verdict: Literal["supported", "contradicted", "insufficient_evidence"]
    solidity: Literal["holds_under_every_variant", "holds_under_some_variants", "not_applicable"]
    overridden: bool
    text: str = Field(max_length=2000)


class NarrateRequest(BaseModel):
    view: Literal["story", "checklist", "evidence", "raw"]
    claims: list[NarrateClaimIn] = Field(max_length=100)

    @field_validator("claims")
    @classmethod
    def _unique_ids(cls, claims: list[NarrateClaimIn]) -> list[NarrateClaimIn]:
        ids = [c.id for c in claims]
        if len(set(ids)) != len(ids):
            raise ValueError("claim ids must be unique")
        return claims


class NarrateResponse(BaseModel):
    source: Literal["ai", "template"]
    headline: str | None = None
    caption: str | None = None
    claims: dict[str, str] | None = None
    reason: str | None = None


def _template(reason: str) -> NarrateResponse:
    return NarrateResponse(source="template", reason=reason)


@router.post("/ai/narrate", response_model=NarrateResponse)
def narrate_view(body: NarrateRequest) -> NarrateResponse:
    """AI wording with slots for the numbers, or `template` (the browser's own text) when the AI is off or fails."""
    try:
        client = make_client()
    except Exception:  # noqa: BLE001 - the AI layer is optional; this route must still answer
        client = None
    if client is None:
        return _template("The AI helper is off")
    claims = [NarrateClaim(c.id, c.verdict, c.solidity, c.overridden, c.text) for c in body.claims]
    try:
        result = narrate(body.view, claims, client)
    except AIError as err:
        return _template(str(err))
    return NarrateResponse(source="ai", headline=result.headline, caption=result.caption, claims=result.claims)

"""Is the optional AI helper on? Never returns the key."""

from fastapi import APIRouter
from pydantic import BaseModel

from second_opinion.ai.config import ai_status

router = APIRouter(tags=["ai"])


class AIStatus(BaseModel):
    enabled: bool
    model: str | None = None
    host: str | None = None
    reason: str | None = None


@router.get("/ai/status", response_model=AIStatus)
def status() -> AIStatus:
    return AIStatus(**ai_status())

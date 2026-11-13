"""Decision suggestion and export endpoints (stubs until Meghana's M3)."""

from dataclasses import dataclass, field

from fastapi import APIRouter

from second_opinion.model import AuditResult, Decision, DecisionChoice, DecisionSuggestion

router = APIRouter(tags=["export"])


@dataclass
class DecisionRequest:
    audit: AuditResult


@dataclass
class ExportRequest:
    audit: AuditResult
    decision: DecisionChoice


@dataclass
class ExportResponse:
    audit_json: dict = field(default_factory=dict)
    decision_record_md: str = ""


@router.post("/decision", response_model=DecisionSuggestion)
def decision(body: DecisionRequest) -> DecisionSuggestion:
    return DecisionSuggestion(
        decision=Decision.FIX,
        rule="stub",
        reasons=[],
        sign_off=[],
        would_change=[],
    )


@router.post("/export", response_model=ExportResponse)
def export(body: ExportRequest) -> ExportResponse:
    return ExportResponse()

"""Decision suggestion and export endpoints. All logic lives in second_opinion."""

from dataclasses import dataclass, field
from datetime import date

from fastapi import APIRouter, HTTPException

from second_opinion.decision import suggest_decision
from second_opinion.export import build_audit_json, build_decision_record
from second_opinion.model import AuditResult, DecisionChoice, DecisionSuggestion

router = APIRouter(tags=["export"])

TOOL_VERSION = "0.1.0"


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
    return suggest_decision(body.audit)


@router.post("/export", response_model=ExportResponse)
def export(body: ExportRequest) -> ExportResponse:
    unreviewed = [r.claim.id for r in body.audit.claims if r.review is None]
    if unreviewed:
        raise HTTPException(
            status_code=422,
            detail=f"Every claim needs a review before export. Not reviewed yet: {', '.join(unreviewed)}",
        )
    suggestion = suggest_decision(body.audit)
    return ExportResponse(
        audit_json=build_audit_json(body.audit, body.decision),
        decision_record_md=build_decision_record(
            body.audit, body.decision, suggestion, today=date.today(), tool_version=TOOL_VERSION
        ),
    )

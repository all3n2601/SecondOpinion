"""Report reading endpoints: cut a report into sentences and claims, or type one ticked sentence."""

from dataclasses import dataclass

from fastapi import APIRouter, HTTPException

from second_opinion.extract import classify_sentence, extract_claims
from second_opinion.model import Claim, ClaimType, ExtractResult, SentenceInfo

router = APIRouter(tags=["extract"])

MAX_REPORT_CHARS = 500_000  # a long paper is ~100k characters; this only stops runaway uploads


@dataclass
class ExtractRequest:
    report_text: str


@dataclass
class ClassifyRequest:
    text: str
    sentence_index: int
    claim_id: str = "C1"  # the browser holds the claim list, so it passes the next free id


@router.post("/extract", response_model=ExtractResult)
def extract(body: ExtractRequest) -> ExtractResult:
    if not body.report_text.strip():
        raise HTTPException(status_code=422, detail="The report is empty")
    if len(body.report_text) > MAX_REPORT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"The report is too long ({len(body.report_text):,} characters; the limit is {MAX_REPORT_CHARS:,})",
        )
    return extract_claims(body.report_text)


@router.post("/classify", response_model=Claim)
def classify(body: ClassifyRequest) -> Claim:
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="The sentence is empty")
    info = SentenceInfo(index=body.sentence_index, text=text, claim_id=None)
    claim = classify_sentence(info, body.claim_id)
    if claim is None:
        claim = Claim(id=body.claim_id, text=text, sentence_index=body.sentence_index, type=ClaimType.UNMAPPED)
    return claim

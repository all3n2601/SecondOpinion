"""Report reading endpoints: cut a report into sentences and claims, or type one ticked sentence."""

from dataclasses import dataclass

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from second_opinion.ai.client import make_client
from second_opinion.ai.extract_ai import add_missed_claims
from second_opinion.extract import classify_sentence, extract_claims
from second_opinion.model import Claim, ClaimType, ExtractResult, SentenceInfo
from second_opinion.report_file import ReportFileError, ReportKind, read_report_file

router = APIRouter(tags=["extract"])

MAX_REPORT_CHARS = 500_000  # a long paper is ~100k characters; this only stops runaway uploads
MAX_REPORT_FILE_BYTES = 20 * 1024 * 1024  # PDFs with figures run to a few MB


@dataclass
class ExtractRequest:
    report_text: str


@dataclass
class ClassifyRequest:
    text: str
    sentence_index: int
    claim_id: str = "C1"  # the browser holds the claim list, so it passes the next free id


def _with_ai_claims(result: ExtractResult) -> ExtractResult:
    """Add claims the AI recovered from sentences the rules skipped; the rules-only result on any failure."""
    try:
        client = make_client()
    except Exception:  # noqa: BLE001 - the AI layer is optional; /extract must still answer
        return result
    return add_missed_claims(result, client)


@router.post("/extract", response_model=ExtractResult)
def extract(body: ExtractRequest) -> ExtractResult:
    if not body.report_text.strip():
        raise HTTPException(status_code=422, detail="The report is empty")
    if len(body.report_text) > MAX_REPORT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"The report is too long ({len(body.report_text):,} characters; the limit is {MAX_REPORT_CHARS:,})",
        )
    return _with_ai_claims(extract_claims(body.report_text))


class ReportFileResponse(BaseModel):
    filename: str
    kind: ReportKind
    text: str
    pages: int | None = None


@router.post("/report-file", response_model=ReportFileResponse)
def report_file(file: UploadFile = File(...)) -> ReportFileResponse:
    """A report file (Markdown, text or PDF) as text, for the browser to show before /extract reads it."""
    filename = file.filename or "report"
    data = file.file.read(MAX_REPORT_FILE_BYTES + 1)
    if len(data) > MAX_REPORT_FILE_BYTES:
        limit_mb = MAX_REPORT_FILE_BYTES // 2**20
        raise HTTPException(status_code=413, detail=f"The file is too large (the limit is {limit_mb} MB)")
    if not data.strip():
        raise HTTPException(status_code=422, detail="The file is empty")
    try:
        read = read_report_file(data, filename)
    except ReportFileError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if len(read.text) > MAX_REPORT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"The report is too long ({len(read.text):,} characters; the limit is {MAX_REPORT_CHARS:,})",
        )
    return ReportFileResponse(filename=filename, kind=read.kind, text=read.text, pages=read.pages)


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

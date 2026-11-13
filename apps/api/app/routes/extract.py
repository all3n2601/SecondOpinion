"""Report reading endpoints: cut a report into sentences and claims, or type one ticked sentence."""

from dataclasses import dataclass, replace

from fastapi import APIRouter, HTTPException

from second_opinion.ai.client import make_client
from second_opinion.ai.extract_ai import find_missed_claims
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


def _with_ai_claims(result: ExtractResult) -> ExtractResult:
    """Add claims the AI recovered from sentences the rules skipped; the rules-only result on any failure.

    Claim ids are re-numbered C1..Cn in sentence order so SentenceInfo.claim_id keeps matching.
    """
    try:
        client = make_client()
        if client is None:
            return result
        recovered = find_missed_claims(result.sentences, client)
    except Exception:  # noqa: BLE001 - the AI layer is optional; /extract must still answer
        return result
    if not recovered:
        return result
    by_index = {s.index: s for s in result.sentences}
    claims = list(result.claims) + [
        Claim(
            id="", text=by_index[i].text, sentence_index=i, type=ClaimType.UNMAPPED, source="ai",
            original_text=by_index[i].original_text,
        )
        for i in recovered
        if i in by_index and by_index[i].claim_id is None
    ]
    claims.sort(key=lambda c: c.sentence_index)
    claims = [replace(c, id=f"C{n}") for n, c in enumerate(claims, start=1)]
    claim_ids = {c.sentence_index: c.id for c in claims}
    sentences = [replace(s, claim_id=claim_ids.get(s.index)) for s in result.sentences]
    return ExtractResult(sentences=sentences, claims=claims)


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

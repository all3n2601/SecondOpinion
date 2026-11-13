"""Report reading endpoints (stubs until Benoy's B4)."""

from dataclasses import dataclass

from fastapi import APIRouter

from second_opinion.model import Claim, ClaimType, ExtractResult

router = APIRouter(tags=["extract"])


@dataclass
class ExtractRequest:
    report_text: str


@dataclass
class ClassifyRequest:
    text: str
    sentence_index: int


@router.post("/extract", response_model=ExtractResult)
def extract(body: ExtractRequest) -> ExtractResult:
    return ExtractResult(sentences=[], claims=[])


@router.post("/classify", response_model=Claim)
def classify(body: ClassifyRequest) -> Claim:
    return Claim(
        id="C1",
        text=body.text,
        sentence_index=body.sentence_index,
        type=ClaimType.UNMAPPED,
    )
